"""Build an English mirror of test_final.jsonl for vi/en comparison evals.

No LLM call: the 364 rows that came from test.jsonl carry full structured
metadata (question_type, entities, metrics, periods, extra_info), so their
English question is generated from a template keyed by question_type. The
336 rows that came from test_bo_sung.jsonl have no such metadata; those were
hand-translated once and are loaded from bo_sung_en.json (see
bo_sung_en_translations.py).

Usage:
    python translate_dataset.py --lang vi   # path to data_mix_v2/test_final.jsonl
    python translate_dataset.py --lang en   # builds/returns data_mix_v2/test_final.en.jsonl
"""
import argparse
import csv
import json
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data_mix_v2"
COMPANY_CSV = (
    Path(__file__).parent.parent
    / "data_collection"
    / "financial_statement"
    / "transform"
    / "metadata"
    / "df_company_info_v2.csv"
)

COUNTRY_EN = {
    "CAN": "Canada", "CHN": "China", "DEU": "Germany", "FRA": "France",
    "GBR": "the United Kingdom", "IND": "India", "JPN": "Japan", "KOR": "South Korea",
    "SGP": "Singapore", "THA": "Thailand", "USA": "the United States", "VNM": "Vietnam",
}

PEER_GROUP_EN = {
    "ngân hàng": "the banking group",
    "dầu khí": "the oil & gas group",
    "công nghệ": "the technology group",
    "bất động sản": "the real estate group",
    "bán lẻ": "the retail group",
    "thực phẩm": "the food & beverage group",
}

METRIC_EN = {
    "ROA": "ROA", "ROE": "ROE", "NIM": "NIM", "BDR": "bad debt ratio",
    "avg_close": "average closing price", "bad_debt_amount": "bad debt amount",
    "benchmark_return_pct": "benchmark return", "casa": "CASA ratio",
    "cogs": "cost of goods sold", "cogs_yoy": "COGS YoY growth",
    "commodity_return_pct": "commodity return", "current_assets": "current assets",
    "customer_deposits": "customer deposits", "daily_close": "daily closing price",
    "deposit_customer_foreign_business": "foreign-business customer deposits",
    "deposit_customer_individual": "individual customer deposits",
    "ema20": "EMA20", "ema200": "EMA200", "ema50": "EMA50", "equity": "equity",
    "excess_return_vs_vn30": "excess return vs VN30", "excess_return_vs_vnindex": "excess return vs VNINDEX",
    "exports_pct_gdp": "exports as % of GDP", "gdp": "GDP", "gdp_growth_pct": "GDP growth rate",
    "gni": "GNI", "gni_per_capita": "GNI per capita", "imports_pct_gdp": "imports as % of GDP",
    "inflation_pct": "inflation rate", "lending_rate_pct": "lending rate", "liabilities": "liabilities",
    "loan_customer": "customer loans", "loan_customer_individual": "individual customer loans",
    "loan_customer_private_business": "private-business customer loans",
    "loan_customer_state_owned": "state-owned-enterprise customer loans",
    "long_term_borrowings": "long-term borrowings", "net_income": "net income",
    "net_income_yoy": "net income YoY growth", "real_estate_goods": "real estate inventory",
    "return_pct": "return", "revenue": "revenue", "revenue_yoy": "revenue YoY growth",
    "short_term_borrowings": "short-term borrowings", "total_assets": "total assets",
    "unemployment_pct": "unemployment rate",
}


def load_company_map():
    out = {}
    with open(COMPANY_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out[row["stock_code"].strip()] = row.get("short_name", "").strip()
    return out


COMPANY_MAP = load_company_map()


def entity_en(code, is_macro=False):
    # CHN/SGP/VNM collide between ISO country codes and stock tickers; only
    # resolve to the country name in a macro-family question (see the same
    # disambiguation in normalize_questions.py).
    if code in COUNTRY_EN and (is_macro or code not in COMPANY_MAP):
        return COUNTRY_EN[code]
    if code in PEER_GROUP_EN:
        return PEER_GROUP_EN[code]
    return code  # ticker, index, commodity, industry key: already English/code-like


def metric_en(key):
    return METRIC_EN.get(key, key.replace("_", " "))


def period_en(p):
    if not p:
        return ""
    if "-Q" in p:
        y, q = p.split("-Q")
        return f"Q{q} {y}"
    if "-M" in p:
        y, m = p.split("-M")
        return f"month {m} of {y}"
    if "-H" in p:
        y, h = p.split("-H")
        return f"H{h} {y}"
    return p


def first(lst, default=""):
    return lst[0] if lst else default


def nth(lst, i, default=""):
    return lst[i] if len(lst) > i else default


def build_en_question(row):
    """Template-driven English question for rows with structured metadata."""
    qtype = row.get("question_type")
    is_macro = row.get("question_family") == "macro"
    entities = [entity_en(e, is_macro) for e in row.get("entities", [])]
    metrics = [metric_en(m) for m in row.get("metrics", [])]
    periods = [period_en(p) for p in row.get("periods", [])]
    extra = row.get("extra_info", {})
    m0 = first(metrics, "value")
    e0 = first(entities)
    e1 = nth(entities, 1)
    p0 = first(periods)

    if qtype == "company_direct":
        return f"What was {e0}'s {m0} in {p0}?"
    if qtype == "industry_avg_direct":
        return f"What was the industry-average {m0} of the {e0} industry in {p0}?"
    if qtype == "industry_mean":
        return f"What was the industry-average {m0} of the {e0} industry in {p0}?"
    if qtype == "macro_direct":
        return f"In {p0}, what was the {m0} of {e0}?"
    if qtype == "macro_yoy_change_pct":
        return f"In {p0}, by how much did the {m0} of {e0} change year-over-year (%)?"
    if qtype == "macro_highest_year":
        start, end = first(periods), periods[-1] if periods else ""
        return f"Between {start} and {end}, which year had the highest {m0} for {e0}?"
    if qtype == "macro_lowest_year":
        start, end = first(periods), periods[-1] if periods else ""
        return f"Between {start} and {end}, which year had the lowest {m0} for {e0}?"
    if qtype == "commodity_direct":
        return f"What was the {m0} of {e0} in {p0}?"
    if qtype == "index_direct":
        return f"What was the {m0} of the {e0} index in {p0}?"
    if qtype == "company_month_direct":
        return f"What was {e0}'s {m0} in {p0}?"
    if qtype == "company_daily":
        return f"What was {e0}'s {m0} on {p0}?"
    if qtype == "company_yearly":
        return f"What was {e0}'s total {m0} for the year {p0}?"
    if qtype == "company_trailing_4q":
        return f"What was {e0}'s total {m0} over the trailing 4 quarters as of {p0}?"
    if qtype == "company_time_range":
        start, end = first(periods), periods[-1] if periods else ""
        return f"List {e0}'s {m0} by quarter from {start} to {end}."
    if qtype == "company_vs_industry_time_range":
        start, end = first(periods), periods[-1] if periods else ""
        return f"List {e0}'s {m0} and the {e1} industry average {m0} by quarter from {start} to {end}."
    if qtype == "company_vs_benchmark_time_range":
        start, end = first(periods), periods[-1] if periods else ""
        return f"List {e0}'s return and {e1}'s return by quarter from {start} to {end}."
    if qtype == "company_period_diff":
        p1 = nth(periods, 1)
        return f"By how much does {e0}'s {m0} in {p1} differ from {p0}?"
    if qtype in ("company_same_period_quarter_diff", "company_same_period_half_diff", "company_same_period_year_diff"):
        p1 = nth(periods, 1)
        return f"Compare {e0}'s {m0} in {p1} with the same period last year ({p0}); what is the difference?"
    if qtype == "company_h2_vs_h1_diff":
        year = first(row.get("periods", [])).split("-H")[0]
        return f"By how much does {e0}'s {m0} differ between H2 and H1 of {year}?"
    if qtype == "company_vs_company_diff":
        return f"In {p0}, by how much does {e0}'s {m0} differ from {e1}'s?"
    if qtype == "company_vs_company_winner":
        return f"In {p0}, which has the higher {m0}, {e0} or {e1}?"
    if qtype == "company_vs_company_yearly_diff":
        return f"In {p0}, by how much does {e0}'s {m0} differ from {e1}'s?"
    if qtype == "company_vs_industry_avg_diff":
        return f"In {p0}, by how much does {e0}'s {m0} differ from the {e1} industry average?"
    if qtype == "company_vs_industry_total_share_pct":
        return f"What percentage of the {e1} industry's total {m0} does {e0} account for in {p0}?"
    if qtype == "industry_vs_industry_diff":
        return f"In {p0}, by how much does the average {m0} of the {e0} industry differ from the {e1} industry?"
    if qtype == "industry_vs_industry_winner":
        return f"In {p0}, which has the higher average {m0}, the {e0} industry or the {e1} industry?"
    if qtype == "industry_top":
        industry = extra.get("industry", e0)
        return f"In the {industry} industry in {p0}, which stock has the highest {m0}?"
    if qtype == "universe_top":
        return f"In {p0}, what are the top stocks by {m0} across the whole market?"
    if qtype == "universe_positive_count":
        return f"In {p0}, how many companies have a positive {m0}?"
    if qtype == "commodity_top":
        return f"In {p0}, what are the top 10 commodities by {m0}?"
    if qtype == "peer_aggregate":
        return f"In {p0}, what is the average {m0} of {e0}?"
    if qtype == "company_best_worst_quarter_in_year":
        year = first(periods).split()[-1] if periods else ""
        return f"In {year}, which quarter had {e0}'s lowest/highest {m0}?"
    if qtype == "stock_vs_benchmark_diff":
        return f"In {p0}, what is the return gap between {e0} and {e1}?"
    if qtype == "stock_vs_benchmark_direction":
        return f"In {p0}, did {e0} outperform or underperform {e1}, and by how much?"
    if qtype == "stock_vs_commodity_diff":
        return f"In {p0}, what is the return gap between {e0} and {e1}?"
    if qtype == "visualize_industry_top10_bar":
        return f"Get the data to plot a bar chart of the top 10 companies in the {e0} industry by {m0} in {p0}."
    if qtype == "visualize_company_vs_industry_scatter":
        return f"Get the data to plot a scatter chart comparing each company's {m0} against its industry average in {p0}."
    if qtype == "visualize_industry_heatmap_return_pct":
        return "Get the data to plot a heatmap of quarterly returns for the top 10 stocks of the given industry over the trailing 4 quarters."

    # Generic fallback for any unmapped question_type.
    parts = [m0]
    if e0:
        parts.append(f"of {e0}")
    if e1:
        parts.append(f"vs {e1}")
    if p0:
        parts.append(f"in {p0}")
    return "What was the " + " ".join(parts) + "?"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=["vi", "en"], required=True)
    args = parser.parse_args()

    vi_path = DATA_DIR / "test_final.jsonl"

    if args.lang == "vi":
        print(vi_path)
        return

    bo_sung_en_path = DATA_DIR / "bo_sung_en.json"
    with open(bo_sung_en_path, encoding="utf-8") as f:
        bo_sung_en = json.load(f)

    out_path = DATA_DIR / "test_final.en.jsonl"
    n_template, n_lookup, n_missing = 0, 0, 0
    with open(vi_path, encoding="utf-8") as fin, open(out_path, "w", encoding="utf-8") as fout:
        for line in fin:
            if not line.strip():
                continue
            row = json.loads(line)
            new_row = dict(row)
            if row.get("question_type") == "bo_sung":
                if row["id"] in bo_sung_en:
                    new_row["question_raw"] = bo_sung_en[row["id"]]
                    n_lookup += 1
                else:
                    n_missing += 1
            else:
                new_row["question_raw"] = build_en_question(row)
                n_template += 1
            fout.write(json.dumps(new_row, ensure_ascii=False) + "\n")

    print(f"template-translated: {n_template}, dictionary-lookup: {n_lookup}, missing: {n_missing}")
    print(out_path)


if __name__ == "__main__":
    main()
