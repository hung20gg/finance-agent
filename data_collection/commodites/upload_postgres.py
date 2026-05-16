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

TABLE_COMMODITIES_DAILY = "commodities_daily"
TABLE_COMMODITIES_MONTHLY = "commodities_monthly"


def connect_db() -> psycopg.Connection:
    return psycopg.connect(POSTGRES_URL)


def create_table_if_not_exists(conn: psycopg.Connection, table_name: str) -> None:
    if "monthly" in table_name:
        span_ema_fields = [
            '"EMA12" DOUBLE PRECISION',
            '"EMA26" DOUBLE PRECISION',
        ]
    else:
        span_ema_fields = [
            '"EMA20" DOUBLE PRECISION',
            '"EMA50" DOUBLE PRECISION',
        ]

    column_defs = [
        '"time" TIMESTAMP NOT NULL',
        '"indicator_code" TEXT NOT NULL',
        '"indicator_name" TEXT NOT NULL',
        '"value" DOUBLE PRECISION NOT NULL',
        '"volume" BIGINT',
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
    df = df.dropna(subset=["value"])
    if len(df) < original_len:
        print(f"Dropped {original_len - len(df)} rows with null value")

    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df = df.dropna(subset=["time"])

    if "duration" in df.columns:
        df = df.drop(columns=["duration"])

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


def main() -> None:
    with connect_db() as conn:
        create_table_if_not_exists(conn, TABLE_COMMODITIES_DAILY)
        create_table_if_not_exists(conn, TABLE_COMMODITIES_MONTHLY)

        df_commodities_daily = pd.read_parquet("../data/commodities_daily.parquet")
        upload_dataframe_to_postgres(df_commodities_daily, conn, TABLE_COMMODITIES_DAILY)

        # df_commodities_monthly = pd.read_parquet("../data/commodities_monthly.parquet")
        # upload_dataframe_to_postgres(df_commodities_monthly, conn, TABLE_COMMODITIES_MONTHLY)


if __name__ == "__main__":
    main()
