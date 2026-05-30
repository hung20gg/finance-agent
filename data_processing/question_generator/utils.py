import calendar
import random
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from .const import DEFAULT_COMMODITY_DISPLAY, INDUSTRY_VN, METRIC_DISPLAY
from .models import QuestionRecord


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


def _date_label(date_value: Any) -> str:
    date_obj = pd.to_datetime(date_value).date()
    return f"ngày {date_obj.day:02d}/{date_obj.month:02d}/{date_obj.year}"


def _period_label(period_type: str, time_val: int, year: int) -> str:
    if period_type == "quarter":
        return f"quý {time_val} năm {year}"
    return f"tháng {time_val} năm {year}"


def _period_key(period_type: str, year: int, time_val: int) -> str:
    prefix = "Q" if period_type == "quarter" else "M"
    return f"{year}-{prefix}{time_val}"


def _generate_ask_date(period_type: str, year: int, time_val: int, source_priority: str, rng: random.Random) -> Tuple[str, int]:
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
    if ask_date.year >= 2026:
        ask_date = datetime(2025, 12, 31)

    gap_months = max(1, (ask_date.year - period_end.year) * 12 + ask_date.month - period_end.month)
    return ask_date.strftime("%Y-%m-%d"), gap_months


def _generate_daily_ask_date(date_value: Any, rng: random.Random) -> Tuple[str, int]:
    market_date = pd.to_datetime(date_value).to_pydatetime()
    ask_date = market_date + timedelta(days=rng.randint(1, 5))
    if ask_date.year >= 2026:
        ask_date = datetime(2025, 12, 31)
    return ask_date.strftime("%Y-%m-%d"), max(1, (ask_date - market_date).days)


def _choose_distinct(items: Sequence[Any], k: int, rng: random.Random) -> List[Any]:
    items = list(items)
    if len(items) <= k:
        return items.copy()
    return rng.sample(items, k)


def _metric_label(metric: str, is_index=False) -> str:
    if is_index and metric == "avg_close":
        return "Chỉ số"
    return METRIC_DISPLAY.get(metric, metric)


def _display_commodity(name: str) -> str:
    return DEFAULT_COMMODITY_DISPLAY.get(name, name)


def _is_stock(metric):
    return metric in [
        "return_pct",
        "daily_close",
        "ema20",
        "ema50",
        "ema200",
        "volatility",
        "excess_return_vs_vnindex",
        "excess_return_vs_vn30",
    ]


def _display_index(name: str) -> str:
    return name


def _get_don_vi(metric, is_commodity=False):
    don_vi = ""
    if metric in ["return_pct", "net_income_yoy", "revenue_yoy", "cogs_yoy"]:
        don_vi = "phần trăm"
    elif metric in ["ROE", "ROA", "NIM", "BDR", "excess_return_vs_vnindex", "excess_return_vs_vn30"]:
        don_vi = "điểm phần trăm"
    elif metric in [
        "revenue",
        "cogs",
        "net_income",
        "current_assets",
        "total_assets",
        "loan_customer",
        "liabilities",
        "customer_deposits",
        "short_term_borrowings",
        "long_term_borrowings",
        "equity",
        "bad_debt_amount",
        "loan_customer_individual",
        "loan_customer_private_business",
        "loan_customer_state_owned",
        "deposit_customer_individual",
        "deposit_customer_foreign_business",
        "deposit_customer_private_business",
        "casa",
        "loan_construction",
        "loan_real_estate",
        "real_estate_goods",
        "cash_equiv",
    ]:
        don_vi = "tỷ VND"
    elif metric in ["daily_close", "avg_close", "std_close", "ema20", "ema50", "ema200"]:
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
    if frame.empty:
        return None
    cols = [period_col] + (value_cols or [])
    out: Dict[str, List[Any]] = {col: [] for col in cols}
    for _, row in frame[cols].iterrows():
        out[period_col].append(row[period_col])
        for c in value_cols or []:
            out[c].append(_safe_float(row[c], 4, metric=c) if c in row else None)
    return out


def _to_answer_values(series: pd.Series, metric: str) -> List[Optional[float]]:
    return [_safe_float(value, 4, metric=metric) for value in series.tolist()]
