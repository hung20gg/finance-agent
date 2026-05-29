from __future__ import annotations

from typing import Any, Dict, List, Sequence

import numpy as np
import pandas as pd

from .const import FINANCIAL_CATEGORY_MAP, FINANCIAL_NAMES, INDUSTRY_VN, PEER_GROUPS, RATIO_NAMES, VN30_TICKERS
from .generator import GeneratorConfig


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
        commodity_names = self.config.commodity_allowlist or self.loader.fetch_distinct_commodities()

        stock_market = self.loader.fetch_market_period_features(
            table_name="stock_daily",
            entity_col="stock_code",
            value_col="close",
            allowed_names=stock_codes,
            price_multiplier=1000.0,
        )
        index_market = self.loader.fetch_market_period_features(
            table_name="indices_daily",
            entity_col="index_name",
            value_col="close",
            allowed_names=self.config.index_names,
            price_multiplier=1.0,
        )
        commodity_market = self.loader.fetch_market_period_features(
            table_name="commodities_daily",
            entity_col="indicator_name",
            value_col="value",
            allowed_names=commodity_names,
            price_multiplier=1.0,
        )
        financial_raw = self.loader.fetch_financial_statement()
        ratio_raw = self.loader.fetch_financial_ratio()
        macro_raw = self.loader.fetch_macro()

        financial_company, financial_industry = self._prepare_financials(financial_raw)
        ratio_company, ratio_industry = self._prepare_ratios(ratio_raw)
        financial_trailing = self._build_trailing_financial(financial_company, group_col="stock_code")
        industry_avg_trailing = self._build_trailing_financial(financial_industry, group_col="industry")
        macro_quarter = self._prepare_macro(macro_raw)

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
        company_month = self._build_company_month(stock_market, index_market, company_info)
        industry_avg_quarter = self._merge_industry_quarter(financial_industry, ratio_industry, company_info)
        peer_rollups = self._build_peer_rollups(company_quarter)

        return {
            "company_info": company_info,
            "stock_market": stock_market,
            "index_market": index_market,
            "commodity_market": commodity_market,
            "financial_company": financial_company,
            "financial_trailing": financial_trailing,
            "ratio_company": ratio_company,
            "financial_industry": financial_industry,
            "ratio_industry": ratio_industry,
            "industry_avg_quarter": industry_avg_quarter,
            "industry_avg_trailing": industry_avg_trailing,
            "macro_quarter": macro_quarter,
            "company_quarter": company_quarter,
            "company_trailing": company_trailing,
            "company_month": company_month,
            "peer_rollups": peer_rollups,
        }

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
        company_wide = self._add_yoy_qoq(company_wide, group_col="stock_code", metrics=list(FINANCIAL_NAMES.keys()))

        industry = df[df["segment"].fillna("").str.lower() == "industry"].copy()
        industry = industry.rename(columns={"stock_code": "industry"})
        industry_wide = industry.pivot_table(
            index=["industry", "year", "quarter"],
            columns="metric_name",
            values="data",
            aggfunc="first",
        ).reset_index()
        industry_wide = self._add_yoy_qoq(industry_wide, group_col="industry", metrics=list(FINANCIAL_NAMES.keys()))
        industry_wide["industry_name_vn"] = industry_wide["industry"].map(_display_industry)
        industry_wide["period_key"] = industry_wide.apply(lambda r: _period_key("quarter", int(r["year"]), int(r["quarter"])), axis=1)

        return company_wide, industry_wide

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

        return out

    def _build_trailing_financial(self, df: pd.DataFrame, group_col: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()

        out = df.sort_values([group_col, "year", "quarter"]).copy()
        rolling_metrics = [m for m in ["revenue", "net_income", "cash_equiv"] if m in out.columns]
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
        out["period_basis"] = np.where(out["quarter"] == 1, "year", "ttm")
        out["period_key"] = out.apply(lambda r: _period_key("quarter", int(r["year"]), int(r["quarter"])), axis=1)
        out = self._add_yoy_qoq(out, group_col=group_col, metrics=rolling_metrics)
        return out

    def _prepare_macro(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        df = df.sort_values(["indicator_name", "year", "quarter"]).copy()
        df["prev_close"] = df.groupby("indicator_name")["q_close"].shift(1)
        df["change_pct"] = (df["q_close"] - df["prev_close"]) / df["prev_close"] * 100.0
        wide = df.pivot_table(index=["year", "quarter"], columns="indicator_name", values="change_pct", aggfunc="first").reset_index()
        return wide.rename(columns={
            "Inflation_%": "inflation_change_pct",
            "Unemployment_%": "unemployment_change_pct",
        })

    def _build_company_quarter(
        self,
        stock_market: pd.DataFrame,
        financial_company: pd.DataFrame,
        ratio_company: pd.DataFrame,
        index_market: pd.DataFrame,
        macro_quarter: pd.DataFrame,
        company_info: pd.DataFrame,
    ) -> pd.DataFrame:
        quarter_market = stock_market[stock_market["period_type"] == "quarter"].copy().rename(columns={"entity": "stock_code", "time_val": "quarter"})
        out = quarter_market.merge(financial_company, on=["stock_code", "year", "quarter"], how="left")
        out = out.merge(ratio_company, on=["stock_code", "year", "quarter"], how="left", suffixes=("", "_ratio"))
        out = out.merge(company_info, on="stock_code", how="left")

        idx = index_market[index_market["period_type"] == "quarter"].copy().rename(columns={"time_val": "quarter"})
        idx_keep = idx[["entity", "year", "quarter", "return_pct"]].copy()
        vnindex = idx_keep[idx_keep["entity"] == "VNINDEX"].rename(columns={"return_pct": "vnindex_return_pct"})[["year", "quarter", "vnindex_return_pct"]]
        vn30 = idx_keep[idx_keep["entity"] == "VN30"].rename(columns={"return_pct": "vn30_return_pct"})[["year", "quarter", "vn30_return_pct"]]

        out = out.merge(vnindex, on=["year", "quarter"], how="left")
        out = out.merge(vn30, on=["year", "quarter"], how="left")
        out = out.merge(macro_quarter, on=["year", "quarter"], how="left")

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

        quarter_market = stock_market[stock_market["period_type"] == "quarter"].copy().rename(columns={"entity": "stock_code", "time_val": "quarter"})
        out = quarter_market.merge(financial_trailing, on=["stock_code", "year", "quarter"], how="right")
        out = out.merge(company_info, on="stock_code", how="left")

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
        out["period_key"] = out.apply(lambda r: _period_key("quarter", int(r["year"]), int(r["quarter"])), axis=1)
        out["industry_name_vn"] = out["industry"].map(_display_industry)
        return out

    def _build_company_month(self, stock_market: pd.DataFrame, index_market: pd.DataFrame, company_info: pd.DataFrame) -> pd.DataFrame:
        stock = stock_market[stock_market["period_type"] == "month"].copy().rename(columns={"entity": "stock_code", "time_val": "month"})
        stock = stock.merge(company_info, on="stock_code", how="left")
        idx = index_market[index_market["period_type"] == "month"].copy().rename(columns={"entity": "index_name", "time_val": "month"})
        vnindex = idx[idx["index_name"] == "VNINDEX"][["year", "month", "return_pct"]].rename(columns={"return_pct": "vnindex_return_pct"})
        out = stock.merge(vnindex, on=["year", "month"], how="left")
        out["excess_return_vs_vnindex"] = out["return_pct"] - out["vnindex_return_pct"]
        out["period_key"] = out.apply(lambda r: _period_key("month", int(r["year"]), int(r["month"])), axis=1)
        out["industry_name_vn"] = out["industry"].map(_display_industry)
        return out

    def _build_peer_rollups(self, company_quarter: pd.DataFrame) -> pd.DataFrame:
        rows: List[Dict[str, Any]] = []
        metrics = [m for m in ["return_pct", "excess_return_vs_vnindex", "revenue", "net_income", "ROE", "ROA", "NIM", "BDR"] if m in company_quarter.columns]
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
                    row[f"{metric}_median"] = _safe_float(series.median(), 4) if len(series) else None
                rows.append(row)
        return pd.DataFrame(rows)

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
