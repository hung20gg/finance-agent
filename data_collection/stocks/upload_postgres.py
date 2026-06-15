import os
from dotenv import load_dotenv

import pandas as pd
import psycopg
from psycopg import sql


load_dotenv()

POSTGRES_URL = os.getenv(
    "POSTGRES_URL",
    "postgresql://postgres:12345678@localhost:5432/postgres",
)

TABLE_STOCK_DAILY = "stock_daily"
TABLE_STOCK_MONTHLY = "stock_monthly"
TABLE_INDICES_DAILY = "indices_daily"
TABLE_INDICES_MONTHLY = "indices_monthly"


def connect_db() -> psycopg.Connection:
    return psycopg.connect(POSTGRES_URL)


def create_table_if_not_exists(conn: psycopg.Connection, table_name: str) -> None:
    if "indices" in table_name:
        name_value = '"index_name" TEXT NOT NULL'
    else:
        name_value = '"stock_code" TEXT NOT NULL'

    if "monthly" in table_name:
        span_ema_fields = [
            '"EMA12" DOUBLE PRECISION',
            '"EMA26" DOUBLE PRECISION',
        ]
    else:
        span_ema_fields = [
            '"EMA20" DOUBLE PRECISION',
            '"EMA50" DOUBLE PRECISION',
            '"EMA200" DOUBLE PRECISION',
        ]

    column_defs = [
        '"time" TIMESTAMP NOT NULL',
        '"close" DOUBLE PRECISION NOT NULL',
        '"volume" BIGINT',
        name_value,
    ] + span_ema_fields

    statement = f"""
        CREATE TABLE IF NOT EXISTS \"{table_name}\" (
            {", ".join(column_defs)}
        )
    """
    with conn.cursor() as cur:
        cur.execute(statement)
    conn.commit()


def upload_dataframe_to_postgres(df: pd.DataFrame, conn: psycopg.Connection, table_name: str) -> None:
    original_len = len(df)
    df = df.dropna(subset=["close"])
    
    if "yahoo_symbol" in df.columns:
        df = df.drop(columns=["yahoo_symbol"])

    if len(df) < original_len:
        print(f"Dropped {original_len - len(df)} rows with null close values")

    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df = df.dropna(subset=["time"])

    df = df.where(pd.notnull(df), None)
    if df.empty:
        print(f"No rows to upload for {table_name}")
        return

    columns = list(df.columns)
    insert_stmt = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        sql.Identifier(table_name),
        sql.SQL(", ").join(sql.Identifier(col) for col in columns),
        sql.SQL(", ").join(sql.Placeholder() for _ in columns),
    )

    records = list(df.itertuples(index=False, name=None))
    with conn.cursor() as cur:
        cur.executemany(insert_stmt, records)
    conn.commit()
    print(f"Uploaded {len(records)} rows to {table_name}")

def truncate_table(conn: psycopg.Connection, table_name: str) -> None:
    statement = sql.SQL("TRUNCATE TABLE {}").format(sql.Identifier(table_name))
    with conn.cursor() as cur:
        cur.execute(statement)
    conn.commit()


def main() -> None:
    with connect_db() as conn:
        create_table_if_not_exists(conn, TABLE_STOCK_DAILY)
        create_table_if_not_exists(conn, TABLE_STOCK_MONTHLY)
        create_table_if_not_exists(conn, TABLE_INDICES_DAILY)
        create_table_if_not_exists(conn, TABLE_INDICES_MONTHLY)

        truncate_table(conn, TABLE_STOCK_DAILY)
        truncate_table(conn, TABLE_INDICES_DAILY)

        df_stock_daily = pd.read_parquet("../data/stock_daily.parquet")
        upload_dataframe_to_postgres(df_stock_daily, conn, TABLE_STOCK_DAILY)

        df_indices_daily = pd.read_parquet("../data/indices_daily.parquet")
        upload_dataframe_to_postgres(df_indices_daily, conn, TABLE_INDICES_DAILY)

        df_indices_daily = pd.read_parquet("../data/stock_price_daily_yahoo.parquet")
        upload_dataframe_to_postgres(df_indices_daily, conn, TABLE_STOCK_DAILY)

if __name__ == "__main__":
    main()
