
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
from .const import *

# Update METRIC_DISPLAY with new derived/macro metrics
METRIC_DISPLAY.update({
    "revenue_qoq": "tăng trưởng QoQ doanh thu",
    "net_income_qoq": "tăng trưởng QoQ lợi nhuận sau thuế",
    "return_pct_qoq": "tăng trưởng QoQ tỷ suất sinh lời",
    "cash_equiv_yoy": "tăng trưởng YoY tiền và tương đương tiền",
    "cash_equiv_qoq": "tăng trưởng QoQ tiền và tương đương tiền",
    "inflation_change_pct": "thay đổi tỷ lệ lạm phát",
    "unemployment_change_pct": "thay đổi tỷ lệ thất nghiệp",
})

# =========================================================
# Constants
# =========================================================


# =========================================================
# Config & models
# =========================================================

@dataclass
class GeneratorConfig:
    project_table_prefix: str = "neusolution.ktln"
    key_path: Optional[str] = None
    output_dir: str = "data_mix_v4"
    seed: int = 42
    start_date: str = "2023-06-01"
    max_stocks: int = 150
    total_target_samples: int = 22000
    ambiguous_ratio: float = 0.10

    # Tỷ trọng họ câu hỏi rõ nghĩa.
    ratio_calculate: float = 0.28
    ratio_compare: float = 0.32
    ratio_roll_up: float = 0.20
    ratio_drill_down: float = 0.20

    # Split theo time_asked.
    train_end: str = "2025-06-30"
    val_end: str = "2025-09-30"
    val_target_size: int = 2000
    test_target_size: int = 2000

    # Sampling / paraphrase.
    paraphrase_per_candidate: int = 2
    top_k_values: Tuple[int, int] = (5, 10)

    # Cho phép bỏ answer ở câu khó.
    omit_answer_for_complex: bool = True
    answerless_modes: Tuple[str, ...] = ("visualize")

    # Các index và commodity.
    index_names: List[str] = field(default_factory=lambda: INDEX_NAMES.copy())
    commodity_allowlist: Optional[List[str]] = None

@dataclass
class PostgresGeneratorConfig:
    postgres_url: Optional[str] = None
    output_dir: str = "data_mix_v5"
    seed: int = 42
    start_date: str = "2023-06-01"
    max_stocks: int = 150
    total_target_samples: int = 22000
    ambiguous_ratio: float = 0.10

    # Tỷ trọng họ câu hỏi rõ nghĩa.
    ratio_calculate: float = 0.28
    ratio_compare: float = 0.32
    ratio_roll_up: float = 0.20
    ratio_drill_down: float = 0.20

    # Split theo time_asked.
    train_end: str = "2025-06-30"
    val_end: str = "2025-09-30"
    val_target_size: int = 2000
    test_target_size: int = 2000

    # Sampling / paraphrase.
    paraphrase_per_candidate: int = 2
    top_k_values: Tuple[int, int] = (5, 10)

    # Cho phép bỏ answer ở câu khó.
    omit_answer_for_complex: bool = True
    answerless_modes: Tuple[str, ...] = ("top10", "time_range", "visualize")

    # Các index và commodity.
    index_names: List[str] = field(default_factory=lambda: INDEX_NAMES.copy())
    commodity_allowlist: Optional[List[str]] = None


@dataclass
class QuestionRecord:
    question_raw: str
    answer_type: str  # entity | tuple
    answer: Any
    question_family: str
    question_subtype: str
    ambiguity: str  # clear | ambiguous
    time_asked: str
    gap: int
    data_cutoff: str
    entities: List[str]
    metrics: List[str]
    periods: List[str]
    sources: List[str]
    reasoning_hops: int
    extra_info: Dict[str, Any]

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)


# =========================================================
# Utility helpers
# =========================================================


def _safe_float(value: Any, ndigits: int = 4, metric: Optional[str] = None) -> Optional[float]:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        val = float(value)
        if metric is not None and metric in ["ROE", "ROA", "NIM", "BDR", "excess_return_vs_vnindex", "excess_return_vs_vn30"] and abs(val) < 10:
            val *= 100
        return round(val, ndigits)
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
    
    # Cap ask_date to <= 2025-12-31 to strictly enforce time < 2026
    if ask_date.year >= 2026:
        ask_date = datetime(2025, 12, 31)

    gap_months = max(1, (ask_date.year - period_end.year) * 12 + ask_date.month - period_end.month)
    return ask_date.strftime("%Y-%m-%d"), gap_months



def _choose_distinct(items: Sequence[Any], k: int, rng: random.Random) -> List[Any]:
    items = list(items)
    if len(items) <= k:
        return items.copy()
    return rng.sample(items, k)



def _metric_label(metric: str, is_index=False) -> str:
    if is_index and metric == 'avg_close':
        return 'Chỉ số'
    return METRIC_DISPLAY.get(metric, metric)



def _display_commodity(name: str) -> str:
    return DEFAULT_COMMODITY_DISPLAY.get(name, name)

def _is_stock(metric):
    return metric in ["return_pct", "volatility", "excess_return_vs_vnindex", "excess_return_vs_vn30"]


def _display_index(name: str) -> str:
    return name

def _get_don_vi(metric, is_commodity=False):
    don_vi = ""
    if metric in ["return_pct", "net_income_yoy", "revenue_yoy", "revenue_qoq", "net_income_qoq", "return_pct_yoy", "return_pct_qoq", "cash_equiv_yoy", "cash_equiv_qoq", "inflation_change_pct", "unemployment_change_pct"]:
        don_vi = "phần trăm"
    elif metric in [ "ROE", "ROA", "NIM", "BDR", "excess_return_vs_vnindex", "excess_return_vs_vn30"]:
        don_vi = "điểm phần trăm"
    elif metric in ["revenue", "net_income", "loan_customer", "liabilities", "casa", "loan_construction", "loan_real_estate", "cash_equiv"]:
        don_vi = "tỷ VND"
    elif metric in ["avg_close", "std_close"]:
        if is_commodity:
            don_vi = "USD"
        else:
            don_vi = "VND"
    return don_vi

def _display_industry(industry: str) -> str:
    return INDUSTRY_VN.get(industry, industry)

def _count_by(items: Iterable[QuestionRecord], key) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for item in items:
        k = key(item)
        out[k] = out.get(k, 0) + 1
    return dict(sorted(out.items(), key=lambda kv: kv[0]))



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



def _to_period_list(frame: pd.DataFrame, period_col: str = "period_key", value_cols: Optional[List[str]] = None) -> Optional[Dict[str, List[Any]]]:
    """Đổi một frame nhỏ thành dict of lists, tiện cho LLM format và đánh giá."""
    if frame.empty:
        return None
    cols = [period_col] + (value_cols or [])
    out: Dict[str, List[Any]] = {col: [] for col in cols}
    for _, row in frame[cols].iterrows():
        out[period_col].append(row[period_col])
        for c in value_cols or []:
            out[c].append(_safe_float(row[c], 4, metric=c) if c in row else None)
    return out



class QuestionGenerator:
    """Sinh câu hỏi từ các bảng trung gian."""

    def __init__(self, store: Dict[str, pd.DataFrame], config: GeneratorConfig):
        # Prevent any data >= 2026 from being used in generation
        for key, df in store.items():
            if isinstance(df, pd.DataFrame) and not df.empty:
                if "year" in df.columns:
                    df = df[pd.to_numeric(df["year"], errors="coerce") < 2026]
                if "time" in df.columns:
                    df = df[pd.to_datetime(df["time"], errors="coerce") < pd.Timestamp("2026-01-01")]
                if "datetime" in df.columns:
                    df = df[pd.to_datetime(df["datetime"], errors="coerce") < pd.Timestamp("2026-01-01")]
                store[key] = df

        self.store = store
        self.config = config
        self.rng = random.Random(config.seed)

        # Map metadata theo mã để gọi tên đúng kiểu doanh nghiệp.
        company_info = store.get("company_info", pd.DataFrame()).copy()
        if not company_info.empty and "stock_code" in company_info.columns:
            company_info["stock_code"] = company_info["stock_code"].astype(str)
            if "is_bank" not in company_info.columns:
                company_info["is_bank"] = False
            if "is_securities" not in company_info.columns:
                company_info["is_securities"] = False
            self.company_meta = company_info.drop_duplicates(subset=["stock_code"]).set_index("stock_code").to_dict("index")
        else:
            self.company_meta = {}

    def _company_label(self, stock_code: str, is_stock: bool = True) -> str:
        meta = self.company_meta.get(str(stock_code), {})
        prefix = "mã cổ phiếu " if is_stock else ""
        return prefix + _company_label(
            stock_code=str(stock_code),
            is_bank=bool(meta.get("is_bank", False)),
            is_securities=bool(meta.get("is_securities", False)),
        )

    def generate(self) -> List[QuestionRecord]:
        clear_candidates: Dict[str, List[QuestionRecord]] = {
            "calculate": self.generate_calculate_questions() + \
                         self.generate_macro_direct_questions() + \
                         self.generate_company_trailing_direct_questions() + \
                         self.generate_company_growth_questions(),
            "compare": self.generate_compare_questions() + \
                       self.generate_company_metric_vs_metric_questions() + \
                       self.generate_company_triple_compare_questions(),
            "roll_up": self.generate_rollup_questions() + \
                       self.generate_peer_outperform_benchmark_questions(),
            "drill_down": self.generate_drilldown_questions() + \
                         self.generate_peer_group_minmax_questions() + \
                         self.generate_industry_risk_return_questions() + \
                         self.generate_consecutive_growth_questions(),
        }
        sampled_clear = self._sample_clear_mix(clear_candidates)
        ambiguous = self.generate_ambiguous_questions(sampled_clear)
        final_records = sampled_clear + ambiguous
        self.rng.shuffle(final_records)
        return final_records

    # -----------------------------------------------------
    # Answer policy helpers
    # -----------------------------------------------------
    def _maybe_answer(self, mode: str, answer: Any) -> Any:
        # if self.config.omit_answer_for_complex and mode in set(self.config.answerless_modes):
        #     return None
        return answer

    def _common_metadata(self, **kwargs: Any) -> Dict[str, Any]:
        return dict(kwargs)

    # -----------------------------------------------------
    # Calculate / Select
    # -----------------------------------------------------
    def generate_calculate_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        cq = self.store["company_quarter"]
        cm = self.store["company_month"]
        industry_avg = self.store["industry_avg_quarter"]
        index_market = self.store["index_market"]
        commodity_market = self.store["commodity_market"]

        direct_company_metrics = [
            "return_pct", "avg_close",  "revenue", "net_income",
            "loan_customer", "liabilities", "casa", "loan_construction", "loan_real_estate",
            "cash_equiv", "ROE", "ROA", "NIM", "BDR", "excess_return_vs_vnindex",
            "excess_return_vs_vn30", "revenue_yoy", "net_income_yoy",
        ]
        direct_company_metrics = [m for m in direct_company_metrics if m in cq.columns]

        for _, row in cq.iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            for metric in direct_company_metrics:
                value = _safe_float(row.get(metric), 4, metric=metric)
                if value is None:
                    continue
                don_vi_str = _get_don_vi(metric)
                is_stock = _is_stock(metric)
                
                variants = [
                    f"{_metric_label(metric).capitalize()} của {self._company_label(row['stock_code'], is_stock)} trong {period_text} là bao nhiêu {don_vi_str}?",
                    f"Trong {period_text}, {_metric_label(metric)} của {self._company_label(row['stock_code'], is_stock)} là bao nhiêu {don_vi_str}?",
                ]
                for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                    out.append(self._build_record(
                        question_raw=question_text,
                        answer_type="entity",
                        answer=value,
                        family="calculate",
                        subtype=f"company_direct_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[row["stock_code"]],
                        metrics=[metric],
                        periods=[row["period_key"]],
                        sources=["company_quarter"],
                        reasoning_hops=1 if metric not in {"excess_return_vs_vnindex", "excess_return_vs_vn30", "revenue_yoy", "net_income_yoy"} else 2,
                        extra_info=self._common_metadata(industry=row.get("industry"), benchmark=row.get("benchmark_index")),
                    ))

        # Industry average direct questions.
        for _, row in industry_avg.iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            for metric in ["return_pct", "revenue", "net_income", "ROE", "ROA", "NIM", "BDR", "revenue_yoy", "net_income_yoy"]:
                
                don_vi_str = _get_don_vi(metric)
                
                value = _safe_float(row.get(f"{metric}_mean"), 4, metric=metric)
                if value is None:
                    continue
                out.append(self._build_record(
                    question_raw=f"Trung bình ngành của {_metric_label(metric)} trong {_display_entity(row['industry'], 'industry')} ở {period_text} là bao nhiêu {don_vi_str}?",
                    answer_type="entity",
                    answer=value,
                    family="calculate",
                    subtype=f"industry_avg_direct_{metric}",
                    ambiguity="clear",
                    time_asked=ask_date,
                    gap=gap,
                    data_cutoff=ask_date,
                    entities=[row["industry"]],
                    metrics=[metric],
                    periods=[row["period_key"]],
                    sources=["industry_avg_quarter"],
                    reasoning_hops=2,
                    extra_info=self._common_metadata(group_by="industry", aggregate="mean", n_stocks=int(row["n_stocks"])),
                ))

        # Monthly market direct questions.
        for _, row in cm.iterrows():
            year, month = int(row["year"]), int(row["month"])
            ask_date, gap = _generate_ask_date("month", year, month, "market", self.rng)
            period_text = _period_label("month", month, year)
            for metric in ["return_pct", "avg_close", "excess_return_vs_vnindex"]:
                value = _safe_float(row.get(metric), 4, metric=metric)
                if value is None:
                    continue
                don_vi = ""
                don_vi_str = _get_don_vi(metric)
                out.append(self._build_record(
                    question_raw=f"{_metric_label(metric).capitalize()} của cổ phiếu {row['stock_code']} trong {period_text} là bao nhiêu {don_vi_str}?",
                    answer_type="entity",
                    answer=value,
                    family="calculate",
                    subtype=f"company_month_direct_{metric}",
                    ambiguity="clear",
                    time_asked=ask_date,
                    gap=gap,
                    data_cutoff=ask_date,
                    entities=[row["stock_code"]],
                    metrics=[metric],
                    periods=[row["period_key"]],
                    sources=["company_month"],
                    reasoning_hops=1,
                    extra_info=self._common_metadata(industry=row.get("industry")),
                ))

        for entity_type, frame, source_name in [
            ("index", index_market, "index_market"),
            ("commodity", commodity_market, "commodity_market"),
        ]:
            for _, row in frame.iterrows():
                year, time_val = int(row["year"]), int(row["time_val"])
                period_type = row["period_type"]
                ask_date, gap = _generate_ask_date(period_type, year, time_val, "market", self.rng)
                period_text = _period_label(period_type, time_val, year)
                for metric in ["return_pct", "avg_close"]:
                    value = _safe_float(row.get(metric), 4, metric=metric)
                    if value is None:
                        continue
                    don_vi = ""
                    don_vi_str = _get_don_vi(metric, is_commodity=(entity_type == "commodity"))
                    

                    
                    out.append(self._build_record(
                        question_raw=f"{_metric_label(metric, entity_type == 'index').capitalize()} của {_display_entity(row['entity'], entity_type)} trong {period_text} là bao nhiêu {don_vi_str}?",
                        answer_type="entity",
                        answer=value,
                        family="calculate",
                        subtype=f"{entity_type}_direct_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[row["entity"]],
                        metrics=[metric],
                        periods=[row["period_key"]],
                        sources=[source_name],
                        reasoning_hops=1,
                        extra_info=self._common_metadata(entity_type=entity_type),
                    ))
        return out

    # -----------------------------------------------------
    # Compare
    # -----------------------------------------------------
    def generate_compare_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        cq = self.store["company_quarter"]
        commodity = self.store["commodity_market"]
        industry_avg = self.store["industry_avg_quarter"]

        # 1) Same period, company vs company.
        metrics = [m for m in ["return_pct", "ROE", "ROA", "NIM", "BDR", "revenue", "net_income"] if m in cq.columns]
        for (year, quarter), frame in cq.groupby(["year", "quarter"], dropna=False):
            codes = frame["stock_code"].dropna().astype(str).unique().tolist()
            if len(codes) < 2:
                continue
            ask_date, gap = _generate_ask_date("quarter", int(year), int(quarter), "financial", self.rng)
            period_text = _period_label("quarter", int(quarter), int(year))
            if len(codes) <= 16:
                pairs = [(codes[i], codes[j]) for i in range(len(codes)) for j in range(i + 1, len(codes))]
            else:
                pairs = [tuple(self.rng.sample(codes, 2)) for _ in range(min(50, len(codes)))]
            for a, b in pairs:
                row_a = frame[frame["stock_code"] == a].iloc[0]
                row_b = frame[frame["stock_code"] == b].iloc[0]
                for metric in metrics:
                    va = _safe_float(row_a.get(metric), 4, metric=metric)
                    vb = _safe_float(row_b.get(metric), 4, metric=metric)
                    if va is None or vb is None:
                        continue

                    is_stock = _is_stock(metric)  
                    don_vi_str = _get_don_vi(metric)

                    out.append(self._build_record(
                        question_raw=f"Trong {period_text}, đơn vị nào có {_metric_label(metric)} cao hơn giữa {self._company_label(a, is_stock)} và {self._company_label(b, is_stock)}?",
                        answer_type="entity",
                        answer=a if va >= vb else b,
                        family="compare",
                        subtype=f"company_vs_company_winner_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[a, b],
                        metrics=[metric],
                        periods=[_period_key('quarter', int(year), int(quarter))],
                        sources=["company_quarter"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(value_a=va, value_b=vb),
                    ))
                    don_vi_str = _get_don_vi(metric)
                    is_stock = _is_stock(metric)          
                    out.append(self._build_record(
                        question_raw=f"Trong {period_text}, {_metric_label(metric)} của {self._company_label(a, is_stock)} chênh {self._company_label(b, is_stock)} bao nhiêu {don_vi_str}?",
                        answer_type="entity",
                        answer=_safe_float(va - vb, 4),
                        family="compare",
                        subtype=f"company_vs_company_diff_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[a, b],
                        metrics=[metric],
                        periods=[_period_key('quarter', int(year), int(quarter))],
                        sources=["company_quarter"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(value_a=va, value_b=vb),
                    ))

        # 2) Same company, different quarters.
        period_metrics = [m for m in ["return_pct", "revenue", "net_income", "ROE", "ROA", "NIM", "BDR"] if m in cq.columns]
        for stock_code, frame in cq.groupby("stock_code", dropna=False):
            frame = frame.sort_values(["year", "quarter"])
            for idx in range(1, len(frame)):
                cur = frame.iloc[idx]
                prev = frame.iloc[idx - 1]
                ask_date, gap = _generate_ask_date("quarter", int(cur["year"]), int(cur["quarter"]), "financial", self.rng)
                cur_period = _period_label("quarter", int(cur["quarter"]), int(cur["year"]))
                prev_period = _period_label("quarter", int(prev["quarter"]), int(prev["year"]))
                for metric in period_metrics:
                    v1 = _safe_float(cur.get(metric), 4, metric=metric)
                    v0 = _safe_float(prev.get(metric), 4, metric=metric)
                    if v1 is None or v0 is None:
                        continue
                    don_vi = ""
                    don_vi_str = _get_don_vi(metric)

                    is_stock = _is_stock(metric)
                    
                    out.append(self._build_record(
                        question_raw=f"{_metric_label(metric).capitalize()} của {self._company_label(stock_code, is_stock)} trong {cur_period} so với {prev_period} chênh lệch bao nhiêu {don_vi_str}?",
                        answer_type="entity",
                        answer=_safe_float(v1 - v0, 4),
                        family="compare",
                        subtype=f"company_period_diff_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[stock_code],
                        metrics=[metric],
                        periods=[prev["period_key"], cur["period_key"]],
                        sources=["company_quarter"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(current=v1, previous=v0),
                    ))

        # 3) Company vs benchmark index.
        for _, row in cq.iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            stock_ret = _safe_float(row.get("return_pct"), 4, metric="return_pct")
            bm_ret = _safe_float(row.get("benchmark_return_pct"), 4, metric="benchmark_return_pct")
            if stock_ret is None or bm_ret is None:
                continue
            bm_name = str(row.get("benchmark_index", "VNINDEX"))
            out.append(self._build_record(
                question_raw=f"Trong {period_text}, chênh lệch tăng trưởng cổ phiếu {row['stock_code']} outperform hay underperform {bm_name} là bao nhiêu?",
                answer_type="entity",
                answer=_safe_float(stock_ret - bm_ret, 4),
                family="compare",
                subtype="stock_vs_benchmark_direction",
                ambiguity="clear",
                time_asked=ask_date,
                gap=gap,
                data_cutoff=ask_date,
                entities=[row["stock_code"], bm_name],
                metrics=["return_pct", "benchmark_return_pct"],
                periods=[row["period_key"]],
                sources=["company_quarter", "index_market"],
                reasoning_hops=2,
                extra_info=self._common_metadata(stock_return=stock_ret, benchmark_return=bm_ret),
            ))
            out.append(self._build_record(
                question_raw=f"Trong {period_text}, mức chênh lệch sinh lời giữa cổ phiếu {row['stock_code']} và {bm_name} là bao nhiêu điểm %?",
                answer_type="entity",
                answer=_safe_float(stock_ret - bm_ret, 4),
                family="compare",
                subtype="stock_vs_benchmark_diff",
                ambiguity="clear",
                time_asked=ask_date,
                gap=gap,
                data_cutoff=ask_date,
                entities=[row["stock_code"], bm_name],
                metrics=["return_pct", "benchmark_return_pct"],
                periods=[row["period_key"]],
                sources=["company_quarter", "index_market"],
                reasoning_hops=2,
                extra_info=self._common_metadata(stock_return=stock_ret, benchmark_return=bm_ret),
            ))

        # 4) Company vs industry average. Đây là phần user yêu cầu rõ.
        industry_join = cq.merge(
            industry_avg[[c for c in industry_avg.columns if c in {"industry", "year", "quarter", "period_key"} or c.endswith("_mean")]],
            on=["industry", "year", "quarter"],
            how="left",
            suffixes=("", "_industry"),
        )
        industry_metrics = [m for m in ["revenue", "net_income", "ROE", "ROA", "NIM", "BDR"] if m in cq.columns]
        for _, row in industry_join.dropna(subset=["industry"]).iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            industry_name_vn = _display_industry(str(row["industry"]))
            for metric in industry_metrics:
                company_val = _safe_float(row.get(metric), 4, metric=metric)
                industry_mean = _safe_float(row.get(f"{metric}_mean"), 4, metric=metric)
                if company_val is None or industry_mean is None:
                    continue
                diff = _safe_float(company_val - industry_mean, 4)
                don_vi_str = _get_don_vi(metric)
                is_stock = _is_stock(metric)  
                out.append(self._build_record(
                    question_raw=f"Trong {period_text}, {_metric_label(metric)} của {self._company_label(row['stock_code'], is_stock)} chênh trung bình ngành {industry_name_vn} bao nhiêu {don_vi_str}?",
                    answer_type="entity",
                    answer=diff,
                    family="compare",
                    subtype=f"company_vs_industry_avg_diff_{metric}",
                    ambiguity="clear",
                    time_asked=ask_date,
                    gap=gap,
                    data_cutoff=ask_date,
                    entities=[row["stock_code"], str(row["industry"])],
                    metrics=[metric],
                    periods=[row["period_key"]],
                    sources=["company_quarter", "industry_avg_quarter"],
                    reasoning_hops=2,
                    extra_info=self._common_metadata(company_value=company_val, industry_mean=industry_mean, industry=row["industry"]),
                ))

        # 5) Company vs linked commodities.
        commodity_quarter = commodity[commodity["period_type"] == "quarter"].copy().rename(columns={"time_val": "quarter"})
        for _, row in cq.iterrows():
            stock_code = str(row["stock_code"])
            links = LINKED_COMMODITY_BY_TICKER.get(stock_code, [])
            if not links:
                continue
            year, quarter = int(row["year"]), int(row["quarter"])
            stock_ret = _safe_float(row.get("return_pct"), 4, metric="return_pct")
            if stock_ret is None:
                continue
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            sub = commodity_quarter[
                (commodity_quarter["year"] == year)
                & (commodity_quarter["quarter"] == quarter)
                & (commodity_quarter["entity"].isin(links))
            ]
            for _, crow in sub.iterrows():
                comm_ret = _safe_float(crow.get("return_pct"), 4, metric="return_pct")
                if comm_ret is None:
                    continue
                
                out.append(self._build_record(
                    question_raw=f"Trong {period_text}, tỷ suất sinh lời về giá của cổ phiếu {stock_code} chênh {_display_commodity(crow['entity'])} bao nhiêu điểm %?",
                    answer_type="entity",
                    answer=_safe_float(stock_ret - comm_ret, 4),
                    family="compare",
                    subtype="stock_vs_commodity_diff",
                    ambiguity="clear",
                    time_asked=ask_date,
                    gap=gap,
                    data_cutoff=ask_date,
                    entities=[stock_code, crow["entity"]],
                    metrics=["return_pct", "commodity_return_pct"],
                    periods=[row["period_key"]],
                    sources=["company_quarter", "commodity_market"],
                    reasoning_hops=2,
                    extra_info=self._common_metadata(stock_return=stock_ret, commodity_return=comm_ret),
                ))
        return out

    # -----------------------------------------------------
    # Roll up
    # -----------------------------------------------------
    def generate_rollup_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        industry_avg = self.store["industry_avg_quarter"]
        cq = self.store["company_quarter"]
        peer_rollups = self.store["peer_rollups"]

        # Industry mean / median / positive count.
        for _, row in industry_avg.iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            industry = str(row["industry"])
            for metric in [ "revenue", "net_income", "ROE", "ROA", "NIM", "BDR", "revenue_yoy", "net_income_yoy"]:
                mean_val = _safe_float(row.get(f"{metric}_mean"), 4, metric=metric)
                median_val = _safe_float(row.get(f"{metric}_median"), 4, metric=metric)
                pos_count = row.get(f"{metric}_positive_count")
                don_vi = _get_don_vi(metric)
                don_vi_str = f" {don_vi}" if don_vi else ""
                if mean_val is not None:
                    out.append(self._build_record(
                        question_raw=f"Trong {period_text}, trung bình ngành của {_metric_label(metric)} trong {_display_entity(industry, 'industry')} là bao nhiêu {don_vi_str}?",
                        answer_type="entity",
                        answer=mean_val,
                        family="roll_up",
                        subtype=f"industry_mean_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[industry],
                        metrics=[metric],
                        periods=[row["period_key"]],
                        sources=["industry_avg_quarter"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(group_by="industry", aggregate="mean", n_stocks=int(row["n_stocks"])),
                    ))
                if median_val is not None:
                    out.append(self._build_record(
                        question_raw=f"Trong {period_text}, median của {_metric_label(metric)} trong {_display_entity(industry, 'industry')} là bao nhiêu {don_vi_str}?",
                        answer_type="entity",
                        answer=median_val,
                        family="roll_up",
                        subtype=f"industry_median_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[industry],
                        metrics=[metric],
                        periods=[row["period_key"]],
                        sources=["industry_avg_quarter"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(group_by="industry", aggregate="median", n_stocks=int(row["n_stocks"])),
                    ))
                if pos_count is not None:
                    out.append(self._build_record(
                        question_raw=f"Trong {period_text}, có bao nhiêu công ty trong {_display_entity(industry, 'industry')} có {_metric_label(metric)} dương?",
                        answer_type="entity",
                        answer=int(pos_count),
                        family="roll_up",
                        subtype=f"industry_positive_count_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[industry],
                        metrics=[metric],
                        periods=[row["period_key"]],
                        sources=["industry_avg_quarter"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(group_by="industry", aggregate="positive_count", n_stocks=int(row["n_stocks"])),
                    ))

        # Peer group summary.
        for _, row in peer_rollups.iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            group_name = str(row["group_name"])
            for metric in ["return_pct", "excess_return_vs_vnindex", "revenue", "net_income", "ROE", "ROA", "NIM", "BDR"]:
                for agg in ["mean", "median"]:
                    value = _safe_float(row.get(f"{metric}_{agg}"), 4, metric=metric)
                    if value is None:
                        continue
                    don_vi_str = _get_don_vi(metric)
                    out.append(self._build_record(
                        question_raw=f"Trong {period_text}, {agg} của {_metric_label(metric)} trong nhóm {group_name} là bao nhiêu {don_vi_str}?",
                        answer_type="entity",
                        answer=value,
                        family="roll_up",
                        subtype=f"peer_{agg}_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[group_name],
                        metrics=[metric],
                        periods=[row["period_key"]],
                        sources=["peer_rollups"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(group_name=group_name, n_members=int(row["n_members"])),
                    ))

        # Count trên toàn universe.
        for (year, quarter), frame in cq.groupby(["year", "quarter"]):
            ask_date, gap = _generate_ask_date("quarter", int(year), int(quarter), "financial", self.rng)
            period_text = _period_label("quarter", int(quarter), int(year))
            for metric in ["return_pct", "net_income_yoy", "revenue_yoy", "ROE", "ROA"]:
                if metric not in frame.columns:
                    continue
                series = frame[metric].dropna()
                if len(series) == 0:
                    continue
                out.append(self._build_record(
                    question_raw=f"Trong {period_text}, có bao nhiêu công ty có {_metric_label(metric)} dương?",
                    answer_type="entity",
                    answer=int((series > 0).sum()),
                    family="roll_up",
                    subtype=f"universe_positive_count_{metric}",
                    ambiguity="clear",
                    time_asked=ask_date,
                    gap=gap,
                    data_cutoff=ask_date,
                    entities=["stock_universe"],
                    metrics=[metric],
                    periods=[_period_key('quarter', int(year), int(quarter))],
                    sources=["company_quarter"],
                    reasoning_hops=2,
                    extra_info=self._common_metadata(group_by="universe", n_companies=int(frame["stock_code"].nunique())),
                ))
        return out

    # -----------------------------------------------------
    # Drill down, top-k, listing, visualize
    # -----------------------------------------------------
    def generate_drilldown_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        cq = self.store["company_quarter"]
        index_market = self.store["index_market"]
        commodity_market = self.store["commodity_market"]

        out.extend(self._generate_industry_top_questions(cq))
        out.extend(self._generate_market_top_questions(cq, index_market, commodity_market))
        out.extend(self._generate_time_range_listing_questions(cq))
        out.extend(self._generate_visualize_questions(cq))
        return out

    def _generate_industry_top_questions(self, cq: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        if cq.empty or "industry" not in cq.columns:
            return out

        metrics = [m for m in ["net_income", "ROE", "ROA", "NIM"] if m in cq.columns]
        grouped = cq.dropna(subset=["industry"]).groupby(["industry", "year", "quarter"], dropna=False)
        for (industry, year, quarter), frame in grouped:
            ask_date, gap = _generate_ask_date("quarter", int(year), int(quarter), "financial", self.rng)
            period_text = _period_label("quarter", int(quarter), int(year))
            industry_name_vn = _display_industry(str(industry))
            for metric in metrics:
                sub = frame[["stock_code", metric]].dropna().copy()
                sub[metric] = pd.to_numeric(sub[metric], errors="coerce")
                sub = sub.dropna(subset=[metric])
                if len(sub) < 2:
                    continue
                ranked = sub.sort_values(metric, ascending=False)

                # Top 1 luôn có answer.
                best = ranked.iloc[0]
                out.append(self._build_record(
                    question_raw=f"Trong ngành {industry_name_vn} ở {period_text}, mã nào có {_metric_label(metric)} cao nhất?",
                    answer_type="entity",
                    answer=best["stock_code"],
                    family="drill_down",
                    subtype=f"industry_top1_{metric}",
                    ambiguity="clear",
                    time_asked=ask_date,
                    gap=gap,
                    data_cutoff=ask_date,
                    entities=ranked["stock_code"].astype(str).tolist(),
                    metrics=[metric],
                    periods=[_period_key('quarter', int(year), int(quarter))],
                    sources=["company_quarter"],
                    reasoning_hops=2,
                    extra_info=self._common_metadata(request_mode="top_k", top_k=1, group_by="industry", industry=industry, sort_metric=metric, sort_order="desc"),
                ))


                # Top 5 / top 10. Top 10 có thể bỏ answer.
                for k in self.config.top_k_values:
                    if len(ranked) < k:
                        continue
                    ans_df = ranked.head(k)
                    answer = {
                        "stock_code": ans_df["stock_code"].astype(str).tolist(),
                        metric: ans_df[metric].tolist()
                    }
                    mode = f"top{k}" if k == 10 else "top_k"
                    out.append(self._build_record(
                        question_raw=f"Trong ngành {industry_name_vn} ở {period_text}, top {k} mã theo {_metric_label(metric)} là những mã nào?",
                        answer_type="tuple",
                        answer=self._maybe_answer(mode, answer),
                        family="drill_down",
                        subtype=f"industry_top{k}_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=ranked["stock_code"].astype(str).tolist(),
                        metrics=[metric],
                        periods=[_period_key('quarter', int(year), int(quarter))],
                        sources=["company_quarter"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(
                            request_mode="top_k",
                            top_k=k,
                            group_by="industry",
                            industry=industry,
                            sort_metric=metric,
                            sort_order="desc",
                            result_columns=["stock_code", metric],
                            n_candidates=len(ranked),
                            answer_expected=(self._maybe_answer(mode, answer) is not None),
                        ),
                    ))
        return out

    def _generate_market_top_questions(self, cq: pd.DataFrame, index_market: pd.DataFrame, commodity_market: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []

        # Universe stock top 5/top 10 theo quý.
        stock_metrics = [m for m in ["return_pct", "ROE", "ROA"] if m in cq.columns]
        for (year, quarter), frame in cq.groupby(["year", "quarter"], dropna=False):
            ask_date, gap = _generate_ask_date("quarter", int(year), int(quarter), "financial", self.rng)
            period_text = _period_label("quarter", int(quarter), int(year))
            for metric in stock_metrics:
                sub = frame[["stock_code", metric]].dropna().copy()
                sub[metric] = pd.to_numeric(sub[metric], errors="coerce")
                sub = sub.dropna(subset=[metric])
                if len(sub) < 2:
                    continue
                ranked = sub.sort_values(metric, ascending=False)
                for k in self.config.top_k_values:
                    if len(ranked) < k:
                        continue
                    ans_df = ranked.head(k)
                    answer = {
                        "stock_code": ans_df["stock_code"].astype(str).tolist(),
                        metric: ans_df[metric].tolist()
                    }
                    mode = f"top{k}" if k == 10 else "top_k"
                    out.append(self._build_record(
                        question_raw=f"Trong {period_text}, top {k} cổ phiếu theo {_metric_label(metric)} trên toàn bộ thị trường là những mã nào?",
                        answer_type="tuple",
                        answer=self._maybe_answer(mode, answer),
                        family="drill_down",
                        subtype=f"universe_top{k}_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=ranked["stock_code"].astype(str).tolist(),
                        metrics=[metric],
                        periods=[_period_key('quarter', int(year), int(quarter))],
                        sources=["company_quarter"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(request_mode="top_k", top_k=k, group_by="universe", sort_metric=metric, sort_order="desc", result_columns=["stock_code", metric], answer_expected=(self._maybe_answer(mode, answer) is not None)),
                    ))

        # Index / commodity top-k theo quý.
        for frame, entity_type, source_name in [
            (index_market[index_market["period_type"] == "quarter"], "index", "index_market"),
            (commodity_market[commodity_market["period_type"] == "quarter"], "commodity", "commodity_market"),
        ]:
            if frame.empty:
                continue
            for (year, time_val), g in frame.groupby(["year", "time_val"], dropna=False):
                ask_date, gap = _generate_ask_date("quarter", int(year), int(time_val), "market", self.rng)
                period_text = _period_label("quarter", int(time_val), int(year))
                for metric in ["return_pct"]:
                    sub = g[["entity", metric]].dropna().copy()
                    sub[metric] = pd.to_numeric(sub[metric], errors="coerce")
                    sub = sub.dropna(subset=[metric])
                    if len(sub) < 2:
                        continue
                    ranked = sub.sort_values(metric, ascending=False)
                    best = ranked.iloc[0]["entity"]
                    
                    for k in self.config.top_k_values:
                        if len(ranked) < k:
                            continue
                        ans_df = ranked.head(k)
                        answer = {
                            "entity": ans_df["entity"].astype(str).tolist(),
                            metric: ans_df[metric].tolist()
                        }
                        mode = f"top{k}" if k == 10 else "top_k"
                        out.append(self._build_record(
                            question_raw=f"Trong {period_text}, top {k} {entity_type} theo {_metric_label(metric)} là gì?",
                            answer_type="tuple",
                            answer=self._maybe_answer(mode, answer),
                            family="drill_down",
                            subtype=f"{entity_type}_top{k}_{metric}",
                            ambiguity="clear",
                            time_asked=ask_date,
                            gap=gap,
                            data_cutoff=ask_date,
                            entities=ranked["entity"].astype(str).tolist(),
                            metrics=[metric],
                            periods=[_period_key('quarter', int(year), int(time_val))],
                            sources=[source_name],
                            reasoning_hops=2,
                            extra_info=self._common_metadata(request_mode="top_k", top_k=k, entity_type=entity_type, sort_metric=metric, sort_order="desc", result_columns=["entity", metric], answer_expected=(self._maybe_answer(mode, answer) is not None)),
                        ))
        return out

    def _generate_time_range_listing_questions(self, cq: pd.DataFrame) -> List[QuestionRecord]:
        """
        Sinh câu hỏi liệt kê dữ liệu theo dải thời gian.
        Nhóm này rất hợp cho use case lấy nhiều dữ liệu để feed chart hoặc table.
        """
        out: List[QuestionRecord] = []
        if cq.empty:
            return out

        # A. Một công ty qua 4 quý gần nhất.
        for stock_code, frame in cq.groupby("stock_code", dropna=False):
            frame = frame.sort_values(["year", "quarter"]).copy()
            if len(frame) < 4:
                continue
            for end_idx in range(3, len(frame)):
                sub = frame.iloc[end_idx - 3 : end_idx + 1].copy()
                last = sub.iloc[-1]
                ask_date, gap = _generate_ask_date("quarter", int(last["year"]), int(last["quarter"]), "financial", self.rng)
                start_label, end_label = sub.iloc[0]["period_key"], sub.iloc[-1]["period_key"]

                for metric in ["return_pct", "revenue", "net_income", "ROE", "ROA", "NIM"]:
                    if metric not in sub.columns or sub[metric].dropna().empty:
                        continue
                    answer_payload = _to_period_list(sub.dropna(subset=[metric]), value_cols=[metric])
                    if not answer_payload:
                        continue
                    is_stock = _is_stock(metric)  
                    out.append(self._build_record(
                        question_raw=f"Liệt kê {_metric_label(metric)} theo từng quý của {self._company_label(stock_code, is_stock)} từ {start_label} đến {end_label}.",
                        answer_type="tuple",
                        answer=self._maybe_answer("time_range", answer_payload),
                        family="drill_down",
                        subtype=f"company_time_range_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[stock_code],
                        metrics=[metric],
                        periods=sub["period_key"].astype(str).tolist(),
                        sources=["company_quarter"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(
                            request_mode="time_range_listing",
                            range_type="quarter",
                            start_period=start_label,
                            end_period=end_label,
                            result_columns=["period_key", metric],
                            visualization_ready=True,
                            suggested_visualization="line_chart",
                            answer_expected=(self._maybe_answer("time_range", answer_payload) is not None),
                        ),
                    ))

                # Company vs benchmark theo dải thời gian.
                answer_payload = _to_period_list(sub.dropna(subset=["return_pct", "benchmark_return_pct"]), value_cols=["return_pct", "benchmark_return_pct"])
                if answer_payload:
                    benchmark_name = str(last.get("benchmark_index", "VNINDEX"))
                    is_stock = _is_stock(metric)  
                    out.append(self._build_record(
                        question_raw=f"Liệt kê tỷ suất sinh lời theo từng quý của mã cổ phiếu {self._company_label(stock_code, is_stock)} và {benchmark_name} từ {start_label} đến {end_label}.",
                        answer_type="tuple",
                        answer=self._maybe_answer("time_range", answer_payload),
                        family="drill_down",
                        subtype="company_vs_benchmark_time_range",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[stock_code, benchmark_name],
                        metrics=["return_pct", "benchmark_return_pct"],
                        periods=sub["period_key"].astype(str).tolist(),
                        sources=["company_quarter", "index_market"],
                        reasoning_hops=3,
                        extra_info=self._common_metadata(
                            request_mode="time_range_listing",
                            range_type="quarter",
                            start_period=start_label,
                            end_period=end_label,
                            benchmark=benchmark_name,
                            result_columns=["period_key", "return_pct", "benchmark_return_pct"],
                            visualization_ready=True,
                            suggested_visualization="line_chart",
                            answer_expected=(self._maybe_answer("time_range", answer_payload) is not None),
                        ),
                    ))

                # Company vs industry average theo dải thời gian.
                if str(last.get("industry", "")):
                    ind_sub = sub.dropna(subset=["industry"]).copy()
                    if len(ind_sub) == len(sub):
                        answer_payload = None
                        ind_name = str(last["industry"])
                        ind_avg_df = self.store.get("industry_avg_quarter")
                        
                        valid_rows = ind_sub.dropna(subset=["ROE"])
                        if not valid_rows.empty and ind_avg_df is not None and not ind_avg_df.empty:
                            ind_avg_sub = ind_avg_df[(ind_avg_df["industry"] == ind_name) & (ind_avg_df["period_key"].isin(valid_rows["period_key"]))]
                            avg_dict = dict(zip(ind_avg_sub["period_key"], ind_avg_sub["ROE"]))
                            answer_payload = {
                                "period_key": valid_rows["period_key"].astype(str).tolist(),
                                "company_ROE": valid_rows["ROE"].apply(lambda x: _safe_float(x, 4, metric="ROE")).tolist(),
                                "industry_mean_ROE": valid_rows["period_key"].apply(lambda pk: _safe_float(avg_dict.get(pk), 4, metric="ROE")).tolist()
                            }
                            
                        is_stock = _is_stock(metric)      
                        if answer_payload:
                            out.append(self._build_record(
                                question_raw=f"Liệt kê ROE theo từng quý của {self._company_label(stock_code, is_stock)} và mức trung bình ngành {_display_industry(str(last['industry']))} từ {start_label} đến {end_label}.",
                                answer_type="tuple",
                                answer=self._maybe_answer("time_range", answer_payload),
                                family="drill_down",
                                subtype="company_vs_industry_time_range_ROE",
                                ambiguity="clear",
                                time_asked=ask_date,
                                gap=gap,
                                data_cutoff=ask_date,
                                entities=[stock_code, str(last["industry"])],
                                metrics=["ROE"],
                                periods=sub["period_key"].astype(str).tolist(),
                                sources=["company_quarter", "industry_avg_quarter"],
                                reasoning_hops=3,
                                extra_info=self._common_metadata(
                                    request_mode="time_range_listing",
                                    range_type="quarter",
                                    start_period=start_label,
                                    end_period=end_label,
                                    compare_to="industry_mean",
                                    industry=str(last["industry"]),
                                    result_columns=["period_key", "company_ROE", "industry_mean_ROE"],
                                    visualization_ready=True,
                                    suggested_visualization="line_chart",
                                    answer_expected=(self._maybe_answer("time_range", answer_payload) is not None),
                                ),
                            ))
        return out

    def _generate_visualize_questions(self, cq: pd.DataFrame) -> List[QuestionRecord]:
        """
        Nhóm câu hỏi yêu cầu nhiều dữ liệu để trực quan hóa.
        Thường answer để null, nhưng metadata sẽ rất đầy đủ.
        """
        out: List[QuestionRecord] = []
        if cq.empty:
            return out

        # 1) Bar chart top 10 một ngành theo 1 metric tại 1 quý.
        for (industry, year, quarter), frame in cq.dropna(subset=["industry"]).groupby(["industry", "year", "quarter"], dropna=False):
            if len(frame) < 5:
                continue
            ask_date, gap = _generate_ask_date("quarter", int(year), int(quarter), "financial", self.rng)
            period_key = _period_key("quarter", int(year), int(quarter))
            period_text = _period_label("quarter", int(quarter), int(year))
            industry_name_vn = _display_industry(str(industry))
            for metric in ["return_pct", "ROE", "ROA", "net_income"]:
                if metric not in frame.columns or frame[metric].dropna().empty:
                    continue
                sub_df = frame[["stock_code", metric]].dropna().copy()
                sub_df[metric] = pd.to_numeric(sub_df[metric], errors="coerce")
                sub_df = sub_df.dropna(subset=[metric]).sort_values(metric, ascending=False).head(10)
                if sub_df.empty:
                    continue
                ans_payload = {
                    "stock_code": sub_df["stock_code"].astype(str).tolist(),
                    metric: sub_df[metric].tolist()
                }
                out.append(self._build_record(
                    question_raw=f"Lấy dữ liệu để vẽ bar chart top 10 công ty ngành {industry_name_vn} theo {_metric_label(metric)} trong {period_text}.",
                    answer_type="tuple",
                    answer=self._maybe_answer("visualize", ans_payload),
                    family="drill_down",
                    subtype=f"visualize_industry_top10_bar_{metric}",
                    ambiguity="clear",
                    time_asked=ask_date,
                    gap=gap,
                    data_cutoff=ask_date,
                    entities=sorted(frame["stock_code"].dropna().astype(str).unique().tolist()),
                    metrics=[metric],
                    periods=[period_key],
                    sources=["company_quarter"],
                    reasoning_hops=3,
                    extra_info=self._common_metadata(
                        request_mode="visualize",
                        visualization_hint="bar_chart",
                        top_k=10,
                        group_by="industry",
                        industry=str(industry),
                        sort_metric=metric,
                        sort_order="desc",
                        result_columns=["stock_code", metric],
                        answer_expected=(self._maybe_answer("visualize", ans_payload) is not None),
                    ),
                ))

        # 2) Heatmap theo quý cho top 10 mã trong một industry.
        for industry, frame in cq.dropna(subset=["industry"]).groupby("industry", dropna=False):
            frame = frame.sort_values(["year", "quarter"])
            if frame["period_key"].nunique() < 4 or frame["stock_code"].nunique() < 5:
                continue
            latest_period = frame[["year", "quarter"]].drop_duplicates().sort_values(["year", "quarter"]).tail(1).iloc[0]
            latest = frame[(frame["year"] == latest_period["year"]) & (frame["quarter"] == latest_period["quarter"])]
            if latest["return_pct"].dropna().empty:
                continue
            top10_stocks = latest.sort_values("return_pct", ascending=False)["stock_code"].dropna().astype(str).head(10).tolist()
            sub = frame[frame["stock_code"].isin(top10_stocks)].copy()
            periods = sub[["year", "quarter", "period_key"]].drop_duplicates().sort_values(["year", "quarter"]).tail(4)
            sub = sub[sub["period_key"].isin(periods["period_key"].tolist())]
            if sub.empty:
                continue
            ans_payload = {
                "stock_code": sub["stock_code"].astype(str).tolist(),
                "period_key": sub["period_key"].astype(str).tolist(),
                "return_pct": sub["return_pct"].apply(lambda x: _safe_float(x, 4, metric="return_pct")).tolist()
            }
            ask_date, gap = _generate_ask_date("quarter", int(latest_period["year"]), int(latest_period["quarter"]), "financial", self.rng)
            out.append(self._build_record(
                question_raw=f"Lấy dữ liệu để vẽ biểu đồ hiển  tỷ suất sinh lời theo quý cho top 10 mã cổ phiếu của ngành {_display_industry(str(industry))} trong 4 quý gần nhất.",
                answer_type="tuple",
                answer=self._maybe_answer("visualize", ans_payload),
                family="drill_down",
                subtype="visualize_industry_heatmap_return_pct",
                ambiguity="clear",
                time_asked=ask_date,
                gap=gap,
                data_cutoff=ask_date,
                entities=top10_stocks,
                metrics=["return_pct"],
                periods=periods["period_key"].astype(str).tolist(),
                sources=["company_quarter"],
                reasoning_hops=4,
                extra_info=self._common_metadata(
                    request_mode="visualize",
                    visualization_hint="heatmap",
                    group_by="industry",
                    industry=str(industry),
                    entity_selection="top10_by_latest_return",
                    result_columns=["stock_code", "period_key", "return_pct"],
                    answer_expected=(self._maybe_answer("visualize", ans_payload) is not None),
                ),
            ))

        # 3) Scatter công ty vs trung bình ngành tại 1 quý.
        for (year, quarter), frame in cq.dropna(subset=["industry"]).groupby(["year", "quarter"], dropna=False):
            if len(frame) < 10:
                continue
            ask_date, gap = _generate_ask_date("quarter", int(year), int(quarter), "financial", self.rng)
            period_key = _period_key("quarter", int(year), int(quarter))
            for metric in ["ROE", "ROA", "return_pct"]:
                if metric not in frame.columns or frame[metric].dropna().empty:
                    continue
                sub_df = frame[["stock_code", "industry", metric]].dropna()
                if sub_df.empty:
                    continue
                ans_payload = {
                    "stock_code": sub_df["stock_code"].astype(str).tolist(),
                    "industry": sub_df["industry"].astype(str).tolist(),
                    f"company_{metric}": sub_df[metric].apply(lambda x: _safe_float(x, 4, metric=metric)).tolist()
                }
                out.append(self._build_record(
                    question_raw=f"Lấy dữ liệu để vẽ scatter so sánh {_metric_label(metric)} của từng công ty với mức trung bình ngành trong {_period_label('quarter', int(quarter), int(year))}.",
                    answer_type="tuple",
                    answer=self._maybe_answer("visualize", ans_payload),
                    family="drill_down",
                    subtype=f"visualize_company_vs_industry_scatter_{metric}",
                    ambiguity="clear",
                    time_asked=ask_date,
                    gap=gap,
                    data_cutoff=ask_date,
                    entities=sorted(frame["stock_code"].dropna().astype(str).unique().tolist()),
                    metrics=[metric],
                    periods=[period_key],
                    sources=["company_quarter", "industry_avg_quarter"],
                    reasoning_hops=4,
                    extra_info=self._common_metadata(
                        request_mode="visualize",
                        visualization_hint="scatter",
                        compare_to="industry_mean",
                        result_columns=["stock_code", "industry", f"company_{metric}", f"industry_mean_{metric}"],
                        answer_expected=(self._maybe_answer("visualize", ans_payload) is not None),
                    ),
                ))
        return out

    # -----------------------------------------------------
    # Controlled ambiguous questions
    # -----------------------------------------------------
    def generate_ambiguous_questions(self, clear_records: List[QuestionRecord]) -> List[QuestionRecord]:
        target = max(1, int(len(clear_records) * self.config.ambiguous_ratio))
        pool = [r for r in clear_records if r.question_family in {"calculate", "compare", "roll_up", "drill_down"}]
        if not pool:
            return []
        selected = _choose_distinct(pool, min(target, len(pool)), self.rng)
        ambiguous: List[QuestionRecord] = []
        for base in selected:
            ambiguous.append(self._build_record(
                question_raw=self._ambiguify_question(base.question_raw),
                answer_type=base.answer_type,
                answer=base.answer,
                family=base.question_family,
                subtype=f"ambiguous::{base.question_subtype}",
                ambiguity="ambiguous",
                time_asked=base.time_asked,
                gap=base.gap,
                data_cutoff=base.data_cutoff,
                entities=base.entities,
                metrics=base.metrics,
                periods=base.periods,
                sources=base.sources,
                reasoning_hops=base.reasoning_hops,
                extra_info={
                    **base.extra_info,
                    "resolved_from_clear_question": base.question_raw,
                    "ambiguity_rule": "controlled_ambiguity",
                },
            ))
        return ambiguous

    def _ambiguify_question(self, q: str) -> str:
        replacements = [
            ("VNINDEX", "thị trường chung"),
            ("VN30", "rổ bluechip"),
            ("lợi nhuận ròng", "lợi nhuận"),
            ("tỷ suất sinh lời", "mức sinh lời"),
            ("trung bình ngành", "mức trung bình của ngành"),
            ("quý 1 năm", "quý đầu năm"),
            ("quý 4 năm", "quý cuối năm"),
            ("công ty", "mã"),
        ]
        applied = False
        for src, dst in replacements:
            if src in q and self.rng.random() < 0.55:
                q = q.replace(src, dst)
                applied = True
        if not applied:
            if "bao nhiêu" in q:
                q = q.replace("bao nhiêu", "cỡ nào", 1)
            elif "Trong " in q:
                q = q.replace("Trong ", "Ở ", 1)
            else:
                q = f"Xét theo dữ liệu gần nhất đủ dùng, {q[0].lower() + q[1:]}"
        return q

    # -----------------------------------------------------
    # Sampling / split / export
    # -----------------------------------------------------
    def _sample_clear_mix(self, candidate_dict: Dict[str, List[QuestionRecord]]) -> List[QuestionRecord]:
        total_clear_target = max(1, int(self.config.total_target_samples * (1.0 - self.config.ambiguous_ratio)))
        weights = {
            "calculate": self.config.ratio_calculate,
            "compare": self.config.ratio_compare,
            "roll_up": self.config.ratio_roll_up,
            "drill_down": self.config.ratio_drill_down,
        }
        norm = sum(weights.values())
        quotas = {k: max(1, int(total_clear_target * v / norm)) for k, v in weights.items()}

        sampled: List[QuestionRecord] = []
        for family, pool in candidate_dict.items():
            self.rng.shuffle(pool)
            sampled.extend(pool[: min(len(pool), quotas.get(family, 0))])

        if len(sampled) < total_clear_target:
            leftovers: List[QuestionRecord] = []
            selected_ids = {id(x) for x in sampled}
            for pool in candidate_dict.values():
                leftovers.extend([x for x in pool if id(x) not in selected_ids])
            self.rng.shuffle(leftovers)
            sampled.extend(leftovers[: total_clear_target - len(sampled)])

        self.rng.shuffle(sampled)
        return sampled

    def _is_priority_non_stock_question(self, record: QuestionRecord) -> bool:
        """Ưu tiên giữ các câu hỏi ngành, chỉ số, commodity trước khi downsample.

        Lưu ý: câu stock vs benchmark vẫn có index_market trong sources nhưng về bản chất
        vẫn là stock-related, nên không được xếp vào nhóm ưu tiên này.
        """
        subtype = str(record.question_subtype or "")
        sources = set(record.sources or [])

        # Câu có chuẩn ngành hoặc roll-up / drill-down theo ngành.
        if subtype.startswith("industry_") or "company_vs_industry" in subtype or subtype.startswith("visualize_industry_"):
            return True
        if "industry_avg_quarter" in sources:
            return True
        if str(record.extra_info.get("group_by", "")) == "industry":
            return True

        # Câu thuần chỉ số. Loại trừ các câu có company_quarter để tránh lẫn với stock-related.
        if (subtype.startswith("index_") or sources == {"index_market"}) and "company_quarter" not in sources:
            return True

        # Câu thuần commodity.
        if (subtype.startswith("commodity_") or sources == {"commodity_market"}) and "company_quarter" not in sources:
            return True

        return False

    def _vn30_weight(self, record: QuestionRecord) -> float:
        """Tăng trọng số x5 cho câu stock-related có dính mã VN30.

        Dùng cho bước random downsample ở val/test sau khi đã giữ lại nhóm câu hỏi
        ngành, chỉ số và commodity. Nếu một câu không phải stock-related hoặc không
        chứa mã VN30 nào thì trọng số giữ nguyên bằng 1.
        """
        if self._is_priority_non_stock_question(record):
            return 1.0

        entities = {str(x) for x in (record.entities or [])}
        if entities & VN30_TICKERS:
            return 5.0

        stock_list = record.extra_info.get("stock_list")
        if isinstance(stock_list, list) and {str(x) for x in stock_list} & VN30_TICKERS:
            return 5.0

        top_entities = record.extra_info.get("top_entities")
        if isinstance(top_entities, list) and {str(x) for x in top_entities} & VN30_TICKERS:
            return 5.0

        return 1.0

    def _weighted_sample_without_replacement(self, items: List[QuestionRecord], k: int, weight_fn) -> List[QuestionRecord]:
        """Weighted random sampling không hoàn lại.

        Dùng biến thể Efraimidis-Spirakis: mỗi phần tử nhận một key ngẫu nhiên phụ thuộc
        vào trọng số; trọng số càng lớn thì xác suất nằm trong top-k càng cao.
        """
        if k <= 0:
            return []
        if len(items) <= k:
            return list(items)

        scored: List[Tuple[float, QuestionRecord]] = []
        for item in items:
            weight = max(float(weight_fn(item)), 1e-9)
            key = self.rng.random() ** (1.0 / weight)
            scored.append((key, item))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:k]]

    def _downsample_split(self, items: List[QuestionRecord], target_size: int) -> List[QuestionRecord]:
        """Cắt bớt split theo rule ưu tiên user yêu cầu.

        Rule:
        1. Giữ câu ngành, chỉ số, commodity trước.
        2. Phần còn lại lấy weighted random, trong đó câu stock-related có mã VN30
           được nhân trọng số 5 lần.
        """
        if target_size <= 0 or len(items) <= target_size:
            return list(items)

        priority_items = [x for x in items if self._is_priority_non_stock_question(x)]
        other_items = [x for x in items if not self._is_priority_non_stock_question(x)]

        selected: List[QuestionRecord]
        if len(priority_items) >= target_size:
            selected = self._weighted_sample_without_replacement(priority_items, target_size, lambda _: 1.0)
        else:
            selected = list(priority_items)
            remaining = target_size - len(selected)
            selected.extend(self._weighted_sample_without_replacement(other_items, remaining, self._vn30_weight))

        self.rng.shuffle(selected)
        return selected

    def split_records(self, records: List[QuestionRecord]) -> Dict[str, List[QuestionRecord]]:
        train_end = datetime.strptime(self.config.train_end, "%Y-%m-%d")
        val_end = datetime.strptime(self.config.val_end, "%Y-%m-%d")
        split_dict = {"train": [], "val": [], "test": []}
        self.rng.shuffle(records)
        for record in records:
            asked = datetime.strptime(record.time_asked, "%Y-%m-%d")
            if asked <= train_end:
                split_dict["train"].append(record)
            elif asked <= val_end:
                split_dict["val"].append(record)
            else:
                split_dict["test"].append(record)

        # Val và test bị khóa kích thước tối đa 2k theo yêu cầu.
        split_dict["val"] = self._downsample_split(split_dict["val"], self.config.val_target_size)
        split_dict["test"] = self._downsample_split(split_dict["test"], self.config.test_target_size)
        return split_dict

    def export_jsonl(self, split_dict: Dict[str, List[QuestionRecord]]) -> None:
        os.makedirs(self.config.output_dir, exist_ok=True)
        for split_name, items in split_dict.items():
            path = os.path.join(self.config.output_dir, f"{split_name}.jsonl")
            with open(path, "w", encoding="utf-8") as f:
                for idx, item in enumerate(items):
                    row = item.to_json()
                    row["id"] = f"{split_name}-{idx:08d}"
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")

        summary = {
            split: {
                "count": len(items),
                "ambiguous": sum(1 for x in items if x.ambiguity == "ambiguous"),
                "families": _count_by(items, key=lambda r: r.question_family),
                "subtypes": _count_by(items, key=lambda r: r.question_subtype),
                "answer_types": _count_by(items, key=lambda r: r.answer_type),
                "answer_missing": sum(1 for x in items if x.answer is None),
            }
            for split, items in split_dict.items()
        }
        with open(os.path.join(self.config.output_dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    def _build_record(
        self,
        question_raw: str,
        answer_type: str,
        answer: Any,
        family: str,
        subtype: str,
        ambiguity: str,
        time_asked: str,
        gap: int,
        data_cutoff: str,
        entities: List[str],
        metrics: List[str],
        periods: List[str],
        sources: List[str],
        reasoning_hops: int,
        extra_info: Dict[str, Any],
    ) -> QuestionRecord:
        return QuestionRecord(
            question_raw=question_raw,
            answer_type=answer_type,
            answer=answer,
            question_family=family,
            question_subtype=subtype,
            ambiguity=ambiguity,
            time_asked=time_asked,
            gap=gap,
            data_cutoff=data_cutoff,
            entities=list(dict.fromkeys([str(x) for x in entities if x is not None])),
            metrics=list(dict.fromkeys([str(x) for x in metrics if x is not None])),
            periods=list(dict.fromkeys([str(x) for x in periods if x is not None])),
            sources=list(dict.fromkeys([str(x) for x in sources if x is not None])),
            reasoning_hops=reasoning_hops,
            extra_info=extra_info,
        )

    # -----------------------------------------------------
    # New Diverse Scenarios (Easy to Hard)
    # -----------------------------------------------------

    def generate_macro_direct_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        mq = self.store.get("macro_quarter")
        if mq is None or mq.empty:
            return out

        metrics = ["inflation_change_pct", "unemployment_change_pct"]
        metrics = [m for m in metrics if m in mq.columns]

        for _, row in mq.iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "macro", self.rng)
            period_text = _period_label("quarter", quarter, year)
            for metric in metrics:
                value = _safe_float(row.get(metric), 4, metric=metric)
                if value is None:
                    continue
                
                metric_name = "tỷ lệ lạm phát" if metric == "inflation_change_pct" else "tỷ lệ thất nghiệp"
                don_vi_str = "phần trăm"
                variants = [
                    f"Thay đổi {metric_name} của Việt Nam trong {period_text} là bao nhiêu {don_vi_str}?",
                    f"Trong {period_text}, {metric_name} thay đổi bao nhiêu {don_vi_str}?",
                ]
                for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                    out.append(self._build_record(
                        question_raw=question_text,
                        answer_type="entity",
                        answer=value,
                        family="calculate",
                        subtype=f"macro_direct_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=["macro"],
                        metrics=[metric],
                        periods=[_period_key("quarter", year, quarter)],
                        sources=["macro_quarter"],
                        reasoning_hops=1,
                        extra_info=self._common_metadata(metric=metric),
                    ))
        return out

    def generate_company_trailing_direct_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        ct = self.store.get("company_trailing")
        if ct is None or ct.empty:
            return out

        metrics = ["revenue", "net_income", "cash_equiv"]
        metrics = [m for m in metrics if m in ct.columns]

        for _, row in ct.iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            for metric in metrics:
                value = _safe_float(row.get(metric), 4, metric=metric)
                if value is None:
                    continue
                
                don_vi_str = "tỷ VND"
                metric_lbl = "doanh thu lũy kế 4 quý gần nhất (TTM)" if metric == "revenue" else \
                             "lợi nhuận sau thuế lũy kế 4 quý gần nhất (TTM)" if metric == "net_income" else \
                             "tiền và tương đương tiền cuối kỳ lũy kế TTM"
                is_stock = _is_stock(metric)
                variants = [
                    f"{metric_lbl.capitalize()} của {self._company_label(row['stock_code'], is_stock)} tính đến {period_text} là bao nhiêu {don_vi_str}?",
                    f"Tính đến hết {period_text}, {metric_lbl} của {self._company_label(row['stock_code'], is_stock)} đạt bao nhiêu {don_vi_str}?",
                ]
                for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                    out.append(self._build_record(
                        question_raw=question_text,
                        answer_type="entity",
                        answer=value,
                        family="calculate",
                        subtype=f"company_trailing_direct_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[row["stock_code"]],
                        metrics=[metric],
                        periods=[row["period_key"]],
                        sources=["company_trailing"],
                        reasoning_hops=1,
                        extra_info=self._common_metadata(industry=row.get("industry")),
                    ))
        return out

    def generate_company_growth_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        cq = self.store.get("company_quarter")
        if cq is None or cq.empty:
            return out

        metrics = ["revenue", "net_income"]
        types = ["yoy", "qoq"]

        for _, row in cq.iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            for metric in metrics:
                for t in types:
                    col = f"{metric}_{t}"
                    if col not in cq.columns:
                        continue
                    value = _safe_float(row.get(col), 4)
                    if value is None:
                        continue
                    
                    is_stock = _is_stock(metric)
                    don_vi_str = "phần trăm"
                    growth_lbl = "so với cùng kỳ năm ngoái (YoY)" if t == "yoy" else "so với quý trước (QoQ)"
                    metric_lbl = "doanh thu" if metric == "revenue" else "lợi nhuận sau thuế"
                    
                    variants = [
                        f"Tăng trưởng {metric_lbl} {growth_lbl} của {self._company_label(row['stock_code'], is_stock)} trong {period_text} là bao nhiêu {don_vi_str}?",
                        f"Trong {period_text}, {metric_lbl} của {self._company_label(row['stock_code'], is_stock)} tăng trưởng {growth_lbl} bao nhiêu {don_vi_str}?",
                    ]
                    for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                        out.append(self._build_record(
                            question_raw=question_text,
                            answer_type="entity",
                            answer=value,
                            family="calculate",
                            subtype=f"company_growth_{t}_{metric}",
                            ambiguity="clear",
                            time_asked=ask_date,
                            gap=gap,
                            data_cutoff=ask_date,
                            entities=[row["stock_code"]],
                            metrics=[col],
                            periods=[row["period_key"]],
                            sources=["company_quarter"],
                            reasoning_hops=2,
                            extra_info=self._common_metadata(industry=row.get("industry")),
                        ))
        return out

    def generate_peer_group_minmax_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        cq = self.store.get("company_quarter")
        if cq is None or cq.empty:
            return out

        metrics = ["return_pct", "revenue", "net_income", "ROE", "ROA"]
        metrics = [m for m in metrics if m in cq.columns]

        for group_name, tickers in PEER_GROUPS.items():
            sub_cq = cq[cq["stock_code"].isin(tickers)].copy()
            if sub_cq.empty:
                continue
            grouped = sub_cq.groupby(["year", "quarter"])
            for (year, quarter), frame in grouped:
                ask_date, gap = _generate_ask_date("quarter", int(year), int(quarter), "financial", self.rng)
                period_text = _period_label("quarter", int(quarter), int(year))
                period_key = _period_key("quarter", int(year), int(quarter))
                for metric in metrics:
                    valid = frame[["stock_code", metric]].dropna()
                    if len(valid) < 2:
                        continue
                    
                    best = valid.sort_values(metric, ascending=False).iloc[0]
                    worst = valid.sort_values(metric, ascending=True).iloc[0]

                    is_stock = _is_stock(metric)
                    metric_lbl = _metric_label(metric)
                    
                    out.append(self._build_record(
                        question_raw=f"Trong nhóm peer {group_name} ở {period_text}, đơn vị nào có {metric_lbl} cao nhất?",
                        answer_type="entity",
                        answer=best["stock_code"],
                        family="drill_down",
                        subtype=f"peer_group_highest_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=list(tickers),
                        metrics=[metric],
                        periods=[period_key],
                        sources=["company_quarter"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(group_name=group_name, best_code=best["stock_code"], best_val=float(best[metric])),
                    ))
                    
                    out.append(self._build_record(
                        question_raw=f"Trong nhóm peer {group_name} ở {period_text}, đơn vị nào có {metric_lbl} thấp nhất?",
                        answer_type="entity",
                        answer=worst["stock_code"],
                        family="drill_down",
                        subtype=f"peer_group_lowest_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=list(tickers),
                        metrics=[metric],
                        periods=[period_key],
                        sources=["company_quarter"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(group_name=group_name, worst_code=worst["stock_code"], worst_val=float(worst[metric])),
                    ))
        return out

    def generate_company_metric_vs_metric_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        cq = self.store.get("company_quarter")
        if cq is None or cq.empty:
            return out

        pairs = [
            ("revenue", "net_income", "doanh thu", "lợi nhuận sau thuế"),
            ("revenue", "liabilities", "doanh thu", "tổng nợ phải trả"),
        ]
        
        bank_pairs = [
            ("casa", "loan_customer", "tiền gửi không kỳ hạn", "dư nợ cho vay khách hàng"),
            ("loan_real_estate", "loan_construction", "cho vay bất động sản và tư vấn", "cho vay ngành xây dựng"),
        ]

        for _, row in cq.iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            is_bank = bool(row.get("is_bank", False))
            
            selected_pairs = pairs.copy()
            if is_bank:
                selected_pairs.extend(bank_pairs)
                
            for m1, m2, l1, l2 in selected_pairs:
                if m1 not in cq.columns or m2 not in cq.columns:
                    continue
                v1 = _safe_float(row.get(m1), 4, metric=m1)
                v2 = _safe_float(row.get(m2), 4, metric=m2)
                if v1 is None or v2 is None:
                    continue
                
                is_stock = _is_stock(m1)
                ans = "Có" if v1 > v2 else "Không"
                question_text = f"Trong {period_text}, {l1} của {self._company_label(row['stock_code'], is_stock)} có lớn hơn {l2} không?"
                
                out.append(self._build_record(
                    question_raw=question_text,
                    answer_type="entity",
                    answer=ans,
                    family="compare",
                    subtype=f"company_{m1}_vs_{m2}",
                    ambiguity="clear",
                    time_asked=ask_date,
                    gap=gap,
                    data_cutoff=ask_date,
                    entities=[row["stock_code"]],
                    metrics=[m1, m2],
                    periods=[row["period_key"]],
                    sources=["company_quarter"],
                    reasoning_hops=2,
                    extra_info=self._common_metadata(v1=v1, v2=v2, industry=row.get("industry")),
                ))
        return out

    def generate_industry_risk_return_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        cq = self.store.get("company_quarter")
        if cq is None or cq.empty or "industry" not in cq.columns:
            return out

        grouped = cq.dropna(subset=["industry"]).groupby(["industry", "year", "quarter"])
        for (industry, year, quarter), frame in grouped:
            ask_date, gap = _generate_ask_date("quarter", int(year), int(quarter), "financial", self.rng)
            period_text = _period_label("quarter", int(quarter), int(year))
            period_key = _period_key("quarter", int(year), int(quarter))
            industry_name_vn = _display_industry(str(industry))

            winners = frame[frame["return_pct"] > 0].dropna(subset=["std_close"])
            if len(winners) < 2:
                continue

            best = winners.sort_values("std_close", ascending=True).iloc[0]
            
            question_text = f"Trong {period_text}, cổ phiếu nào thuộc ngành {industry_name_vn} có tỷ suất sinh lời dương nhưng có độ lệch chuẩn giá đóng cửa thấp nhất?"
            
            out.append(self._build_record(
                question_raw=question_text,
                answer_type="entity",
                answer=best["stock_code"],
                family="drill_down",
                subtype=f"industry_risk_return_{industry}",
                ambiguity="clear",
                time_asked=ask_date,
                gap=gap,
                data_cutoff=ask_date,
                entities=[best["stock_code"], str(industry)],
                metrics=["return_pct", "std_close"],
                periods=[period_key],
                sources=["company_quarter"],
                reasoning_hops=3,
                extra_info=self._common_metadata(
                    industry=str(industry),
                    stock_code=best["stock_code"],
                    return_pct=float(best["return_pct"]),
                    std_close=float(best["std_close"]),
                ),
            ))
        return out

    def generate_consecutive_growth_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        cq = self.store.get("company_quarter")
        if cq is None or cq.empty:
            return out

        metrics = ["revenue", "net_income"]

        for stock_code, frame in cq.groupby("stock_code"):
            frame = frame.sort_values(["year", "quarter"]).copy()
            if len(frame) < 3:
                continue
            
            for idx in range(2, len(frame)):
                q1 = frame.iloc[idx - 2]
                q2 = frame.iloc[idx - 1]
                q3 = frame.iloc[idx]
                
                if (q3["year"] * 4 + q3["quarter"]) - (q1["year"] * 4 + q1["quarter"]) != 2:
                    continue
                
                ask_date, gap = _generate_ask_date("quarter", int(q3["year"]), int(q3["quarter"]), "financial", self.rng)
                p1_label = q1["period_key"]
                p3_label = q3["period_key"]
                
                for metric in metrics:
                    col_qoq = f"{metric}_qoq"
                    if col_qoq not in frame.columns:
                        continue
                    
                    val2 = q2[col_qoq]
                    val3 = q3[col_qoq]
                    if pd.isna(val2) or pd.isna(val3):
                        continue
                    
                    ans = "Có" if val2 > 0 and val3 > 0 else "Không"
                    is_stock = _is_stock(metric)
                    metric_lbl = "doanh thu" if metric == "revenue" else "lợi nhuận sau thuế"
                    
                    question_text = f"Trong giai đoạn từ {p1_label} đến {p3_label}, {self._company_label(stock_code, is_stock)} có duy trì được đà tăng trưởng {metric_lbl} liên tiếp qua các quý (QoQ > 0) không?"
                    
                    out.append(self._build_record(
                        question_raw=question_text,
                        answer_type="entity",
                        answer=ans,
                        family="drill_down",
                        subtype=f"company_consecutive_growth_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[stock_code],
                        metrics=[col_qoq],
                        periods=[q1["period_key"], q2["period_key"], q3["period_key"]],
                        sources=["company_quarter"],
                        reasoning_hops=3,
                        extra_info=self._common_metadata(
                            stock_code=stock_code,
                            val_q2_qoq=float(val2),
                            val_q3_qoq=float(val3),
                        ),
                    ))
        return out

    def generate_company_triple_compare_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        cq = self.store.get("company_quarter")
        industry_avg = self.store.get("industry_avg_quarter")
        if cq is None or cq.empty or industry_avg is None or industry_avg.empty:
            return out

        roe_col = "ROE_mean" if "ROE_mean" in industry_avg.columns else "ROE"
        if roe_col not in industry_avg.columns:
            return out
        industry_roe = industry_avg[["industry", "year", "quarter", roe_col]].dropna().rename(columns={roe_col: "ROE_mean"})
        join_df = cq.merge(industry_roe, on=["industry", "year", "quarter"], how="inner")

        for _, row in join_df.iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            
            stock_ret = _safe_float(row.get("return_pct"), 4, metric="return_pct")
            bm_ret = _safe_float(row.get("benchmark_return_pct"), 4, metric="benchmark_return_pct")
            roe = _safe_float(row.get("ROE"), 4, metric="ROE")
            ind_roe = _safe_float(row.get("ROE_mean"), 4, metric="ROE")

            if any(v is None for v in [stock_ret, bm_ret, roe, ind_roe]):
                continue

            bm_name = str(row.get("benchmark_index", "VNINDEX"))
            ind_name = _display_industry(str(row["industry"]))
            is_stock = _is_stock("return_pct")

            ans = "Có" if (stock_ret > bm_ret and roe > ind_roe) else "Không"
            
            question_text = f"Trong {period_text}, tỷ suất sinh lời của {self._company_label(row['stock_code'], is_stock)} có vượt qua {bm_name} đồng thời ROE của công ty có cao hơn mức trung bình ngành {ind_name} không?"
            
            out.append(self._build_record(
                question_raw=question_text,
                answer_type="entity",
                answer=ans,
                family="compare",
                subtype="company_triple_compare_return_roe",
                ambiguity="clear",
                time_asked=ask_date,
                gap=gap,
                data_cutoff=ask_date,
                entities=[row["stock_code"], bm_name, str(row["industry"])],
                metrics=["return_pct", "benchmark_return_pct", "ROE"],
                periods=[row["period_key"]],
                sources=["company_quarter", "industry_avg_quarter", "index_market"],
                reasoning_hops=3,
                extra_info=self._common_metadata(
                    stock_return=stock_ret,
                    benchmark_return=bm_ret,
                    company_roe=roe,
                    industry_roe=ind_roe,
                ),
            ))
        return out

    def generate_peer_outperform_benchmark_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        cq = self.store.get("company_quarter")
        if cq is None or cq.empty:
            return out

        for group_name, tickers in PEER_GROUPS.items():
            sub_cq = cq[cq["stock_code"].isin(tickers)].copy()
            if sub_cq.empty:
                continue
            grouped = sub_cq.groupby(["year", "quarter"])
            for (year, quarter), frame in grouped:
                ask_date, gap = _generate_ask_date("quarter", int(year), int(quarter), "financial", self.rng)
                period_text = _period_label("quarter", int(quarter), int(year))
                period_key = _period_key("quarter", int(year), int(quarter))
                
                valid = frame[["stock_code", "return_pct", "benchmark_return_pct", "benchmark_index"]].dropna()
                if valid.empty:
                    continue
                
                outperform_count = 0
                outperform_tickers = []
                for _, r in valid.iterrows():
                    if float(r["return_pct"]) > float(r["benchmark_return_pct"]):
                        outperform_count += 1
                        outperform_tickers.append(r["stock_code"])
                
                question_text = f"Trong {period_text}, có bao nhiêu cổ phiếu thuộc nhóm {group_name} có tỷ suất sinh lời vượt qua chỉ số tham chiếu tương ứng?"
                
                out.append(self._build_record(
                    question_raw=question_text,
                    answer_type="entity",
                    answer=int(outperform_count),
                    family="roll_up",
                    subtype=f"peer_outperform_benchmark_count_{group_name}",
                    ambiguity="clear",
                    time_asked=ask_date,
                    gap=gap,
                    data_cutoff=ask_date,
                    entities=list(tickers),
                    metrics=["return_pct", "benchmark_return_pct"],
                    periods=[period_key],
                    sources=["company_quarter", "index_market"],
                    reasoning_hops=3,
                    extra_info=self._common_metadata(
                        group_name=group_name,
                        outperform_count=outperform_count,
                        outperform_tickers=outperform_tickers,
                    ),
                ))
        return out
        