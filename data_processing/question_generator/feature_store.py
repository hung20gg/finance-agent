from __future__ import annotations

from typing import Any, Dict, List, Sequence

import numpy as np
import pandas as pd

from .const import (
    CORP_FINANCIAL_INDUSTRY_SHARE_METRICS,
    FINANCIAL_CATEGORY_MAP,
    FINANCIAL_DERIVED_SUM_MAP,
    FINANCIAL_FLOW_METRICS,
    FINANCIAL_INDUSTRY_SHARE_METRICS,
    BANK_FINANCIAL_INDUSTRY_SHARE_METRICS,
    FINANCIAL_NAMES,
    INDUSTRY_VN,
    MACRO_METRIC_MAP,
    PEER_GROUPS,
    RATIO_NAMES,
    REAL_ESTATE_FINANCIAL_INDUSTRY_SHARE_METRICS,
    VN30_TICKERS,
)
from .generator import GeneratorConfig


MARKET_PERIOD_COLUMNS = [
    "entity",
    "period_type",
    "year",
    "time_val",
    "avg_close",
    "std_close",
    "std_daily_return",
    "n_obs",
    "end_close",
    "start_close",
    "return_pct",
    "period_key",
]


def _safe_float(value: Any, ndigits: int = 4):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
        return round(float(value), ndigits)
    except Exception:
        return None


def _display_industry(industry: str) -> str:
    return INDUSTRY_VN.get(industry, industry)


def _period_key(period_type: str, year: int, time_val: int) -> str:
    prefix = "Q" if period_type == "quarter" else "M"
    return f"{year}-{prefix}{time_val}"


class FeatureStoreBuilder:
    """Tạo các bảng trung gian để generator sinh câu hỏi.

    Thay đổi chính của bản này:
    1. Bỏ hoàn toàn _build_industry_avg_quarter(company_quarter).
    2. Industry benchmark được lấy trực tiếp từ:
       - financial_statement WHERE segment='industry'
       - financial_ratio WHERE segment='industry'
    3. Trong các bảng trên, stock_code chính là tên ngành.
    """

    def __init__(self, loader, config: GeneratorConfig):
        self.loader = loader
        self.config = config

    def build(self) -> Dict[str, pd.DataFrame]:
        stock_codes = self.loader.fetch_stock_universe()
        company_info = self.loader.fetch_company_info(stock_codes)
        stock_codes = self._filter_stock_codes_with_company_info(stock_codes, company_info)
        commodity_names = self.config.commodity_allowlist or self.loader.fetch_distinct_commodities()

        stock_market = self._ensure_market_period_columns(
            self.loader.fetch_market_period_features(
                table_name="stock_daily",
                entity_col="stock_code",
                value_col="close",
                allowed_names=stock_codes,
                price_multiplier=1000.0,
            )
        )
        stock_daily = self._prepare_stock_daily(
            self.loader.fetch_stock_daily_prices(
                stock_codes=stock_codes,
                price_multiplier=1000.0,
            ),
            company_info=company_info,
        )
        index_market = self._ensure_market_period_columns(
            self.loader.fetch_market_period_features(
                table_name="indices_daily",
                entity_col="index_name",
                value_col="close",
                allowed_names=self.config.index_names,
                price_multiplier=1.0,
            )
        )
        commodity_market = self._ensure_market_period_columns(
            self.loader.fetch_market_period_features(
                table_name="commodities_daily",
                entity_col="indicator_name",
                value_col="value",
                allowed_names=commodity_names,
                price_multiplier=1.0,
            )
        )
        financial_raw = self.loader.fetch_financial_statement()
        ratio_raw = self.loader.fetch_financial_ratio()
        macro_raw = self.loader.fetch_macro()

        financial_company, financial_industry = self._prepare_financials(financial_raw)
        ratio_company, ratio_industry = self._prepare_ratios(ratio_raw)
        financial_company = self._filter_company_frame(financial_company, stock_codes)
        ratio_company = self._filter_company_frame(ratio_company, stock_codes)
        financial_trailing = self._build_trailing_financial(financial_company, group_col="stock_code")
        financial_yearly = self._build_yearly_financial(financial_company, group_col="stock_code")
        financial_half = self._build_half_financial(financial_company, group_col="stock_code")
        industry_avg_trailing = self._build_trailing_financial(financial_industry, group_col="industry")
        macro_yearly = self._prepare_macro_long(macro_raw)
        macro_quarter = self._prepare_macro(macro_yearly)

        company_quarter = self._build_company_quarter(
            stock_market=stock_market,
            financial_company=financial_company,
            ratio_company=ratio_company,
            index_market=index_market,
            macro_quarter=macro_quarter,
            company_info=company_info,
        )
        company_trailing = self._build_company_trailing(
            stock_market=stock_market,
            financial_trailing=financial_trailing,
            index_market=index_market,
            company_info=company_info,
        )
        company_yearly = self._merge_company_info(financial_yearly, company_info)
        company_half = self._merge_company_info(financial_half, company_info)
        company_month = self._build_company_month(stock_market, index_market, company_info)
        industry_avg_quarter = self._merge_industry_quarter(financial_industry, ratio_industry, company_info)
        peer_rollups = self._build_peer_rollups(company_quarter)

        return {
            "company_info": company_info,
            "stock_daily": stock_daily,
            "stock_market": stock_market,
            "index_market": index_market,
            "commodity_market": commodity_market,
            "financial_company": financial_company,
            "financial_trailing": financial_trailing,
            "financial_yearly": financial_yearly,
            "financial_half": financial_half,
            "ratio_company": ratio_company,
            "financial_industry": financial_industry,
            "ratio_industry": ratio_industry,
            "industry_avg_quarter": industry_avg_quarter,
            "industry_avg_trailing": industry_avg_trailing,
            "macro_quarter": macro_quarter,
            "macro_yearly": macro_yearly,
            "macro_quarter_long": macro_yearly,
            "company_quarter": company_quarter,
            "company_trailing": company_trailing,
            "company_yearly": company_yearly,
            "company_half": company_half,
            "company_month": company_month,
            "peer_rollups": peer_rollups,
        }

    @staticmethod
    def _filter_stock_codes_with_company_info(stock_codes: Sequence[str], company_info: pd.DataFrame) -> List[str]:
        if not stock_codes or company_info.empty or "stock_code" not in company_info.columns:
            return []

        available_codes = set(company_info["stock_code"].dropna().astype(str))
        return [str(code) for code in stock_codes if str(code) in available_codes]

    @staticmethod
    def _filter_company_frame(df: pd.DataFrame, stock_codes: Sequence[str]) -> pd.DataFrame:
        if df.empty or "stock_code" not in df.columns:
            return df

        allowed_codes = set(str(code) for code in stock_codes)
        if not allowed_codes:
            return df.iloc[0:0].copy()

        return df[df["stock_code"].astype(str).isin(allowed_codes)].copy()

    @staticmethod
    def _ensure_market_period_columns(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        for column in MARKET_PERIOD_COLUMNS:
            if column not in out.columns:
                out[column] = pd.Series(dtype="object")
        return out

    def _prepare_stock_daily(self, df: pd.DataFrame, company_info: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(
                columns=[
                    "stock_code",
                    "date",
                    "year",
                    "daily_close",
                    "ema20",
                    "ema50",
                    "ema200",
                    "period_key",
                    "industry",
                    "industry_name_vn",
                ],
            )

        out = df.sort_values(["stock_code", "date"]).copy()
        out["date"] = pd.to_datetime(out["date"]).dt.date
        out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
        out["daily_close"] = pd.to_numeric(out["daily_close"], errors="coerce")

        for span in [20, 50, 200]:
            out[f"ema{span}"] = (
                out.groupby("stock_code")["daily_close"]
                .transform(lambda x: x.ewm(span=span, adjust=False, min_periods=span).mean())
            )

        out["period_key"] = out["date"].astype(str)
        if not company_info.empty and "stock_code" in company_info.columns:
            out = out.merge(company_info, on="stock_code", how="left")
            out["industry_name_vn"] = out["industry"].map(_display_industry)
            bank_mask = out["is_bank"].eq(True) if "is_bank" in out.columns else pd.Series(False, index=out.index)
            if "cogs" in out.columns:
                out.loc[bank_mask, "cogs"] = np.nan
            if "cogs_yoy" in out.columns:
                out.loc[bank_mask, "cogs_yoy"] = np.nan
        else:
            out["industry"] = None
            out["industry_name_vn"] = None
        return out

    def _prepare_financials(self, df: pd.DataFrame):
        if df.empty:
            return pd.DataFrame(), pd.DataFrame()

        df = df.copy()
        df["metric_name"] = df["category_code"].map(FINANCIAL_CATEGORY_MAP)
        df = df.dropna(subset=["metric_name"])

        company = df[df["segment"].fillna("").str.lower() != "industry"].copy()
        company_wide = company.pivot_table(
            index=["stock_code", "year", "quarter", "segment"],
            columns="metric_name",
            values="data",
            aggfunc="first",
        ).reset_index()
        company_wide = self._add_derived_sum_metrics(company_wide)
        company_wide = self._add_yoy_qoq(company_wide, group_col="stock_code", metrics=list(FINANCIAL_NAMES.keys()))

        industry = df[df["segment"].fillna("").str.lower() == "industry"].copy()
        industry = industry.rename(columns={"stock_code": "industry"})
        if industry.empty:
            industry_wide = pd.DataFrame()
        else:
            industry_wide = industry.pivot_table(
                index=["industry", "year", "quarter"],
                columns="metric_name",
                values="data",
                aggfunc="first",
            ).reset_index()
            industry_wide = self._add_derived_sum_metrics(industry_wide)
            industry_wide = self._add_yoy_qoq(industry_wide, group_col="industry", metrics=list(FINANCIAL_NAMES.keys()))
            industry_wide["industry_name_vn"] = industry_wide["industry"].map(_display_industry)
            industry_wide["period_key"] = industry_wide.apply(lambda r: _period_key("quarter", int(r["year"]), int(r["quarter"])), axis=1)

        return company_wide, industry_wide

    def _add_derived_sum_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        out = df.copy()
        for metric, source_metrics in FINANCIAL_DERIVED_SUM_MAP.items():
            available = [source for source in source_metrics if source in out.columns]
            if available:
                out[metric] = out[available].sum(axis=1, min_count=1)
        return out

    def _prepare_ratios(self, df: pd.DataFrame):
        if df.empty:
            return pd.DataFrame(), pd.DataFrame()

        company = df[df["segment"].fillna("").str.lower() != "industry"].copy()
        company_wide = company.pivot_table(
            index=["stock_code", "year", "quarter", "segment"],
            columns="ratio_code",
            values="data",
            aggfunc="first",
        ).reset_index()
        company_wide = self._add_yoy_qoq(company_wide, group_col="stock_code", metrics=list(RATIO_NAMES.keys()))

        industry = df[df["segment"].fillna("").str.lower() == "industry"].copy()
        industry = industry.rename(columns={"stock_code": "industry"})
        if industry.empty:
            industry_wide = pd.DataFrame()
        else:
            industry_wide = industry.pivot_table(
                index=["industry", "year", "quarter"],
                columns="ratio_code",
                values="data",
                aggfunc="first",
            ).reset_index()
            industry_wide = self._add_yoy_qoq(industry_wide, group_col="industry", metrics=list(RATIO_NAMES.keys()))
            industry_wide["industry_name_vn"] = industry_wide["industry"].map(_display_industry)
            industry_wide["period_key"] = industry_wide.apply(lambda r: _period_key("quarter", int(r["year"]), int(r["quarter"])), axis=1)

        return company_wide, industry_wide

    def _merge_industry_quarter(
        self,
        financial_industry: pd.DataFrame,
        ratio_industry: pd.DataFrame,
        company_info: pd.DataFrame,
    ) -> pd.DataFrame:
        if financial_industry.empty and ratio_industry.empty:
            return pd.DataFrame()

        if financial_industry.empty:
            out = ratio_industry.copy()
        elif ratio_industry.empty:
            out = financial_industry.copy()
        else:
            out = financial_industry.merge(
                ratio_industry,
                on=["industry", "year", "quarter", "industry_name_vn", "period_key"],
                how="outer",
                suffixes=("", "_ratio"),
            )

        # Số công ty trong ngành chỉ để metadata, không phải để tính benchmark.
        if not company_info.empty and "industry" in company_info.columns:
            counts = company_info.groupby("industry")["stock_code"].nunique().reset_index(name="n_stocks")
            out = out.merge(counts, on="industry", how="left")
        else:
            out["n_stocks"] = None
        out["n_stocks"] = pd.to_numeric(out["n_stocks"], errors="coerce").fillna(0).astype(int)

        # The industry rows come from segment='industry' and are already benchmark
        # values. The generator expects aggregate-style names for industry means.
        metric_names = list(FINANCIAL_NAMES.keys()) + list(RATIO_NAMES.keys())
        for metric in metric_names:
            if metric in out.columns and f"{metric}_mean" not in out.columns:
                out[f"{metric}_mean"] = out[metric]
            yoy_metric = f"{metric}_yoy"
            if yoy_metric in out.columns and f"{yoy_metric}_mean" not in out.columns:
                out[f"{yoy_metric}_mean"] = out[yoy_metric]
            qoq_metric = f"{metric}_qoq"
            if qoq_metric in out.columns and f"{qoq_metric}_mean" not in out.columns:
                out[f"{qoq_metric}_mean"] = out[qoq_metric]

        if "industry" in out.columns:
            bank_industry_mask = out["industry"].astype(str) == "Banking"
            for col in ["cogs", "cogs_mean", "cogs_yoy", "cogs_yoy_mean", "cogs_qoq", "cogs_qoq_mean"]:
                if col in out.columns:
                    out.loc[bank_industry_mask, col] = np.nan
            real_estate_mask = out["industry"].astype(str) == "Real Estate"
            for col in ["real_estate_goods", "real_estate_goods_mean"]:
                if col in out.columns:
                    out.loc[~real_estate_mask, col] = np.nan
            corp_industry_mask = ~out["industry"].astype(str).isin(["Banking", "Financial Services"])
            for col in CORP_FINANCIAL_INDUSTRY_SHARE_METRICS:
                for candidate in [col, f"{col}_mean"]:
                    if candidate in out.columns:
                        out.loc[~corp_industry_mask, candidate] = np.nan

        return out

    def _build_trailing_financial(self, df: pd.DataFrame, group_col: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()

        out = df.sort_values([group_col, "year", "quarter"]).copy()
        rolling_metrics = [m for m in FINANCIAL_FLOW_METRICS if m in out.columns]
        if not rolling_metrics:
            return pd.DataFrame()

        for metric in rolling_metrics:
            out[metric] = (
                out.groupby(group_col)[metric]
                .rolling(4, min_periods=4)
                .sum()
                .reset_index(level=0, drop=True)
            )

        out = out.dropna(subset=rolling_metrics, how="all").copy()
        if out.empty:
            return pd.DataFrame()

        out["period_basis"] = np.where(out["quarter"] == 1, "year", "ttm")
        out["period_key"] = out.apply(lambda r: _period_key("quarter", int(r["year"]), int(r["quarter"])), axis=1)
        out = self._add_yoy_qoq(out, group_col=group_col, metrics=rolling_metrics)
        return out

    def _build_yearly_financial(self, df: pd.DataFrame, group_col: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()

        metrics = [m for m in FINANCIAL_FLOW_METRICS if m in df.columns]
        if not metrics:
            return pd.DataFrame()

        out = df.groupby([group_col, "year"], dropna=False)[metrics].sum(min_count=1).reset_index()
        quarter_counts = (
            df.groupby([group_col, "year"], dropna=False)["quarter"]
            .nunique()
            .reset_index(name="n_quarters")
        )
        out = out.merge(quarter_counts, on=[group_col, "year"], how="left")
        out["period_key"] = out["year"].astype(int).astype(str)
        out["period_basis"] = "year"
        out = self._add_yearly_yoy(out, group_col=group_col, metrics=metrics)
        return out

    def _build_half_financial(self, df: pd.DataFrame, group_col: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()

        metrics = [m for m in FINANCIAL_FLOW_METRICS if m in df.columns]
        if not metrics:
            return pd.DataFrame()

        out = df[df["quarter"].isin([1, 2, 3, 4])].copy()
        if out.empty:
            return pd.DataFrame()

        out["half"] = np.where(out["quarter"].isin([1, 2]), 1, 2)
        half = out.groupby([group_col, "year", "half"], dropna=False)[metrics].sum(min_count=1).reset_index()
        quarter_counts = (
            out.groupby([group_col, "year", "half"], dropna=False)["quarter"]
            .nunique()
            .reset_index(name="n_quarters")
        )
        half = half.merge(quarter_counts, on=[group_col, "year", "half"], how="left")
        half["period_key"] = half.apply(lambda r: f"{int(r['year'])}-H{int(r['half'])}", axis=1)
        half["period_basis"] = "half"
        half["quarter_range"] = half["half"].map({1: "Q1+Q2", 2: "Q3+Q4"})
        return half

    def _prepare_macro_long(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()

        out = df.copy()
        out["metric"] = out["indicator_name"].map(MACRO_METRIC_MAP)
        out = out.dropna(subset=["metric"])
        out["year"] = pd.to_numeric(out["year"], errors="coerce").astype("Int64")
        out["q_close"] = pd.to_numeric(out["q_close"], errors="coerce")
        if "country" not in out.columns:
            out["country"] = "Vietnam"
        if "unit" not in out.columns:
            out["unit"] = None
        out = out.dropna(subset=["year", "q_close"]).copy()
        sort_cols = ["country", "indicator_name", "year"]
        if "quarter" in out.columns:
            out["quarter"] = pd.to_numeric(out["quarter"], errors="coerce").astype("Int64")
            sort_cols.append("quarter")
        out = out.sort_values(sort_cols)
        out = out.drop_duplicates(subset=["country", "indicator_name", "year"], keep="last").copy()
        out["period_type"] = "year"
        out["prev_close"] = out.groupby(["country", "indicator_name"])["q_close"].shift(1)
        out["change_pct"] = (out["q_close"] - out["prev_close"]) / out["prev_close"] * 100.0
        out["period_key"] = out["year"].astype(int).astype(str)
        return out

    def _prepare_macro(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["year", "quarter"])
        # Keep one annual macro row on Q4 for the existing company-quarter join.
        # If multiple countries exist, use the first country in sorted order.
        countries = sorted(df["country"].dropna().astype(str).unique().tolist()) if "country" in df.columns else []
        preferred = [country for country in countries if country.lower() in {"vietnam", "viet nam", "việt nam", "vn"}]
        selected_country = preferred[0] if preferred else (countries[0] if countries else None)
        base = df[df["country"].astype(str) == selected_country].copy() if selected_country is not None else df.copy()
        base["quarter"] = 4
        value_wide = base.pivot_table(index=["year", "quarter"], columns="metric", values="q_close", aggfunc="first").reset_index()
        change_wide = base.pivot_table(index=["year", "quarter"], columns="metric", values="change_pct", aggfunc="first").reset_index()
        change_wide = change_wide.rename(columns={col: f"{col}_change_pct" for col in change_wide.columns if col not in {"year", "quarter"}})
        return value_wide.merge(change_wide, on=["year", "quarter"], how="outer")

    def _merge_company_info(self, df: pd.DataFrame, company_info: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()

        out = df.copy()
        if not company_info.empty and "stock_code" in company_info.columns:
            out = out.merge(company_info, on="stock_code", how="left")
            out["industry_name_vn"] = out["industry"].map(_display_industry)
        else:
            out["industry"] = None
            out["industry_name_vn"] = None
        return out

    def _build_company_quarter(
        self,
        stock_market: pd.DataFrame,
        financial_company: pd.DataFrame,
        ratio_company: pd.DataFrame,
        index_market: pd.DataFrame,
        macro_quarter: pd.DataFrame,
        company_info: pd.DataFrame,
    ) -> pd.DataFrame:
        stock_market = self._ensure_market_period_columns(stock_market)
        index_market = self._ensure_market_period_columns(index_market)
        quarter_market = stock_market[stock_market["period_type"] == "quarter"].copy().rename(columns={"entity": "stock_code", "time_val": "quarter"})
        quarter_market["has_stock_market_data"] = True
        merge_keys = ["stock_code", "year", "quarter"]
        if not financial_company.empty and set(merge_keys).issubset(financial_company.columns):
            out = quarter_market.merge(financial_company, on=merge_keys, how="outer")
        else:
            out = quarter_market.copy()
        if not ratio_company.empty and set(merge_keys).issubset(ratio_company.columns):
            out = out.merge(ratio_company, on=merge_keys, how="outer", suffixes=("", "_ratio"))
        if not company_info.empty and "stock_code" in company_info.columns:
            out = out.merge(company_info, on="stock_code", how="left")
        else:
            out["industry"] = None
            out["is_bank"] = False
            out["is_securities"] = False
        bank_mask = out["is_bank"].eq(True) if "is_bank" in out.columns else pd.Series(False, index=out.index)
        if "cogs" in out.columns:
            out.loc[bank_mask, "cogs"] = np.nan
        if "cogs_yoy" in out.columns:
            out.loc[bank_mask, "cogs_yoy"] = np.nan
        if "real_estate_goods" in out.columns and "industry" in out.columns:
            out.loc[out["industry"].astype(str) != "Real Estate", "real_estate_goods"] = np.nan
        if {"is_bank", "is_securities"}.issubset(out.columns):
            non_corp_mask = out["is_bank"].eq(True) | out["is_securities"].eq(True)
            for col in CORP_FINANCIAL_INDUSTRY_SHARE_METRICS:
                if col in out.columns:
                    out.loc[non_corp_mask, col] = np.nan

        idx = index_market[index_market["period_type"] == "quarter"].copy().rename(columns={"time_val": "quarter"})
        idx_keep = idx[["entity", "year", "quarter", "return_pct"]].copy()
        vnindex = idx_keep[idx_keep["entity"] == "VNINDEX"].rename(columns={"return_pct": "vnindex_return_pct"})[["year", "quarter", "vnindex_return_pct"]]
        vn30 = idx_keep[idx_keep["entity"] == "VN30"].rename(columns={"return_pct": "vn30_return_pct"})[["year", "quarter", "vn30_return_pct"]]

        out = out.merge(vnindex, on=["year", "quarter"], how="left")
        out = out.merge(vn30, on=["year", "quarter"], how="left")
        out = out.merge(macro_quarter, on=["year", "quarter"], how="left")
        if out.empty:
            return out

        out["has_stock_market_data"] = out["has_stock_market_data"].eq(True)
        out["benchmark_index"] = out["stock_code"].apply(lambda x: "VN30" if x in VN30_TICKERS else "VNINDEX")
        out["benchmark_return_pct"] = out.apply(
            lambda r: r["vn30_return_pct"] if r["benchmark_index"] == "VN30" else r["vnindex_return_pct"],
            axis=1,
        )
        out["excess_return_vs_vnindex"] = out["return_pct"] - out["vnindex_return_pct"]
        out["excess_return_vs_vn30"] = out["return_pct"] - out["vn30_return_pct"]
        out = self._add_yoy_qoq(out, group_col="stock_code", metrics=["return_pct", "avg_close", "volatility"])
        out["period_key"] = out.apply(lambda r: _period_key("quarter", int(r["year"]), int(r["quarter"])), axis=1)
        out["industry_name_vn"] = out["industry"].map(_display_industry)
        return out

    def _build_company_trailing(
        self,
        stock_market: pd.DataFrame,
        financial_trailing: pd.DataFrame,
        index_market: pd.DataFrame,
        company_info: pd.DataFrame,
    ) -> pd.DataFrame:
        if financial_trailing.empty:
            return pd.DataFrame()

        stock_market = self._ensure_market_period_columns(stock_market)
        index_market = self._ensure_market_period_columns(index_market)
        quarter_market = stock_market[stock_market["period_type"] == "quarter"].copy().rename(columns={"entity": "stock_code", "time_val": "quarter"})
        quarter_market["has_stock_market_data"] = True
        quarter_market = quarter_market.drop(columns=["period_key"], errors="ignore")
        out = quarter_market.merge(financial_trailing, on=["stock_code", "year", "quarter"], how="right")
        out["has_stock_market_data"] = out["has_stock_market_data"].eq(True)
        if "period_key" not in out.columns:
            out["period_key"] = out.apply(lambda r: _period_key("quarter", int(r["year"]), int(r["quarter"])), axis=1)
        if not company_info.empty and "stock_code" in company_info.columns:
            out = out.merge(company_info, on="stock_code", how="left")
        else:
            out["industry"] = None

        idx = index_market[index_market["period_type"] == "quarter"].copy().rename(columns={"time_val": "quarter"})
        idx_keep = idx[["entity", "year", "quarter", "return_pct"]].copy()
        vnindex = idx_keep[idx_keep["entity"] == "VNINDEX"].rename(columns={"return_pct": "vnindex_return_pct"})[["year", "quarter", "vnindex_return_pct"]]
        vn30 = idx_keep[idx_keep["entity"] == "VN30"].rename(columns={"return_pct": "vn30_return_pct"})[["year", "quarter", "vn30_return_pct"]]

        out = out.merge(vnindex, on=["year", "quarter"], how="left")
        out = out.merge(vn30, on=["year", "quarter"], how="left")
        out["benchmark_index"] = out["stock_code"].apply(lambda x: "VN30" if x in VN30_TICKERS else "VNINDEX")
        out["benchmark_return_pct"] = out.apply(
            lambda r: r["vn30_return_pct"] if r["benchmark_index"] == "VN30" else r["vnindex_return_pct"],
            axis=1,
        )
        out["excess_return_vs_vnindex"] = out["return_pct"] - out["vnindex_return_pct"]
        out["industry_name_vn"] = out["industry"].map(_display_industry)
        return out

    def _build_company_month(self, stock_market: pd.DataFrame, index_market: pd.DataFrame, company_info: pd.DataFrame) -> pd.DataFrame:
        stock_market = self._ensure_market_period_columns(stock_market)
        index_market = self._ensure_market_period_columns(index_market)
        stock = stock_market[stock_market["period_type"] == "month"].copy().rename(columns={"entity": "stock_code", "time_val": "month"})
        if not company_info.empty and "stock_code" in company_info.columns:
            stock = stock.merge(company_info, on="stock_code", how="left")
        else:
            stock["industry"] = None
        idx = index_market[index_market["period_type"] == "month"].copy().rename(columns={"entity": "index_name", "time_val": "month"})
        vnindex = idx[idx["index_name"] == "VNINDEX"][["year", "month", "return_pct"]].rename(columns={"return_pct": "vnindex_return_pct"})
        out = stock.merge(vnindex, on=["year", "month"], how="left")
        if out.empty:
            return out

        out["excess_return_vs_vnindex"] = out["return_pct"] - out["vnindex_return_pct"]
        out["period_key"] = out.apply(lambda r: _period_key("month", int(r["year"]), int(r["month"])), axis=1)
        out["industry_name_vn"] = out["industry"].map(_display_industry)
        return out

    def _build_peer_rollups(self, company_quarter: pd.DataFrame) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        metrics = list(dict.fromkeys([
            m
            for m in [
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
            ]
            if m in company_quarter.columns
        ]))
        for group_name, tickers in PEER_GROUPS.items():
            subset = company_quarter[company_quarter["stock_code"].isin(tickers)].copy()
            if subset.empty:
                continue
            for (year, quarter), frame in subset.groupby(["year", "quarter"], dropna=False):
                row: Dict[str, Any] = {
                    "group_name": group_name,
                    "year": int(year),
                    "quarter": int(quarter),
                    "period_key": _period_key("quarter", int(year), int(quarter)),
                    "n_members": int(frame["stock_code"].nunique()),
                    "stock_list": sorted(frame["stock_code"].dropna().astype(str).unique().tolist()),
                }
                for metric in metrics:
                    series = frame[metric].dropna()
                    row[f"{metric}_mean"] = _safe_float(series.mean(), 4) if len(series) else None
                rows.append(row)
        return pd.DataFrame(rows)

    @staticmethod
    def _add_yearly_yoy(df: pd.DataFrame, group_col: str, metrics: Sequence[str]) -> pd.DataFrame:
        if df.empty:
            return df

        out = df.sort_values([group_col, "year"]).copy()
        for metric in metrics:
            if metric not in out.columns:
                continue

            out[f"{metric}_prev_y"] = out.groupby(group_col)[metric].shift(1)
            prev_y = out[f"{metric}_prev_y"]
            out[f"{metric}_yoy"] = np.where(
                prev_y.notna() & (prev_y != 0),
                (out[metric] - prev_y) / prev_y * 100.0,
                np.nan,
            )
        return out

    @staticmethod
    def _add_yoy_qoq(df: pd.DataFrame, group_col: str, metrics: Sequence[str]) -> pd.DataFrame:
        if df.empty:
            return df

        out = df.sort_values([group_col, "year", "quarter"]).copy()
        for metric in metrics:
            if metric not in out.columns:
                continue

            out[f"{metric}_prev_q"] = out.groupby(group_col)[metric].shift(1)
            out[f"{metric}_prev_y"] = out.groupby(group_col)[metric].shift(4)

            prev_q = out[f"{metric}_prev_q"]
            prev_y = out[f"{metric}_prev_y"]

            out[f"{metric}_qoq"] = np.where(
                prev_q.notna() & (prev_q != 0),
                (out[metric] - prev_q) / prev_q * 100.0,
                np.nan,
            )
            out[f"{metric}_yoy"] = np.where(
                prev_y.notna() & (prev_y != 0),
                (out[metric] - prev_y) / prev_y * 100.0,
                np.nan,
            )
        return out
