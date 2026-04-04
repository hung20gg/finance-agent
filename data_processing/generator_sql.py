from __future__ import annotations

"""
Generator tạo bộ câu hỏi tài chính tiếng Việt từ Postgres.

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
from sqlalchemy import create_engine, text
from question_generator.const import *
from question_generator.generator import PostgresGeneratorConfig, QuestionRecord, QuestionGenerator
from question_generator.feature_store import FeatureStoreBuilder

# =========================================================
# Utility helpers
# =========================================================


def _safe_float(value: Any, ndigits: int = 4) -> Optional[float]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return round(float(value), ndigits)
    except Exception:
        return None



def _quarter_end(year: int, quarter: int) -> datetime:
    month = quarter * 3
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, last_day)



def _month_end(year: int, month: int) -> datetime:
    last_day = calendar.monthrange(year, month)[1]
    return datetime(year, month, last_day)



def _period_label(period_type: str, time_val: int, year: int) -> str:
    if period_type == "quarter":
        return f"quý {time_val} năm {year}"
    return f"tháng {time_val} năm {year}"



def _period_key(period_type: str, year: int, time_val: int) -> str:
    prefix = "Q" if period_type == "quarter" else "M"
    return f"{year}-{prefix}{time_val}"



def _generate_ask_date(period_type: str, year: int, time_val: int, source_priority: str, rng: random.Random) -> Tuple[str, int]:
    """
    Giả lập ngày hỏi sau khi dữ liệu đã có thể dùng.
    market nhanh hơn, financial/ratio chậm hơn.
    """
    if period_type == "quarter":
        period_end = _quarter_end(year, time_val)
    else:
        period_end = _month_end(year, time_val)

    if source_priority == "market":
        gap_days = rng.randint(5, 25)
    elif source_priority == "macro":
        gap_days = rng.randint(12, 35)
    else:
        gap_days = rng.randint(20, 55)

    ask_date = period_end + timedelta(days=gap_days)
    gap_months = max(1, (ask_date.year - period_end.year) * 12 + ask_date.month - period_end.month)
    return ask_date.strftime("%Y-%m-%d"), gap_months



def _choose_distinct(items: Sequence[Any], k: int, rng: random.Random) -> List[Any]:
    items = list(items)
    if len(items) <= k:
        return items.copy()
    return rng.sample(items, k)



def _metric_label(metric: str) -> str:
    return METRIC_DISPLAY.get(metric, metric)



def _display_commodity(name: str) -> str:
    return DEFAULT_COMMODITY_DISPLAY.get(name, name)



def _display_index(name: str) -> str:
    return name



def _display_industry(industry: str) -> str:
    return INDUSTRY_VN.get(industry, industry)



def _company_label(stock_code: str, is_bank: bool = False, is_securities: bool = False) -> str:
    """Chuẩn hóa cách gọi tên doanh nghiệp theo company_info.

    Ưu tiên:
    1. is_bank=True -> "ngân hàng {mã}"
    2. is_securities=True -> "công ty chứng khoán {mã}"
    3. còn lại -> "công ty {mã}"
    """
    code = str(stock_code)
    if bool(is_bank):
        return f"ngân hàng {code}"
    if bool(is_securities):
        return f"công ty chứng khoán {code}"
    return f"công ty {code}"



def _display_entity(entity: str, entity_type: str) -> str:
    if entity_type == "stock":
        return f"cổ phiếu {entity}"
    if entity_type == "index":
        return f"chỉ số {_display_index(entity)}"
    if entity_type == "commodity":
        return _display_commodity(entity)
    if entity_type == "industry":
        return f"ngành {_display_industry(entity)}"
    return str(entity)



def _to_period_list(frame: pd.DataFrame, period_col: str = "period_key", value_cols: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """Đổi một frame nhỏ thành list dict, tiện cho câu hỏi tuple/list."""
    cols = [period_col] + (value_cols or [])
    rows: List[Dict[str, Any]] = []
    for _, row in frame[cols].iterrows():
        item: Dict[str, Any] = {period_col: row[period_col]}
        for c in value_cols or []:
            item[c] = _safe_float(row[c], 4) if c in row else None
        rows.append(item)
    return rows


# =========================================================
# Postgres loader
# =========================================================

class PostgresLoader:
    """Tầng chỉ lo đọc dữ liệu từ Postgres."""

    def __init__(self, config: PostgresGeneratorConfig):
        self.config = config
        if not config.postgres_url:
            raise ValueError("Thiếu Postgres URL. Hãy truyền --postgres-url hoặc đặt biến môi trường POSTGRES_URL / DATABASE_URL.")
        self.engine = create_engine(config.postgres_url, pool_pre_ping=True)

    def query_df(self, sql: str) -> pd.DataFrame:
        with self.engine.connect() as conn:
            return pd.read_sql_query(text(sql), conn)

    def fetch_stock_universe(self) -> List[str]:
        """
        Lấy universe mã cổ phiếu từ Postgres.
        Ưu tiên các mã có mặt ở company_info và có dữ liệu thị trường.
        """
        sql = f"""
        WITH base AS (
            SELECT DISTINCT ci.stock_code
            FROM company_info ci
            JOIN stock_daily s
              ON ci.stock_code = s.stock_code
            WHERE ci.industry IS NOT NULL
              AND s.time >= DATE '{self.config.start_date}'
        )
        SELECT stock_code
        FROM base
        ORDER BY stock_code
        """
        df = self.query_df(sql)
        codes = df["stock_code"].dropna().astype(str).tolist()
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
            MAX(industry) AS industry,
            BOOL_OR(COALESCE(is_bank::boolean, FALSE)) AS is_bank,
            BOOL_OR(COALESCE(is_securities::boolean, FALSE)) AS is_securities
        FROM company_info
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
        filters = [f"{entity_col} IS NOT NULL", f"time >= DATE '{self.config.start_date}'"]
        if allowed_names:
            allowed = ", ".join([f"'{x}'" for x in allowed_names])
            filters.append(f"{entity_col} IN ({allowed})")
        where_clause = " AND ".join(filters)

        sql = f"""
        WITH daily AS (
            SELECT
                {entity_col} AS entity,
                time,
                EXTRACT(YEAR FROM time)::int AS year,
                EXTRACT(QUARTER FROM time)::int AS quarter,
                EXTRACT(MONTH FROM time)::int AS month,
                {value_col}::double precision AS close,
                LAG({value_col}::double precision) OVER (PARTITION BY {entity_col} ORDER BY time) AS prev_close
            FROM {table_name}
            WHERE {where_clause}
        ),
        daily_ret AS (
            SELECT
                entity,
                time,
                year,
                quarter,
                month,
                close,
                prev_close,
                CASE
                    WHEN prev_close IS NULL OR prev_close = 0 THEN NULL
                    ELSE (close - prev_close) / prev_close
                END AS daily_return
            FROM daily
            WHERE prev_close IS NOT NULL
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
                (ARRAY_AGG(close ORDER BY time DESC))[1] AS end_close,
                (ARRAY_AGG(prev_close ORDER BY time ASC))[1] AS start_close
            FROM daily_ret
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
                (ARRAY_AGG(close ORDER BY time DESC))[1] AS end_close,
                (ARRAY_AGG(prev_close ORDER BY time ASC))[1] AS start_close
            FROM daily_ret
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
        df["period_key"] = df.apply(lambda r: _period_key(r["period_type"], int(r["year"]), int(r["time_val"])), axis=1)
        return df

    def fetch_financial_statement(self) -> pd.DataFrame:
        sql = f"""
        SELECT stock_code, year, quarter, category_code, data, segment
        FROM financial_statement
        WHERE year >= 2023
          AND quarter > 0
          AND category_code IN ('IS_020', 'IS_100', 'BS_125', 'BS_300', 'Bank_TM_121', 'Bank_TM_45', 'Bank_TM_61', 'CF_130')
        """
        return self.query_df(sql)

    def fetch_financial_ratio(self) -> pd.DataFrame:
        sql = f"""
        SELECT stock_code, year, quarter, ratio_code, data, segment
        FROM financial_ratio
        WHERE year >= 2023
          AND quarter > 0
          AND ratio_code IN ('NIM', 'BDR', 'ROE', 'ROA', 'EBITDA', 'DTTCR', 'QR', 'CashR')
        """
        return self.query_df(sql)

    def fetch_macro(self) -> pd.DataFrame:
        sql = f"""
        WITH q AS (
            SELECT
                indicator_name,
                EXTRACT(YEAR FROM datetime)::int AS year,
                EXTRACT(QUARTER FROM datetime)::int AS quarter,
                LAST_VALUE(value) OVER (
                    PARTITION BY indicator_name, EXTRACT(YEAR FROM datetime), EXTRACT(QUARTER FROM datetime)
                    ORDER BY datetime
                    ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING
                ) AS q_close
            FROM macro
            WHERE datetime >= DATE '{self.config.start_date}'
              AND indicator_name IN ('Inflation_%', 'Unemployment_%')
        )
        SELECT DISTINCT indicator_name, year, quarter, q_close
        FROM q
        ORDER BY indicator_name, year, quarter
        """
        return self.query_df(sql)

    def fetch_distinct_commodities(self) -> List[str]:
        sql = f"""
        SELECT DISTINCT indicator_name
        FROM commodities_daily
        WHERE time >= DATE '{self.config.start_date}'
        ORDER BY indicator_name
        """
        df = self.query_df(sql)
        return df["indicator_name"].dropna().astype(str).tolist()
# =========================================================
# Feature store builder
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


def parse_args() -> PostgresGeneratorConfig:
    parser = argparse.ArgumentParser(description="Generate mixed Vietnamese finance questions from Postgres.")
    parser.add_argument("--postgres-url", type=str, default=os.getenv("POSTGRES_URL") or os.getenv("DATABASE_URL"))
    parser.add_argument("--output-dir", type=str, default="data_mix_v5")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-date", type=str, default="2023-06-01")
    parser.add_argument("--max-stocks", type=int, default=150)
    parser.add_argument("--total-target-samples", type=int, default=22000)
    parser.add_argument("--ambiguous-ratio", type=float, default=0.10)
    parser.add_argument("--train-end", type=str, default="2025-06-30")
    parser.add_argument("--val-end", type=str, default="2025-09-30")
    parser.add_argument("--val-target-size", type=int, default=2000)
    parser.add_argument("--test-target-size", type=int, default=2000)
    parser.add_argument("--commodity-allowlist", type=str, default="")
    parser.add_argument("--omit-answer-for-complex", action="store_true", default=True)
    parser.add_argument("--keep-answer-for-complex", action="store_true", default=False)
    args = parser.parse_args()

    commodity_allowlist = [x.strip() for x in args.commodity_allowlist.split(",") if x.strip()] or None
    omit_answer_for_complex = False if args.keep_answer_for_complex else bool(args.omit_answer_for_complex)

    return PostgresGeneratorConfig(
        postgres_url=args.postgres_url,
        output_dir=args.output_dir,
        seed=args.seed,
        start_date=args.start_date,
        max_stocks=args.max_stocks,
        total_target_samples=args.total_target_samples,
        ambiguous_ratio=args.ambiguous_ratio,
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

    loader = PostgresLoader(config)
    builder = FeatureStoreBuilder(loader, config)
    store = builder.build()

    generator = QuestionGenerator(store, config)
    records = generator.generate()
    split_dict = generator.split_records(records)
    generator.export_jsonl(split_dict)

    print("Generated question mix successfully.")
    for split, items in split_dict.items():
        ambiguous = sum(1 for x in items if x.ambiguity == "ambiguous")
        answer_missing = sum(1 for x in items if x.answer is None)
        print(f"{split}: {len(items)} rows | ambiguous={ambiguous} | answer_missing={answer_missing}")
        print(_count_by(items, key=lambda r: r.question_family))


if __name__ == "__main__":
    main()