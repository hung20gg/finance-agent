from typing import List

from .const import (
    BANK_FINANCIAL_INDUSTRY_SHARE_METRICS,
    CORP_FINANCIAL_INDUSTRY_SHARE_METRICS,
    FINANCIAL_INDUSTRY_SHARE_METRICS,
    REAL_ESTATE_FINANCIAL_INDUSTRY_SHARE_METRICS,
)
from .models import QuestionRecord
from .utils import (
    _display_entity,
    _generate_ask_date,
    _get_don_vi,
    _metric_label,
    _period_key,
    _period_label,
    _safe_float,
)


class RollupQuestionMixin:
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
            industry_rollup_metrics = list(dict.fromkeys([
                "revenue",
                "cogs",
                "net_income",
                *FINANCIAL_INDUSTRY_SHARE_METRICS,
                *BANK_FINANCIAL_INDUSTRY_SHARE_METRICS,
                *CORP_FINANCIAL_INDUSTRY_SHARE_METRICS,
                *REAL_ESTATE_FINANCIAL_INDUSTRY_SHARE_METRICS,
                "cash_equiv",
                "ROE",
                "ROA",
                "NIM",
                "BDR",
                "revenue_yoy",
                "cogs_yoy",
                "net_income_yoy",
            ]))
            for metric in industry_rollup_metrics:
                mean_val = _safe_float(row.get(f"{metric}_mean"), 4, metric=metric)
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
            peer_metrics = list(dict.fromkeys([
                "return_pct",
                "excess_return_vs_vnindex",
                "revenue",
                "cogs",
                "net_income",
                *FINANCIAL_INDUSTRY_SHARE_METRICS,
                *BANK_FINANCIAL_INDUSTRY_SHARE_METRICS,
                *CORP_FINANCIAL_INDUSTRY_SHARE_METRICS,
                *REAL_ESTATE_FINANCIAL_INDUSTRY_SHARE_METRICS,
                "cash_equiv",
                "ROE",
                "ROA",
                "NIM",
                "BDR",
            ]))
            for metric in peer_metrics:
                for agg in ["mean"]:
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
            for metric in ["return_pct", "net_income_yoy", "revenue_yoy", "cogs_yoy", "ROE", "ROA"]:
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
