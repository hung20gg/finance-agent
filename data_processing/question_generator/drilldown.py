from typing import List

import pandas as pd

from .const import (
    BANK_FINANCIAL_INDUSTRY_SHARE_METRICS,
    CORP_FINANCIAL_INDUSTRY_SHARE_METRICS,
    FINANCIAL_INDUSTRY_SHARE_METRICS,
    REAL_ESTATE_FINANCIAL_INDUSTRY_SHARE_METRICS,
)
from .models import QuestionRecord
from .utils import (
    _display_industry,
    _generate_ask_date,
    _is_stock,
    _metric_label,
    _period_key,
    _period_label,
    _safe_float,
    _to_answer_values,
    _to_period_list,
)


class DrilldownQuestionMixin:
    STOCK_MARKET_METRICS = {
        "return_pct",
    }

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
        out.extend(self._generate_company_best_worst_quarter_questions(cq))
        out.extend(self._generate_time_range_listing_questions(cq))
        out.extend(self._generate_visualize_questions(cq))
        return out

    def _generate_company_best_worst_quarter_questions(self, cq: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        if cq.empty:
            return out

        metrics = list(dict.fromkeys([
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
        if not metrics:
            return out

        for (stock_code, year), frame in cq.groupby(["stock_code", "year"], dropna=False):
            frame = frame.sort_values("quarter").copy()
            if frame["quarter"].nunique() < 2:
                continue
            ask_date, gap = _generate_ask_date("quarter", int(year), int(frame["quarter"].max()), "financial", self.rng)
            for metric in metrics:
                sub = frame[["period_key", "quarter", metric]].dropna().copy()
                sub[metric] = pd.to_numeric(sub[metric], errors="coerce")
                sub = sub.dropna(subset=[metric])
                if sub["quarter"].nunique() < 4:
                    continue
                best = sub.sort_values(metric, ascending=False).iloc[0]
                worst = sub.sort_values(metric, ascending=True).iloc[0]
                for mode, row, sort_order, label in [
                    ("best", best, "desc", "cao nhất"),
                    ("worst", worst, "asc", "thấp nhất"),
                ]:
                    out.append(self._build_record(
                        question_raw=f"Trong năm {int(year)}, quý nào của {self._company_label(stock_code, _is_stock(metric))} có {_metric_label(metric)} {label}?",
                        answer_type="entity",
                        answer=str(row["period_key"]),
                        family="drill_down",
                        subtype=f"company_{mode}_quarter_in_year_{metric}",
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
                            request_mode="best_worst_period",
                            period_basis="quarter_in_year",
                            year=int(year),
                            selected_period=str(row["period_key"]),
                            selected_value=_safe_float(row[metric], 4, metric=metric),
                            sort_metric=metric,
                            sort_order=sort_order,
                            industry=frame.iloc[-1].get("industry"),
                        ),
                    ))
        return out

    def _generate_industry_top_questions(self, cq: pd.DataFrame) -> List[QuestionRecord]:
        out: List[QuestionRecord] = []
        if cq.empty or "industry" not in cq.columns:
            return out

        metrics = list(dict.fromkeys([
            m
            for m in [
                "net_income",
                "cogs",
                *FINANCIAL_INDUSTRY_SHARE_METRICS,
                *BANK_FINANCIAL_INDUSTRY_SHARE_METRICS,
                *CORP_FINANCIAL_INDUSTRY_SHARE_METRICS,
                *REAL_ESTATE_FINANCIAL_INDUSTRY_SHARE_METRICS,
                "cash_equiv",
                "ROE",
                "ROA",
                "NIM",
            ]
            if m in cq.columns
        ]))
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
                        metric: _to_answer_values(ans_df[metric], metric),
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
                        metric: _to_answer_values(ans_df[metric], metric),
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
                            metric: _to_answer_values(ans_df[metric], metric),
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

                time_range_metrics = list(dict.fromkeys([
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
                ]))
                for metric in time_range_metrics:
                    if metric in self.STOCK_MARKET_METRICS and not sub["has_stock_market_data"].eq(True).any():
                        continue

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
                stock_sub = sub[sub["has_stock_market_data"].eq(True)].copy()
                answer_payload = _to_period_list(stock_sub.dropna(subset=["return_pct", "benchmark_return_pct"]), value_cols=["return_pct", "benchmark_return_pct"])
                if answer_payload:
                    benchmark_name = str(last.get("benchmark_index", "VNINDEX"))
                    out.append(self._build_record(
                        question_raw=f"Liệt kê tỷ suất sinh lời theo từng quý của mã cổ phiếu {self._company_label(stock_code)} và {benchmark_name} từ {start_label} đến {end_label}.",
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
                        
                        valid_rows = ind_sub.dropna(subset=["ROE"]) if "ROE" in ind_sub.columns else pd.DataFrame()
                        if not valid_rows.empty and ind_avg_df is not None and not ind_avg_df.empty:
                            mean_col = "ROE_mean" if "ROE_mean" in ind_avg_df.columns else "ROE"
                            ind_avg_sub = ind_avg_df[
                                (ind_avg_df["industry"] == ind_name)
                                & (ind_avg_df["period_key"].isin(valid_rows["period_key"]))
                            ][["period_key", mean_col]].dropna()
                            merged = valid_rows[["period_key", "ROE"]].merge(
                                ind_avg_sub.rename(columns={mean_col: "industry_mean_ROE"}),
                                on="period_key",
                                how="inner",
                            )
                            if not merged.empty:
                                answer_payload = {
                                    "period_key": merged["period_key"].astype(str).tolist(),
                                    "company_ROE": _to_answer_values(merged["ROE"], "ROE"),
                                    "industry_mean_ROE": _to_answer_values(merged["industry_mean_ROE"], "ROE"),
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
            visualize_metrics = list(dict.fromkeys([
                "return_pct",
                "ROE",
                "ROA",
                "net_income",
                "cogs",
                *FINANCIAL_INDUSTRY_SHARE_METRICS,
                *BANK_FINANCIAL_INDUSTRY_SHARE_METRICS,
                *CORP_FINANCIAL_INDUSTRY_SHARE_METRICS,
                *REAL_ESTATE_FINANCIAL_INDUSTRY_SHARE_METRICS,
                "cash_equiv",
            ]))
            for metric in visualize_metrics:
                metric_frame = frame
                if metric in self.STOCK_MARKET_METRICS:
                    metric_frame = frame[frame["has_stock_market_data"].eq(True)]

                if metric not in metric_frame.columns or metric_frame[metric].dropna().empty:
                    continue
                sub_df = metric_frame[["stock_code", metric]].dropna().copy()
                sub_df[metric] = pd.to_numeric(sub_df[metric], errors="coerce")
                sub_df = sub_df.dropna(subset=[metric]).sort_values(metric, ascending=False).head(10)
                if sub_df.empty:
                    continue
                ans_payload = {
                    "stock_code": sub_df["stock_code"].astype(str).tolist(),
                    metric: _to_answer_values(sub_df[metric], metric),
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
            latest = latest[latest["has_stock_market_data"].eq(True)]
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
        ind_avg_df = self.store.get("industry_avg_quarter")
        for (year, quarter), frame in cq.dropna(subset=["industry"]).groupby(["year", "quarter"], dropna=False):
            if len(frame) < 10:
                continue
            ask_date, gap = _generate_ask_date("quarter", int(year), int(quarter), "financial", self.rng)
            period_key = _period_key("quarter", int(year), int(quarter))
            scatter_metrics = list(dict.fromkeys([
                "ROE",
                "ROA",
                "return_pct",
                *FINANCIAL_INDUSTRY_SHARE_METRICS,
                *BANK_FINANCIAL_INDUSTRY_SHARE_METRICS,
                *CORP_FINANCIAL_INDUSTRY_SHARE_METRICS,
                *REAL_ESTATE_FINANCIAL_INDUSTRY_SHARE_METRICS,
                "cash_equiv",
            ]))
            for metric in scatter_metrics:
                metric_frame = frame
                if metric in self.STOCK_MARKET_METRICS:
                    metric_frame = frame[frame["has_stock_market_data"].eq(True)]

                if metric not in metric_frame.columns or metric_frame[metric].dropna().empty:
                    continue
                if ind_avg_df is None or ind_avg_df.empty:
                    continue
                mean_col = f"{metric}_mean" if f"{metric}_mean" in ind_avg_df.columns else metric
                if mean_col not in ind_avg_df.columns:
                    continue
                ind_means = ind_avg_df[
                    (ind_avg_df["year"] == year)
                    & (ind_avg_df["quarter"] == quarter)
                ][["industry", mean_col]].dropna()
                sub_df = metric_frame[["stock_code", "industry", metric]].dropna().merge(
                    ind_means.rename(columns={mean_col: f"industry_mean_{metric}"}),
                    on="industry",
                    how="inner",
                )
                if sub_df.empty:
                    continue
                ans_payload = {
                    "stock_code": sub_df["stock_code"].astype(str).tolist(),
                    "industry": sub_df["industry"].astype(str).tolist(),
                    f"company_{metric}": _to_answer_values(sub_df[metric], metric),
                    f"industry_mean_{metric}": _to_answer_values(sub_df[f"industry_mean_{metric}"], metric),
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
