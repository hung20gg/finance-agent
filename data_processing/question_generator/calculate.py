from typing import List

import pandas as pd

from .const import (
    BANK_FINANCIAL_INDUSTRY_SHARE_METRICS,
    CORP_FINANCIAL_INDUSTRY_SHARE_METRICS,
    FINANCIAL_FLOW_METRICS,
    FINANCIAL_INDUSTRY_SHARE_METRICS,
)
from .models import QuestionRecord
from .utils import (
    _choose_distinct,
    _date_label,
    _display_entity,
    _generate_ask_date,
    _generate_daily_ask_date,
    _get_don_vi,
    _is_stock,
    _metric_label,
    _period_label,
    _safe_float,
)


class CalculateQuestionMixin:
    STOCK_MARKET_METRICS = {
        "return_pct",
        "avg_close",
        "excess_return_vs_vnindex",
        "excess_return_vs_vn30",
    }

    # -----------------------------------------------------
    # Calculate / Select
    # -----------------------------------------------------
    def generate_calculate_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        cq = self.store["company_quarter"]
        cm = self.store["company_month"]
        stock_daily = self.store.get("stock_daily", pd.DataFrame())
        company_trailing = self.store.get("company_trailing", pd.DataFrame())
        company_yearly = self.store.get("company_yearly", pd.DataFrame())
        industry_avg = self.store["industry_avg_quarter"]
        index_market = self.store["index_market"]
        commodity_market = self.store["commodity_market"]

        direct_company_metrics = [
            "return_pct", "avg_close",  "revenue", "cogs", "net_income",
            "current_assets", "total_assets", "loan_customer", "liabilities", "customer_deposits", "equity",
            "short_term_borrowings", "long_term_borrowings",
            "bad_debt_amount", "loan_customer_individual", "loan_customer_private_business",
            "loan_customer_state_owned", "deposit_customer_individual", "deposit_customer_foreign_business",
            "deposit_customer_private_business",
            "casa", "loan_construction", "loan_real_estate",
            "real_estate_goods", "cash_equiv", "ROE", "ROA", "NIM", "BDR", "excess_return_vs_vnindex",
            "excess_return_vs_vn30", "revenue_yoy", "cogs_yoy", "net_income_yoy",
        ]
        direct_company_metrics = [m for m in direct_company_metrics if m in cq.columns]

        for _, row in cq.iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            for metric in direct_company_metrics:
                if metric in self.STOCK_MARKET_METRICS and not bool(row.get("has_stock_market_data", False)):
                    continue

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
                        reasoning_hops=1 if metric not in {"excess_return_vs_vnindex", "excess_return_vs_vn30", "revenue_yoy", "cogs_yoy", "net_income_yoy"} else 2,
                        extra_info=self._common_metadata(industry=row.get("industry"), benchmark=row.get("benchmark_index")),
                    ))

        out.extend(self._generate_company_yearly_financial_questions(company_yearly))
        out.extend(self._generate_company_trailing_financial_questions(company_trailing))

        # Industry average direct questions.
        for _, row in industry_avg.iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            industry_direct_metrics = list(dict.fromkeys([
                "return_pct",
                "revenue",
                "cogs",
                "net_income",
                *FINANCIAL_INDUSTRY_SHARE_METRICS,
                *BANK_FINANCIAL_INDUSTRY_SHARE_METRICS,
                *CORP_FINANCIAL_INDUSTRY_SHARE_METRICS,
                "real_estate_goods",
                "cash_equiv",
                "ROE",
                "ROA",
                "NIM",
                "BDR",
                "revenue_yoy",
                "cogs_yoy",
                "net_income_yoy",
            ]))
            for metric in industry_direct_metrics:
                
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

        # Daily stock close and EMA questions.
        if not stock_daily.empty:
            stock_daily_records: List[QuestionRecord] = []
            daily_metrics = [m for m in ["daily_close", "ema20", "ema50", "ema200"] if m in stock_daily.columns]
            for _, row in stock_daily.iterrows():
                ask_date, gap = _generate_daily_ask_date(row["date"], self.rng)
                date_text = _date_label(row["date"])
                year = int(row["year"])
                for metric in daily_metrics:
                    value = _safe_float(row.get(metric), 4, metric=metric)
                    if value is None:
                        continue
                    don_vi_str = _get_don_vi(metric)
                    if metric == "daily_close":
                        variants = [
                            f"Giá đóng cửa của {self._company_label(row['stock_code'])} trong năm {year}, {date_text} là bao nhiêu {don_vi_str}?",
                            f"Lấy chỉ số giá của {self._company_label(row['stock_code'])} vào {date_text} năm {year}.",
                        ]
                    else:
                        variants = [
                            f"Chỉ số {_metric_label(metric)} của {self._company_label(row['stock_code'])} vào {date_text} là bao nhiêu {don_vi_str}?",
                            f"Lấy {_metric_label(metric)} theo ngày của {self._company_label(row['stock_code'])} trong năm {year}, {date_text}.",
                        ]
                    for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                        stock_daily_records.append(self._build_record(
                            question_raw=question_text,
                            answer_type="entity",
                            answer=value,
                            family="calculate",
                            subtype=f"company_daily_{metric}",
                            ambiguity="clear",
                            time_asked=ask_date,
                            gap=gap,
                            data_cutoff=ask_date,
                            entities=[row["stock_code"]],
                            metrics=[metric],
                            periods=[row["period_key"]],
                            sources=["stock_daily"],
                            reasoning_hops=1 if metric == "daily_close" else 2,
                            extra_info=self._common_metadata(
                                industry=row.get("industry"),
                                date=str(row["period_key"]),
                                year=year,
                            ),
                        ))
            stock_daily_records.extend(self._generate_ema20_ema200_cross_questions(stock_daily))
            out.extend(self._limit_stock_daily_records(stock_daily_records))

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

    def _generate_ema20_ema200_cross_questions(self, stock_daily: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        required_columns = {"stock_code", "date", "year", "ema20", "ema200", "period_key"}
        if stock_daily.empty or not required_columns.issubset(stock_daily.columns):
            return out

        daily = stock_daily.copy()
        daily["date"] = pd.to_datetime(daily["date"], errors="coerce")
        daily["year"] = pd.to_numeric(daily["year"], errors="coerce")
        daily["ema20"] = pd.to_numeric(daily["ema20"], errors="coerce")
        daily["ema200"] = pd.to_numeric(daily["ema200"], errors="coerce")
        daily = daily.dropna(subset=["stock_code", "date", "year", "ema20", "ema200"])
        if daily.empty:
            return out

        daily = daily.sort_values(["stock_code", "date"])
        daily["ema_diff"] = daily["ema20"] - daily["ema200"]
        daily["ema_sign"] = daily["ema_diff"].apply(lambda value: 1 if value > 0 else (-1 if value < 0 else 0))
        daily = daily[daily["ema_sign"] != 0]
        if daily.empty:
            return out

        daily["prev_ema_sign"] = daily.groupby("stock_code")["ema_sign"].shift(1)
        daily["is_ema_cross"] = daily["prev_ema_sign"].notna() & (daily["ema_sign"] != daily["prev_ema_sign"])

        for (stock_code, year), frame in daily.groupby(["stock_code", "year"]):
            frame = frame.sort_values("date").copy()
            if len(frame) < 2:
                continue

            crosses = frame[frame["is_ema_cross"]].copy()
            cross_count = int(len(crosses))
            year_int = int(year)
            ask_date, gap = _generate_ask_date("quarter", year_int, 4, "market", self.rng)
            variants = [
                f"Trong năm {year_int}, EMA20 cắt EMA200 bao nhiêu lần đối với {self._company_label(stock_code)}?",
                f"Năm {year_int}, số lần EMA20 giao cắt EMA200 của {self._company_label(stock_code)} là bao nhiêu?",
            ]
            cross_events = [
                {
                    "date": row["date"].date().isoformat(),
                    "direction": "bullish" if int(row["ema_sign"]) > 0 else "bearish",
                }
                for _, row in crosses.iterrows()
            ]

            for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                out.append(self._build_record(
                    question_raw=question_text,
                    answer_type="entity",
                    answer=cross_count,
                    family="calculate",
                    subtype="company_yearly_ema20_ema200_cross_count",
                    ambiguity="clear",
                    time_asked=ask_date,
                    gap=gap,
                    data_cutoff=ask_date,
                    entities=[stock_code],
                    metrics=["ema20", "ema200"],
                    periods=[str(year_int)],
                    sources=["stock_daily"],
                    reasoning_hops=3,
                    extra_info=self._common_metadata(
                        industry=frame["industry"].dropna().iloc[0] if "industry" in frame.columns and not frame["industry"].dropna().empty else None,
                        cross_events=cross_events,
                        n_crosses=cross_count,
                        year=year_int,
                    ),
                ))
        return out

    def _generate_company_yearly_financial_questions(self, company_yearly: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        if company_yearly.empty:
            return out

        metrics = [m for m in FINANCIAL_FLOW_METRICS if m in company_yearly.columns]
        for _, row in company_yearly.iterrows():
            if int(row.get("n_quarters", 0)) < 4:
                continue
            year = int(row["year"])
            ask_date, gap = _generate_ask_date("quarter", year, 4, "financial", self.rng)
            for metric in metrics:
                value = _safe_float(row.get(metric), 4, metric=metric)
                if value is None:
                    continue
                don_vi_str = _get_don_vi(metric)
                variants = [
                    f"Tổng {_metric_label(metric)} theo năm {year} của {self._company_label(row['stock_code'], False)} là bao nhiêu {don_vi_str}?",
                    f"Năm {year}, {_metric_label(metric)} cả năm của {self._company_label(row['stock_code'], False)} đạt bao nhiêu {don_vi_str}?",
                ]
                for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                    out.append(self._build_record(
                        question_raw=question_text,
                        answer_type="entity",
                        answer=value,
                        family="calculate",
                        subtype=f"company_yearly_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[row["stock_code"]],
                        metrics=[metric],
                        periods=[row["period_key"]],
                        sources=["company_yearly"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(
                            industry=row.get("industry"),
                            period_basis="year",
                            n_quarters=int(row.get("n_quarters", 0)),
                        ),
                    ))
        return out

    def _generate_company_trailing_financial_questions(self, company_trailing: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        if company_trailing.empty:
            return out

        metrics = [m for m in FINANCIAL_FLOW_METRICS if m in company_trailing.columns]
        for _, row in company_trailing.iterrows():
            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            for metric in metrics:
                value = _safe_float(row.get(metric), 4, metric=metric)
                if value is None:
                    continue
                don_vi_str = _get_don_vi(metric)
                variants = [
                    f"Trailing 4 quarters của {_metric_label(metric)} tính đến {period_text} của {self._company_label(row['stock_code'], False)} là bao nhiêu {don_vi_str}?",
                    f"Tổng {_metric_label(metric)} trong 4 quý gần nhất đến {period_text} của {self._company_label(row['stock_code'], False)} là bao nhiêu {don_vi_str}?",
                ]
                for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                    out.append(self._build_record(
                        question_raw=question_text,
                        answer_type="entity",
                        answer=value,
                        family="calculate",
                        subtype=f"company_trailing_4q_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[row["stock_code"]],
                        metrics=[metric],
                        periods=[row["period_key"]],
                        sources=["company_trailing"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(
                            industry=row.get("industry"),
                            period_basis="trailing_4q",
                            end_period=row["period_key"],
                        ),
                    ))
        return out
