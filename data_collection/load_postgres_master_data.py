import os
from datetime import datetime

import psycopg
from psycopg import sql


POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://postgres:12345678@localhost:5432/postgres",
)

MASTER_TABLE = "master_data_catalog"

COLUMN_EXPLANATION_MAP = {
    "time": "Event timestamp for this record.",
    "datetime": "Event timestamp for this record.",
    "date_added": "Data ingestion timestamp.",
    "stock_code": "Stock ticker/code identifier. Contain industry identification if the segment = industry ",
    "index_name": "Name of the market index.",
    "indicator_code": "Short code of the indicator.",
    "indicator_name": "Readable indicator name.",
    "category_code": "Financial statement category code. (e.g, IS_010, BS_020, CF_030).",
    "ratio_code": "Financial ratio code. (e.g, PE, ROE, ROI).",
    "ratio_name": "Financial ratio name.",
    "function_name": "Function/formula used to derive ratio.",
    "data": "Primary numeric value for the metric.",
    "value": "Primary numeric value for the metric.",
    "close": "Closing price/value.",
    "volume": "Trading or observed volume.",
    "year": "Calendar/fiscal year of the metric.",
    "quarter": "Quarter number of the metric.",
    "segment": "Business/reporting segment. can be corp, bank, sec or industry. Industry is for taking average metric across sectors",
    "duration": "Aggregation duration or tenor.",
    "country": "Country associated with this metric.",
    "unit": "Measurement unit.",
    "EMA12": "Exponential moving average over 12 periods.",
    "EMA20": "Exponential moving average over 20 periods.",
    "EMA26": "Exponential moving average over 26 periods.",
    "EMA50": "Exponential moving average over 50 periods.",
    "EMA200": "Exponential moving average over 200 periods.",
    "company_name": "Full name of the company. (or industry name for compatible with financial_statement/financial_ratio)",
    "industry": "Industry classification of the company.",
    "exchange": "Stock exchange where the company is listed. (HOSE, HNX)",
    "stock_indices": "Stock indices the company belongs to. (VN30)",
    "is_bank": "Boolean flag indicating if the company is a bank.",
    "is_securities": "Boolean flag indicating if the company is a securities firm.",
}


def connect_db() -> psycopg.Connection:
    return psycopg.connect(POSTGRES_URL)


def create_master_table(conn: psycopg.Connection) -> None:
    create_stmt = f"""
        CREATE TABLE IF NOT EXISTS \"{MASTER_TABLE}\" (
            table_name TEXT NOT NULL,
            column_name TEXT NOT NULL,
            explaination TEXT NOT NULL,
            dtype TEXT NOT NULL,
            node TEXT NOT NULL,
            note TEXT,
            is_nullable BOOLEAN NOT NULL,
            column_default TEXT,
            ordinal_position INTEGER NOT NULL,
            refreshed_at TIMESTAMP NOT NULL,
            PRIMARY KEY (table_name, column_name)
        )
    """
    with conn.cursor() as cur:
        cur.execute(create_stmt)
        # Keep backward compatibility if table existed before note column was introduced.
        cur.execute(f'ALTER TABLE "{MASTER_TABLE}" ADD COLUMN IF NOT EXISTS note TEXT')
    conn.commit()


def infer_node(table_name: str) -> str:
    # Keep node list-driven from the discovered schema (no manual mapping).
    return table_name


def infer_explanation(column_name: str) -> str:
    if column_name in COLUMN_EXPLANATION_MAP:
        return COLUMN_EXPLANATION_MAP[column_name]
    pretty = column_name.replace("_", " ").strip().capitalize()
    return f"{pretty}."


def fetch_columns(conn: psycopg.Connection) -> list[tuple]:
    query = """
        SELECT
            c.table_name,
            c.column_name,
            c.data_type,
            c.udt_name,
            c.is_nullable,
            c.column_default,
            c.ordinal_position
        FROM information_schema.columns c
        JOIN information_schema.tables t
            ON t.table_schema = c.table_schema
           AND t.table_name = c.table_name
        WHERE c.table_schema = 'public'
          AND t.table_type = 'BASE TABLE'
          AND c.table_name <> %s
        ORDER BY c.table_name, c.ordinal_position
    """

    with conn.cursor() as cur:
        cur.execute(query, (MASTER_TABLE,))
        return cur.fetchall()


def upsert_master_data(conn: psycopg.Connection, rows: list[tuple]) -> None:
    if not rows:
        print("No columns found in public schema.")
        return

    insert_stmt = sql.SQL(
        """
        INSERT INTO {} (
            table_name,
            column_name,
            explaination,
            dtype,
            node,
            note,
            is_nullable,
            column_default,
            ordinal_position,
            refreshed_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (table_name, column_name)
        DO UPDATE SET
            explaination = EXCLUDED.explaination,
            dtype = EXCLUDED.dtype,
            node = EXCLUDED.node,
            -- Keep user-maintained note unchanged on refresh.
            note = {}.note,
            is_nullable = EXCLUDED.is_nullable,
            column_default = EXCLUDED.column_default,
            ordinal_position = EXCLUDED.ordinal_position,
            refreshed_at = EXCLUDED.refreshed_at
        """
    ).format(sql.Identifier(MASTER_TABLE), sql.Identifier(MASTER_TABLE))

    with conn.cursor() as cur:
        cur.executemany(insert_stmt, rows)
    conn.commit()


def main() -> None:
    now = datetime.utcnow()

    with connect_db() as conn:
        create_master_table(conn)
        columns = fetch_columns(conn)

        include_tables = [
            'stock_daily',
            'indices_daily',
            'financial_statement',
            'financial_ratio',
            'commodities_daily',
            'company_info',
            # 'macro_indicator',
        ]

        payload = []
        for table_name, column_name, data_type, udt_name, is_nullable, column_default, ordinal_position in columns:
            dtype = data_type if data_type else udt_name
            payload.append(
                (
                    table_name,
                    column_name,
                    infer_explanation(column_name),
                    dtype,
                    infer_node(table_name),
                    None,
                    is_nullable == "YES",
                    column_default,
                    ordinal_position,
                    now,
                )
            )

        upsert_master_data(conn, payload)
        print(f"Upserted {len(payload)} rows into {MASTER_TABLE}")


if __name__ == "__main__":
    main()
