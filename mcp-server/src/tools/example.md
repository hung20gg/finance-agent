## Trong quý 3 năm 2024, chênh lệch sinh lời giữa cổ phiếu BSR (Công ty Cổ phần Lọc Hóa dầu Bình Sơn) và VNINDEX là bao nhiêu điểm phần trăm? [entity]

```sql
WITH bsr_start AS (
    SELECT close FROM fact_stock_daily
    WHERE stock_code = 'BSR'
      AND time >= '2024-07-01'::date AND time <= '2024-09-30'::date
    ORDER BY time ASC
    LIMIT 1
), bsr_end AS (
    SELECT close FROM fact_stock_daily
    WHERE stock_code = 'BSR'
      AND time >= '2024-07-01'::date AND time <= '2024-09-30'::date
    ORDER BY time DESC
    LIMIT 1
), vn_start AS (
    SELECT close FROM fact_index_daily
    WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX')
      AND time >= '2024-07-01'::date AND time <= '2024-09-30'::date
    ORDER BY time ASC
    LIMIT 1
), vn_end AS (
    SELECT close FROM fact_index_daily
    WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX')
      AND time >= '2024-07-01'::date AND time <= '2024-09-30'::date
    ORDER BY time DESC
    LIMIT 1
), bsr_ret AS (
    SELECT ((end_c.close - start_c.close) / start_c.close) * 100 AS ret
    FROM (SELECT close FROM bsr_start) start_c, (SELECT close FROM bsr_end) end_c
), vn_ret AS (
    SELECT ((end_c.close - start_c.close) / start_c.close) * 100 AS ret
    FROM (SELECT close FROM vn_start) start_c, (SELECT close FROM vn_end) end_c
)
SELECT (bsr_ret.ret - vn_ret.ret) AS diff_percentage_point
FROM bsr_ret, vn_ret;
```

## Liệt kê tỷ suất sinh lời (điểm phần trăm) theo từng quý của cổ phiếu Ngân hàng Thương mại Cổ phần Á Châu (ACB) và VN30 từ quý 3/2023 đến quý 2/2024. [tuple] (Expected columns: period_key, return_pct, benchmark_return_pct)

```sql
WITH quarters AS (
  SELECT generate_series('2023-07-01'::date, '2024-06-30'::date, interval '3 month') AS start_date
),
quarter_bounds AS (
  SELECT
    CASE EXTRACT(MONTH FROM start_date)
      WHEN 7 THEN to_char(start_date, 'YYYY') || '-Q3'
      WHEN 10 THEN to_char(start_date, 'YYYY') || '-Q4'
      WHEN 1 THEN to_char(start_date, 'YYYY') || '-Q1'
      WHEN 4 THEN to_char(start_date, 'YYYY') || '-Q2'
    END AS period_key,
    start_date,
    (start_date + interval '3 month' - interval '1 day')::date AS end_date
  FROM quarters
),
asset_prices AS (
  SELECT
    qb.period_key,
    'ACB' AS asset,
    (
      SELECT close FROM fact_stock_daily sd
      WHERE sd.stock_code = 'ACB'
        AND sd.time BETWEEN qb.start_date AND qb.end_date
      ORDER BY sd.time ASC
      LIMIT 1
    ) AS first_close,
    (
      SELECT close FROM fact_stock_daily sd
      WHERE sd.stock_code = 'ACB'
        AND sd.time BETWEEN qb.start_date AND qb.end_date
      ORDER BY sd.time DESC
      LIMIT 1
    ) AS last_close
  FROM quarter_bounds qb
  UNION ALL
  SELECT
    qb.period_key,
    'VN30' AS asset,
    (
      SELECT close FROM fact_index_daily id
      WHERE id.index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VN30')
        AND id.time BETWEEN qb.start_date AND qb.end_date
      ORDER BY id.time ASC
      LIMIT 1
    ),
    (
      SELECT close FROM fact_index_daily id
      WHERE id.index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VN30')
        AND id.time BETWEEN qb.start_date AND qb.end_date
      ORDER BY id.time DESC
      LIMIT 1
    )
  FROM quarter_bounds qb
),
returns AS (
  SELECT
    period_key,
    asset,
    ((last_close - first_close) / first_close) * 100 AS pct
  FROM asset_prices
  WHERE first_close IS NOT NULL AND last_close IS NOT NULL
)
SELECT
  r_acb.period_key,
  r_acb.pct AS return_pct,
  r_vn30.pct AS benchmark_return_pct
FROM returns r_acb
JOIN returns r_vn30 ON r_acb.period_key = r_vn30.period_key
WHERE r_acb.asset = 'ACB' AND r_vn30.asset = 'VN30'
ORDER BY r_acb.period_key;
```

## Cổ phiếu OCB (Ngân hàng Thương mại Cổ phần Phương Đông) sinh lời bao nhiêu điểm phần trăm trong tháng 5 năm 2025? [entity]

```sql
WITH start_end AS (
 SELECT
   (SELECT close::numeric FROM fact_stock_daily WHERE stock_code='OCB' AND time >= '2025-05-01' AND time <= '2025-05-31' ORDER BY time ASC LIMIT 1) AS start_close,
   (SELECT close::numeric FROM fact_stock_daily WHERE stock_code='OCB' AND time >= '2025-05-01' AND time <= '2025-05-31' ORDER BY time DESC LIMIT 1) AS end_close
)
SELECT ROUND( ( (end_close - start_close) / start_close * 100 ) , 4) AS return_pct
FROM start_end;
```

## ROE của Công ty Cổ phần Vinhomes (ngành bất động sản) trong quý 1/2024 so với quý 4/2023 chênh lệch bao nhiêu điểm phần trăm? [entity]

```sql
SELECT (q1.data - q4.data) * 100 AS diff_pp
FROM (
    SELECT data FROM fact_financial_ratio 
    WHERE stock_code = 'VHM' AND ratio_code = 'ROE' AND year = 2024 AND quarter = 1
) q1,
(
    SELECT data FROM fact_financial_ratio 
    WHERE stock_code = 'VHM' AND ratio_code = 'ROE' AND year = 2023 AND quarter = 4
) q4;
```

## Giá đóng cửa trung bình của dầu thô WTI trong quý 3 năm 2024 là bao nhiêu USD? [entity]

```sql
SELECT AVG(value) AS avg_close FROM fact_commodity_daily WHERE indicator_code = (SELECT indicator_code FROM dim_commodity_indicator WHERE indicator_name = 'Crude Oil WTI') AND time >= '2024-07-01' AND time < '2024-10-01';
```

## Doanh thu của Công ty Cổ phần Tập đoàn Công nghệ CMC trong quý 3 năm 2024 là bao nhiêu tỷ VND? [entity]

```sql
SELECT data FROM fact_financial_statement WHERE stock_code = 'CMG' AND category_code = 'IS_001' AND year = 2024 AND quarter = 3;
```

## Tỷ suất sinh lời của cổ phiếu ACL (Công ty Cổ phần Xuất nhập khẩu Thủy sản Cửu Long An Giang) trong quý 2 năm 2024 là bao nhiêu điểm phần trăm? [entity]

```sql
SELECT ((end_close - start_close) / start_close) * 100 AS return_pct FROM (
    SELECT 
        (SELECT close::numeric FROM fact_stock_daily WHERE stock_code = 'ACL' AND time = (SELECT MIN(time) FROM fact_stock_daily WHERE stock_code = 'ACL' AND time >= '2024-04-01' AND time <= '2024-06-30')) AS start_close,
        (SELECT close::numeric FROM fact_stock_daily WHERE stock_code = 'ACL' AND time = (SELECT MAX(time) FROM fact_stock_daily WHERE stock_code = 'ACL' AND time >= '2024-04-01' AND time <= '2024-06-30')) AS end_close
) sub;
```

## Mức sinh lời của mã PVC (Tổng Công ty Hóa chất và Dịch vụ Dầu khí - Công ty Cổ phần) vượt VN30 trong quý 4 năm 2023 là bao nhiêu điểm phần trăm? [entity]

```sql
SELECT 
  ((stock_end - stock_start)::numeric / stock_start * 100) -
  ((idx_end - idx_start)::numeric / idx_start * 100) AS excess_return
FROM (
  SELECT 
    (SELECT close FROM fact_stock_daily WHERE stock_code='PVC' AND time BETWEEN '2023-10-01' AND '2023-12-31' ORDER BY time ASC LIMIT 1) AS stock_start,
    (SELECT close FROM fact_stock_daily WHERE stock_code='PVC' AND time BETWEEN '2023-10-01' AND '2023-12-31' ORDER BY time DESC LIMIT 1) AS stock_end
) s,
(
  SELECT 
    (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VN30') AND time BETWEEN '2023-10-01' AND '2023-12-31' ORDER BY time ASC LIMIT 1) AS idx_start,
    (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VN30') AND time BETWEEN '2023-10-01' AND '2023-12-31' ORDER BY time DESC LIMIT 1) AS idx_end
) i;
```

## Trong quý 4 năm 2023, tỷ suất sinh lời của cổ phiếu ngân hàng NVB so với cổ phiếu công ty chứng khoán MBS là bao nhiêu điểm phần trăm? [entity]

```sql
WITH dates AS (
  SELECT stock_code,
         MIN(time) AS start_date,
         MAX(time) AS end_date
  FROM fact_stock_daily
  WHERE time BETWEEN '2023-10-01' AND '2023-12-31'
    AND stock_code IN ('NVB','MBS')
  GROUP BY stock_code
),
prices AS (
  SELECT d.stock_code,
         sd_start.close AS start_close,
         sd_end.close AS end_close,
         ((sd_end.close - sd_start.close)::numeric / sd_start.close) * 100 AS return_percent
  FROM dates d
  JOIN fact_stock_daily sd_start ON sd_start.stock_code = d.stock_code AND sd_start.time = d.start_date
  JOIN fact_stock_daily sd_end ON sd_end.stock_code = d.stock_code AND sd_end.time = d.end_date
)
SELECT (
  MAX(CASE WHEN stock_code='NVB' THEN return_percent END) -
  MAX(CASE WHEN stock_code='MBS' THEN return_percent END)
) AS diff_percent_points
FROM prices;
```

## Trong quý 4 năm 2023, tổng nợ phải trả của Công ty Cổ phần Bất động sản Thế Kỷ là bao nhiêu tỷ VND? [entity]

```sql
SELECT data FROM fact_financial_statement WHERE stock_code = 'CRE' AND category_code = 'BS_300' AND year = 2023 AND quarter = 4 ORDER BY data DESC LIMIT 1;
```

## Liệt kê mức sinh lời (điểm phần trăm) theo từng quý của cổ phiếu BMP (Công ty Cổ phần Nhựa Bình Minh) và VNINDEX từ quý 4/2023 đến quý 3/2024. [tuple] (Expected columns: period_key, return_pct, benchmark_return_pct)

```sql
WITH quarters AS (
  SELECT '2023-Q4'::text as period_key, DATE '2023-10-01' as start_date, DATE '2023-12-31' as end_date
  UNION ALL SELECT '2024-Q1', DATE '2024-01-01', DATE '2024-03-31'
  UNION ALL SELECT '2024-Q2', DATE '2024-04-01', DATE '2024-06-30'
  UNION ALL SELECT '2024-Q3', DATE '2024-07-01', DATE '2024-09-30'
),
 bmp_prices AS (
  SELECT q.period_key,
         (SELECT close FROM fact_stock_daily sd WHERE sd.stock_code='BMP' AND sd.time >= q.start_date AND sd.time <= q.end_date ORDER BY sd.time ASC LIMIT 1) AS start_close,
         (SELECT close FROM fact_stock_daily sd WHERE sd.stock_code='BMP' AND sd.time >= q.start_date AND sd.time <= q.end_date ORDER BY sd.time DESC LIMIT 1) AS end_close
  FROM quarters q
),
 vnindex_prices AS (
  SELECT q.period_key,
         (SELECT close FROM fact_index_daily id WHERE id.index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND id.time >= q.start_date AND id.time <= q.end_date ORDER BY id.time ASC LIMIT 1) AS start_close,
         (SELECT close FROM fact_index_daily id WHERE id.index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND id.time >= q.start_date AND id.time <= q.end_date ORDER BY id.time DESC LIMIT 1) AS end_close
  FROM quarters q
)
SELECT q.period_key,
       ((b.end_close - b.start_close) / b.start_close) * 100 AS return_pct,
       ((v.end_close - v.start_close) / v.start_close) * 100 AS benchmark_return_pct
FROM quarters q
JOIN bmp_prices b USING (period_key)
JOIN vnindex_prices v USING (period_key)
ORDER BY q.period_key;
```

## Trong quý 3 năm 2023, công ty nào có tỷ suất sinh lời (điểm phần trăm) cao hơn: Cổ phiếu NTP (Công ty Cổ phần Nhựa Thiếu niên Tiền Phong) hay Cổ phiếu KDH (Công ty Cổ phần Đầu tư và Kinh doanh nhà Khang Điền)? [entity]

```sql
SELECT stock_code,
       (SUM(CASE WHEN category_code='IS_100' THEN data END) / NULLIF(SUM(CASE WHEN category_code='IS_020' THEN data END),0))*100 AS profitability_pct
FROM fact_financial_statement
WHERE stock_code IN ('NTP','KDH')
  AND year=2023 AND quarter=3
GROUP BY stock_code
ORDER BY profitability_pct DESC
LIMIT 1;
```

## Trong quý 3 năm 2024, mức chênh lệch sinh lời giữa cổ phiếu của Công ty Cổ phần Đầu tư - Kinh doanh nhà (ITC) và VNINDEX là bao nhiêu điểm phần trăm? [entity]

```sql
SELECT 
  ((end_itc - start_itc)::numeric / start_itc) * 100
  - ((end_vn - start_vn)::numeric / start_vn) * 100 AS diff_percentage_point
FROM (
  SELECT 
    (SELECT close FROM fact_stock_daily WHERE stock_code='ITC' AND time >= '2024-07-01' AND time <= '2024-09-30' ORDER BY time ASC LIMIT 1) AS start_itc,
    (SELECT close FROM fact_stock_daily WHERE stock_code='ITC' AND time >= '2024-07-01' AND time <= '2024-09-30' ORDER BY time DESC LIMIT 1) AS end_itc,
    (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time >= '2024-07-01' AND time <= '2024-09-30' ORDER BY time ASC LIMIT 1) AS start_vn,
    (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time >= '2024-07-01' AND time <= '2024-09-30' ORDER BY time DESC LIMIT 1) AS end_vn
) sub;
```

## Trong ngành Dịch vụ Tài chính, mã nào có ROA cao nhất trong quý 4 năm 2023? [entity]

```sql
SELECT fr.stock_code, fr.data FROM fact_financial_ratio fr JOIN dim_company ci ON fr.stock_code = ci.stock_code JOIN dim_industry di ON ci.industry_id = di.industry_id WHERE fr.ratio_code = 'ROA' AND fr.year = 2023 AND fr.quarter = 4 AND di.industry_name = 'Financial Services' AND fr.segment <> 'industry' ORDER BY fr.data DESC LIMIT 1;
```

## Liệt kê ROE (điểm phần trăm) theo từng quý của Tập đoàn Xăng dầu Việt Nam (mã PLX) và mức trung bình của ngành Dầu khí từ quý 2/2023 đến quý 1/2024. [tuple] (Expected columns: period_key, company_ROE, industry_mean_ROE)

```sql
SELECT CONCAT(fr.year, '-Q', fr.quarter) AS period_key,
       ROUND(CAST(fr.data * 100 AS NUMERIC), 4) AS company_ROE,
       ROUND(CAST(industry_avg.industry_mean * 100 AS NUMERIC), 4) AS industry_mean_ROE
FROM fact_financial_ratio fr
JOIN dim_company ci ON fr.stock_code = ci.stock_code
LEFT JOIN (
   SELECT year, quarter, AVG(data) AS industry_mean
   FROM fact_financial_ratio fr2
   JOIN dim_company ci2 ON fr2.stock_code = ci2.stock_code
   JOIN dim_industry di2 ON ci2.industry_id = di2.industry_id
   WHERE fr2.ratio_code = 'ROE'
     AND di2.industry_name = 'Oil and Gas'
     AND fr2.segment = 'corp'
     AND (fr2.year > 2023 OR (fr2.year = 2023 AND fr2.quarter >= 2))
     AND (fr2.year < 2024 OR (fr2.year = 2024 AND fr2.quarter <= 1))
   GROUP BY year, quarter
) industry_avg
  ON fr.year = industry_avg.year AND fr.quarter = industry_avg.quarter
WHERE fr.stock_code = 'PLX'
  AND fr.ratio_code = 'ROE'
  AND fr.segment = 'corp'
  AND (fr.year > 2023 OR (fr.year = 2023 AND fr.quarter >= 2))
  AND (fr.year < 2024 OR (fr.year = 2024 AND fr.quarter <= 1))
ORDER BY fr.year, fr.quarter;
```

## Trong quý 1 năm 2024, chênh lệch sinh lời giữa cổ phiếu ELC (Công ty Cổ phần Công nghệ - Viễn thông ELCOM) và VNINDEX là bao nhiêu điểm phần trăm? [entity]

```sql
WITH sp AS (
  SELECT
    (SELECT close FROM fact_stock_daily WHERE stock_code='ELC' AND time BETWEEN '2024-01-01' AND '2024-03-31' ORDER BY time ASC LIMIT 1) AS start_price,
    (SELECT close FROM fact_stock_daily WHERE stock_code='ELC' AND time BETWEEN '2024-01-01' AND '2024-03-31' ORDER BY time DESC LIMIT 1) AS end_price
), ip AS (
  SELECT
    (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time BETWEEN '2024-01-01' AND '2024-03-31' ORDER BY time ASC LIMIT 1) AS start_price,
    (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time BETWEEN '2024-01-01' AND '2024-03-31' ORDER BY time DESC LIMIT 1) AS end_price
)
SELECT
  ((sp.end_price - sp.start_price)::numeric / sp.start_price) * 100 -
  ((ip.end_price - ip.start_price)::numeric / ip.start_price) * 100 AS diff_percentage
FROM sp, ip;
```

## Hãy liệt kê lợi nhuận sau thuế theo từng quý của Tổng Công ty Cổ phần Khoan và Dịch vụ khoan Dầu khí (mã PVD) từ quý 3/2023 đến quý 2/2024. [tuple] (Expected columns: period_key, net_income)

```sql
SELECT (year::text || '-Q' || quarter::text) AS period_key,
       data AS net_income
FROM fact_financial_statement
WHERE stock_code = 'PVD'
  AND category_code = 'IS_100'
  AND (
        (year = 2023 AND quarter >= 3)
        OR (year = 2024 AND quarter <= 2)
      )
ORDER BY year, quarter;
```

## ROE của Công ty Cổ phần Công nghệ Tiên Phòng (mã ITD) trong quý 4 năm 2023 là bao nhiêu điểm phần trăm? [entity]

```sql
SELECT ROUND(CAST(data*100 AS NUMERIC),2) AS roe_percent FROM fact_financial_ratio WHERE stock_code='ITD' AND ratio_code='ROE' AND year=2023 AND quarter=4;
```

## Giá đóng cửa trung bình của cổ phiếu CMX (Công ty Cổ phần CAMIMEX Group) trong tháng 7 năm 2023 là bao nhiêu VND? [entity]

```sql
SELECT AVG(close) * 1000 AS avg_close_vnd
FROM fact_stock_daily
WHERE stock_code = 'CMX'
  AND time >= '2023-07-01'::date
  AND time < '2023-08-01'::date;
```

## Trong quý 4 năm 2024, tiền và tương đương tiền cuối kỳ của Tổng Công ty Cổ phần Công trình Viettel là bao nhiêu tỷ [entity]

```sql
SELECT data FROM fact_financial_statement WHERE stock_code='CTR' AND category_code='CF_130' AND year=2024 AND quarter=4 LIMIT 1;
```

## Trong quý 3 năm 2023, mức chênh lệch tăng trưởng (điểm phần trăm) của cổ phiếu DPM (Tổng Công ty Phân bón và Hóa chất Dầu khí) so với VNINDEX là bao nhiêu? [entity]

```sql
WITH dpm AS (
 SELECT
   FIRST_VALUE(close) OVER (ORDER BY time ASC) AS start_price,
   FIRST_VALUE(close) OVER (ORDER BY time DESC) AS end_price
 FROM fact_stock_daily
 WHERE stock_code='DPM' AND time BETWEEN '2023-07-01' AND '2023-09-30'
 ORDER BY time
 LIMIT 1
), vn AS (
 SELECT
   FIRST_VALUE(close) OVER (ORDER BY time ASC) AS start_price,
   FIRST_VALUE(close) OVER (ORDER BY time DESC) AS end_price
 FROM fact_index_daily
 WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time BETWEEN '2023-07-01' AND '2023-09-30'
 ORDER BY time
 LIMIT 1
)
SELECT ((d.end_price - d.start_price)::numeric / d.start_price * 100) - ((v.end_price - v.start_price)::numeric / v.start_price * 100) AS growth_diff
FROM (SELECT start_price, end_price FROM dpm LIMIT 1) d,
     (SELECT start_price, end_price FROM vn LIMIT 1) v;
```

## ROA của Tổng Công ty Cổ phần Dịch vụ Kỹ thuật Dầu khí Việt Nam (PVS) trong quý 4 năm 2023 so với quý 3 năm 2023 chênh lệch bao nhiêu điểm phần trăm? [entity]

```sql
SELECT (MAX(CASE WHEN quarter = 4 THEN data END) - MAX(CASE WHEN quarter = 3 THEN data END)) * 100 AS diff_pp
FROM fact_financial_ratio
WHERE stock_code = 'PVS'
  AND ratio_code = 'ROA'
  AND year = 2023
```

## Công ty Cổ phần Lizen (LCG) có bao nhiêu tỷ VND tiền và tương đương tiền vào cuối quý 2 năm 2023? [entity]

```sql
SELECT data FROM fact_financial_statement WHERE stock_code = 'LCG' AND category_code = 'BS_110' AND year = 2023 AND quarter = 2 LIMIT 1
```

## Bạn có thể liệt kê lợi nhuận sau thuế theo từng quý của Công ty Cổ phần Lizen (LCG) từ quý 3/2023 đến quý 2/2024 không? [tuple] (Expected columns: period_key, net_income)

```sql
SELECT CONCAT(year::text, '-Q', quarter::text) AS period_key, data AS net_income FROM fact_financial_statement WHERE stock_code='LCG' AND category_code='IS_100' AND (year = 2023 AND quarter >= 3 OR year = 2024 AND quarter <= 2) ORDER BY year, quarter;
```

## ROE của Tổng Công ty Khí Việt Nam (GAS) trong quý 2/2024 so với quý 1/2024 chênh lệch bao nhiêu điểm phần trăm? [entity]

```sql
WITH roes AS (
  SELECT quarter, data
  FROM fact_financial_ratio
  WHERE stock_code = 'GAS' AND ratio_code = 'ROE' AND year = 2024 AND quarter IN (1,2)
)
SELECT ROUND(CAST((MAX(CASE WHEN quarter = 2 THEN data END) - MAX(CASE WHEN quarter = 1 THEN data END)) * 100 AS NUMERIC), 4) AS diff_percentage_points
FROM roes;
```

## Trong quý 3 năm 2024, mức chênh lệch tăng trưởng (điểm phần trăm) của cổ phiếu Ngân hàng Thương mại Cổ phần Việt Nam Thịnh Vượng so với VN30 là bao nhiêu? [entity]

```sql
WITH stock_prices AS (
  SELECT
    FIRST_VALUE(close) OVER (ORDER BY time ASC) AS start_close,
    FIRST_VALUE(close) OVER (ORDER BY time DESC) AS end_close
  FROM fact_stock_daily
  WHERE stock_code = 'VPB'
    AND time >= '2024-07-01'::date
    AND time <= '2024-09-30'::date
  ORDER BY time
  LIMIT 1
), index_prices AS (
  SELECT
    FIRST_VALUE(close) OVER (ORDER BY time ASC) AS start_close,
    FIRST_VALUE(close) OVER (ORDER BY time DESC) AS end_close
  FROM fact_index_daily
  WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VN30')
    AND time >= '2024-07-01'::date
    AND time <= '2024-09-30'::date
  ORDER BY time
  LIMIT 1
)
SELECT
  ((sp.end_close - sp.start_close) / sp.start_close * 100) -
  ((ip.end_close - ip.start_close) / ip.start_close * 100) AS growth_diff_pp
FROM stock_prices sp, index_prices ip;
```

## Liệt kê tỷ suất sinh lời (điểm phần trăm) theo từng quý của mã cổ phiếu NLG (Công ty Cổ phần Đầu tư Nam Long) và VNINDEX từ quý 3/2023 đến quý 2/2024. [tuple] (Expected columns: period_key, return_pct, benchmark_return_pct)

```sql
WITH stock_q AS (
  SELECT 
    to_char(date_trunc('quarter', time), 'YYYY') || '-Q' || extract(quarter FROM time) AS period_key,
    MIN(time) AS start_date,
    MAX(time) AS end_date
  FROM fact_stock_daily
  WHERE stock_code = 'NLG'
    AND time >= DATE '2023-07-01'
    AND time < DATE '2024-07-01'
  GROUP BY 1
), stock_prices AS (
  SELECT 
    q.period_key,
    s_start.close AS start_close,
    s_end.close AS end_close
  FROM stock_q q
  JOIN fact_stock_daily s_start ON s_start.stock_code = 'NLG' AND s_start.time = q.start_date
  JOIN fact_stock_daily s_end ON s_end.stock_code = 'NLG' AND s_end.time = q.end_date
), index_q AS (
  SELECT 
    to_char(date_trunc('quarter', time), 'YYYY') || '-Q' || extract(quarter FROM time) AS period_key,
    MIN(time) AS start_date,
    MAX(time) AS end_date
  FROM fact_index_daily
  WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX')
    AND time >= DATE '2023-07-01'
    AND time < DATE '2024-07-01'
  GROUP BY 1
), index_prices AS (
  SELECT 
    q.period_key,
    i_start.close AS start_close,
    i_end.close AS end_close
  FROM index_q q
  JOIN fact_index_daily i_start ON i_start.index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND i_start.time = q.start_date
  JOIN fact_index_daily i_end ON i_end.index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND i_end.time = q.end_date
)
SELECT 
  s.period_key AS period_key,
  (s.end_close - s.start_close) / s.start_close * 100 AS return_pct,
  (i.end_close - i.start_close) / i.start_close * 100 AS benchmark_return_pct
FROM stock_prices s
JOIN index_prices i USING (period_key)
ORDER BY period_key;
```

## Roe của Ngân hàng Thương mại Cổ phần Việt Nam Thịnh Vượng (VPB) trong quý 3 năm 2023 so với quý 2 năm 2023 chênh lệch bao nhiêu điểm phần trăm? [entity]

```sql
SELECT (MAX(CASE WHEN quarter = 3 THEN data END) - MAX(CASE WHEN quarter = 2 THEN data END)) * 100 AS diff_pp
FROM fact_financial_ratio
WHERE stock_code = 'VPB' AND ratio_code = 'ROE' AND year = 2023 AND quarter IN (2,3);
```

## Tỷ suất lợi nhuận trên vốn (ROE) của Công ty Cổ phần Tập đoàn Xây dựng Hòa Bình (mã HBC) trong quý 3 năm 2024 so với quý 2 năm 2024 chênh lệch bao nhiêu điểm phần trăm? [entity]

```sql
SELECT (MAX(CASE WHEN year=2024 AND quarter=3 THEN data END) - MAX(CASE WHEN year=2024 AND quarter=2 THEN data END)) * 100 AS diff_percent_points FROM fact_financial_ratio WHERE stock_code='HBC' AND ratio_code='ROE' AND year=2024 AND quarter IN (2,3);
```

## Giá đóng cửa trung bình của cổ phiếu Tổng Công ty Điện lực Dầu khí Việt Nam (POW) trong tháng 5 năm 2025 là bao nhiêu VND? [entity]

```sql
SELECT AVG(close) * 1000 AS avg_close_vnd FROM fact_stock_daily WHERE stock_code = 'POW' AND time >= '2025-05-01' AND time < '2025-06-01';
```

## Theo dữ liệu mới nhất có sẵn, liệt kê ROA (điểm phần trăm) theo từng quý của Ngân hàng Thương mại Cổ phần Kiên Long (KLB) từ quý 2/2024 đến quý 1/2025. [tuple] (Expected columns: period_key, ROA)

```sql
SELECT (year::text || '-Q' || quarter) AS period_key,
       data * 100 AS ROA
FROM fact_financial_ratio
WHERE stock_code = 'KLB' AND ratio_code = 'ROA'
  AND (year > 2024 OR (year = 2024 AND quarter >= 2))
  AND (year < 2025 OR (year = 2025 AND quarter <= 1))
ORDER BY year, quarter
```

## Trong lĩnh vực ngân hàng, mã chứng khoán nào có lợi nhuận sau thuế cao nhất trong quý 3 năm 2024? [entity]

```sql
SELECT fs.stock_code, fs.data AS net_profit
FROM fact_financial_statement fs
JOIN dim_company ci ON fs.stock_code = ci.stock_code
WHERE ci.is_bank = true
  AND fs.category_code = 'IS_100'
  AND fs.year = 2024
  AND fs.quarter = 3
ORDER BY fs.data DESC
LIMIT 1;
```

## Trong quý đầu năm 2025, chênh lệch sinh lời giữa cổ phiếu của Công ty Cổ phần Đầu tư và Phát triển Bất động sản An Gia (AGG) và VNINDEX là bao nhiêu điểm %? [entity]

```sql
WITH agg AS (
  SELECT (last_c - first_c) / first_c * 100 AS ret
  FROM (
    SELECT close AS first_c
    FROM fact_stock_daily
    WHERE stock_code='AGG' AND time BETWEEN '2025-01-01' AND '2025-03-31'
    ORDER BY time ASC LIMIT 1
  ) f
  CROSS JOIN (
    SELECT close AS last_c
    FROM fact_stock_daily
    WHERE stock_code='AGG' AND time BETWEEN '2025-01-01' AND '2025-03-31'
    ORDER BY time DESC LIMIT 1
  ) l
),
vni AS (
  SELECT (last_c - first_c) / first_c * 100 AS ret
  FROM (
    SELECT close AS first_c
    FROM fact_index_daily
    WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time BETWEEN '2025-01-01' AND '2025-03-31'
    ORDER BY time ASC LIMIT 1
  ) f
  CROSS JOIN (
    SELECT close AS last_c
    FROM fact_index_daily
    WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time BETWEEN '2025-01-01' AND '2025-03-31'
    ORDER BY time DESC LIMIT 1
  ) l
)
SELECT (agg.ret - vni.ret) AS diff_pct
FROM agg, vni;
```

## Công ty Cổ phần Nam Việt (ANV) trong quý 1 năm 2025 so với quý 4 năm 2024, ROA thay đổi bao nhiêu điểm phần trăm? [entity]

```sql
WITH q1 AS (
  SELECT data FROM fact_financial_ratio
  WHERE stock_code = 'ANV' AND ratio_code = 'ROA' AND year = 2025 AND quarter = 1
  ORDER BY date_added DESC LIMIT 1
), q4 AS (
  SELECT data FROM fact_financial_ratio
  WHERE stock_code = 'ANV' AND ratio_code = 'ROA' AND year = 2024 AND quarter = 4
  ORDER BY date_added DESC LIMIT 1
)
SELECT (q1.data - q4.data) * 100 AS roa_change_pp
FROM q1, q4;
```

## Cổ phiếu của Công ty Cổ phần Supe Phốt phát và Hóa chất Lâm Thao (LAS) trong tháng 9 năm 2023 có tỷ suất sinh lời bao nhiêu điểm phần trăm? [entity]

```sql
SELECT
  ( (SELECT close FROM fact_stock_daily WHERE stock_code='LAS' AND time BETWEEN '2023-09-01' AND '2023-09-30' ORDER BY time DESC LIMIT 1) -
    (SELECT close FROM fact_stock_daily WHERE stock_code='LAS' AND time BETWEEN '2023-09-01' AND '2023-09-30' ORDER BY time ASC LIMIT 1)
  )::numeric /
  (SELECT close FROM fact_stock_daily WHERE stock_code='LAS' AND time BETWEEN '2023-09-01' AND '2023-09-30' ORDER BY time ASC LIMIT 1) * 100
  AS return_pct;
```

## Liệt kê tỷ suất sinh lời (điểm phần trăm) theo từng quý của mã cổ phiếu BAF (Công ty Cổ phần Nông nghiệp BAF Việt Nam) và VNINDEX từ quý 3/2023 đến quý 2/2024. [tuple] (Expected columns: period_key, return_pct, benchmark_return_pct)

```sql
WITH quarters AS (
  SELECT generate_series('2023-07-01'::date, '2024-04-01'::date, interval '3 month') AS start_date
), period AS (
  SELECT start_date,
         (start_date + interval '3 month' - interval '1 day')::date AS end_date,
         to_char(start_date, 'YYYY') || '-Q' ||
         CASE WHEN extract(month from start_date) in (1,2,3) THEN '1'
              WHEN extract(month from start_date) in (4,5,6) THEN '2'
              WHEN extract(month from start_date) in (7,8,9) THEN '3'
              ELSE '4' END AS period_key
  FROM quarters
)
SELECT p.period_key,
       100.0 * (s_end.close - s_start.close) / s_start.close AS return_pct,
       100.0 * (i_end.close - i_start.close) / i_start.close AS benchmark_return_pct
FROM period p
JOIN LATERAL (
   SELECT close FROM fact_stock_daily
   WHERE stock_code = 'BAF' AND time >= p.start_date AND time <= p.end_date
   ORDER BY time ASC LIMIT 1
) s_start ON true
JOIN LATERAL (
   SELECT close FROM fact_stock_daily
   WHERE stock_code = 'BAF' AND time >= p.start_date AND time <= p.end_date
   ORDER BY time DESC LIMIT 1
) s_end ON true
JOIN LATERAL (
   SELECT close FROM fact_index_daily
   WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time >= p.start_date AND time <= p.end_date
   ORDER BY time ASC LIMIT 1
) i_start ON true
JOIN LATERAL (
   SELECT close FROM fact_index_daily
   WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time >= p.start_date AND time <= p.end_date
   ORDER BY time DESC LIMIT 1
) i_end ON true
ORDER BY p.start_date;
```

## Liệt kê tỷ suất sinh lời (điểm phần trăm) theo từng quý của mã cổ phiếu DRI (Công ty Cổ phần Đầu tư Cao su Đắk Lắk) từ quý 1/2024 đến quý 4/2024. [tuple] (Expected columns: period_key, return_pct)

```sql
WITH d AS (
  SELECT time, close,
         to_char(time, 'YYYY-"Q"Q') AS period_key
  FROM fact_stock_daily
  WHERE stock_code = 'DRI'
    AND time >= '2024-01-01'::date
    AND time <= '2024-12-31'::date
),
agg AS (
  SELECT period_key,
         first_value(close) OVER (PARTITION BY period_key ORDER BY time ASC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS start_close,
         first_value(close) OVER (PARTITION BY period_key ORDER BY time DESC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING) AS end_close
  FROM d
)
SELECT DISTINCT period_key,
       ((end_close - start_close) / start_close) * 100 AS return_pct
FROM agg
WHERE period_key IN ('2024-Q1','2024-Q2','2024-Q3','2024-Q4')
ORDER BY period_key;
```

## Hãy liệt kê lợi nhuận sau thuế theo từng quý của Công ty Cổ phần Nam Việt (mã ANV) từ quý 2 năm 2023 đến quý 1 năm 2024. [tuple] (Expected columns: period_key, net_income)

```sql
SELECT CONCAT(year, '-Q', quarter) AS period_key,
       data AS net_income
FROM fact_financial_statement
WHERE stock_code = 'ANV'
  AND category_code = 'IS_100'
  AND ((year = 2023 AND quarter >= 2) OR (year = 2024 AND quarter <= 1))
ORDER BY year, quarter
LIMIT 20;
```

## Trong quý 4 năm 2024, chênh lệch sinh lời giữa cổ phiếu ngân hàng An Bình (ABB) và VNINDEX là bao nhiêu điểm %? [entity]

```sql
WITH 
  stock_start AS (
    SELECT close FROM fact_stock_daily 
    WHERE stock_code = 'ABB' 
      AND time BETWEEN '2024-10-01'::date AND '2024-12-31'::date
    ORDER BY time ASC LIMIT 1
  ),
  stock_end AS (
    SELECT close FROM fact_stock_daily 
    WHERE stock_code = 'ABB' 
      AND time BETWEEN '2024-10-01'::date AND '2024-12-31'::date
    ORDER BY time DESC LIMIT 1
  ),
  index_start AS (
    SELECT close FROM fact_index_daily 
    WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') 
      AND time BETWEEN '2024-10-01'::date AND '2024-12-31'::date
    ORDER BY time ASC LIMIT 1
  ),
  index_end AS (
    SELECT close FROM fact_index_daily 
    WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') 
      AND time BETWEEN '2024-10-01'::date AND '2024-12-31'::date
    ORDER BY time DESC LIMIT 1
  )
SELECT 
  ROUND(
    CAST(
      (CAST((se.close - ss.close) AS numeric) / ss.close) * 100 
      - (CAST((ie.close - is_.close) AS numeric) / is_.close) * 100
    AS numeric),
    4
  ) AS diff_percent
FROM stock_start ss, stock_end se, index_start is_, index_end ie;
```

## Trong quý 1 năm 2025, tỉ lệ lợi nhuận trên tài sản (ROA) của Công ty Cổ phần CAMIMEX Group là bao nhiêu điểm phần trăm? [entity]

```sql
SELECT (data * 100) AS roa_percent
FROM fact_financial_ratio
WHERE stock_code = 'CMX'
  AND ratio_code = 'ROA'
  AND year = 2025
  AND quarter = 1
ORDER BY date_added DESC
LIMIT 1;
```

## Trong quý 1 năm 2025, giá đóng cửa trung bình của Công ty Cổ phần Đầu tư Phát triển Thành Đạt là bao nhiêu VND? [entity]

```sql
SELECT (AVG(close) * 1000)::numeric AS avg_close_vnd
FROM fact_stock_daily
WHERE stock_code = 'DTD'
  AND time >= DATE '2025-01-01'
  AND time <= DATE '2025-03-31';
```

## Trong quý 3 năm 2024, ROA của Công ty Cổ phần Vincom Retail (VRE) là bao nhiêu điểm phần trăm? [entity]

```sql
SELECT data FROM fact_financial_ratio WHERE stock_code='VRE' AND ratio_code='ROA' AND year=2024 AND quarter=3 LIMIT 1
```

## Trong quý 1 năm 2025, mức chênh lệch sinh lời giữa cổ phiếu LBM (công ty Cổ phần Khoáng sản và Vật liệu xây dựng Lâm Đồng) và VNINDEX là bao nhiêu điểm %? [entity]

```sql
WITH lbm AS (
  SELECT ((last_c - first_c) / first_c * 100) AS ret
  FROM (
    SELECT close AS first_c
    FROM fact_stock_daily
    WHERE stock_code='LBM' AND time >= '2025-01-01' AND time <= '2025-03-31'
    ORDER BY time ASC
    LIMIT 1
  ) s,
  (
    SELECT close AS last_c
    FROM fact_stock_daily
    WHERE stock_code='LBM' AND time >= '2025-01-01' AND time <= '2025-03-31'
    ORDER BY time DESC
    LIMIT 1
  ) e
),
vni AS (
  SELECT ((last_c - first_c) / first_c * 100) AS ret
  FROM (
    SELECT close AS first_c
    FROM fact_index_daily
    WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time >= '2025-01-01' AND time <= '2025-03-31'
    ORDER BY time ASC
    LIMIT 1
  ) s,
  (
    SELECT close AS last_c
    FROM fact_index_daily
    WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time >= '2025-01-01' AND time <= '2025-03-31'
    ORDER BY time DESC
    LIMIT 1
  ) e
)
SELECT (lbm.ret - vni.ret) AS difference_percentage_point
FROM lbm, vni;
```

## Trong quý 2 năm 2023, ROE của Công ty Cổ phần Dược phẩm Hà Tây (DHT) là bao nhiêu điểm phần trăm [entity]

```sql
SELECT data * 100 AS roe_percent FROM fact_financial_ratio WHERE stock_code = 'DHT' AND ratio_code = 'ROE' AND year = 2023 AND quarter = 2 LIMIT 1;
```

## Doanh thu của Tổng Công ty Cổ phần Công trình Viettel (mã CTR) trong quý 2 năm 2024 là bao nhiêu tỷ VND? [entity]

```sql
SELECT data AS revenue FROM fact_financial_statement WHERE stock_code = 'CTR' AND category_code = 'IS_001' AND year = 2024 AND quarter = 2;
```

## Trong quý 4 năm 2024, tỷ suất sinh lời của cổ phiếu Công ty Cổ phần Công nghệ - Viễn thông ELCOM so với cổ phiếu Công ty Cổ phần Xây dựng Coteccons chênh lệch bao nhiêu điểm phần trăm? [entity]

```sql
WITH elc AS (
  SELECT
    (SELECT close FROM fact_stock_daily WHERE stock_code='ELC' AND time BETWEEN '2024-10-01' AND '2024-12-31' ORDER BY time ASC LIMIT 1) AS start_close,
    (SELECT close FROM fact_stock_daily WHERE stock_code='ELC' AND time BETWEEN '2024-10-01' AND '2024-12-31' ORDER BY time DESC LIMIT 1) AS end_close
),
ctd AS (
  SELECT
    (SELECT close FROM fact_stock_daily WHERE stock_code='CTD' AND time BETWEEN '2024-10-01' AND '2024-12-31' ORDER BY time ASC LIMIT 1) AS start_close,
    (SELECT close FROM fact_stock_daily WHERE stock_code='CTD' AND time BETWEEN '2024-10-01' AND '2024-12-31' ORDER BY time DESC LIMIT 1) AS end_close
)
SELECT ( (elc.end_close - elc.start_close) / elc.start_close * 100 ) -
       ( (ctd.end_close - ctd.start_close) / ctd.start_close * 100 ) AS diff_pct
FROM elc, ctd;
```

## Trong quý 1 năm 2024, ROA của Công ty Cổ phần Tập đoàn C.E.O là bao nhiêu điểm phần trăm? [entity]

```sql
SELECT (data * 100) AS roa_percent FROM fact_financial_ratio WHERE stock_code = 'CEO' AND ratio_code = 'ROA' AND year = 2024 AND quarter = 1 ORDER BY date_added DESC LIMIT 1;
```

## Liệt kê tỷ suất sinh lời (điểm phần trăm) theo từng quý của mã cổ phiếu Ngân hàng Thương mại Cổ phần Quốc Dân (NVB) từ quý 4 năm 2023 đến quý 3 năm 2024. [tuple] (Expected columns: period_key, return_pct)

```sql
WITH data AS (
  SELECT
    to_char(time, 'YYYY-"Q"Q') as period_key,
    time,
    close
  FROM fact_stock_daily
  WHERE stock_code='NVB'
    AND time >= '2023-10-01'::date
    AND time < '2024-10-01'::date
),
first_close AS (
  SELECT DISTINCT ON (period_key) period_key, close as first_close
  FROM data
  ORDER BY period_key, time ASC
),
last_close AS (
  SELECT DISTINCT ON (period_key) period_key, close as last_close
  FROM data
  ORDER BY period_key, time DESC
)
SELECT f.period_key,
       (l.last_close - f.first_close)::numeric / f.first_close * 100 as return_pct
FROM first_close f
JOIN last_close l USING (period_key)
WHERE f.period_key BETWEEN '2023-Q4' AND '2024-Q3'
ORDER BY f.period_key;
```

## Trong quý 3 năm 2023, ROE của Ngân hàng Thương mại Cổ phần Phương Đông so với Công ty Cổ phần Nam Việt chênh bao nhiêu điểm phần trăm? [entity]

```sql
WITH roe_vals AS (
    SELECT stock_code, data AS roe
    FROM fact_financial_ratio
    WHERE ratio_code = 'ROE' AND year = 2023 AND quarter = 3 AND stock_code IN ('OCB','ANV')
)
SELECT (MAX(CASE WHEN stock_code = 'OCB' THEN roe END) - MAX(CASE WHEN stock_code = 'ANV' THEN roe END)) * 100 AS diff_percentage_points
FROM roe_vals;
```

## Tỷ suất sinh lời của cổ phiếu Công ty Cổ phần Đầu tư và Xây dựng số 18 trong quý 4 năm 2024 là bao nhiêu phần trăm? [entity]

```sql
WITH price_range AS (
    SELECT 
        MIN(time) AS start_date,
        MAX(time) AS end_date
    FROM fact_stock_daily
    WHERE stock_code = 'L18'
      AND to_char(time, 'YYYY"-Q"Q') = '2024-Q4'
), start_price AS (
    SELECT close AS start_close
    FROM fact_stock_daily, price_range
    WHERE stock_code = 'L18'
      AND time = price_range.start_date
), end_price AS (
    SELECT close AS end_close
    FROM fact_stock_daily, price_range
    WHERE stock_code = 'L18'
      AND time = price_range.end_date
)
SELECT ((end_price.end_close - start_price.start_close) / start_price.start_close) * 100 AS return_percent
FROM start_price, end_price;
```

## Bạn có thể liệt kê tỷ suất sinh lời (điểm phần trăm) theo từng quý cho mã cổ phiếu NHA (Tổng Công ty Đầu tư Phát triển Nhà và Đô thị Nam Hà Nội) và VNINDEX từ quý 4/2023 đến quý 3/2024 không? [tuple] (Expected columns: period_key, return_pct, benchmark_return_pct)

```sql
WITH periods AS (
  SELECT 
    generate_series('2023-10-01'::date, '2024-07-01'::date, interval '3 month') AS start_date
),
stock_ret AS (
  SELECT 
    to_char(p.start_date, 'YYYY-"Q"Q') AS period_key,
    ((s_end.close - s_start.close) / s_start.close) * 100 AS return_pct
  FROM periods p
  JOIN LATERAL (
    SELECT close FROM fact_stock_daily 
    WHERE stock_code='NHA' 
      AND time >= p.start_date 
      AND time < p.start_date + interval '3 month'
    ORDER BY time ASC LIMIT 1
  ) s_start ON true
  JOIN LATERAL (
    SELECT close FROM fact_stock_daily 
    WHERE stock_code='NHA' 
      AND time >= p.start_date 
      AND time < p.start_date + interval '3 month'
    ORDER BY time DESC LIMIT 1
  ) s_end ON true
),
index_ret AS (
  SELECT 
    to_char(p.start_date, 'YYYY-"Q"Q') AS period_key,
    ((i_end.close - i_start.close) / i_start.close) * 100 AS benchmark_return_pct
  FROM periods p
  JOIN LATERAL (
    SELECT close FROM fact_index_daily 
    WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') 
      AND time >= p.start_date 
      AND time < p.start_date + interval '3 month'
    ORDER BY time ASC LIMIT 1
  ) i_start ON true
  JOIN LATERAL (
    SELECT close FROM fact_index_daily 
    WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') 
      AND time >= p.start_date 
      AND time < p.start_date + interval '3 month'
    ORDER BY time DESC LIMIT 1
  ) i_end ON true
)
SELECT s.period_key, s.return_pct, i.benchmark_return_pct
FROM stock_ret s
JOIN index_ret i USING (period_key)
ORDER BY s.period_key;
```

## Trong quý 2 năm 2024, mức chênh lệch tăng trưởng (điểm phần trăm) của cổ phiếu L18 (Công ty Cổ phần Đầu tư và Xây dựng số 18) so với VNINDEX là bao nhiêu, và nó có outperform hay underperform? [entity]

```sql
WITH stock_prices AS (
    SELECT
        (SELECT close FROM fact_stock_daily WHERE stock_code='L18' AND time BETWEEN '2024-04-01' AND '2024-06-30' ORDER BY time ASC LIMIT 1) AS start_close,
        (SELECT close FROM fact_stock_daily WHERE stock_code='L18' AND time BETWEEN '2024-04-01' AND '2024-06-30' ORDER BY time DESC LIMIT 1) AS end_close
),
index_prices AS (
    SELECT
        (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time BETWEEN '2024-04-01' AND '2024-06-30' ORDER BY time ASC LIMIT 1) AS start_close,
        (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time BETWEEN '2024-04-01' AND '2024-06-30' ORDER BY time DESC LIMIT 1) AS end_close
),
calc AS (
    SELECT
        (sp.end_close - sp.start_close) / sp.start_close * 100 AS stock_growth,
        (ip.end_close - ip.start_close) / ip.start_close * 100 AS index_growth
    FROM stock_prices sp, index_prices ip
)
SELECT
    (stock_growth - index_growth) AS growth_diff
FROM calc;
```

## Giá đóng cửa trung bình của nước ép cam trong tháng 9 năm 2023 là bao nhiêu USD? [entity]

```sql
SELECT AVG(value) AS avg_close_price_usd
FROM fact_commodity_daily
WHERE indicator_code = (SELECT indicator_code FROM dim_commodity_indicator WHERE indicator_name = 'Orange Juice')
  AND time >= '2023-09-01'::date
  AND time <= '2023-09-30'::date;
```

## Giá đóng cửa trung bình của cổ phiếu Công ty Cổ phần Thế Giới Số (DGW) trong tháng 3 năm 2025 là bao nhiêu VND? [entity]

```sql
SELECT ROUND(CAST(AVG(close) * 1000 AS NUMERIC), 2) AS avg_close_vnd
FROM fact_stock_daily
WHERE stock_code = 'DGW'
  AND time >= '2025-03-01'::date
  AND time < '2025-04-01'::date;
```

## Liệt kê lợi nhuận sau thuế theo từng quý của Công ty Cổ phần SAM Holdings từ quý 2 năm 2024 đến quý 1 năm 2025. [tuple] (Expected columns: period_key, net_income)

```sql
SELECT (year::text || '-Q' || quarter::text) AS period_key, data AS net_income FROM fact_financial_statement WHERE stock_code = 'SAM' AND category_code = 'IS_100' AND ((year = 2024 AND quarter >= 2) OR (year = 2025 AND quarter <= 1)) ORDER BY year, quarter;
```

## Giá đóng cửa trung bình của cổ phiếu GEE (Công ty Cổ phần Điện lực Gelex) trong tháng 2 năm 2024 là bao nhiêu V [entity]

```sql
SELECT AVG(close) * 1000 AS avg_close
FROM fact_stock_daily
WHERE stock_code = 'GEE'
  AND time >= '2024-02-01'::date
  AND time < '2024-03-01'::date;
```

## Trong quý 4 năm 2023, chênh lệch tăng trưởng (điểm phần trăm) của cổ phiếu KDH (Công ty Cổ phần Đầu tư và Kinh doanh nhà Khang Điền) so với VN‑INDEX là bao nhiêu? [entity]

```sql
WITH stock_start AS (
  SELECT close AS start_close
  FROM fact_stock_daily
  WHERE stock_code = 'KDH'
    AND time BETWEEN '2023-10-01' AND '2023-12-31'
  ORDER BY time ASC
  LIMIT 1
),
stock_end AS (
  SELECT close AS end_close
  FROM fact_stock_daily
  WHERE stock_code = 'KDH'
    AND time BETWEEN '2023-10-01' AND '2023-12-31'
  ORDER BY time DESC
  LIMIT 1
),
index_start AS (
  SELECT close AS start_close
  FROM fact_index_daily
  WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX')
    AND time BETWEEN '2023-10-01' AND '2023-12-31'
  ORDER BY time ASC
  LIMIT 1
),
index_end AS (
  SELECT close AS end_close
  FROM fact_index_daily
  WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX')
    AND time BETWEEN '2023-10-01' AND '2023-12-31'
  ORDER BY time DESC
  LIMIT 1
)
SELECT 
  ((stock_end.end_close - stock_start.start_close)::numeric / stock_start.start_close) * 100 AS stock_growth,
  ((index_end.end_close - index_start.start_close)::numeric / index_start.start_close) * 100 AS index_growth,
  (((stock_end.end_close - stock_start.start_close)::numeric / stock_start.start_close) * 100) - (((index_end.end_close - index_start.start_close)::numeric / index_start.start_close) * 100) AS growth_diff
FROM stock_start, stock_end, index_start, index_end;
```

## Liệt kê tỷ suất sinh lời (điểm phần trăm) theo từng quý của mã cổ phiếu HDC (Công ty Cổ phần Phát triển Nhà Bà Rịa Vũng Tàu) từ 2024‑Q1 đến 2024‑Q4. [tuple] (Expected columns: period_key, return_pct)

```sql
WITH q AS (
  SELECT '2024-Q1' AS period_key, DATE '2024-01-01' AS start_date, DATE '2024-03-31' AS end_date
  UNION ALL SELECT '2024-Q2', DATE '2024-04-01', DATE '2024-06-30'
  UNION ALL SELECT '2024-Q3', DATE '2024-07-01', DATE '2024-09-30'
  UNION ALL SELECT '2024-Q4', DATE '2024-10-01', DATE '2024-12-31'
),
start_prices AS (
  SELECT q.period_key, sd.close AS start_close
  FROM q
  JOIN LATERAL (
    SELECT close
    FROM fact_stock_daily
    WHERE stock_code = 'HDC' AND time >= q.start_date AND time <= q.end_date
    ORDER BY time ASC
    LIMIT 1
  ) sd ON true
),
end_prices AS (
  SELECT q.period_key, sd.close AS end_close
  FROM q
  JOIN LATERAL (
    SELECT close
    FROM fact_stock_daily
    WHERE stock_code = 'HDC' AND time >= q.start_date AND time <= q.end_date
    ORDER BY time DESC
    LIMIT 1
  ) sd ON true
)
SELECT s.period_key,
       ((e.end_close - s.start_close)::numeric / s.start_close) * 100 AS return_pct
FROM start_prices s
JOIN end_prices e USING (period_key)
ORDER BY s.period_key;
```

## Vào quý II năm 2023, tiền và tương đương tiền cuối kỳ của Công ty Cổ phần Lọc Hóa dầu Bình Sơn (BSR) là bao nhiêu tỷ [entity]

```sql
SELECT data FROM fact_financial_statement WHERE stock_code = 'BSR' AND category_code = 'BS_110' AND year = 2023 AND quarter = 2
```

## Trong quý 2 năm 2024, giá đóng cửa trung bình của Công ty Cổ phần Tập đoàn Đạt Phương là bao nhiêu VND? [entity]

```sql
SELECT ROUND(AVG(close) * 1000)::bigint AS avg_close_vnd
FROM fact_stock_daily
WHERE stock_code = 'DPG'
  AND time >= '2024-04-01'::date
  AND time <= '2024-06-30'::date;
```

## Tỷ suất sinh lời của cổ phiếu Công ty Cổ phần Cảng Cát Lái (CLL) trong tháng 12 năm 2023 là bao nhiêu phần trăm? [entity]

```sql
WITH start_price AS (
  SELECT close FROM fact_stock_daily
  WHERE stock_code='CLL' AND time >= '2023-12-01' AND time < '2024-01-01'
  ORDER BY time ASC LIMIT 1
),
end_price AS (
  SELECT close FROM fact_stock_daily
  WHERE stock_code='CLL' AND time >= '2023-12-01' AND time < '2024-01-01'
  ORDER BY time DESC LIMIT 1
)
SELECT ROUND(((end_price.close - start_price.close)::numeric / start_price.close::numeric) * 100, 4) AS return_pct
FROM start_price, end_price;
```

## Giá đóng cửa trung bình của cổ phiếu Ngân hàng Thương mại Cổ phần Nam Á (NAB) trong tháng 3 năm 2025 là bao nhiêu VND? [entity]

```sql
SELECT AVG(close) * 1000 AS avg_close_vnd
FROM fact_stock_daily
WHERE stock_code = 'NAB'
  AND time >= DATE '2025-03-01' AND time < DATE '2025-04-01';
```

## ROA của Công ty Cổ phần Chứng khoán SSI trong quý 2 năm 2024 so với quý 1 năm 2024 chênh lệch bao nhiêu điểm phần trăm? [entity]

```sql
SELECT quarter, data FROM fact_financial_ratio WHERE stock_code='SSI' AND ratio_code='ROA' AND year=2024 AND quarter IN (1,2) ORDER BY quarter;
```

## Hãy liệt kê doanh thu hàng quý của Ngân hàng Thương mại Cổ phần Quân đội (MBB) từ quý 2 năm 2024 đến quý 1 năm 2025. [tuple] (Expected columns: period_key, revenue)

```sql
SELECT CONCAT(year, '-Q', quarter) AS period_key, data AS revenue FROM fact_financial_statement WHERE stock_code = 'MBB' AND category_code = 'IS_020' AND ((year = 2024 AND quarter >= 2) OR (year = 2025 AND quarter <= 1)) ORDER BY year, quarter
```

## Trong quý 4 năm 2024, ROA của Tổng Công ty Khí Việt Nam (công ty GAS) là bao nhiêu điểm phần trăm? [entity]

```sql
SELECT (data * 100) AS roa_percent FROM fact_financial_ratio WHERE stock_code = 'GAS' AND ratio_code = 'ROA' AND year = 2024 AND quarter = 4 LIMIT 1;
```

## Giá đóng cửa trung bình của Soybean Oil trong tháng 10/2023 là bao nhiêu USD? [entity]

```sql
SELECT AVG(value) AS avg_close_price_usd
FROM fact_commodity_daily
WHERE indicator_code IN (SELECT indicator_code FROM dim_commodity_indicator WHERE indicator_name ILIKE '%Soybean Oil%')
  AND time >= '2023-10-01'::date
  AND time < '2023-11-01'::date;
```

## Liệt kê ROE (điểm phần trăm) theo từng quý của Ngân hàng Thương mại Cổ phần Phát Triển Thành phố Hồ Chí Minh (HDB) từ 2024‑Q1 đến 2024‑Q4. [tuple] (Expected columns: period_key, ROE)

```sql
SELECT CONCAT(year, '-Q', quarter) AS period_key,
       data * 100 AS ROE
FROM fact_financial_ratio
WHERE stock_code = 'HDB'
  AND ratio_code = 'ROE'
  AND year = 2024
ORDER BY quarter
LIMIT 20;
```

## Hãy liệt kê tỷ suất sinh lời (điểm phần trăm) theo từng quý của mã cổ phiếu HPG (Công ty Cổ phần Tập đoàn Hòa Phát) từ quý 3/2023 đến quý 2/202 [tuple] (Expected columns: period_key, return_pct)

```sql
WITH filtered AS (
  SELECT
    stock_code,
    time,
    close,
    to_char(time, 'YYYY-"Q"Q') AS period_key
  FROM fact_stock_daily
  WHERE stock_code = 'HPG'
    AND time >= DATE '2023-07-01'
    AND time <= DATE '2024-06-30'
),
quarter_bounds AS (
  SELECT
    period_key,
    MIN(time) AS start_date,
    MAX(time) AS end_date
  FROM filtered
  GROUP BY period_key
),
start_prices AS (
  SELECT
    qb.period_key,
    f.close AS start_close
  FROM quarter_bounds qb
  JOIN filtered f
    ON f.period_key = qb.period_key AND f.time = qb.start_date
),
end_prices AS (
  SELECT
    qb.period_key,
    f.close AS end_close
  FROM quarter_bounds qb
  JOIN filtered f
    ON f.period_key = qb.period_key AND f.time = qb.end_date
)
SELECT
  sp.period_key AS period_key,
  ((ep.end_close - sp.start_close) / sp.start_close) * 100 AS return_pct
FROM start_prices sp
JOIN end_prices ep ON sp.period_key = ep.period_key
ORDER BY sp.period_key;
```

## Trong quý 1 năm 2025, tỷ suất sinh lời của cổ phiếu Công ty Cổ phần Đầu tư và Phát triển Đa Quốc Gia I.D.I là bao nhiêu điểm phần trăm? [entity]

```sql
WITH period AS (
  SELECT time, close
  FROM fact_stock_daily
  WHERE stock_code = 'IDI'
    AND time >= DATE '2025-01-01'
    AND time <= DATE '2025-03-31'
),
first_last AS (
  SELECT 
    (SELECT close FROM period ORDER BY time ASC LIMIT 1) AS first_close,
    (SELECT close FROM period ORDER BY time DESC LIMIT 1) AS last_close
)
SELECT ((last_close - first_close) / first_close) * 100 AS return_pct
FROM first_last;
```

## ROA của Ngân hàng Thương mại Cổ phần Sài Gòn – Hà Nội (SHB) trong quý 1 năm 2025 so với quý 4 năm 2024 chênh lệch bao nhiêu điểm phần trăm? [entity]

```sql
WITH q1 AS (
  SELECT data AS roa_q1 FROM fact_financial_ratio WHERE stock_code='SHB' AND ratio_code='ROA' AND year=2025 AND quarter=1
), q4 AS (
  SELECT data AS roa_q4 FROM fact_financial_ratio WHERE stock_code='SHB' AND ratio_code='ROA' AND year=2024 AND quarter=4
)
SELECT (q1.roa_q1 - q4.roa_q4) * 100 AS diff_percentage_point FROM q1, q4;
```

## Trong quý 1 năm 2025, chênh lệch tăng trưởng (điểm phần trăm) của cổ phiếu MBS (Công ty Cổ phần Chứng khoán MB) so với VNINDEX là bao nhiêu? [entity]

```sql
WITH sp AS (
 SELECT 
   (SELECT close FROM fact_stock_daily WHERE stock_code='MBS' AND time BETWEEN '2025-01-01' AND '2025-03-31' ORDER BY time ASC LIMIT 1) AS start_price,
   (SELECT close FROM fact_stock_daily WHERE stock_code='MBS' AND time BETWEEN '2025-01-01' AND '2025-03-31' ORDER BY time DESC LIMIT 1) AS end_price
),
ip AS (
 SELECT 
   (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time BETWEEN '2025-01-01' AND '2025-03-31' ORDER BY time ASC LIMIT 1) AS start_price,
   (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time BETWEEN '2025-01-01' AND '2025-03-31' ORDER BY time DESC LIMIT 1) AS end_price
)
SELECT 
   ((sp.end_price - sp.start_price)::numeric / sp.start_price * 100) -
   ((ip.end_price - ip.start_price)::numeric / ip.start_price * 100) AS growth_diff
FROM sp, ip;
```

## Tỷ suất sinh lời của cổ phiếu Tổng Công ty Cảng Hàng không Việt Nam (ACV) trong tháng 12 năm 2023 là bao nhiêu phần trăm? [entity]

```sql
WITH cte AS (
    SELECT time, close
    FROM fact_stock_daily
    WHERE stock_code = 'ACV'
      AND time >= '2023-12-01'::date
      AND time < '2024-01-01'::date
    ORDER BY time
), first_close AS (
    SELECT close AS val FROM cte ORDER BY time ASC LIMIT 1
), last_close AS (
    SELECT close AS val FROM cte ORDER BY time DESC LIMIT 1
)
SELECT ((last_close.val - first_close.val)::numeric / first_close.val) * 100 AS return_pct
FROM first_close, last_close;
```

## ROE của Công ty Cổ phần Lizen (mã LCG) trong quý 2 năm 2023 là bao nhiêu điểm phần trăm? [entity]

```sql
SELECT (data*100) AS roe_percent FROM fact_financial_ratio WHERE stock_code='LCG' AND ratio_code='ROE' AND year=2023 AND quarter=2 ORDER BY date_added DESC LIMIT 1
```

## Trong quý 3 năm 2024, mã cổ phiếu nào có tỷ suất sinh lời (điểm phần trăm) cao hơn: ILB (Công ty Cổ phần ICD Tân Cảng - Long Bình) hay HCM (Công ty Cổ phần Chứng khoán Thành phố Hồ Chí Minh)? [entity]

```sql
WITH price_range AS (
    SELECT stock_code,
           MIN(time) AS start_date,
           MAX(time) AS end_date
    FROM fact_stock_daily
    WHERE stock_code IN ('ILB','HCM')
      AND time >= '2024-07-01'::date
      AND time <= '2024-09-30'::date
    GROUP BY stock_code
), price_vals AS (
    SELECT pr.stock_code,
           sd_start.close AS start_close,
           sd_end.close AS end_close,
           ((sd_end.close - sd_start.close) / sd_start.close) * 100.0 AS return_pct
    FROM price_range pr
    JOIN LATERAL (
        SELECT close FROM fact_stock_daily
        WHERE stock_code = pr.stock_code AND time = pr.start_date
        LIMIT 1
    ) sd_start ON true
    JOIN LATERAL (
        SELECT close FROM fact_stock_daily
        WHERE stock_code = pr.stock_code AND time = pr.end_date
        LIMIT 1
    ) sd_end ON true
)
SELECT stock_code
FROM price_vals
ORDER BY return_pct DESC
LIMIT 1;
```

## Liệt kê ROA (điểm phần trăm) theo từng quý của Công ty Cổ phần Chứng khoán Ngân hàng Công thương Việt Nam (CTS) từ quý 4/2023 đến quý 3/2024. [tuple] (Expected columns: period_key, ROA)

```sql
SELECT CONCAT(year, '-Q', quarter) AS period_key,
       data * 100 AS ROA
FROM fact_financial_ratio
WHERE stock_code = 'CTS'
  AND ratio_code = 'ROA'
  AND (year * 10 + quarter) BETWEEN (2023 * 10 + 4) AND (2024 * 10 + 3)
ORDER BY year, quarter;
```

## ROA của mã chứng khoán APG (Công ty Cổ phần Chứng khoán APG) trong quý 2 năm 2024 so với quý đầu năm 2024 chênh lệch bao nhiêu điểm phần trăm? [entity]

```sql
SELECT (MAX(CASE WHEN quarter=2 THEN data END) - MAX(CASE WHEN quarter=1 THEN data END)) * 100 AS diff_pp FROM fact_financial_ratio WHERE stock_code='APG' AND ratio_code='ROA' AND year=2024;
```

## ROE của Công ty Cổ phần Tập đoàn Hòa Phát trong quý 1 năm 2024 so với quý 4 năm 2023 chênh lệch bao nhiêu điểm phần trăm? [entity]

```sql
WITH q1 AS (SELECT data FROM fact_financial_ratio WHERE stock_code='HPG' AND ratio_code='ROE' AND year=2024 AND quarter=1 ORDER BY date_added DESC LIMIT 1), q4 AS (SELECT data FROM fact_financial_ratio WHERE stock_code='HPG' AND ratio_code='ROE' AND year=2023 AND quarter=4 ORDER BY date_added DESC LIMIT 1) SELECT (q1.data - q4.data) * 100 AS diff_pp FROM q1, q4;
```

## Xin liệt kê tỷ suất sinh lời (điểm phần trăm) theo từng quý cho mã cổ phiếu PSH (Công ty Cổ phần Thương mại Đầu tư Dầu khí Nam Sông Hậu) và VNINDEX, từ quý 4 năm 2023 đến quý 3 năm 2024. [tuple] (Expected columns: period_key, return_pct, benchmark_return_pct)

```sql
WITH stock_quarter AS (
    SELECT to_char(time, 'YYYY-"Q"Q') AS period_key,
           MIN(time) AS start_time,
           MAX(time) AS end_time
    FROM fact_stock_daily
    WHERE stock_code = 'PSH'
      AND time >= '2023-10-01' AND time < '2024-10-01'
    GROUP BY period_key
), stock_prices AS (
    SELECT sq.period_key,
           MIN(sd_start.close) AS start_close,
           MAX(sd_end.close)   AS end_close
    FROM stock_quarter sq
    JOIN fact_stock_daily sd_start ON sd_start.stock_code = 'PSH' AND sd_start.time = sq.start_time
    JOIN fact_stock_daily sd_end   ON sd_end.stock_code   = 'PSH' AND sd_end.time   = sq.end_time
    GROUP BY sq.period_key
), index_quarter AS (
    SELECT to_char(time, 'YYYY-"Q"Q') AS period_key,
           MIN(time) AS start_time,
           MAX(time) AS end_time
    FROM fact_index_daily
    WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX')
      AND time >= '2023-10-01' AND time < '2024-10-01'
    GROUP BY period_key
), index_prices AS (
    SELECT iq.period_key,
           MIN(id_start.close) AS start_close,
           MAX(id_end.close)   AS end_close
    FROM index_quarter iq
    JOIN fact_index_daily id_start ON id_start.index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND id_start.time = iq.start_time
    JOIN fact_index_daily id_end   ON id_end.index_name   = 'VNINDEX' AND id_end.time   = iq.end_time
    GROUP BY iq.period_key
)
SELECT sp.period_key,
       ((sp.end_close - sp.start_close) / sp.start_close) * 100 AS return_pct,
       ((ip.end_close - ip.start_close) / ip.start_close) * 100 AS benchmark_return_pct
FROM stock_prices sp
JOIN index_prices ip ON sp.period_key = ip.period_key
ORDER BY sp.period_key;
```

## Liệt kê tỷ suất sinh lời (điểm phần trăm) theo từng quý của mã cổ phiếu CTI (Công ty Cổ phần Đầu tư Phát triển Cường Thuận IDICO) từ quý 4/2023 đến quý 3/2024 [tuple] (Expected columns: period_key, return_pct)

```sql
WITH periods AS (
 SELECT
   to_char(date_trunc('quarter', time), 'YYYY-"Q"Q') AS period_key,
   MIN(time) AS start_time,
   MAX(time) AS end_time
 FROM fact_stock_daily
 WHERE stock_code = 'CTI'
   AND time >= '2023-10-01'::date
   AND time < '2024-10-01'::date
 GROUP BY period_key
),
prices AS (
 SELECT
   p.period_key,
   sd_start.close AS start_close,
   sd_end.close AS end_close
 FROM periods p
 JOIN fact_stock_daily sd_start
   ON sd_start.stock_code='CTI' AND sd_start.time = p.start_time
 JOIN fact_stock_daily sd_end
   ON sd_end.stock_code='CTI' AND sd_end.time = p.end_time
)
SELECT
  period_key,
  ((end_close - start_close)::numeric / start_close) * 100 AS return_pct
FROM prices
ORDER BY period_key;
```

## Trong quý 1 năm 2024, tiền gửi không kỳ hạn của Ngân hàng Thương mại Cổ phần Quân đội (MBB) là bao nhiêu tỷ đồng? [entity]

```sql
SELECT stock_code, category_code, data, year, quarter FROM fact_financial_statement WHERE stock_code = 'MBB' AND category_code = 'Bank_TM_121' AND year = 2024 AND quarter = 1;
```

## Liệt kê tỷ suất lợi nhuận trên vốn chủ sở hữu (ROE) tính bằng điểm phần trăm theo từng quý của Tổng Công ty Cổ phần Dịch vụ Kỹ thuật Dầu khí Việt Nam (PVS) từ quý 3/2023 đến quý 2/2024. [tuple] (Expected columns: period_key, ROE)

```sql
SELECT CONCAT(year, '-Q', quarter) AS period_key,
       ROUND(CAST(data*100 AS NUMERIC), 4) AS ROE
FROM fact_financial_ratio
WHERE stock_code = 'PVS'
  AND ratio_code = 'ROE'
  AND ((year = 2023 AND quarter >= 3) OR (year = 2024 AND quarter <= 2))
ORDER BY year, quarter;
```

## Trong quý 3 năm 2023, chênh lệch sinh lời giữa cổ phiếu của Tập đoàn Xăng dầu Việt Nam (PLX) và VN30 là bao nhiêu điểm phần trăm? [entity]

```sql
WITH plx_start AS (
 SELECT close FROM fact_stock_daily
 WHERE stock_code='PLX' AND time >= '2023-07-01' AND time <= '2023-09-30'
 ORDER BY time ASC LIMIT 1
),
plx_end AS (
 SELECT close FROM fact_stock_daily
 WHERE stock_code='PLX' AND time >= '2023-07-01' AND time <= '2023-09-30'
 ORDER BY time DESC LIMIT 1
),
vn30_start AS (
 SELECT close FROM fact_index_daily
 WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VN30') AND time >= '2023-07-01' AND time <= '2023-09-30'
 ORDER BY time ASC LIMIT 1
),
vn30_end AS (
 SELECT close FROM fact_index_daily
 WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VN30') AND time >= '2023-07-01' AND time <= '2023-09-30'
 ORDER BY time DESC LIMIT 1
)
SELECT
 ((plx_end.close - plx_start.close)::numeric / plx_start.close) * 100 -
 ((vn30_end.close - vn30_start.close)::numeric / vn30_start.close) * 100
 AS diff_percentage_point
FROM plx_start, plx_end, vn30_start, vn30_end;
```

## Cổ phiếu của Tổng Công ty Cổ phần Khoan và Dịch vụ khoan Dầu khí (PVD) trong tháng 6 năm 2024 có tỷ suất sinh lời bao nhiêu điểm phần trăm? [entity]

```sql
WITH june_prices AS (
  SELECT close, time,
         ROW_NUMBER() OVER (ORDER BY time) as rn_asc,
         ROW_NUMBER() OVER (ORDER BY time DESC) as rn_desc
  FROM fact_stock_daily
  WHERE stock_code = 'PVD'
    AND time >= '2024-06-01'::date
    AND time < '2024-07-01'::date
)
SELECT ((last_close - first_close) / first_close * 100) as return_percent
FROM (
  SELECT 
    MAX(CASE WHEN rn_asc = 1 THEN close END) as first_close,
    MAX(CASE WHEN rn_desc = 1 THEN close END) as last_close
  FROM june_prices
) t;
```

## ROE của Ngân hàng Thương mại Cổ phần Phát Triển Thành phố Hồ Chí Minh (HDB) trong quý 1 năm 2024 so với quý 4 năm 2023 chênh lệch bao nhiêu điểm phần trăm? [entity]

```sql
SELECT 
  (MAX(CASE WHEN year = 2024 AND quarter = 1 THEN data END) - 
   MAX(CASE WHEN year = 2023 AND quarter = 4 THEN data END)) * 100 AS diff_pp
FROM fact_financial_ratio
WHERE stock_code = 'HDB' AND ratio_code = 'ROE' AND segment <> 'industry';
```

## Liệt kê tỷ suất sinh lời (điểm phần trăm) theo từng quý của mã cổ phiếu ngân hàng An Bình (ABB) và VNINDEX từ quý 4/2023 đến quý 3/2024. [tuple] (Expected columns: period_key, return_pct, benchmark_return_pct)

```sql
WITH quarters AS (
  SELECT generate_series('2023-10-01'::date, '2024-09-30'::date, interval '3 month') AS start_date
),
stock_returns AS (
  SELECT
    to_char(q.start_date, 'YYYY-"Q"Q') AS period_key,
    ((l.last_close - f.first_close) / f.first_close) * 100 AS return_pct
  FROM quarters q
  LEFT JOIN LATERAL (
    SELECT close AS first_close
    FROM fact_stock_daily
    WHERE stock_code='ABB' AND time >= q.start_date AND time < q.start_date + interval '3 month'
    ORDER BY time ASC LIMIT 1
  ) f ON true
  LEFT JOIN LATERAL (
    SELECT close AS last_close
    FROM fact_stock_daily
    WHERE stock_code='ABB' AND time >= q.start_date AND time < q.start_date + interval '3 month'
    ORDER BY time DESC LIMIT 1
  ) l ON true
  WHERE f.first_close IS NOT NULL AND l.last_close IS NOT NULL
),
benchmark_returns AS (
  SELECT
    to_char(q.start_date, 'YYYY-"Q"Q') AS period_key,
    ((l.last_close - f.first_close) / f.first_close) * 100 AS benchmark_return_pct
  FROM quarters q
  LEFT JOIN LATERAL (
    SELECT close AS first_close
    FROM fact_index_daily
    WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time >= q.start_date AND time < q.start_date + interval '3 month'
    ORDER BY time ASC LIMIT 1
  ) f ON true
  LEFT JOIN LATERAL (
    SELECT close AS last_close
    FROM fact_index_daily
    WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time >= q.start_date AND time < q.start_date + interval '3 month'
    ORDER BY time DESC LIMIT 1
  ) l ON true
  WHERE f.first_close IS NOT NULL AND l.last_close IS NOT NULL
)
SELECT s.period_key,
       s.return_pct,
       b.benchmark_return_pct
FROM stock_returns s
JOIN benchmark_returns b USING (period_key)
ORDER BY s.period_key;
```

## Trong quý 2 năm 2023, lợi nhuận sau thuế của Công ty Cổ phần Gemadept (GMD) chênh lệch so với Công ty Cổ phần Tập đoàn Công nghệ CMC (CMG) bao nhiêu tỷ VND? [entity]

```sql
SELECT ROUND((
    MAX(CASE WHEN stock_code='GMD' THEN data END) -
    MAX(CASE WHEN stock_code='CMG' THEN data END)
)::numeric, 4) AS diff_billion_vnd
FROM fact_financial_statement
WHERE stock_code IN ('GMD','CMG') AND category_code='IS_100' AND year=2023 AND quarter=2;
```

## Trong quý 1 năm 2025, công ty nào có lợi nhuận sau thuế cao hơn: Công ty Cổ phần Bất động sản Thế Kỷ (CRE) hay Công ty Cổ phần Vinhomes (VHM)? [entity]

```sql
SELECT stock_code, data AS profit
FROM fact_financial_statement
WHERE stock_code IN ('CRE','VHM')
  AND category_code = 'IS_103'
  AND year = 2025
  AND quarter = 1
ORDER BY profit DESC
LIMIT 1;
```

## Công ty chứng khoán CTS đạt ROE bao nhiêu điểm phần trăm trong quý 3 năm 2023? [entity]

```sql
SELECT (data * 100) AS roe_percent
FROM fact_financial_ratio
WHERE stock_code = 'CTS'
  AND ratio_code = 'ROE'
  AND year = 2023
  AND quarter = 3
LIMIT 1;
```

## Tỷ lệ ROA của Công ty Cổ phần Hưng Thịnh Incons trong quý 1 năm 2024 so với quý 4 năm 2023 chênh lệch bao nhiêu điểm phần trăm? [entity]

```sql
SELECT (MAX(CASE WHEN year = 2024 AND quarter = 1 THEN data END) -
               MAX(CASE WHEN year = 2023 AND quarter = 4 THEN data END)) * 100 AS diff_pp
FROM fact_financial_ratio
WHERE stock_code = 'HTN' AND ratio_code = 'ROA';
```

## Tỷ suất sinh lời của cổ phiếu Aluminum trong quý 2 năm 2024 là bao nhiêu phần trăm? [entity]

```sql
SELECT ROUND(CAST(((end_val - start_val) / start_val) * 100 AS NUMERIC), 4) AS profitability
FROM (
  SELECT
    (SELECT value FROM fact_commodity_daily WHERE indicator_code = (SELECT indicator_code FROM dim_commodity_indicator WHERE indicator_name = 'Aluminum') AND time >= '2024-04-01' AND time <= '2024-06-30' ORDER BY time ASC LIMIT 1) AS start_val,
    (SELECT value FROM fact_commodity_daily WHERE indicator_code = (SELECT indicator_code FROM dim_commodity_indicator WHERE indicator_name = 'Aluminum') AND time >= '2024-04-01' AND time <= '2024-06-30' ORDER BY time DESC LIMIT 1) AS end_val
) sub;
```

## Trong quý 3 năm 2023, giá đóng cửa trung bình của Công ty Cổ phần Phát triển Bất động sản Phát Đạt là bao nhiêu VND? [entity]

```sql
SELECT ROUND(AVG(close) * 1000)::bigint AS avg_close_vnd FROM fact_stock_daily WHERE stock_code = 'PDR' AND time >= '2023-07-01' AND time <= '2023-09-30';
```

## Tỷ suất sinh lời của mã cổ phiếu PVC (Tổng Công ty Hóa chất và Dịch vụ Dầu khí) trong quý 3 năm 2024 so với quý 2 năm 2024 chênh lệch bao nhiêu điểm phần trăm? [entity]

```sql
SELECT
  ((q3_end.close - q3_start.close) / q3_start.close * 100) -
  ((q2_end.close - q2_start.close) / q2_start.close * 100) AS diff
FROM
  (SELECT close FROM fact_stock_daily WHERE stock_code='PVC' AND time BETWEEN '2024-07-01' AND '2024-09-30' ORDER BY time ASC LIMIT 1) q3_start,
  (SELECT close FROM fact_stock_daily WHERE stock_code='PVC' AND time BETWEEN '2024-07-01' AND '2024-09-30' ORDER BY time DESC LIMIT 1) q3_end,
  (SELECT close FROM fact_stock_daily WHERE stock_code='PVC' AND time BETWEEN '2024-04-01' AND '2024-06-30' ORDER BY time ASC LIMIT 1) q2_start,
  (SELECT close FROM fact_stock_daily WHERE stock_code='PVC' AND time BETWEEN '2024-04-01' AND '2024-06-30' ORDER BY time DESC LIMIT 1) q2_end;
```

## Bạn có thể liệt kê doanh thu theo từng quý của Công ty Cổ phần Tập đoàn Hoa Sen (mã HSG) từ quý 2 năm 2023 đến quý 1 năm 2024 không? [tuple] (Expected columns: period_key, revenue)

```sql
SELECT concat(year, '-Q', quarter) AS period_key, data AS revenue
FROM fact_financial_statement
WHERE stock_code='HSG' AND category_code='IS_020'
  AND ( (year=2023 AND quarter>=2) OR (year=2024 AND quarter<=1) )
ORDER BY year, quarter;
```

## Liệt kê tỷ suất sinh lời (điểm phần trăm) theo từng quý cho cổ phiếu PTB (Công ty Cổ phần Phú Tài) từ quý 3 năm 2023 đến quý 2 năm 2024. [tuple] (Expected columns: period_key, return_pct)

```sql
WITH filtered AS (
    SELECT time, close,
           TO_CHAR(DATE_TRUNC('quarter', time), 'YYYY') || '-Q' || EXTRACT(quarter FROM time) AS period_key,
           DATE_TRUNC('quarter', time) AS quarter_start
    FROM fact_stock_daily
    WHERE stock_code = 'PTB'
      AND time >= '2023-07-01'::date
      AND time <= '2024-06-30'::date
),
quarter_prices AS (
    SELECT period_key,
           FIRST_VALUE(close) OVER (PARTITION BY period_key ORDER BY time ASC) AS start_close,
           FIRST_VALUE(close) OVER (PARTITION BY period_key ORDER BY time DESC) AS end_close
    FROM filtered
    GROUP BY period_key, time, close
)
SELECT DISTINCT period_key,
       (end_close - start_close) / start_close * 100 AS return_pct
FROM quarter_prices
ORDER BY period_key;
```

## Mức sinh lời của mã cổ phiếu CTG (ngân hàng) vượt VN30 trong quý 3 năm 2024 là bao nhiêu điểm phần trăm? [entity]

```sql
WITH ctg_prices AS (
 SELECT
   (SELECT close FROM fact_stock_daily WHERE stock_code='CTG' AND time >= '2024-07-01' AND time <= '2024-09-30' ORDER BY time ASC LIMIT 1) AS start_price,
   (SELECT close FROM fact_stock_daily WHERE stock_code='CTG' AND time >= '2024-07-01' AND time <= '2024-09-30' ORDER BY time DESC LIMIT 1) AS end_price
),
vn30_prices AS (
 SELECT
   (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VN30') AND time >= '2024-07-01' AND time <= '2024-09-30' ORDER BY time ASC LIMIT 1) AS start_price,
   (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VN30') AND time >= '2024-07-01' AND time <= '2024-09-30' ORDER BY time DESC LIMIT 1) AS end_price
)
SELECT
  ((ctg.end_price - ctg.start_price) / ctg.start_price * 100) -
  ((vn30.end_price - vn30.start_price) / vn30.start_price * 100) AS diff_percentage
FROM ctg_prices ctg, vn30_prices vn30;
```

## Lợi nhuận sau thuế của Công ty Cổ phần Điện lực Dầu khí Nhơn Trạch 2 trong quý 1 năm 2025 là bao nhiêu tỷ VND? [entity]

```sql
SELECT data FROM fact_financial_statement WHERE stock_code = 'NT2' AND category_code = 'IS_100' AND year = 2025 AND quarter = 1
```

## Giá đóng cửa trung bình của cổ phiếu Ngân hàng Thương mại Cổ phần Đầu tư và Phát triển Việt Nam (BID) trong tháng 6 năm 2023 là bao nhiêu VND? [entity]

```sql
SELECT AVG(close) * 1000 AS avg_close_vnd
FROM fact_stock_daily
WHERE stock_code = 'BID'
  AND time >= DATE '2023-06-01'
  AND time < DATE '2023-07-01';
```

## Liệt kê ROE (điểm phần trăm) theo từng quý của Ngân hàng Thương mại Cổ phần Quốc tế Việt Nam (VIB) từ quý 2/2024 đến quý 1/2025. [tuple] (Expected columns: period_key, ROE)

```sql
SELECT CONCAT(year, '-Q', quarter) AS period_key,
       data * 100 AS ROE
FROM fact_financial_ratio
WHERE stock_code = 'VIB'
  AND ratio_code = 'ROE'
  AND ((year = 2024 AND quarter >= 2) OR (year = 2025 AND quarter <= 1))
ORDER BY year, quarter
```

## Trong quý 2 năm 2024, chênh lệch tăng trưởng (điểm phần trăm) của cổ phiếu FMC – Công ty Cổ phần Thực phẩm Sao Ta – so với VNINDEX là bao nhiêu? [entity]

```sql
SELECT
    ((f_end - f_start) / f_start) * 100 - ((v_end - v_start) / v_start) * 100 AS growth_diff
FROM (
    SELECT
        (SELECT close FROM fact_stock_daily WHERE stock_code = 'FMC' AND time >= '2024-04-01'::date AND time <= '2024-06-30'::date ORDER BY time ASC LIMIT 1) AS f_start,
        (SELECT close FROM fact_stock_daily WHERE stock_code = 'FMC' AND time >= '2024-04-01'::date AND time <= '2024-06-30'::date ORDER BY time DESC LIMIT 1) AS f_end
) f,
(
    SELECT
        (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time >= '2024-04-01'::date AND time <= '2024-06-30'::date ORDER BY time ASC LIMIT 1) AS v_start,
        (SELECT close FROM fact_index_daily WHERE index_id = (SELECT index_id FROM dim_market_index WHERE index_name = 'VNINDEX') AND time >= '2024-04-01'::date AND time <= '2024-06-30'::date ORDER BY time DESC LIMIT 1) AS v_end
) v;
```

## Trong quý 1 năm 2024, doanh thu của Công ty Cổ phần Đầu tư và Kinh doanh nhà Khang Điền (KDH) chênh lệch so với Công ty Cổ phần Thành Thành Công - Biên Hòa (SBT) bao nhiêu tỷ VND? [entity]

```sql
SELECT (k.data - s.data) AS revenue_diff
FROM (SELECT data FROM fact_financial_statement WHERE stock_code='KDH' AND category_code='IS_020' AND year=2024 AND quarter=1) k,
     (SELECT data FROM fact_financial_statement WHERE stock_code='SBT' AND category_code='IS_020' AND year=2024 AND quarter=1) s;
```

