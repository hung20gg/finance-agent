-- =============================================================
-- create_schema.sql
-- DDL-only schema creation for the Finance Agent database.
-- This file is executed by migrate_database_schema.py.
-- Do NOT run standalone — the Python script manages the
-- transaction and disables FK checks during DDL.
-- =============================================================

-- =========================
-- DROP OLD TABLES (reverse FK order)
-- =========================

DROP TABLE IF EXISTS fact_industry_financial_ratio CASCADE;
DROP TABLE IF EXISTS fact_industry_financial_statement CASCADE;
DROP TABLE IF EXISTS fact_financial_ratio CASCADE;
DROP TABLE IF EXISTS fact_financial_statement CASCADE;
DROP TABLE IF EXISTS fact_macro CASCADE;
DROP TABLE IF EXISTS fact_commodity_monthly CASCADE;
DROP TABLE IF EXISTS fact_commodity_daily CASCADE;
DROP TABLE IF EXISTS fact_index_monthly CASCADE;
DROP TABLE IF EXISTS fact_index_daily CASCADE;
DROP TABLE IF EXISTS fact_stock_monthly CASCADE;
DROP TABLE IF EXISTS fact_stock_daily CASCADE;

DROP TABLE IF EXISTS dim_data_catalog CASCADE;
DROP TABLE IF EXISTS dim_macro_indicator CASCADE;
DROP TABLE IF EXISTS dim_country CASCADE;
DROP TABLE IF EXISTS dim_commodity_indicator CASCADE;
DROP TABLE IF EXISTS dim_market_index CASCADE;
DROP TABLE IF EXISTS dim_financial_ratio CASCADE;
DROP TABLE IF EXISTS dim_financial_statement_category CASCADE;
DROP TABLE IF EXISTS dim_company CASCADE;
DROP TABLE IF EXISTS dim_exchange CASCADE;
DROP TABLE IF EXISTS dim_industry CASCADE;

-- =========================
-- CREATE DIMENSIONS
-- =========================

CREATE TABLE IF NOT EXISTS dim_industry (
    industry_id   BIGSERIAL PRIMARY KEY,
    industry_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_exchange (
    exchange_id   BIGSERIAL PRIMARY KEY,
    exchange_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_company (
    stock_code    TEXT    NOT NULL PRIMARY KEY,
    company_name  TEXT,
    short_name    TEXT,
    industry_id   BIGINT  REFERENCES dim_industry(industry_id),
    exchange_id   BIGINT  REFERENCES dim_exchange(exchange_id),
    stock_indices TEXT,
    is_bank       BOOLEAN,
    is_securities BOOLEAN
);

CREATE TABLE IF NOT EXISTS dim_financial_statement_category (
    category_code TEXT NOT NULL PRIMARY KEY,
    category_name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_financial_ratio (
    ratio_code    TEXT NOT NULL PRIMARY KEY,
    ratio_name    TEXT NOT NULL,
    function_name TEXT
);

CREATE TABLE IF NOT EXISTS dim_market_index (
    index_id   BIGSERIAL PRIMARY KEY,
    index_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_commodity_indicator (
    indicator_code TEXT NOT NULL PRIMARY KEY,
    indicator_name TEXT,
    unit           TEXT
);

CREATE TABLE IF NOT EXISTS dim_country (
    country_id   BIGSERIAL PRIMARY KEY,
    country_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dim_macro_indicator (
    indicator_id   BIGSERIAL PRIMARY KEY,
    indicator_name TEXT NOT NULL,
    country_id     BIGINT REFERENCES dim_country(country_id),
    unit           TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_dim_macro_indicator
    ON dim_macro_indicator (
        indicator_name,
        COALESCE(country_id, -1),
        COALESCE(unit, '')
    );

CREATE TABLE IF NOT EXISTS dim_data_catalog (
    table_name       TEXT    NOT NULL,
    column_name      TEXT    NOT NULL,
    explanation      TEXT,
    dtype            TEXT,
    node             TEXT,
    note             TEXT,
    is_nullable      TEXT,
    column_default   TEXT,
    ordinal_position INTEGER,
    refreshed_at     TIMESTAMP DEFAULT now(),
    PRIMARY KEY (table_name, column_name)
);

-- =========================
-- CREATE FACTS
-- =========================

CREATE TABLE IF NOT EXISTS fact_stock_daily (
    stock_code TEXT      NOT NULL REFERENCES dim_company(stock_code),
    time       TIMESTAMP NOT NULL,
    close      NUMERIC,
    volume     NUMERIC,
    ema20      NUMERIC,
    ema50      NUMERIC,
    ema200     NUMERIC,
    PRIMARY KEY (stock_code, time)
);

CREATE TABLE IF NOT EXISTS fact_stock_monthly (
    stock_code TEXT      NOT NULL REFERENCES dim_company(stock_code),
    time       TIMESTAMP NOT NULL,
    close      NUMERIC,
    volume     NUMERIC,
    ema12      NUMERIC,
    ema26      NUMERIC,
    PRIMARY KEY (stock_code, time)
);

CREATE TABLE IF NOT EXISTS fact_index_daily (
    index_id BIGINT    NOT NULL REFERENCES dim_market_index(index_id),
    time     TIMESTAMP NOT NULL,
    close    NUMERIC,
    volume   NUMERIC,
    ema20    NUMERIC,
    ema50    NUMERIC,
    ema200   NUMERIC,
    PRIMARY KEY (index_id, time)
);

CREATE TABLE IF NOT EXISTS fact_index_monthly (
    index_id BIGINT    NOT NULL REFERENCES dim_market_index(index_id),
    time     TIMESTAMP NOT NULL,
    close    NUMERIC,
    volume   NUMERIC,
    ema12    NUMERIC,
    ema26    NUMERIC,
    PRIMARY KEY (index_id, time)
);

CREATE TABLE IF NOT EXISTS fact_commodity_daily (
    indicator_code TEXT      NOT NULL REFERENCES dim_commodity_indicator(indicator_code),
    time           TIMESTAMP NOT NULL,
    value          NUMERIC,
    volume         NUMERIC,
    ema20          NUMERIC,
    ema50          NUMERIC,
    PRIMARY KEY (indicator_code, time)
);

CREATE TABLE IF NOT EXISTS fact_commodity_monthly (
    indicator_code TEXT      NOT NULL REFERENCES dim_commodity_indicator(indicator_code),
    time           TIMESTAMP NOT NULL,
    value          NUMERIC,
    volume         NUMERIC,
    ema12          NUMERIC,
    ema26          NUMERIC,
    PRIMARY KEY (indicator_code, time)
);

CREATE TABLE IF NOT EXISTS fact_macro (
    indicator_id BIGINT    NOT NULL REFERENCES dim_macro_indicator(indicator_id),
    datetime     TIMESTAMP NOT NULL,
    duration     TEXT,
    value        NUMERIC,
    PRIMARY KEY (indicator_id, datetime)
);

CREATE TABLE IF NOT EXISTS fact_financial_statement (
    stock_code    TEXT                  NOT NULL REFERENCES dim_company(stock_code),
    category_code TEXT                  NOT NULL REFERENCES dim_financial_statement_category(category_code),
    year          INTEGER               NOT NULL,
    quarter       INTEGER               NOT NULL,
    segment       TEXT NOT NULL DEFAULT '',
    data          NUMERIC,
    date_added    TIMESTAMP,
    PRIMARY KEY (stock_code, category_code, year, quarter, segment)
);

CREATE TABLE IF NOT EXISTS fact_financial_ratio (
    stock_code TEXT                  NOT NULL REFERENCES dim_company(stock_code),
    ratio_code TEXT                  NOT NULL REFERENCES dim_financial_ratio(ratio_code),
    year       INTEGER               NOT NULL,
    quarter    INTEGER               NOT NULL,
    segment    TEXT NOT NULL DEFAULT '',
    data       NUMERIC,
    date_added TIMESTAMP,
    PRIMARY KEY (stock_code, ratio_code, year, quarter, segment)
);

CREATE TABLE IF NOT EXISTS fact_industry_financial_statement (
    industry_id   BIGINT  NOT NULL REFERENCES dim_industry(industry_id),
    category_code TEXT    NOT NULL REFERENCES dim_financial_statement_category(category_code),
    year          INTEGER NOT NULL,
    quarter       INTEGER NOT NULL,
    segment       TEXT NOT NULL DEFAULT '',
    data          NUMERIC,
    date_added    TIMESTAMP,
    PRIMARY KEY (industry_id, category_code, year, quarter, segment)
);

CREATE TABLE IF NOT EXISTS fact_industry_financial_ratio (
    industry_id BIGINT  NOT NULL REFERENCES dim_industry(industry_id),
    ratio_code  TEXT    NOT NULL REFERENCES dim_financial_ratio(ratio_code),
    year        INTEGER NOT NULL,
    quarter     INTEGER NOT NULL,
    segment     TEXT NOT NULL DEFAULT '',
    data        NUMERIC,
    date_added  TIMESTAMP,
    PRIMARY KEY (industry_id, ratio_code, year, quarter, segment)
);
