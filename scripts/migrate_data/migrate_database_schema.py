"""
migrate_database_schema.py
--------------------------
Migrates data from ./scripts/data/to_be_migrated/ into the new PostgreSQL schema.

Source files:
  - df_company_info_v2.csv          -> dim_industry, dim_exchange, dim_company
  - stock_daily.parquet             \
                                     -> merged -> fact_stock_daily
  - stock_price_daily_yahoo.parquet           /
  - financial_ratio_v3.parquet      -> fact_financial_ratio
  - financial_statement_v3.parquet  -> fact_financial_statement
  - indices_daily.parquet           -> dim_market_index, fact_index_daily
  - macro.parquet                   -> dim_country, dim_macro_indicator, fact_macro
  - commodities_daily.parquet       -> dim_commodity_indicator, fact_commodity_daily

Dimension metadata sourced from:
  - data_collection/financial_statement/transform/metadata/map_ratio_code.csv
  - data_collection/financial_statement/transform/metadata/map_category_code.csv

All SQL DDL is executed from:
  - scripts/data/sql_scripts/create_schema_and_migrate.sql  (schema creation only)

The Python script handles data loading via psycopg2 COPY for performance.

Usage:
    python migrate_database_schema.py [--postgres-url <url>] [--data-dir <path>] [--dry-run]

Environment:
    POSTGRES_URL — overrides --postgres-url if set (default: postgresql://postgres:admin@localhost:5432/postgres)
"""

import argparse
import io
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd
import psycopg2
import psycopg2.extras

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "to_be_migrated"
SQL_SCRIPTS_DIR = SCRIPT_DIR / "sql_scripts"
METADATA_DIR = SCRIPT_DIR.parent.parent / "data_collection" / "financial_statement" / "transform" / "metadata"

DDL_SQL_FILE = SQL_SCRIPTS_DIR / "create_schema.sql"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _df_to_copy_buffer(df: pd.DataFrame) -> io.StringIO:
    """Serialize a DataFrame into a tab-separated buffer for COPY FROM STDIN."""
    buf = io.StringIO()
    df.to_csv(buf, sep="\t", header=False, index=False, na_rep="\\N")
    buf.seek(0)
    return buf


def copy_df_to_table(cursor, df: pd.DataFrame, table: str, columns: list) -> int:
    """Bulk-insert a DataFrame into *table* using COPY FROM STDIN.

    Args:
        cursor: psycopg2 cursor.
        df: DataFrame whose columns match *columns* (in order).
        table: Target table name.
        columns: Ordered list of column names to insert.

    Returns:
        Number of rows copied.
    """
    df_subset = df[columns].copy()
    buf = _df_to_copy_buffer(df_subset)
    cols_sql = ", ".join(columns)
    cursor.copy_from(buf, table, sep="\t", null="\\N", columns=columns)
    return len(df_subset)


def run_sql_file(conn, path: Path) -> None:
    """Execute a SQL file within the current connection (no auto-commit)."""
    sql = path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql)
    logger.info("Executed SQL file: %s", path.name)


# ---------------------------------------------------------------------------
# Load source data
# ---------------------------------------------------------------------------


def load_source_data(data_dir: Path, metadata_dir: Path) -> dict:
    """Load all source files and return a dict of DataFrames."""
    logger.info("Loading source files from %s", data_dir)
    data = {}

    # Company info
    company_path = data_dir / "df_company_info_v2.csv"
    logger.info("  Reading %s …", company_path.name)
    data["company_info"] = pd.read_csv(company_path)

    # Stock daily — merge two files (no overlapping rows confirmed)
    sd1_path = data_dir / "stock_daily.parquet"
    sd2_path = data_dir / "stock_price_daily_yahoo.parquet"
    logger.info("  Reading %s …", sd1_path.name)
    sd1 = pd.read_parquet(sd1_path)
    logger.info("  Reading %s …", sd2_path.name)
    sd2 = pd.read_parquet(sd2_path)
    logger.info(
        "  Merging stock_daily (%d rows) + stock_price_daily_yahoo (%d rows) …",
        len(sd1),
        len(sd2),
    )
    stock_daily = pd.concat([sd1, sd2], ignore_index=True)
    # Drop exact duplicate (stock_code, time) pairs, keep first
    before = len(stock_daily)
    stock_daily = stock_daily.drop_duplicates(subset=["stock_code", "time"], keep="first")
    after = len(stock_daily)
    if before != after:
        logger.warning("  Dropped %d duplicate (stock_code, time) rows from merged stock_daily.", before - after)
    data["stock_daily"] = stock_daily
    logger.info("  Merged stock_daily: %d rows total.", after)

    # Indices daily
    logger.info("  Reading indices_daily.parquet …")
    data["indices_daily"] = pd.read_parquet(data_dir / "indices_daily.parquet")

    # Commodities daily
    logger.info("  Reading commodities_daily.parquet …")
    data["commodities_daily"] = pd.read_parquet(data_dir / "commodities_daily.parquet")

    # Macro
    logger.info("  Reading macro.parquet …")
    data["macro"] = pd.read_parquet(data_dir / "macro.parquet")

    # Financial statement
    logger.info("  Reading financial_statement_v3.parquet …")
    data["financial_statement"] = pd.read_parquet(data_dir / "financial_statement_v3.parquet")

    # Financial ratio
    logger.info("  Reading financial_ratio_v3.parquet …")
    data["financial_ratio"] = pd.read_parquet(data_dir / "financial_ratio_v3.parquet")

    # Dimension metadata
    ratio_meta_path = metadata_dir / "map_ratio_code.csv"
    cat_meta_path = metadata_dir / "map_category_code.csv"
    if ratio_meta_path.exists():
        logger.info("  Reading map_ratio_code.csv …")
        data["ratio_dim"] = pd.read_csv(ratio_meta_path)
    else:
        logger.warning("  map_ratio_code.csv not found — will derive ratio_code from fact data only.")
        data["ratio_dim"] = None

    if cat_meta_path.exists():
        logger.info("  Reading map_category_code.csv …")
        data["category_dim"] = pd.read_csv(cat_meta_path)
    else:
        logger.warning("  map_category_code.csv not found — will derive category_code from fact data only.")
        data["category_dim"] = None

    return data


# ---------------------------------------------------------------------------
# Migrate dimensions
# ---------------------------------------------------------------------------


def migrate_dim_industry(cur, company_info: pd.DataFrame) -> pd.DataFrame:
    """Insert distinct industries; return dim_industry lookup DataFrame."""
    logger.info("  Inserting dim_industry …")
    industries = (
        company_info[["industry"]]
        .dropna()
        .drop_duplicates()
        .rename(columns={"industry": "industry_name"})
        .reset_index(drop=True)
    )
    cur.executemany(
        "INSERT INTO dim_industry (industry_name) VALUES (%s) ON CONFLICT (industry_name) DO NOTHING",
        [(row,) for row in industries["industry_name"]],
    )
    # Fetch back with generated ids
    cur.execute("SELECT industry_id, industry_name FROM dim_industry")
    dim = pd.DataFrame(cur.fetchall(), columns=["industry_id", "industry_name"])
    logger.info("    %d industries.", len(dim))
    return dim


def migrate_dim_exchange(cur, company_info: pd.DataFrame) -> pd.DataFrame:
    """Insert distinct exchanges; return dim_exchange lookup DataFrame."""
    logger.info("  Inserting dim_exchange …")
    exchanges = (
        company_info[["exchange"]]
        .dropna()
        .drop_duplicates()
        .rename(columns={"exchange": "exchange_name"})
        .reset_index(drop=True)
    )
    cur.executemany(
        "INSERT INTO dim_exchange (exchange_name) VALUES (%s) ON CONFLICT (exchange_name) DO NOTHING",
        [(row,) for row in exchanges["exchange_name"]],
    )
    cur.execute("SELECT exchange_id, exchange_name FROM dim_exchange")
    dim = pd.DataFrame(cur.fetchall(), columns=["exchange_id", "exchange_name"])
    logger.info("    %d exchanges.", len(dim))
    return dim


def migrate_dim_company(
    cur,
    company_info: pd.DataFrame,
    dim_industry: pd.DataFrame,
    dim_exchange: pd.DataFrame,
) -> None:
    """Insert companies with resolved FK ids."""
    logger.info("  Inserting dim_company …")
    df = company_info.copy()
    df = df.merge(dim_industry, left_on="industry", right_on="industry_name", how="left")
    df = df.merge(dim_exchange, left_on="exchange", right_on="exchange_name", how="left")
    df = df[df["stock_code"].notna()].drop_duplicates(subset=["stock_code"])

    rows = [
        (
            row["stock_code"],
            row.get("company_name") if pd.notna(row.get("company_name")) else None,
            row.get("short_name") if pd.notna(row.get("short_name")) else None,
            int(row["industry_id"]) if pd.notna(row.get("industry_id")) else None,
            int(row["exchange_id"]) if pd.notna(row.get("exchange_id")) else None,
            row.get("stock_indices") if pd.notna(row.get("stock_indices")) else None,
            bool(row["is_bank"]) if pd.notna(row.get("is_bank")) else None,
            bool(row["is_securities"]) if pd.notna(row.get("is_securities")) else None,
        )
        for _, row in df.iterrows()
    ]
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO dim_company
            (stock_code, company_name, short_name, industry_id, exchange_id,
             stock_indices, is_bank, is_securities)
        VALUES %s
        ON CONFLICT (stock_code) DO NOTHING
        """,
        rows,
    )
    logger.info("    %d companies.", len(rows))


def migrate_dim_financial_statement_category(cur, category_dim, financial_statement: pd.DataFrame) -> None:
    """Insert financial statement categories from metadata (or derive from fact data)."""
    logger.info("  Inserting dim_financial_statement_category …")
    if category_dim is not None:
        df = category_dim[["category_code", "category_name"]].dropna(subset=["category_code"]).drop_duplicates()
    else:
        # Derive from fact data — no category_name available
        codes = financial_statement[["category_code"]].dropna().drop_duplicates()
        df = codes.copy()
        df["category_name"] = df["category_code"]

    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO dim_financial_statement_category (category_code, category_name)
        VALUES %s
        ON CONFLICT (category_code) DO NOTHING
        """,
        list(df.itertuples(index=False, name=None)),
    )
    # Also insert any codes that appear in fact data but not in metadata
    fact_codes = set(financial_statement["category_code"].dropna().unique())
    cur.execute("SELECT category_code FROM dim_financial_statement_category")
    existing = {r[0] for r in cur.fetchall()}
    missing = fact_codes - existing
    if missing:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO dim_financial_statement_category (category_code, category_name) VALUES %s ON CONFLICT DO NOTHING",
            [(c, c) for c in missing],
        )
        logger.warning("    Inserted %d category_codes found only in fact data.", len(missing))
    logger.info("    %d financial statement categories.", len(existing) + len(missing))


def migrate_dim_financial_ratio(cur, ratio_dim, financial_ratio: pd.DataFrame) -> None:
    """Insert financial ratio dimension."""
    logger.info("  Inserting dim_financial_ratio …")
    if ratio_dim is not None:
        df = ratio_dim[["ratio_code", "ratio_name", "function_name"]].dropna(subset=["ratio_code"]).drop_duplicates()
        psycopg2.extras.execute_values(
            cur,
            """
            INSERT INTO dim_financial_ratio (ratio_code, ratio_name, function_name)
            VALUES %s
            ON CONFLICT (ratio_code) DO NOTHING
            """,
            list(df.itertuples(index=False, name=None)),
        )
    # Insert any ratio_codes in fact data missing from metadata
    fact_codes = set(financial_ratio["ratio_code"].dropna().unique())
    cur.execute("SELECT ratio_code FROM dim_financial_ratio")
    existing = {r[0] for r in cur.fetchall()}
    missing = fact_codes - existing
    if missing:
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO dim_financial_ratio (ratio_code, ratio_name) VALUES %s ON CONFLICT DO NOTHING",
            [(c, c) for c in missing],
        )
        logger.warning("    Inserted %d ratio_codes found only in fact data.", len(missing))
    cur.execute("SELECT COUNT(*) FROM dim_financial_ratio")
    logger.info("    %d financial ratios.", cur.fetchone()[0])


def migrate_dim_market_index(cur, indices_daily: pd.DataFrame) -> pd.DataFrame:
    """Insert distinct market indices; return dim_market_index lookup."""
    logger.info("  Inserting dim_market_index …")
    names = indices_daily[["index_name"]].dropna().drop_duplicates()
    for name in names["index_name"]:
        cur.execute(
            "INSERT INTO dim_market_index (index_name) VALUES (%s) ON CONFLICT (index_name) DO NOTHING",
            (name,),
        )
    cur.execute("SELECT index_id, index_name FROM dim_market_index")
    dim = pd.DataFrame(cur.fetchall(), columns=["index_id", "index_name"])
    logger.info("    %d market indices.", len(dim))
    return dim


def migrate_dim_commodity_indicator(cur, commodities_daily: pd.DataFrame) -> None:
    """Insert distinct commodity indicators."""
    logger.info("  Inserting dim_commodity_indicator …")
    df = (
        commodities_daily[["indicator_code", "indicator_name"]]
        .dropna(subset=["indicator_code"])
        .drop_duplicates(subset=["indicator_code"])
    )
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO dim_commodity_indicator (indicator_code, indicator_name)
        VALUES %s
        ON CONFLICT (indicator_code) DO NOTHING
        """,
        list(df.itertuples(index=False, name=None)),
    )
    logger.info("    %d commodity indicators.", len(df))


def migrate_dim_country(cur, macro: pd.DataFrame) -> pd.DataFrame:
    """Insert distinct countries; return dim_country lookup."""
    logger.info("  Inserting dim_country …")
    countries = macro[["country"]].dropna().drop_duplicates().rename(columns={"country": "country_name"})
    for name in countries["country_name"]:
        cur.execute(
            "INSERT INTO dim_country (country_name) VALUES (%s) ON CONFLICT (country_name) DO NOTHING",
            (name,),
        )
    cur.execute("SELECT country_id, country_name FROM dim_country")
    dim = pd.DataFrame(cur.fetchall(), columns=["country_id", "country_name"])
    logger.info("    %d countries.", len(dim))
    return dim


def migrate_dim_macro_indicator(cur, macro: pd.DataFrame, dim_country: pd.DataFrame) -> pd.DataFrame:
    """Insert distinct macro indicators (name + country + unit); return lookup."""
    logger.info("  Inserting dim_macro_indicator …")
    df = (
        macro[["indicator_name", "country", "unit"]]
        .dropna(subset=["indicator_name"])
        .drop_duplicates()
        .merge(dim_country, left_on="country", right_on="country_name", how="left")
    )
    rows = [
        (
            row["indicator_name"],
            int(row["country_id"]) if pd.notna(row.get("country_id")) else None,
            row["unit"] if pd.notna(row.get("unit")) else None,
        )
        for _, row in df.iterrows()
    ]
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO dim_macro_indicator (indicator_name, country_id, unit)
        VALUES %s
        ON CONFLICT DO NOTHING
        """,
        rows,
    )
    cur.execute("SELECT indicator_id, indicator_name, country_id, unit FROM dim_macro_indicator")
    dim = pd.DataFrame(cur.fetchall(), columns=["indicator_id", "indicator_name", "country_id", "unit"])
    logger.info("    %d macro indicators.", len(dim))
    return dim


# ---------------------------------------------------------------------------
# Migrate facts
# ---------------------------------------------------------------------------


def migrate_fact_stock_daily(cur, stock_daily: pd.DataFrame) -> None:
    """Insert merged stock_daily into fact_stock_daily.

    Only rows whose stock_code exists in dim_company are inserted.
    """
    logger.info("  Inserting fact_stock_daily …")
    cur.execute("SELECT stock_code FROM dim_company")
    valid_codes = {r[0] for r in cur.fetchall()}

    df = stock_daily[stock_daily["stock_code"].isin(valid_codes)].copy()
    df = df.dropna(subset=["stock_code", "time"])
    df = df.drop_duplicates(subset=["stock_code", "time"])

    df_insert = df[["stock_code", "time", "close", "volume", "EMA20", "EMA50", "EMA200"]].rename(
        columns={"EMA20": "ema20", "EMA50": "ema50", "EMA200": "ema200"}
    )
    rows = copy_df_to_table(cur, df_insert, "fact_stock_daily", ["stock_code", "time", "close", "volume", "ema20", "ema50", "ema200"])
    logger.info("    %d rows inserted into fact_stock_daily.", rows)

    skipped = len(stock_daily) - len(df)
    if skipped:
        logger.warning("    Skipped %d stock_daily rows (stock_code not in dim_company or missing key).", skipped)


def migrate_fact_index_daily(cur, indices_daily: pd.DataFrame, dim_market_index: pd.DataFrame) -> None:
    """Insert fact_index_daily."""
    logger.info("  Inserting fact_index_daily …")
    df = indices_daily.merge(dim_market_index, on="index_name", how="inner")
    df = df.dropna(subset=["index_id", "time"])
    df = df.drop_duplicates(subset=["index_id", "time"])
    df_insert = df[["index_id", "time", "close", "volume", "EMA20", "EMA50", "EMA200"]].rename(
        columns={"EMA20": "ema20", "EMA50": "ema50", "EMA200": "ema200"}
    )
    rows = copy_df_to_table(cur, df_insert, "fact_index_daily", ["index_id", "time", "close", "volume", "ema20", "ema50", "ema200"])
    logger.info("    %d rows inserted into fact_index_daily.", rows)


def migrate_fact_commodity_daily(cur, commodities_daily: pd.DataFrame) -> None:
    """Insert fact_commodity_daily."""
    logger.info("  Inserting fact_commodity_daily …")
    df = commodities_daily.copy()
    df = df.dropna(subset=["indicator_code", "time"])
    df = df.drop_duplicates(subset=["indicator_code", "time"])
    df_insert = df[["indicator_code", "time", "value", "volume", "EMA20", "EMA50"]].rename(
        columns={"EMA20": "ema20", "EMA50": "ema50"}
    )
    rows = copy_df_to_table(cur, df_insert, "fact_commodity_daily", ["indicator_code", "time", "value", "volume", "ema20", "ema50"])
    logger.info("    %d rows inserted into fact_commodity_daily.", rows)


def migrate_fact_macro(cur, macro: pd.DataFrame, dim_macro_indicator: pd.DataFrame, dim_country: pd.DataFrame) -> None:
    """Insert fact_macro."""
    logger.info("  Inserting fact_macro …")
    df = macro.copy()
    df = df.merge(dim_country, left_on="country", right_on="country_name", how="left")
    df = df.merge(
        dim_macro_indicator,
        left_on=["indicator_name", "country_id", "unit"],
        right_on=["indicator_name", "country_id", "unit"],
        how="inner",
    )
    df = df.dropna(subset=["indicator_id", "datetime"])
    df = df.drop_duplicates(subset=["indicator_id", "datetime"])
    df_insert = df[["indicator_id", "datetime", "duration", "value"]]
    rows = copy_df_to_table(cur, df_insert, "fact_macro", ["indicator_id", "datetime", "duration", "value"])
    logger.info("    %d rows inserted into fact_macro.", rows)


def migrate_fact_financial_statement(cur, financial_statement: pd.DataFrame) -> None:
    """Insert fact_financial_statement.

    Filters to rows whose stock_code and category_code exist in their dimension tables.
    """
    logger.info("  Inserting fact_financial_statement …")
    cur.execute("SELECT stock_code FROM dim_company")
    valid_stocks = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT category_code FROM dim_financial_statement_category")
    valid_cats = {r[0] for r in cur.fetchall()}

    df = financial_statement.copy()
    df["quarter"] = df["quarter"].astype("Int64")
    df["year"] = df["year"].astype("Int64")
    df["segment"] = df["segment"].fillna("")
    df = df[df["stock_code"].isin(valid_stocks) & df["category_code"].isin(valid_cats)]
    df = df.dropna(subset=["stock_code", "category_code", "year", "quarter"])
    df = df.drop_duplicates(subset=["stock_code", "category_code", "year", "quarter", "segment"])

    df_insert = df[["stock_code", "category_code", "year", "quarter", "segment", "data", "date_added"]]
    rows = copy_df_to_table(
        cur,
        df_insert,
        "fact_financial_statement",
        ["stock_code", "category_code", "year", "quarter", "segment", "data", "date_added"],
    )
    logger.info("    %d rows inserted into fact_financial_statement.", rows)


def migrate_fact_financial_ratio(cur, financial_ratio: pd.DataFrame) -> None:
    """Insert fact_financial_ratio."""
    logger.info("  Inserting fact_financial_ratio …")
    cur.execute("SELECT stock_code FROM dim_company")
    valid_stocks = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT ratio_code FROM dim_financial_ratio")
    valid_ratios = {r[0] for r in cur.fetchall()}

    df = financial_ratio.copy()
    df["segment"] = df["segment"].fillna("")
    df = df[df["stock_code"].isin(valid_stocks) & df["ratio_code"].isin(valid_ratios)]
    df = df.dropna(subset=["stock_code", "ratio_code", "year", "quarter"])
    df = df.drop_duplicates(subset=["stock_code", "ratio_code", "year", "quarter", "segment"])

    df_insert = df[["stock_code", "ratio_code", "year", "quarter", "segment", "data", "date_added"]]
    rows = copy_df_to_table(
        cur,
        df_insert,
        "fact_financial_ratio",
        ["stock_code", "ratio_code", "year", "quarter", "segment", "data", "date_added"],
    )
    logger.info("    %d rows inserted into fact_financial_ratio.", rows)


def migrate_fact_industry_financial_statement(cur) -> None:
    """Aggregate fact_financial_statement by industry into fact_industry_financial_statement.

    Joins fact_financial_statement → dim_company → dim_industry to resolve industry_id,
    then groups by (industry_id, category_code, year, quarter, segment) using
    AVG(data) and MAX(date_added).
    """
    logger.info("  Inserting fact_industry_financial_statement (aggregated from fact_financial_statement) …")
    cur.execute(
        """
        INSERT INTO fact_industry_financial_statement (
            industry_id, category_code, year, quarter, segment, data, date_added
        )
        SELECT
            c.industry_id,
            fs.category_code,
            fs.year,
            fs.quarter,
            fs.segment,
            AVG(fs.data)         AS data,
            MAX(fs.date_added)   AS date_added
        FROM fact_financial_statement fs
        JOIN dim_company c
            ON fs.stock_code = c.stock_code
        WHERE c.industry_id IS NOT NULL
        GROUP BY
            c.industry_id,
            fs.category_code,
            fs.year,
            fs.quarter,
            fs.segment
        ON CONFLICT (industry_id, category_code, year, quarter, segment)
            DO UPDATE SET
                data       = EXCLUDED.data,
                date_added = EXCLUDED.date_added
        """
    )
    cur.execute("SELECT COUNT(*) FROM fact_industry_financial_statement")
    logger.info("    %d rows in fact_industry_financial_statement.", cur.fetchone()[0])


def migrate_fact_industry_financial_ratio(cur) -> None:
    """Aggregate fact_financial_ratio by industry into fact_industry_financial_ratio.

    Joins fact_financial_ratio → dim_company → dim_industry to resolve industry_id,
    then groups by (industry_id, ratio_code, year, quarter, segment) using
    AVG(data) and MAX(date_added).
    """
    logger.info("  Inserting fact_industry_financial_ratio (aggregated from fact_financial_ratio) …")
    cur.execute(
        """
        INSERT INTO fact_industry_financial_ratio (
            industry_id, ratio_code, year, quarter, segment, data, date_added
        )
        SELECT
            c.industry_id,
            fr.ratio_code,
            fr.year,
            fr.quarter,
            fr.segment,
            AVG(fr.data)         AS data,
            MAX(fr.date_added)   AS date_added
        FROM fact_financial_ratio fr
        JOIN dim_company c
            ON fr.stock_code = c.stock_code
        WHERE c.industry_id IS NOT NULL
        GROUP BY
            c.industry_id,
            fr.ratio_code,
            fr.year,
            fr.quarter,
            fr.segment
        ON CONFLICT (industry_id, ratio_code, year, quarter, segment)
            DO UPDATE SET
                data       = EXCLUDED.data,
                date_added = EXCLUDED.date_added
        """
    )
    cur.execute("SELECT COUNT(*) FROM fact_industry_financial_ratio")
    logger.info("    %d rows in fact_industry_financial_ratio.", cur.fetchone()[0])



# ---------------------------------------------------------------------------
# Data catalog
# ---------------------------------------------------------------------------


def populate_data_catalog(cur) -> None:
    """Populate dim_data_catalog from information_schema."""
    logger.info("  Populating dim_data_catalog …")
    cur.execute(
        """
        INSERT INTO dim_data_catalog (
            table_name, column_name, dtype, is_nullable,
            column_default, ordinal_position, refreshed_at
        )
        SELECT
            cols.table_name,
            cols.column_name,
            cols.data_type,
            cols.is_nullable,
            cols.column_default,
            cols.ordinal_position,
            now()
        FROM information_schema.columns cols
        WHERE cols.table_schema = 'public'
          AND (
              cols.table_name LIKE 'dim_%%'
              OR cols.table_name LIKE 'fact_%%'
          )
        ON CONFLICT (table_name, column_name) DO UPDATE
            SET refreshed_at = EXCLUDED.refreshed_at
        """
    )
    cur.execute("SELECT COUNT(*) FROM dim_data_catalog")
    logger.info("    %d entries in dim_data_catalog.", cur.fetchone()[0])


# ---------------------------------------------------------------------------
# Schema creation (DDL only, no data)
# ---------------------------------------------------------------------------


def create_schema(conn, sql_file: Path, dry_run: bool) -> None:
    """Drop old tables and re-create the new schema from the SQL DDL file.

    The SQL file is expected to handle its own transaction (BEGIN/COMMIT).
    We strip those out and manage the transaction from Python so we can
    rollback on error.
    """
    logger.info("Creating schema from %s …", sql_file.name)
    raw_sql = sql_file.read_text(encoding="utf-8")

    # Remove ROLLBACK/BEGIN/COMMIT — we control the transaction in Python
    lines = []
    for line in raw_sql.splitlines():
        stripped = line.strip().upper()
        if stripped in ("ROLLBACK;", "BEGIN;", "COMMIT;"):
            continue
        lines.append(line)
    ddl_sql = "\n".join(lines)

    if dry_run:
        logger.info("[DRY-RUN] Would execute DDL SQL (%d chars).", len(ddl_sql))
        return

    with conn.cursor() as cur:
        cur.execute(ddl_sql)
    logger.info("Schema created successfully.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate data files into the new PostgreSQL schema.")
    parser.add_argument(
        "--postgres-url",
        default=None,
        help="PostgreSQL connection URL (default: read from POSTGRES_URL env or mcp-server/.env)",
    )
    parser.add_argument(
        "--data-dir",
        default=str(DATA_DIR),
        help=f"Path to the to_be_migrated data folder (default: {DATA_DIR})",
    )
    parser.add_argument(
        "--metadata-dir",
        default=str(METADATA_DIR),
        help=f"Path to financial statement metadata folder (default: {METADATA_DIR})",
    )
    parser.add_argument(
        "--skip-schema",
        action="store_true",
        help="Skip dropping and re-creating the schema (useful when tables already exist).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and validate data but do not write to the database.",
    )
    return parser.parse_args()


def resolve_postgres_url(args: argparse.Namespace) -> str:
    """Resolve the PostgreSQL connection URL from args, env, or .env file."""
    # 1. CLI argument
    if args.postgres_url:
        return args.postgres_url

    # 2. Environment variable
    url = os.environ.get("POSTGRES_URL")
    if url:
        return url

    # 3. mcp-server/.env
    env_path = SCRIPT_DIR.parent.parent / "mcp-server" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("POSTGRES_URL="):
                return line.split("=", 1)[1]

    # 4. Default
    return "postgresql://postgres:admin@localhost:5432/postgres"


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    metadata_dir = Path(args.metadata_dir)
    postgres_url = resolve_postgres_url(args)

    logger.info("=" * 60)
    logger.info("Finance Agent — Database Migration")
    logger.info("=" * 60)
    logger.info("PostgreSQL: %s", postgres_url)
    logger.info("Data dir:   %s", data_dir)
    logger.info("Dry run:    %s", args.dry_run)
    logger.info("=" * 60)

    # ------------------------------------------------------------------
    # Load all source data first (fail fast before touching DB)
    # ------------------------------------------------------------------
    t0 = time.time()
    data = load_source_data(data_dir, metadata_dir)
    logger.info("Source data loaded in %.1fs.", time.time() - t0)

    if args.dry_run:
        logger.info("[DRY-RUN] All data loaded successfully. Skipping database writes.")
        return

    # ------------------------------------------------------------------
    # Connect to PostgreSQL
    # ------------------------------------------------------------------
    logger.info("Connecting to PostgreSQL …")
    conn = psycopg2.connect(postgres_url)
    conn.autocommit = False  # we manage transactions explicitly

    try:
        # ------------------------------------------------------------------
        # Phase 1: Schema creation (DDL)
        # ------------------------------------------------------------------
        if not args.skip_schema:
            with conn.cursor() as cur:
                cur.execute("SET session_replication_role = 'replica'")  # disable FK checks during DDL
            create_schema(conn, DDL_SQL_FILE, dry_run=False)
            with conn.cursor() as cur:
                cur.execute("SET session_replication_role = 'origin'")
            conn.commit()
            logger.info("Schema committed.")
        else:
            logger.info("Skipping schema creation (--skip-schema).")

        # ------------------------------------------------------------------
        # Phase 2: Data migration
        # ------------------------------------------------------------------
        logger.info("Starting data migration …")
        t1 = time.time()

        with conn.cursor() as cur:
            # Dimensions (order matters due to FK constraints)
            logger.info("— Migrating dimensions —")
            dim_industry = migrate_dim_industry(cur, data["company_info"])
            dim_exchange = migrate_dim_exchange(cur, data["company_info"])
            migrate_dim_company(cur, data["company_info"], dim_industry, dim_exchange)
            migrate_dim_financial_statement_category(cur, data["category_dim"], data["financial_statement"])
            migrate_dim_financial_ratio(cur, data["ratio_dim"], data["financial_ratio"])
            dim_market_index = migrate_dim_market_index(cur, data["indices_daily"])
            migrate_dim_commodity_indicator(cur, data["commodities_daily"])
            dim_country = migrate_dim_country(cur, data["macro"])
            dim_macro_indicator = migrate_dim_macro_indicator(cur, data["macro"], dim_country)

            # Facts
            logger.info("— Migrating facts —")
            migrate_fact_stock_daily(cur, data["stock_daily"])
            migrate_fact_index_daily(cur, data["indices_daily"], dim_market_index)
            migrate_fact_commodity_daily(cur, data["commodities_daily"])
            migrate_fact_macro(cur, data["macro"], dim_macro_indicator, dim_country)
            migrate_fact_financial_statement(cur, data["financial_statement"])
            migrate_fact_financial_ratio(cur, data["financial_ratio"])
            migrate_fact_industry_financial_statement(cur)
            migrate_fact_industry_financial_ratio(cur)

            # Data catalog
            logger.info("— Populating data catalog —")
            populate_data_catalog(cur)

        conn.commit()
        elapsed = time.time() - t1
        logger.info("=" * 60)
        logger.info("Migration completed successfully in %.1fs.", elapsed)
        logger.info("=" * 60)

    except Exception as exc:
        conn.rollback()
        logger.error("Migration failed — transaction rolled back. Error: %s", exc)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
