from typing import Any, List

import pandas as pd

from .models import QuestionRecord
from .utils import (
    _choose_distinct,
    _generate_ask_date,
    _metric_label,
    _safe_float,
)


def _country_label(country: Any) -> str:
    value = str(country or "").strip()
    if value.lower() in {"vietnam", "viet nam", "việt nam", "vn"}:
        return "Việt Nam"
    return value or "Việt Nam"


def _macro_unit(row: pd.Series) -> str:
    unit = str(row.get("unit") or "").strip()
    metric = str(row.get("metric") or "")
    if unit:
        return unit
    if metric.endswith("_pct") or metric in {"exports_pct_gdp", "imports_pct_gdp"}:
        return "phần trăm"
    return ""


class MacroQuestionMixin:
    def generate_macro_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        macro_yearly = self.store.get("macro_yearly", self.store.get("macro_quarter_long", pd.DataFrame()))
        if macro_yearly.empty:
            return out

        out.extend(self._generate_macro_direct_questions(macro_yearly))
        out.extend(self._generate_macro_change_questions(macro_yearly))
        out.extend(self._generate_macro_best_worst_year_questions(macro_yearly))
        return out

    def _generate_macro_direct_questions(self, macro_yearly: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        for _, row in macro_yearly.iterrows():
            value = _safe_float(row.get("q_close"), 4, metric=str(row.get("metric")))
            if value is None:
                continue
            year = int(row["year"])
            period_text = f"năm {year}"
            ask_date, gap = _generate_ask_date("quarter", year, 4, "macro", self.rng)
            country = _country_label(row.get("country"))
            unit = _macro_unit(row)
            unit_text = f" {unit}" if unit else ""
            metric = str(row["metric"])
            metric_text = _metric_label(metric)
            variants = [
                f"{metric_text} của nước {country} trong {period_text} là bao nhiêu{unit_text}?",
                f"Trong {period_text}, {metric_text} của nước {country} đạt bao nhiêu{unit_text}?",
            ]
            for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                out.append(self._build_record(
                    question_raw=question_text,
                    answer_type="entity",
                    answer=value,
                    family="macro",
                    subtype=f"macro_direct_{metric}",
                    ambiguity="clear",
                    time_asked=ask_date,
                    gap=gap,
                    data_cutoff=ask_date,
                    entities=[country],
                    metrics=[metric],
                    periods=[row["period_key"]],
                    sources=["macro_yearly"],
                    reasoning_hops=1,
                    extra_info=self._common_metadata(
                        indicator_name=row.get("indicator_name"),
                        country=country,
                        period_basis="year",
                        unit=unit,
                    ),
                ))
        return out

    def _generate_macro_change_questions(self, macro_yearly: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        for _, row in macro_yearly.dropna(subset=["change_pct"]).iterrows():
            value = _safe_float(row.get("change_pct"), 4)
            if value is None:
                continue
            year = int(row["year"])
            period_text = f"năm {year}"
            ask_date, gap = _generate_ask_date("quarter", year, 4, "macro", self.rng)
            country = _country_label(row.get("country"))
            metric = str(row["metric"])
            out.append(self._build_record(
                question_raw=f"Trong {period_text}, {_metric_label(metric)} của nước {country} thay đổi bao nhiêu phần trăm so với năm trước?",
                answer_type="entity",
                answer=value,
                family="macro",
                subtype=f"macro_yoy_change_pct_{metric}",
                ambiguity="clear",
                time_asked=ask_date,
                gap=gap,
                data_cutoff=ask_date,
                entities=[country],
                metrics=[metric],
                periods=[row["period_key"]],
                sources=["macro_yearly"],
                reasoning_hops=2,
                extra_info=self._common_metadata(
                    indicator_name=row.get("indicator_name"),
                    country=country,
                    period_basis="year",
                    previous_period=str(year - 1),
                    previous_value=_safe_float(row.get("prev_close"), 4, metric=metric),
                    current_value=_safe_float(row.get("q_close"), 4, metric=metric),
                ),
            ))
        return out

    def _generate_macro_best_worst_year_questions(self, macro_yearly: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        grouped = macro_yearly.dropna(subset=["q_close"]).groupby(["country", "metric"], dropna=False)
        for (country_value, metric), frame in grouped:
            frame = frame.sort_values("year").copy()
            frame["q_close"] = pd.to_numeric(frame["q_close"], errors="coerce")
            frame = frame.dropna(subset=["q_close"])
            if frame["year"].nunique() < 2:
                continue
            years = sorted(frame["year"].astype(int).unique().tolist())
            start_year, end_year = years[0], years[-1]
            ask_date, gap = _generate_ask_date("quarter", end_year, 4, "macro", self.rng)
            country = _country_label(country_value)
            for mode, row, label in [
                ("highest", frame.sort_values("q_close", ascending=False).iloc[0], "cao nhất"),
                ("lowest", frame.sort_values("q_close", ascending=True).iloc[0], "thấp nhất"),
            ]:
                out.append(self._build_record(
                    question_raw=f"Trong giai đoạn {start_year}-{end_year}, năm nào {_metric_label(str(metric))} của nước {country} {label}?",
                    answer_type="entity",
                    answer=str(row["period_key"]),
                    family="macro",
                    subtype=f"macro_{mode}_year_{metric}",
                    ambiguity="clear",
                    time_asked=ask_date,
                    gap=gap,
                    data_cutoff=ask_date,
                    entities=[country],
                    metrics=[str(metric)],
                    periods=frame["period_key"].astype(str).tolist(),
                    sources=["macro_yearly"],
                    reasoning_hops=2,
                    extra_info=self._common_metadata(
                        indicator_name=row.get("indicator_name"),
                        country=country,
                        period_basis="year",
                        value=_safe_float(row.get("q_close"), 4, metric=str(metric)),
                    ),
                ))
        return out
