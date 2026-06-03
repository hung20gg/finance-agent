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

TABLE_MACRO = "macro"
TABLE_BOND = "bond"


def connect_db() -> psycopg.Connection:
    return psycopg.connect(POSTGRES_URL)


def create_table_if_not_exists(conn: psycopg.Connection, table_name: str) -> None:
    statement = f"""
        CREATE TABLE IF NOT EXISTS \"{table_name}\" (
            "datetime" TIMESTAMP NOT NULL,
            "duration" TEXT NOT NULL,
            "indicator_name" TEXT NOT NULL,
            "country" TEXT NOT NULL,
            "value" DOUBLE PRECISION NOT NULL,
            "unit" TEXT NOT NULL
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

    if "datetime" in df.columns:
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        df = df.dropna(subset=["datetime"])

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
        create_table_if_not_exists(conn, TABLE_MACRO)
        # create_table_if_not_exists(conn, TABLE_BOND)

        df_macro = pd.read_parquet("../data/macro.parquet")
        upload_dataframe_to_postgres(df_macro, conn, TABLE_MACRO)

        # df_bond = pd.read_parquet("../data/monthly_bond.parquet")
        # upload_dataframe_to_postgres(df_bond, conn, TABLE_BOND)


if __name__ == "__main__":
    main()
