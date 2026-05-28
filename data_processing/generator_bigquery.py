from __future__ import annotations

"""
Generator tạo bộ câu hỏi tài chính tiếng Việt từ BigQuery.

Mục tiêu của bản này:
1. Trộn nhiều họ câu hỏi: calculate, compare, roll_up, drill_down.
2. Có so sánh công ty với trung bình ngành thật lấy từ company_info(stock_code, industry).
3. Có top 5, top 10, liệt kê theo dải thời gian và câu phục vụ visualize.
4. Cho phép một số câu khó không có answer. Khi đó answer = null trong JSON.
5. Thêm metadata rõ cho các câu top/list/visualize để pipeline sau dễ dùng.
6. Khi downsample val/test sẽ ưu tiên giữ câu hỏi ngành, chỉ số, commodity;
   với câu stock-related sẽ tăng trọng số cho mã thuộc VN30 lên 5 lần.

Lưu ý:
- Bản này cố gắng bám cấu trúc code cũ nhưng tách rõ hơn theo các lớp:
  loader -> feature store -> question generator -> export.
- Tên bảng/cột được giả định theo phần code cũ và mô tả của user.
  Nếu schema thực tế khác nhẹ, bạn chỉ cần sửa lại các câu SQL hoặc tên cột.
"""

import argparse
import calendar
import json
import math
import os
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd
from google.cloud import bigquery
from question_generator.const import *
from question_generator.generator import GeneratorConfig, QuestionRecord, QuestionGenerator
from question_generator.feature_store import FeatureStoreBuilder

# =========================================================
# Constants
# =========================================================


def _period_key(period_type: str, year: int, time_val: int) -> str:
    prefix = "Q" if period_type == "quarter" else "M"
    return f"{year}-{prefix}{time_val}"


# =========================================================
# BigQuery loader
# =========================================================


class BigQueryLoader:
    """Tầng chỉ lo đọc dữ liệu từ BigQuery.

    Ghi chú quan trọng cho industry rows:
    - Trong financial_statement và financial_ratio:
      * segment = 'industry'  -> stock_code chính là TÊN NGÀNH
      * segment != 'industry' -> stock_code là mã doanh nghiệp thật
    - Vì vậy builder sẽ không tính industry benchmark bằng cách group company rows nữa,
      mà lấy trực tiếp các dòng segment='industry'.
    """

    def __init__(self, config: GeneratorConfig):
        self.config = config
        if config.key_path and os.path.exists(config.key_path):
            self.client = bigquery.Client.from_service_account_json(config.key_path)
        else:
            self.client = bigquery.Client()
        self.prefix = config.project_table_prefix

    def query_df(self, sql: str) -> pd.DataFrame:
        return self.client.query(sql).to_dataframe()

    def fetch_stock_universe(self) -> List[str]:
        sql = f"""
        WITH base AS (
            SELECT DISTINCT ci.stock_code
            FROM `{self.prefix}.company_info` ci
            JOIN `{self.prefix}.stock_daily` s
              ON ci.stock_code = s.stock_code
            WHERE ci.industry IS NOT NULL
              AND s.time >= '{self.config.start_date}'
        )
        SELECT stock_code
        FROM base
        ORDER BY stock_code
        """
        df = self.query_df(sql)
        codes = df["stock_code"].dropna().astype(str).tolist()
        print(codes)
        
        # Đưa các mã VN30 lên đầu để không bị cắt nốt do max-stocks giới hạn alphabet
        vn30_codes = [c for c in codes if c in VN30_TICKERS]
        other_codes = [c for c in codes if c not in VN30_TICKERS]
        codes = vn30_codes + other_codes
        
        if self.config.max_stocks and len(codes) > self.config.max_stocks:
            codes = codes[: self.config.max_stocks]
        return codes

    def fetch_company_info(self, stock_codes: Sequence[str]) -> pd.DataFrame:
        if not stock_codes:
            return pd.DataFrame(columns=["stock_code", "industry", "is_bank", "is_securities"])

        code_list = ", ".join([f"'{x}'" for x in stock_codes])
        sql = f"""
        SELECT
            stock_code,
            ANY_VALUE(industry) AS industry,
            LOGICAL_OR(COALESCE(CAST(is_bank AS BOOL), FALSE)) AS is_bank,
            LOGICAL_OR(COALESCE(CAST(is_securities AS BOOL), FALSE)) AS is_securities
        FROM `{self.prefix}.company_info`
        WHERE stock_code IN ({code_list})
          AND industry IS NOT NULL
        GROUP BY stock_code
        ORDER BY stock_code
        """
        return self.query_df(sql)

    def fetch_market_period_features(
        self,
        table_name: str,
        entity_col: str,
        value_col: str,
        allowed_names: Optional[Sequence[str]] = None,
        price_multiplier: float = 1.0,
    ) -> pd.DataFrame:
        filters = [f"{entity_col} IS NOT NULL", f"time >= '{self.config.start_date}'"]
        if allowed_names:
            allowed = ", ".join([f"'{x}'" for x in allowed_names])
            filters.append(f"{entity_col} IN ({allowed})")
        where_clause = " AND ".join(filters)

        sql = f"""
WITH daily AS (
    SELECT
        {entity_col} AS entity,
        time,
        EXTRACT(YEAR FROM time) AS year,
        EXTRACT(QUARTER FROM time) AS quarter,
        EXTRACT(MONTH FROM time) AS month,
        {value_col} AS close,

        LAG({value_col}) OVER (PARTITION BY {entity_col} ORDER BY time) AS prev_close,

        SAFE_DIVIDE(
            {value_col} - LAG({value_col}) OVER (PARTITION BY {entity_col} ORDER BY time),
            LAG({value_col}) OVER (PARTITION BY {entity_col} ORDER BY time)
        ) AS daily_return

    FROM `{self.prefix}.{table_name}`
    WHERE {where_clause}
),

quarter_agg AS (
    SELECT
        entity,
        'quarter' AS period_type,
        year,
        quarter AS time_val,

        AVG(close) AS avg_close,
        STDDEV_SAMP(close) AS std_close,
        STDDEV_SAMP(daily_return) AS std_daily_return,

        COUNT(*) AS n_obs,

        ARRAY_AGG(close ORDER BY time DESC LIMIT 1)[OFFSET(0)] AS end_close,
        ARRAY_AGG(close ORDER BY time ASC LIMIT 1)[OFFSET(0)] AS start_close

    FROM daily
    GROUP BY entity, year, quarter
),

month_agg AS (
    SELECT
        entity,
        'month' AS period_type,
        year,
        month AS time_val,

        AVG(close) AS avg_close,
        STDDEV_SAMP(close) AS std_close,
        STDDEV_SAMP(daily_return) AS std_daily_return,

        COUNT(*) AS n_obs,

        ARRAY_AGG(close ORDER BY time DESC LIMIT 1)[OFFSET(0)] AS end_close,
        ARRAY_AGG(close ORDER BY time ASC LIMIT 1)[OFFSET(0)] AS start_close

    FROM daily
    GROUP BY entity, year, month
)

SELECT * FROM quarter_agg
UNION ALL
SELECT * FROM month_agg
ORDER BY entity, period_type, year, time_val
"""
        
        
        df = self.query_df(sql)
        if df.empty:
            return df

        for col in ["avg_close", "std_close", "end_close", "start_close"]:
            df[col] = df[col].astype(float) * price_multiplier

        df["return_pct"] = ((df["end_close"] - df["start_close"]) / df["start_close"]) * 100.0

        # THÊM LẠI DÒNG NÀY
        df["period_key"] = df.apply(
            lambda r: f"{int(r['year'])}-{'Q' if r['period_type'] == 'quarter' else 'M'}{int(r['time_val'])}",
            axis=1,
        )

        return df

    def fetch_stock_daily_prices(
        self,
        stock_codes: Sequence[str],
        price_multiplier: float = 1.0,
    ) -> pd.DataFrame:
        if not stock_codes:
            return pd.DataFrame(columns=["stock_code", "date", "year", "daily_close"])

        code_list = ", ".join([f"'{x}'" for x in stock_codes])
        sql = f"""
        SELECT
            stock_code,
            DATE(time) AS date,
            EXTRACT(YEAR FROM time) AS year,
            close AS daily_close
        FROM `{self.prefix}.stock_daily`
        WHERE stock_code IN ({code_list})
          AND time >= '{self.config.start_date}'
        ORDER BY stock_code, time
        """
        df = self.query_df(sql)
        if df.empty:
            return df

        df["daily_close"] = df["daily_close"].astype(float) * price_multiplier
        return df

    def fetch_financial_statement(self) -> pd.DataFrame:
        sql = f"""
        SELECT stock_code, year, quarter, category_code, data, segment
        FROM `{self.prefix}.financial_statement`
        WHERE year >= 2023
          AND quarter > 0
          AND category_code IN (
              'IS_020', 'IS_036', 'IS_100',
              'BS_100', 'BS_110', 'BS_125', 'BS_270', 'BS_300', 'BS_305', 'BS_329', 'BS_350', 'BS_400',
              'Bank_TM_68', 'Bank_TM_69', 'Bank_TM_70',
              'Bank_TM_85', 'Bank_TM_86', 'Bank_TM_87', 'Bank_TM_88', 'Bank_TM_89',
              'Bank_TM_121', 'Bank_TM_131', 'Bank_TM_132', 'Bank_TM_133',
              'Bank_TM_45', 'Bank_TM_61',
              'Corp_TM_27'
          )
        """
        return self.query_df(sql)

    def fetch_financial_ratio(self) -> pd.DataFrame:
        sql = f"""
        SELECT stock_code, year, quarter, ratio_code, data, segment
        FROM `{self.prefix}.financial_ratio`
        WHERE year >= 2023
          AND quarter > 0
          AND ratio_code IN ('NIM', 'BDR', 'ROE', 'ROA', 'EBITDA', 'DTTCR', 'QR', 'CashR')
        """
        return self.query_df(sql)

    def fetch_macro(self) -> pd.DataFrame:
        indicator_list = ", ".join([f"'{x}'" for x in MACRO_INDICATORS])
        sql = f"""
        WITH q AS (
            SELECT
                indicator_name,
                country,
                EXTRACT(YEAR FROM datetime) AS year,
                LAST_VALUE(value) OVER (
                    PARTITION BY indicator_name, country, EXTRACT(YEAR FROM datetime)
                    ORDER BY datetime
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ) AS q_close,
                LAST_VALUE(unit) OVER (
                    PARTITION BY indicator_name, country, EXTRACT(YEAR FROM datetime)
                    ORDER BY datetime
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ) AS unit
            FROM `{self.prefix}.macro`
            WHERE EXTRACT(YEAR FROM datetime) <= 2024
              AND indicator_name IN ({indicator_list})
        )
        SELECT DISTINCT indicator_name, country, year, q_close, unit
        FROM q
        ORDER BY country, indicator_name, year
        """
        return self.query_df(sql)

    def fetch_distinct_commodities(self) -> List[str]:
        sql = f"""
        SELECT DISTINCT indicator_name
        FROM `{self.prefix}.commodities_daily`
        WHERE time >= '{self.config.start_date}'
        ORDER BY indicator_name
        """
        df = self.query_df(sql)
        return df["indicator_name"].dropna().astype(str).tolist()


# =========================================================
# Feature store builder
# =========================================================


# =========================================================
# Helpers
# =========================================================

def _count_by(items: Iterable[QuestionRecord], key) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for item in items:
        k = key(item)
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: kv[0]))


# =========================================================
# CLI / main
# =========================================================


def parse_args() -> GeneratorConfig:
    parser = argparse.ArgumentParser(description="Generate mixed Vietnamese finance questions from BigQuery.")
    parser.add_argument("--key-path", type=str, default='keys/bigquery.json')
    parser.add_argument("--project-table-prefix", type=str, default="neusolution.ktln")
    parser.add_argument("--output-dir", type=str, default="data_mix_v4")
    parser.add_argument("--output-format", type=str, default="json", help="Comma-separated formats: json,excel,csv")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-date", type=str, default="2023-06-01")
    parser.add_argument("--max-stocks", type=int, default=150)
    parser.add_argument("--total-target-samples", type=int, default=20000)
    parser.add_argument("--ambiguous-ratio", type=float, default=0.20)
    parser.add_argument("--stock-daily-max-ratio", type=float, default=0.05)
    parser.add_argument("--train-end", type=str, default="2025-06-30")
    parser.add_argument("--val-end", type=str, default="2025-09-30")
    parser.add_argument("--val-target-size", type=int, default=500)
    parser.add_argument("--test-target-size", type=int, default=500)
    parser.add_argument("--commodity-allowlist", type=str, default="")
    parser.add_argument("--omit-answer-for-complex", action="store_true", default=True)
    parser.add_argument("--keep-answer-for-complex", action="store_true", default=False)
    args = parser.parse_args()

    commodity_allowlist = [x.strip() for x in args.commodity_allowlist.split(",") if x.strip()] or None
    omit_answer_for_complex = False if args.keep_answer_for_complex else bool(args.omit_answer_for_complex)

    return GeneratorConfig(
        project_table_prefix=args.project_table_prefix,
        key_path=args.key_path,
        output_dir=args.output_dir,
        output_format=args.output_format,
        seed=args.seed,
        start_date=args.start_date,
        max_stocks=args.max_stocks,
        total_target_samples=args.total_target_samples,
        ambiguous_ratio=args.ambiguous_ratio,
        stock_daily_max_ratio=args.stock_daily_max_ratio,
        train_end=args.train_end,
        val_end=args.val_end,
        val_target_size=args.val_target_size,
        test_target_size=args.test_target_size,
        commodity_allowlist=commodity_allowlist,
        omit_answer_for_complex=omit_answer_for_complex,
    )



def main() -> None:
    config = parse_args()
    random.seed(config.seed)

    loader = BigQueryLoader(config)
    builder = FeatureStoreBuilder(loader, config)
    store = builder.build()

    generator = QuestionGenerator(store, config)
    records = generator.generate()
    split_dict = generator.split_records(records)
    generator.export_records(split_dict)

    print("Generated question mix successfully.")
    for split, items in split_dict.items():
        ambiguous = sum(1 for x in items if x.ambiguity == "ambiguous")
        answer_missing = sum(1 for x in items if x.answer is None)
        print(f"{split}: {len(items)} rows | ambiguous={ambiguous} | answer_missing={answer_missing}")
        print(_count_by(items, key=lambda r: r.question_family))


if __name__ == "__main__":
    main()
