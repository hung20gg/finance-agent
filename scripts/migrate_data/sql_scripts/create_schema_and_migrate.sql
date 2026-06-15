ROLLBACK;

BEGIN;

-- =========================
-- DROP OLD NEW TABLES
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

CREATE TABLE dim_industry (
    industry_id BIGSERIAL PRIMARY KEY,
    industry_name TEXT UNIQUE NOT NULL
);

CREATE TABLE dim_exchange (
    exchange_id BIGSERIAL PRIMARY KEY,
    exchange_name TEXT UNIQUE NOT NULL
);

CREATE TABLE dim_company (
    stock_code TEXT PRIMARY KEY,
    company_name TEXT,
    short_name TEXT,
    industry_id BIGINT REFERENCES dim_industry(industry_id),
    exchange_id BIGINT REFERENCES dim_exchange(exchange_id),
    stock_indices TEXT,
    is_bank BOOLEAN,
    is_securities BOOLEAN
);

CREATE TABLE dim_financial_statement_category (
    category_code TEXT PRIMARY KEY,
    category_name TEXT NOT NULL
);

CREATE TABLE dim_financial_ratio (
    ratio_code TEXT PRIMARY KEY,
    ratio_name TEXT NOT NULL,
    function_name TEXT
);

CREATE TABLE dim_market_index (
    index_id BIGSERIAL PRIMARY KEY,
    index_name TEXT UNIQUE NOT NULL
);

CREATE TABLE dim_commodity_indicator (
    indicator_code TEXT PRIMARY KEY,
    indicator_name TEXT,
    unit TEXT
);

CREATE TABLE dim_country (
    country_id BIGSERIAL PRIMARY KEY,
    country_name TEXT UNIQUE NOT NULL
);

CREATE TABLE dim_macro_indicator (
    indicator_id BIGSERIAL PRIMARY KEY,
    indicator_name TEXT NOT NULL,
    country_id BIGINT REFERENCES dim_country(country_id),
    unit TEXT
);

CREATE UNIQUE INDEX uq_dim_macro_indicator
ON dim_macro_indicator (
    indicator_name,
    COALESCE(country_id, -1),
    COALESCE(unit, '')
);

CREATE TABLE dim_data_catalog (
    table_name TEXT NOT NULL,
    column_name TEXT NOT NULL,
    explanation TEXT,
    dtype TEXT,
    node TEXT,
    note TEXT,
    is_nullable TEXT,
    column_default TEXT,
    ordinal_position INTEGER,
    refreshed_at TIMESTAMP DEFAULT now(),
    PRIMARY KEY (table_name, column_name)
);

-- =========================
-- CREATE FACTS
-- =========================

CREATE TABLE fact_stock_daily (
    stock_code TEXT NOT NULL REFERENCES dim_company(stock_code),
    time TIMESTAMP NOT NULL,
    close NUMERIC,
    volume NUMERIC,
    ema20 NUMERIC,
    ema50 NUMERIC,
    ema200 NUMERIC,
    PRIMARY KEY (stock_code, time)
);

CREATE TABLE fact_stock_monthly (
    stock_code TEXT NOT NULL REFERENCES dim_company(stock_code),
    time TIMESTAMP NOT NULL,
    close NUMERIC,
    volume NUMERIC,
    ema12 NUMERIC,
    ema26 NUMERIC,
    PRIMARY KEY (stock_code, time)
);

CREATE TABLE fact_index_daily (
    index_id BIGINT NOT NULL REFERENCES dim_market_index(index_id),
    time TIMESTAMP NOT NULL,
    close NUMERIC,
    volume NUMERIC,
    ema20 NUMERIC,
    ema50 NUMERIC,
    ema200 NUMERIC,
    PRIMARY KEY (index_id, time)
);

CREATE TABLE fact_index_monthly (
    index_id BIGINT NOT NULL REFERENCES dim_market_index(index_id),
    time TIMESTAMP NOT NULL,
    close NUMERIC,
    volume NUMERIC,
    ema12 NUMERIC,
    ema26 NUMERIC,
    PRIMARY KEY (index_id, time)
);

CREATE TABLE fact_commodity_daily (
    indicator_code TEXT NOT NULL REFERENCES dim_commodity_indicator(indicator_code),
    time TIMESTAMP NOT NULL,
    value NUMERIC,
    volume NUMERIC,
    ema20 NUMERIC,
    ema50 NUMERIC,
    PRIMARY KEY (indicator_code, time)
);

CREATE TABLE fact_commodity_monthly (
    indicator_code TEXT NOT NULL REFERENCES dim_commodity_indicator(indicator_code),
    time TIMESTAMP NOT NULL,
    value NUMERIC,
    volume NUMERIC,
    ema12 NUMERIC,
    ema26 NUMERIC,
    PRIMARY KEY (indicator_code, time)
);

CREATE TABLE fact_macro (
    indicator_id BIGINT NOT NULL REFERENCES dim_macro_indicator(indicator_id),
    datetime TIMESTAMP NOT NULL,
    duration TEXT,
    value NUMERIC,
    PRIMARY KEY (indicator_id, datetime)
);

CREATE TABLE fact_financial_statement (
    stock_code TEXT NOT NULL REFERENCES dim_company(stock_code),
    category_code TEXT NOT NULL REFERENCES dim_financial_statement_category(category_code),
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    segment TEXT NOT NULL DEFAULT '',
    data NUMERIC,
    date_added TIMESTAMP,
    PRIMARY KEY (stock_code, category_code, year, quarter, segment)
);

CREATE TABLE fact_financial_ratio (
    stock_code TEXT NOT NULL REFERENCES dim_company(stock_code),
    ratio_code TEXT NOT NULL REFERENCES dim_financial_ratio(ratio_code),
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    segment TEXT NOT NULL DEFAULT '',
    data NUMERIC,
    date_added TIMESTAMP,
    PRIMARY KEY (stock_code, ratio_code, year, quarter, segment)
);

CREATE TABLE fact_industry_financial_statement (
    industry_id BIGINT NOT NULL REFERENCES dim_industry(industry_id),
    category_code TEXT NOT NULL REFERENCES dim_financial_statement_category(category_code),
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    segment TEXT NOT NULL DEFAULT '',
    data NUMERIC,
    date_added TIMESTAMP,
    PRIMARY KEY (industry_id, category_code, year, quarter, segment)
);

CREATE TABLE fact_industry_financial_ratio (
    industry_id BIGINT NOT NULL REFERENCES dim_industry(industry_id),
    ratio_code TEXT NOT NULL REFERENCES dim_financial_ratio(ratio_code),
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    segment TEXT NOT NULL DEFAULT '',
    data NUMERIC,
    date_added TIMESTAMP,
    PRIMARY KEY (industry_id, ratio_code, year, quarter, segment)
);

-- =========================
-- MIGRATE DIMENSIONS
-- =========================

INSERT INTO dim_industry (industry_name)
SELECT DISTINCT industry
FROM company_info
WHERE industry IS NOT NULL;

INSERT INTO dim_exchange (exchange_name)
SELECT DISTINCT exchange
FROM company_info
WHERE exchange IS NOT NULL;

INSERT INTO dim_company (
    stock_code, company_name, short_name,
    industry_id, exchange_id,
    stock_indices, is_bank, is_securities
)
SELECT
    c.stock_code,
    c.company_name,
    c.short_name,
    i.industry_id,
    e.exchange_id,
    c.stock_indices,
    c.is_bank,
    c.is_securities
FROM company_info c
LEFT JOIN dim_industry i ON c.industry = i.industry_name
LEFT JOIN dim_exchange e ON c.exchange = e.exchange_name
WHERE c.stock_code IS NOT NULL;

INSERT INTO dim_financial_statement_category (
    category_code, category_name
)
SELECT DISTINCT category_code, category_name
FROM financial_statement_dim
WHERE category_code IS NOT NULL;

INSERT INTO dim_financial_ratio (
    ratio_code, ratio_name, function_name
)
SELECT DISTINCT ratio_code, ratio_name, function_name
FROM financial_ratio_dim
WHERE ratio_code IS NOT NULL;

INSERT INTO dim_market_index (index_name)
SELECT DISTINCT index_name
FROM (
    SELECT index_name FROM indices_daily
    UNION
    SELECT index_name FROM indices_monthly
) x
WHERE index_name IS NOT NULL;

INSERT INTO dim_commodity_indicator (
    indicator_code, indicator_name
)
SELECT DISTINCT indicator_code, indicator_name
FROM (
    SELECT indicator_code, indicator_name FROM commodities_daily
    UNION
    SELECT indicator_code, indicator_name FROM commodities_monthly
) x
WHERE indicator_code IS NOT NULL;

INSERT INTO dim_country (country_name)
SELECT DISTINCT country
FROM macro
WHERE country IS NOT NULL;

INSERT INTO dim_macro_indicator (
    indicator_name, country_id, unit
)
SELECT DISTINCT
    m.indicator_name,
    c.country_id,
    m.unit
FROM macro m
LEFT JOIN dim_country c ON m.country = c.country_name
WHERE m.indicator_name IS NOT NULL;

-- =========================
-- MIGRATE FACTS
-- =========================

INSERT INTO fact_stock_daily (
    stock_code, time, close, volume, ema20, ema50, ema200
)
SELECT
    s.stock_code,
    s.time,
    s.close,
    s.volume,
    s."EMA20",
    s."EMA50",
    s."EMA200"
FROM stock_daily s
JOIN dim_company c ON s.stock_code = c.stock_code
WHERE s.stock_code IS NOT NULL
  AND s.time IS NOT NULL;

INSERT INTO fact_stock_monthly (
    stock_code, time, close, volume, ema12, ema26
)
SELECT
    s.stock_code,
    s.time,
    s.close,
    s.volume,
    s."EMA12",
    s."EMA26"
FROM stock_monthly s
JOIN dim_company c ON s.stock_code = c.stock_code
WHERE s.stock_code IS NOT NULL
  AND s.time IS NOT NULL;

INSERT INTO fact_index_daily (
    index_id, time, close, volume, ema20, ema50, ema200
)
SELECT
    i.index_id,
    d.time,
    d.close,
    d.volume,
    d."EMA20",
    d."EMA50",
    d."EMA200"
FROM indices_daily d
JOIN dim_market_index i ON d.index_name = i.index_name
WHERE d.time IS NOT NULL;

INSERT INTO fact_index_monthly (
    index_id, time, close, volume, ema12, ema26
)
SELECT
    i.index_id,
    m.time,
    m.close,
    m.volume,
    m."EMA12",
    m."EMA26"
FROM indices_monthly m
JOIN dim_market_index i ON m.index_name = i.index_name
WHERE m.time IS NOT NULL;

INSERT INTO fact_commodity_daily (
    indicator_code, time, value, volume, ema20, ema50
)
SELECT
    d.indicator_code,
    d.time,
    d.value,
    d.volume,
    d."EMA20",
    d."EMA50"
FROM commodities_daily d
JOIN dim_commodity_indicator ci ON d.indicator_code = ci.indicator_code
WHERE d.indicator_code IS NOT NULL
  AND d.time IS NOT NULL;

INSERT INTO fact_commodity_monthly (
    indicator_code, time, value, volume, ema12, ema26
)
SELECT
    m.indicator_code,
    m.time,
    m.value,
    m.volume,
    m."EMA12",
    m."EMA26"
FROM commodities_monthly m
JOIN dim_commodity_indicator ci ON m.indicator_code = ci.indicator_code
WHERE m.indicator_code IS NOT NULL
  AND m.time IS NOT NULL;

INSERT INTO fact_macro (
    indicator_id, datetime, duration, value
)
SELECT
    mi.indicator_id,
    m.datetime,
    m.duration,
    m.value
FROM macro m
LEFT JOIN dim_country c ON m.country = c.country_name
JOIN dim_macro_indicator mi
    ON mi.indicator_name = m.indicator_name
   AND COALESCE(mi.country_id, -1) = COALESCE(c.country_id, -1)
   AND COALESCE(mi.unit, '') = COALESCE(m.unit, '')
WHERE m.indicator_name IS NOT NULL
  AND m.datetime IS NOT NULL;

INSERT INTO fact_financial_statement (
    stock_code, category_code, year, quarter, segment, data, date_added
)
SELECT
    fs.stock_code,
    fs.category_code,
    fs.year,
    fs.quarter,
    COALESCE(fs.segment, ''),
    fs.data,
    fs.date_added
FROM financial_statement fs
JOIN dim_company c ON fs.stock_code = c.stock_code
JOIN dim_financial_statement_category cat
    ON fs.category_code = cat.category_code
WHERE fs.stock_code IS NOT NULL
  AND fs.category_code IS NOT NULL
  AND fs.year IS NOT NULL
  AND fs.quarter IS NOT NULL;

INSERT INTO fact_financial_ratio (
    stock_code, ratio_code, year, quarter, segment, data, date_added
)
SELECT
    fr.stock_code,
    fr.ratio_code,
    fr.year,
    fr.quarter,
    COALESCE(fr.segment, ''),
    fr.data,
    fr.date_added
FROM financial_ratio fr
JOIN dim_company c ON fr.stock_code = c.stock_code
JOIN dim_financial_ratio r ON fr.ratio_code = r.ratio_code
WHERE fr.stock_code IS NOT NULL
  AND fr.ratio_code IS NOT NULL
  AND fr.year IS NOT NULL
  AND fr.quarter IS NOT NULL;

INSERT INTO fact_industry_financial_statement (
    industry_id, category_code, year, quarter, segment, data, date_added
)
SELECT
    i.industry_id,
    fs.category_code,
    fs.year,
    fs.quarter,
    COALESCE(fs.segment, ''),
    AVG(fs.data),
    MAX(fs.date_added)
FROM industry_financial_statement fs
JOIN company_info c ON fs.stock_code = c.stock_code
JOIN dim_industry i ON c.industry = i.industry_name
JOIN dim_financial_statement_category cat
    ON fs.category_code = cat.category_code
WHERE fs.category_code IS NOT NULL
  AND fs.year IS NOT NULL
  AND fs.quarter IS NOT NULL
GROUP BY
    i.industry_id,
    fs.category_code,
    fs.year,
    fs.quarter,
    COALESCE(fs.segment, '');

INSERT INTO fact_industry_financial_ratio (
    industry_id, ratio_code, year, quarter, segment, data, date_added
)
SELECT
    i.industry_id,
    fr.ratio_code,
    fr.year,
    fr.quarter,
    COALESCE(fr.segment, ''),
    AVG(fr.data),
    MAX(fr.date_added)
FROM industry_financial_ratio fr
JOIN company_info c ON fr.stock_code = c.stock_code
JOIN dim_industry i ON c.industry = i.industry_name
JOIN dim_financial_ratio r ON fr.ratio_code = r.ratio_code
WHERE fr.ratio_code IS NOT NULL
  AND fr.year IS NOT NULL
  AND fr.quarter IS NOT NULL
GROUP BY
    i.industry_id,
    fr.ratio_code,
    fr.year,
    fr.quarter,
    COALESCE(fr.segment, '');

-- =========================
-- BUILD DATA CATALOG
-- =========================

INSERT INTO dim_data_catalog (
    table_name,
    column_name,
    dtype,
    is_nullable,
    column_default,
    ordinal_position,
    refreshed_at
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
      cols.table_name LIKE 'dim_%'
      OR cols.table_name LIKE 'fact_%'
  );

COMMIT;