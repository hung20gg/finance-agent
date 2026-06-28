from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from core.utils import is_email, is_valid_date_column


POSTGRES_ERROR_KEYS = ("db_error", "exception_class")


def normalize_postgres_sql(sql_text: str) -> str:
    sql_text = sql_text.strip()
    sql_text = re.sub(r"`([^`]+)`", r'"\1"', sql_text)
    return sql_text


@dataclass
class TableColumn:
    name: str
    full_name: str
    description: str
    dtype: str
    ordinal_position: int


class PostgresDatabase:
    def __init__(
        self,
        postgres_url: str,
        schema: str = "public",
        include_tables: Optional[Sequence[str]] = None,
        exclude_tables: Optional[Sequence[str]] = None,
        sample_rows: int = 2000,
        execution_timeout_ms: int = 60000,
    ) -> None:
        if not postgres_url:
            raise ValueError("postgres_url is required")
        self.postgres_url = postgres_url
        self.schema = schema
        self.include_tables = list(include_tables or [])
        self.exclude_tables = set(exclude_tables or ["dim_data_catalog"])
        self.sample_rows = sample_rows
        self.execution_timeout_ms = execution_timeout_ms
        self._info_cache: Dict[str, dict] = {}

    def _quote_ident_text(self, identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

    def _connect(self):
        return psycopg.connect(self.postgres_url, row_factory=dict_row)

    def _fetchall(self, query: str, params: Optional[Sequence] = None) -> List[dict]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchall()

    def _dim_catalog_exists(self) -> bool:
        query = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name = 'dim_data_catalog'
        ) AS exists_flag
        """
        rows = self._fetchall(query, (self.schema,))
        return bool(rows and rows[0]["exists_flag"])

    def list_tables(self) -> List[str]:
        query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = %s
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
        tables = [row["table_name"] for row in self._fetchall(query, (self.schema,))]
        if self.include_tables:
            include = set(self.include_tables)
            tables = [table for table in tables if table in include]
        tables = [table for table in tables if table not in self.exclude_tables]
        return tables

    def _load_columns(self, table_names: Sequence[str]) -> Dict[str, List[TableColumn]]:
        if not table_names:
            return {}

        if self._dim_catalog_exists():
            catalog_table = f'{self._quote_ident_text(self.schema)}."dim_data_catalog"'
            query = """
            SELECT
                cols.table_name,
                cols.column_name,
                COALESCE(meta.explanation, '') AS explanation,
                COALESCE(meta.dtype, cols.data_type) AS dtype,
                cols.ordinal_position
            FROM information_schema.columns AS cols
            LEFT JOIN {catalog_table} AS meta
              ON meta.table_name = cols.table_name
             AND meta.column_name = cols.column_name
            WHERE cols.table_schema = %s
              AND cols.table_name = ANY(%s)
            ORDER BY cols.table_name, cols.ordinal_position
            """.format(catalog_table=catalog_table)
        else:
            query = """
            SELECT
                cols.table_name,
                cols.column_name,
                '' AS explanation,
                cols.data_type AS dtype,
                cols.ordinal_position
            FROM information_schema.columns AS cols
            WHERE cols.table_schema = %s
              AND cols.table_name = ANY(%s)
            ORDER BY cols.table_name, cols.ordinal_position
            """

        rows = self._fetchall(query, (self.schema, list(table_names)))
        result: Dict[str, List[TableColumn]] = {table_name: [] for table_name in table_names}
        for row in rows:
            result[row["table_name"]].append(
                TableColumn(
                    name=row["column_name"],
                    full_name=row["column_name"].replace("_", " "),
                    description=(row.get("explanation") or "").strip(),
                    dtype=(row.get("dtype") or "").upper(),
                    ordinal_position=row["ordinal_position"],
                )
            )
        return result

    def _load_primary_keys(self, table_names: Sequence[str]) -> Dict[str, List[str]]:
        query = """
        SELECT
            tc.table_name,
            kcu.column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY'
          AND tc.table_schema = %s
          AND tc.table_name = ANY(%s)
        ORDER BY tc.table_name, kcu.ordinal_position
        """
        rows = self._fetchall(query, (self.schema, list(table_names)))
        result = {table_name: [] for table_name in table_names}
        for row in rows:
            result[row["table_name"]].append(row["column_name"])
        return result

    def _load_foreign_keys(self, table_names: Sequence[str]) -> Dict[str, List[Tuple[str, str, str]]]:
        query = """
        SELECT
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
         AND ccu.table_schema = tc.table_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.table_schema = %s
          AND tc.table_name = ANY(%s)
        ORDER BY tc.table_name, kcu.ordinal_position
        """
        rows = self._fetchall(query, (self.schema, list(table_names)))
        result = {table_name: [] for table_name in table_names}
        for row in rows:
            result[row["table_name"]].append(
                (row["column_name"], row["foreign_table_name"], row["foreign_column_name"])
            )
        return result

    def _get_value_examples_str(self, values: List[object], col_type: str):
        if not values:
            return ""
        if len(values) > 10 and col_type in ["INTEGER", "REAL", "NUMERIC", "FLOAT", "INT", "BIGINT", "SMALLINT"]:
            return ""

        vals = []
        has_null = False
        for value in values:
            if value is None:
                has_null = True
                continue
            text = str(value).strip()
            if text:
                vals.append(value)

        if not vals:
            return ""

        if any(kind in col_type for kind in ["CHAR", "TEXT"]):
            new_values = []
            for value in vals:
                if not isinstance(value, str):
                    new_values.append(value)
                    continue
                text = value.strip()
                if not text:
                    continue
                if "https://" in text or "http://" in text or is_email(text):
                    return ""
                new_values.append(text)
            vals = new_values
            if not vals:
                return ""
            if max(len(str(item)) for item in vals) > 50:
                return ""

        vals = vals[:6]
        if is_valid_date_column([str(item) for item in vals]):
            vals = vals[:1]
        if has_null:
            vals.insert(0, None)
        return str(vals)

    def _sample_values_for_column(self, table_name: str, column_name: str) -> List[object]:
        with self._connect() as conn:
            with conn.cursor() as cur:
                query = sql.SQL(
                    """
                    WITH sampled AS (
                        SELECT {column} AS value
                        FROM {table}
                        WHERE {column} IS NOT NULL
                        LIMIT %s
                    )
                    SELECT value
                    FROM sampled
                    GROUP BY value
                    ORDER BY COUNT(*) DESC
                    LIMIT 6
                    """
                ).format(
                    column=sql.Identifier(column_name),
                    table=sql.Identifier(self.schema, table_name),
                )
                cur.execute(query, (self.sample_rows,))
                return [row["value"] for row in cur.fetchall()]

    def _load_unique_values(
        self,
        table_names: Sequence[str],
        columns_map: Dict[str, List[TableColumn]],
        pk_map: Dict[str, List[str]],
        fk_map: Dict[str, List[Tuple[str, str, str]]],
    ) -> Dict[str, List[Tuple[str, str]]]:
        result: Dict[str, List[Tuple[str, str]]] = {}
        for table_name in table_names:
            table_columns = columns_map.get(table_name, [])
            fk_columns = {column for column, _, _ in fk_map.get(table_name, [])}
            key_columns = set(pk_map.get(table_name, [])) | fk_columns
            value_rows: List[Tuple[str, str]] = []
            for column in table_columns:
                values_str = ""
                lower_name = column.name.lower()
                if column.name not in key_columns and not lower_name.endswith(("id", "email", "url")):
                    try:
                        raw_values = self._sample_values_for_column(table_name, column.name)
                        values_str = self._get_value_examples_str(raw_values, column.dtype)
                    except Exception:
                        values_str = ""
                value_rows.append((column.name, values_str))
            result[table_name] = value_rows
        return result

    def load_schema_info(self, db_id: str = "postgres") -> dict:
        if db_id in self._info_cache:
            return self._info_cache[db_id]

        table_names = self.list_tables()
        columns_map = self._load_columns(table_names)
        pk_map = self._load_primary_keys(table_names)
        fk_map = self._load_foreign_keys(table_names)
        values_map = self._load_unique_values(table_names, columns_map, pk_map, fk_map)

        desc_dict: Dict[str, List[Tuple[str, str, str]]] = {}
        for table_name, columns in columns_map.items():
            desc_dict[table_name] = [
                (column.name, column.full_name, column.description) for column in columns
            ]

        table_count = len(table_names)
        column_counts = [len(columns_map.get(table_name, [])) for table_name in table_names]
        stats = {
            "table_count": table_count,
            "max_column_count": max(column_counts) if column_counts else 0,
            "total_column_count": sum(column_counts),
            "avg_column_count": sum(column_counts) // table_count if table_count else 0,
        }
        result = {
            "desc_dict": desc_dict,
            "value_dict": values_map,
            "pk_dict": pk_map,
            "fk_dict": fk_map,
            "stats": stats,
        }
        self._info_cache[db_id] = result
        return result

    def execute_sql(self, sql_text: str) -> dict:
        normalized_sql = normalize_postgres_sql(sql_text)
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"SET LOCAL statement_timeout = '{self.execution_timeout_ms}ms'"
                    )
                    cur.execute(normalized_sql)
                    data = cur.fetchmany(5) if cur.description else []
                    return {
                        "sql": normalized_sql,
                        "data": data,
                        "db_error": "",
                        "exception_class": "",
                    }
        except Exception as exc:
            return {
                "sql": normalized_sql,
                "db_error": str(exc),
                "exception_class": exc.__class__.__name__,
            }
