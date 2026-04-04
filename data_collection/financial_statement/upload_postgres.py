import os
from typing import Iterable

import numpy as np
import pandas as pd
import psycopg
from psycopg import sql


POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://postgres:12345678@localhost:5432/postgres",
)

TABLE_FINANCIAL_STATEMENT = "financial_statement"
TABLE_FINANCIAL_RATIO = "financial_ratio"
TABLE_FINANCIAL_STATEMENT_DIM = "financial_statement_dim"
TABLE_FINANCIAL_RATIO_DIM = "financial_ratio_dim"
TABLE_COMPANY_INFO = "company_info"
TABLE_INDUSTRY_FINANCIAL_STATEMENT = "industry_financial_statement"
TABLE_INDUSTRY_FINANCIAL_RATIO = "industry_financial_ratio"

def connect_db() -> psycopg.Connection:
    return psycopg.connect(POSTGRES_URL)


def create_table_if_not_exists(
    conn: psycopg.Connection,
    table_name: str,
    columns: Iterable[tuple[str, str]],
    primary_keys: Iterable[str] | None = None,
) -> None:
    column_defs = [f'"{name}" {dtype}' for name, dtype in columns]
    if primary_keys:
        pk_cols = ", ".join(f'"{name}"' for name in primary_keys)
        column_defs.append(f"PRIMARY KEY ({pk_cols})")

    statement = f"""
        CREATE TABLE IF NOT EXISTS \"{table_name}\" (
            {", ".join(column_defs)}
        )
    """
    with conn.cursor() as cur:
        cur.execute(statement)
    conn.commit()

    extension = "CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;"
    with conn.cursor() as cur:
        cur.execute(extension)
    conn.commit()


def upload_dataframe_to_postgres(df: pd.DataFrame, conn: psycopg.Connection, table_name: str) -> None:
    if "date_added" in df.columns:
        df["date_added"] = pd.to_datetime(df["date_added"], errors="coerce")
        df = df.dropna(subset=["date_added"])

    df = df.replace({np.nan: None})
    if df.empty:
        print(f"No rows to upload for {table_name}")
        return

    columns = list(df.columns)
    placeholders = sql.SQL(", ").join(sql.Placeholder() for _ in columns)
    insert_stmt = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table_name),
        sql.SQL(", ").join(sql.Identifier(col) for col in columns),
        placeholders,
    )

    records = list(df.itertuples(index=False, name=None))
    with conn.cursor() as cur:
        cur.executemany(insert_stmt, records)
    conn.commit()
    print(f"Uploaded {len(records)} rows to {table_name}")


def main() -> None:
    schemas = {
        TABLE_FINANCIAL_STATEMENT: (
            [
                ("stock_code", "TEXT NOT NULL"),
                ("category_code", "TEXT NOT NULL"),
                ("data", "DOUBLE PRECISION"),
                ("year", "INTEGER"),
                ("quarter", "INTEGER"),
                ("date_added", "TIMESTAMP NOT NULL"),
                ("segment", "TEXT NOT NULL"),
            ],
            None,
        ),
        TABLE_FINANCIAL_RATIO: (
            [
                ("stock_code", "TEXT NOT NULL"),
                ("ratio_code", "TEXT NOT NULL"),
                ("data", "DOUBLE PRECISION"),
                ("year", "INTEGER"),
                ("quarter", "INTEGER"),
                ("date_added", "TIMESTAMP NOT NULL"),
                ("segment", "TEXT NOT NULL"),
            ],
            None,
        ),
        TABLE_INDUSTRY_FINANCIAL_STATEMENT: (
            [
                ("stock_code", "TEXT NOT NULL"),
                ("category_code", "TEXT NOT NULL"),
                ("data", "DOUBLE PRECISION"),
                ("year", "INTEGER"),
                ("quarter", "INTEGER"),
                ("date_added", "TIMESTAMP NOT NULL"),
                ("segment", "TEXT NOT NULL"),
            ],
            None,
        ),
        TABLE_FINANCIAL_RATIO: (
            [
                ("stock_code", "TEXT NOT NULL"),
                ("ratio_code", "TEXT NOT NULL"),
                ("data", "DOUBLE PRECISION"),
                ("year", "INTEGER"),
                ("quarter", "INTEGER"),
                ("date_added", "TIMESTAMP NOT NULL"),
                ("segment", "TEXT NOT NULL"),
            ],
            None,
        ),
        TABLE_INDUSTRY_FINANCIAL_RATIO: (
            [
                ("stock_code", "TEXT NOT NULL"),
                ("ratio_code", "TEXT NOT NULL"),
                ("data", "DOUBLE PRECISION"),
                ("year", "INTEGER"),
                ("quarter", "INTEGER"),
                ("date_added", "TIMESTAMP NOT NULL"),
                ("segment", "TEXT NOT NULL"),
            ],
            None,
        ),
        TABLE_COMPANY_INFO: (
            [
                ("stock_code", "TEXT NOT NULL"),
                ("company_name", "TEXT"),
                ("industry", "TEXT"),
                ("exchange", "TEXT"),
                ("stock_indices", "TEXT"),
                ("is_bank", "BOOLEAN"),
                ("is_securities", "BOOLEAN"),
            ],
            ["stock_code"],
        ),
        TABLE_FINANCIAL_STATEMENT_DIM: (
            [
                ("category_code", "TEXT NOT NULL"),
                ("category_name", "TEXT"),
            ],
            ["category_code"],
        ),
        TABLE_FINANCIAL_RATIO_DIM: (
            [
                ("ratio_code", "TEXT NOT NULL"),
                ("ratio_name", "TEXT"),
                ("function_name", "TEXT"),
            ],
            ["ratio_code"],
        ),
    }

    with connect_db() as conn:
        for table_name, (columns, pk_cols) in schemas.items():
            create_table_if_not_exists(conn, table_name, columns, pk_cols)

        # df_fs_dim = pd.read_csv('transform/metadata/map_category_code.csv')
        # upload_dataframe_to_postgres(df_fs_dim, conn, TABLE_FINANCIAL_STATEMENT_DIM)
        
        # df_fr_dim = pd.read_csv('transform/metadata/map_ratio_code.csv')
        # upload_dataframe_to_postgres(df_fr_dim, conn, TABLE_FINANCIAL_RATIO_DIM)

        df_company_info = pd.read_csv('transform/metadata/df_company_info.csv')
        df_company_info = df_company_info[["stock_code", "company_name", "industry", "exchange", "stock_indices", "is_bank", "is_securities"]]
        upload_dataframe_to_postgres(df_company_info, conn, TABLE_COMPANY_INFO)
        
        # df_fs = pd.read_parquet("../data/financial_statement_v3.parquet")
        # upload_dataframe_to_postgres(df_fs, conn, TABLE_FINANCIAL_STATEMENT)

        # df_fr = pd.read_parquet("../data/financial_ratio_v3.parquet")
        # upload_dataframe_to_postgres(df_fr, conn, TABLE_FINANCIAL_RATIO)


if __name__ == "__main__":
    main()
