from typing import List

import pandas as pd

from .const import (
    BANK_FINANCIAL_INDUSTRY_SHARE_METRICS,
    CORP_FINANCIAL_INDUSTRY_SHARE_METRICS,
    FINANCIAL_FLOW_METRICS,
    FINANCIAL_INDUSTRY_SHARE_METRICS,
    FINANCIAL_NAMES,
    LINKED_COMMODITY_BY_TICKER,
    REAL_ESTATE_FINANCIAL_INDUSTRY_SHARE_METRICS,
)
from .models import QuestionRecord
from .utils import (
    _choose_distinct,
    _display_commodity,
    _display_industry,
    _generate_ask_date,
    _get_don_vi,
    _is_stock,
    _metric_label,
    _period_key,
    _period_label,
    _safe_float,
)


class CompareQuestionMixin:
    INDUSTRY_SHARE_ALLOWED_INDUSTRIES = {
        "Banking",
        "Retail",
        "Real Estate",
        "Financial Services",
        "Ngân hàng",
        "Bán lẻ",
        "Bất động sản",
        "Dịch vụ Tài chính",
        "Tài chính",
    }

    # -----------------------------------------------------
    # Compare
    # -----------------------------------------------------
    def generate_compare_questions(self) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        cq = self.store["company_quarter"]
        commodity = self.store["commodity_market"]
        industry_avg = self.store["industry_avg_quarter"]
        company_yearly = self.store.get("company_yearly", pd.DataFrame())
        company_half = self.store.get("company_half", pd.DataFrame())

        out.extend(self._generate_industry_vs_industry_questions(industry_avg))
        out.extend(self._generate_yearly_company_vs_company_questions(company_yearly))
        out.extend(self._generate_yearly_same_period_financial_questions(company_yearly))
        out.extend(self._generate_half_vs_half_financial_questions(company_half))
        out.extend(self._generate_half_same_period_financial_questions(company_half))
        if cq.empty:
            return out

        out.extend(self._generate_quarterly_same_period_financial_questions(cq))

        # 1) Same period, company vs company.
        metrics = list(dict.fromkeys([
            m
            for m in [
                "return_pct",
                "ROE",
                "ROA",
                "NIM",
                "BDR",
                "revenue",
                "cogs",
                "net_income",
                *FINANCIAL_INDUSTRY_SHARE_METRICS,
                *BANK_FINANCIAL_INDUSTRY_SHARE_METRICS,
                *CORP_FINANCIAL_INDUSTRY_SHARE_METRICS,
                *REAL_ESTATE_FINANCIAL_INDUSTRY_SHARE_METRICS,
                "cash_equiv",
            ]
            if m in cq.columns
        ]))
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
        period_metrics = list(dict.fromkeys([
            m
            for m in [
                "return_pct",
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
            ]
            if m in cq.columns
        ]))
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
        if not industry_avg.empty and {"industry", "year", "quarter"}.issubset(industry_avg.columns):
            industry_join = cq.merge(
                industry_avg[[c for c in industry_avg.columns if c in {"industry", "year", "quarter", "period_key", "n_stocks"} or c.endswith("_mean")]],
                on=["industry", "year", "quarter"],
                how="left",
                suffixes=("", "_industry"),
            )
            industry_metrics = list(dict.fromkeys([
                m
                for m in [
                    "revenue",
                    "current_assets",
                    "total_assets",
                    "liabilities",
                    "equity",
                    "loan_customer",
                    "customer_deposits",
                    "short_term_borrowings",
                    "long_term_borrowings",
                    "bad_debt_amount",
                    "real_estate_goods",
                    "cash_equiv",
                    "ROE",
                    "ROA",
                    "NIM",
                    "BDR",
                ]
                if m in cq.columns
            ]))
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
            out.extend(self._generate_company_industry_share_questions(industry_join))

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

    def _generate_company_industry_share_questions(self, industry_join: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        if industry_join.empty or "industry" not in industry_join.columns:
            return out

        for _, row in industry_join.dropna(subset=["industry"]).iterrows():
            industry = str(row["industry"])
            if industry not in self.INDUSTRY_SHARE_ALLOWED_INDUSTRIES:
                continue
            share_metrics = FINANCIAL_INDUSTRY_SHARE_METRICS + BANK_FINANCIAL_INDUSTRY_SHARE_METRICS
            if industry not in {"Banking", "Ngân hàng", "Financial Services", "Dịch vụ Tài chính", "Tài chính"}:
                share_metrics = share_metrics + CORP_FINANCIAL_INDUSTRY_SHARE_METRICS
            if industry in {"Real Estate", "Bất động sản"}:
                share_metrics = share_metrics + REAL_ESTATE_FINANCIAL_INDUSTRY_SHARE_METRICS

            try:
                n_stocks = int(row.get("n_stocks"))
            except Exception:
                continue
            if n_stocks <= 0:
                continue

            year, quarter = int(row["year"]), int(row["quarter"])
            ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
            period_text = _period_label("quarter", quarter, year)
            industry_name_vn = _display_industry(industry)
            for metric in share_metrics:
                if metric not in industry_join.columns:
                    continue
                company_val = _safe_float(row.get(metric), 4, metric=metric)
                industry_mean = _safe_float(row.get(f"{metric}_mean"), 4, metric=metric)
                if company_val is None or industry_mean is None:
                    continue
                industry_total = _safe_float(industry_mean * n_stocks, 4, metric=metric)
                if industry_total is None or industry_total == 0:
                    continue
                share_pct = _safe_float(company_val / industry_total * 100.0, 4)
                if share_pct is None:
                    continue

                variants = [
                    f"Trong {period_text}, {_metric_label(metric)} của {self._company_label(row['stock_code'], False)} chiếm bao nhiêu phần trăm so với toàn ngành {industry_name_vn}?",
                    f"Tỷ lệ {_metric_label(metric)} của {self._company_label(row['stock_code'], False)} so với tổng ngành {industry_name_vn} trong {period_text} là bao nhiêu phần trăm?",
                ]
                for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                    out.append(self._build_record(
                        question_raw=question_text,
                        answer_type="entity",
                        answer=share_pct,
                        family="compare",
                        subtype=f"company_vs_industry_total_share_pct_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[row["stock_code"], industry],
                        metrics=[metric],
                        periods=[row["period_key"]],
                        sources=["company_quarter", "industry_avg_quarter"],
                        reasoning_hops=3,
                        extra_info=self._common_metadata(
                            company_value=company_val,
                            industry_mean=industry_mean,
                            industry_total=industry_total,
                            n_stocks=n_stocks,
                            industry=industry,
                            calculation="company_value / (industry_mean * n_stocks) * 100",
                        ),
                    ))
        return out

    def _generate_industry_vs_industry_questions(self, industry_avg: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        if industry_avg.empty or not {"industry", "year", "quarter"}.issubset(industry_avg.columns):
            return out

        metrics = [
            m
            for m in ["revenue", "cogs", "net_income", "ROE", "ROA", "NIM", "BDR", "revenue_yoy", "cogs_yoy", "net_income_yoy"]
            if f"{m}_mean" in industry_avg.columns or m in industry_avg.columns
        ]
        if not metrics:
            return out

        for (year, quarter), frame in industry_avg.dropna(subset=["industry"]).groupby(["year", "quarter"], dropna=False):
            industries = frame["industry"].dropna().astype(str).unique().tolist()
            if len(industries) < 2:
                continue
            ask_date, gap = _generate_ask_date("quarter", int(year), int(quarter), "financial", self.rng)
            period_text = _period_label("quarter", int(quarter), int(year))
            pairs = (
                [(industries[i], industries[j]) for i in range(len(industries)) for j in range(i + 1, len(industries))]
                if len(industries) <= 12
                else [tuple(self.rng.sample(industries, 2)) for _ in range(min(40, len(industries)))]
            )
            for industry_a, industry_b in pairs:
                row_a = frame[frame["industry"] == industry_a].iloc[0]
                row_b = frame[frame["industry"] == industry_b].iloc[0]
                for metric in metrics:
                    col = f"{metric}_mean" if f"{metric}_mean" in frame.columns else metric
                    value_a = _safe_float(row_a.get(col), 4, metric=metric)
                    value_b = _safe_float(row_b.get(col), 4, metric=metric)
                    if value_a is None or value_b is None:
                        continue
                    don_vi_str = _get_don_vi(metric)
                    out.append(self._build_record(
                        question_raw=f"Trong {period_text}, ngành nào có {_metric_label(metric)} trung bình cao hơn giữa ngành {_display_industry(industry_a)} và ngành {_display_industry(industry_b)}?",
                        answer_type="entity",
                        answer=industry_a if value_a >= value_b else industry_b,
                        family="compare",
                        subtype=f"industry_vs_industry_winner_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[industry_a, industry_b],
                        metrics=[metric],
                        periods=[_period_key("quarter", int(year), int(quarter))],
                        sources=["industry_avg_quarter"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(value_a=value_a, value_b=value_b, aggregate="mean"),
                    ))
                    out.append(self._build_record(
                        question_raw=f"Trong {period_text}, {_metric_label(metric)} trung bình của ngành {_display_industry(industry_a)} chênh ngành {_display_industry(industry_b)} bao nhiêu {don_vi_str}?",
                        answer_type="entity",
                        answer=_safe_float(value_a - value_b, 4),
                        family="compare",
                        subtype=f"industry_vs_industry_diff_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[industry_a, industry_b],
                        metrics=[metric],
                        periods=[_period_key("quarter", int(year), int(quarter))],
                        sources=["industry_avg_quarter"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(value_a=value_a, value_b=value_b, aggregate="mean"),
                    ))
        return out

    def _generate_yearly_company_vs_company_questions(self, company_yearly: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        if company_yearly.empty:
            return out

        metrics = [m for m in FINANCIAL_FLOW_METRICS if m in company_yearly.columns]
        if not metrics:
            return out

        complete = company_yearly[company_yearly["n_quarters"] >= 4].copy()
        for year, frame in complete.groupby("year", dropna=False):
            codes = frame["stock_code"].dropna().astype(str).unique().tolist()
            if len(codes) < 2:
                continue
            ask_date, gap = _generate_ask_date("quarter", int(year), 4, "financial", self.rng)
            pairs = (
                [(codes[i], codes[j]) for i in range(len(codes)) for j in range(i + 1, len(codes))]
                if len(codes) <= 16
                else [tuple(self.rng.sample(codes, 2)) for _ in range(min(50, len(codes)))]
            )
            for stock_a, stock_b in pairs:
                row_a = frame[frame["stock_code"] == stock_a].iloc[0]
                row_b = frame[frame["stock_code"] == stock_b].iloc[0]
                for metric in metrics:
                    value_a = _safe_float(row_a.get(metric), 4, metric=metric)
                    value_b = _safe_float(row_b.get(metric), 4, metric=metric)
                    if value_a is None or value_b is None:
                        continue
                    don_vi_str = _get_don_vi(metric)
                    out.append(self._build_record(
                        question_raw=f"Năm {int(year)}, {_metric_label(metric)} cả năm của {self._company_label(stock_a, False)} chênh {self._company_label(stock_b, False)} bao nhiêu {don_vi_str}?",
                        answer_type="entity",
                        answer=_safe_float(value_a - value_b, 4),
                        family="compare",
                        subtype=f"company_vs_company_yearly_diff_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[stock_a, stock_b],
                        metrics=[metric],
                        periods=[row_a["period_key"], row_b["period_key"]],
                        sources=["company_yearly"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(value_a=value_a, value_b=value_b, period_basis="year"),
                    ))
        return out

    def _generate_quarterly_same_period_financial_questions(self, cq: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        if cq.empty:
            return out

        metrics = [m for m in FINANCIAL_NAMES.keys() if m in cq.columns]
        if not metrics:
            return out

        for stock_code, frame in cq.groupby("stock_code", dropna=False):
            frame = frame.sort_values(["year", "quarter"]).copy()
            for _, cur in frame.iterrows():
                year, quarter = int(cur["year"]), int(cur["quarter"])
                prev_match = frame[(frame["year"] == year - 1) & (frame["quarter"] == quarter)]
                if prev_match.empty:
                    continue
                prev = prev_match.iloc[0]
                ask_date, gap = _generate_ask_date("quarter", year, quarter, "financial", self.rng)
                cur_period = _period_label("quarter", quarter, year)
                prev_period = _period_label("quarter", quarter, year - 1)
                for metric in metrics:
                    cur_value = _safe_float(cur.get(metric), 4, metric=metric)
                    prev_value = _safe_float(prev.get(metric), 4, metric=metric)
                    if cur_value is None or prev_value is None:
                        continue
                    don_vi_str = _get_don_vi(metric)
                    diff = _safe_float(cur_value - prev_value, 4)
                    yoy_value = _safe_float(cur.get(f"{metric}_yoy"), 4, metric=f"{metric}_yoy")
                    variants = [
                        f"{_metric_label(metric).capitalize()} của {self._company_label(stock_code, False)} trong {cur_period} so với cùng kỳ {prev_period} chênh lệch bao nhiêu {don_vi_str}?",
                        f"So sánh {_metric_label(metric)} của {self._company_label(stock_code, False)} ở {cur_period} với cùng kỳ {prev_period}, mức chênh là bao nhiêu {don_vi_str}?",
                    ]
                    for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                        out.append(self._build_record(
                            question_raw=question_text,
                            answer_type="entity",
                            answer=diff,
                            family="compare",
                            subtype=f"company_same_period_quarter_diff_{metric}",
                            ambiguity="clear",
                            time_asked=ask_date,
                            gap=gap,
                            data_cutoff=ask_date,
                            entities=[stock_code],
                            metrics=[metric],
                            periods=[prev["period_key"], cur["period_key"]],
                            sources=["company_quarter"],
                            reasoning_hops=2,
                            extra_info=self._common_metadata(
                                current=cur_value,
                                same_period_previous_year=prev_value,
                                yoy_pct=yoy_value,
                                period_basis="quarter",
                                current_period=cur["period_key"],
                                comparison_period=prev["period_key"],
                                industry=cur.get("industry"),
                            ),
                        ))
        return out

    def _generate_yearly_same_period_financial_questions(self, company_yearly: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        if company_yearly.empty:
            return out

        metrics = [m for m in FINANCIAL_FLOW_METRICS if m in company_yearly.columns]
        if not metrics:
            return out

        complete = company_yearly[company_yearly["n_quarters"] >= 4].copy()
        for stock_code, frame in complete.groupby("stock_code", dropna=False):
            frame = frame.sort_values("year")
            for _, cur in frame.iterrows():
                year = int(cur["year"])
                prev_match = frame[frame["year"] == year - 1]
                if prev_match.empty:
                    continue
                prev = prev_match.iloc[0]
                ask_date, gap = _generate_ask_date("quarter", year, 4, "financial", self.rng)
                for metric in metrics:
                    cur_value = _safe_float(cur.get(metric), 4, metric=metric)
                    prev_value = _safe_float(prev.get(metric), 4, metric=metric)
                    if cur_value is None or prev_value is None:
                        continue
                    don_vi_str = _get_don_vi(metric)
                    diff = _safe_float(cur_value - prev_value, 4)
                    yoy_value = _safe_float(cur.get(f"{metric}_yoy"), 4, metric=f"{metric}_yoy")
                    variants = [
                        f"{_metric_label(metric).capitalize()} cả năm {year} của {self._company_label(stock_code, False)} so với cùng kỳ năm {year - 1} chênh lệch bao nhiêu {don_vi_str}?",
                        f"So sánh {_metric_label(metric)} theo năm của {self._company_label(stock_code, False)} ở năm {year} với cùng kỳ năm {year - 1}, chênh bao nhiêu {don_vi_str}?",
                    ]
                    for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                        out.append(self._build_record(
                            question_raw=question_text,
                            answer_type="entity",
                            answer=diff,
                            family="compare",
                            subtype=f"company_same_period_year_diff_{metric}",
                            ambiguity="clear",
                            time_asked=ask_date,
                            gap=gap,
                            data_cutoff=ask_date,
                            entities=[stock_code],
                            metrics=[metric],
                            periods=[prev["period_key"], cur["period_key"]],
                            sources=["company_yearly"],
                            reasoning_hops=2,
                            extra_info=self._common_metadata(
                                current=cur_value,
                                same_period_previous_year=prev_value,
                                yoy_pct=yoy_value,
                                period_basis="year",
                                current_period=cur["period_key"],
                                comparison_period=prev["period_key"],
                                industry=cur.get("industry"),
                            ),
                        ))
        return out

    def _generate_half_vs_half_financial_questions(self, company_half: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        if company_half.empty:
            return out

        metrics = [m for m in FINANCIAL_FLOW_METRICS if m in company_half.columns]
        if not metrics:
            return out

        for (stock_code, year), frame in company_half.groupby(["stock_code", "year"], dropna=False):
            h1 = frame[(frame["half"] == 1) & (frame["n_quarters"] >= 2)]
            h2 = frame[(frame["half"] == 2) & (frame["n_quarters"] >= 2)]
            if h1.empty or h2.empty:
                continue

            h1_row = h1.iloc[0]
            h2_row = h2.iloc[0]
            ask_date, gap = _generate_ask_date("quarter", int(year), 4, "financial", self.rng)
            for metric in metrics:
                h1_value = _safe_float(h1_row.get(metric), 4, metric=metric)
                h2_value = _safe_float(h2_row.get(metric), 4, metric=metric)
                if h1_value is None or h2_value is None:
                    continue
                don_vi_str = _get_don_vi(metric)
                diff = _safe_float(h2_value - h1_value, 4)
                variants = [
                    f"Nửa cuối năm {int(year)} so với nửa đầu năm, {_metric_label(metric)} của {self._company_label(stock_code, False)} chênh lệch bao nhiêu {don_vi_str}?",
                    f"{_metric_label(metric).capitalize()} của {self._company_label(stock_code, False)} trong H2 năm {int(year)} chênh H1 bao nhiêu {don_vi_str}?",
                ]
                for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                    out.append(self._build_record(
                        question_raw=question_text,
                        answer_type="entity",
                        answer=diff,
                        family="compare",
                        subtype=f"company_h2_vs_h1_diff_{metric}",
                        ambiguity="clear",
                        time_asked=ask_date,
                        gap=gap,
                        data_cutoff=ask_date,
                        entities=[stock_code],
                        metrics=[metric],
                        periods=[h1_row["period_key"], h2_row["period_key"]],
                        sources=["company_half"],
                        reasoning_hops=2,
                        extra_info=self._common_metadata(
                            first_half=h1_value,
                            second_half=h2_value,
                            period_basis="half",
                            first_half_quarters="Q1+Q2",
                            second_half_quarters="Q3+Q4",
                            industry=h2_row.get("industry"),
                        ),
                    ))
        return out

    def _generate_half_same_period_financial_questions(self, company_half: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        if company_half.empty:
            return out

        metrics = [m for m in FINANCIAL_FLOW_METRICS if m in company_half.columns]
        if not metrics:
            return out

        complete = company_half[company_half["n_quarters"] >= 2].copy()
        for (stock_code, half), frame in complete.groupby(["stock_code", "half"], dropna=False):
            frame = frame.sort_values("year")
            for _, cur in frame.iterrows():
                year = int(cur["year"])
                half_value = int(cur["half"])
                prev_match = frame[frame["year"] == year - 1]
                if prev_match.empty:
                    continue
                prev = prev_match.iloc[0]
                ask_date, gap = _generate_ask_date("quarter", year, 2 if half_value == 1 else 4, "financial", self.rng)
                cur_label = f"H{half_value} năm {year}"
                prev_label = f"H{half_value} năm {year - 1}"
                for metric in metrics:
                    cur_value = _safe_float(cur.get(metric), 4, metric=metric)
                    prev_value = _safe_float(prev.get(metric), 4, metric=metric)
                    if cur_value is None or prev_value is None:
                        continue
                    don_vi_str = _get_don_vi(metric)
                    diff = _safe_float(cur_value - prev_value, 4)
                    variants = [
                        f"{_metric_label(metric).capitalize()} của {self._company_label(stock_code, False)} trong {cur_label} so với cùng kỳ {prev_label} chênh lệch bao nhiêu {don_vi_str}?",
                        f"So sánh {_metric_label(metric)} của {self._company_label(stock_code, False)} ở {cur_label} với cùng kỳ {prev_label}, mức chênh là bao nhiêu {don_vi_str}?",
                    ]
                    for question_text in _choose_distinct(variants, min(len(variants), self.config.paraphrase_per_candidate), self.rng):
                        out.append(self._build_record(
                            question_raw=question_text,
                            answer_type="entity",
                            answer=diff,
                            family="compare",
                            subtype=f"company_same_period_half_diff_{metric}",
                            ambiguity="clear",
                            time_asked=ask_date,
                            gap=gap,
                            data_cutoff=ask_date,
                            entities=[stock_code],
                            metrics=[metric],
                            periods=[prev["period_key"], cur["period_key"]],
                            sources=["company_half"],
                            reasoning_hops=2,
                            extra_info=self._common_metadata(
                                current=cur_value,
                                same_period_previous_year=prev_value,
                                period_basis="half",
                                quarter_range=cur.get("quarter_range"),
                                current_period=cur["period_key"],
                                comparison_period=prev["period_key"],
                                industry=cur.get("industry"),
                            ),
                        ))
        return out
