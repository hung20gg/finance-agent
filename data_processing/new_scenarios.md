# Walkthrough - New Question Scenarios Added

We have successfully implemented 9 new question scenarios ranging from easy to hard levels to increase training diversity and data coverage.

## Changes Made

### 1. [generator.py](file:///d:/QuocAnh/Paper/text2sql_Hung/finance-agent/data_processing/question_generator/generator.py)

- **Extended `METRIC_DISPLAY`**: Added mappings for YoY/QoQ metrics (`revenue_qoq`, `net_income_qoq`, `return_pct_qoq`, etc.) and macroeconomics indicators (`inflation_change_pct`, `unemployment_change_pct`) to support display units correctly.
- **Updated `_get_don_vi`**: Registered the new growth and macro metrics as returning `"phần trăm"` (percentage).
- **Added 9 New Generator Methods**:
  - **Easy**:
    - `generate_macro_direct_questions()`: Queries macroeconomics features (`inflation_change_pct`, `unemployment_change_pct`) per quarter.
    - `generate_company_trailing_direct_questions()`: Queries company trailing twelve months (TTM) features (`revenue`, `net_income`, `cash_equiv`).
  - **Medium**:
    - `generate_company_growth_questions()`: Queries QoQ and YoY growth rates of corporate metrics.
    - `generate_peer_group_minmax_questions()`: Finds the best/worst performers in custom peer groups (`PEER_GROUPS`).
    - `generate_company_metric_vs_metric_questions()`: Compares two metrics of the same company (e.g. `revenue` vs `liabilities`, `casa` vs `loan_customer` for banks).
  - **Hard**:
    - `generate_industry_risk_return_questions()`: Standard deviation vs return analysis (lowest `std_close` with positive return).
    - `generate_consecutive_growth_questions()`: Checks if a company maintains QoQ growth across multiple consecutive quarters.
    - `generate_company_triple_compare_questions()`: Compares stock return vs benchmark index and company ROE vs industry average ROE.
    - `generate_peer_outperform_benchmark_questions()`: Counts how many stocks in a peer group outperform their benchmark indices.
- **Registered in `generate()`**: Integrated all new generator functions to feed into `clear_candidates` dictionary for sampling.

### 2. [feature_store.py](file:///d:/QuocAnh/Paper/text2sql_Hung/finance-agent/data_processing/question_generator/feature_store.py)

- **Added `period_key` to `company_trailing`**: Explicitly set the `period_key` column inside `_build_company_trailing()` to avoid Pandas merge name-collision suffixes (`period_key_x` and `period_key_y`) when both merged frames contain the column.


## Verification

- Compilation checks (`py_compile`) passed without errors.
- Visual inspection of the implementation confirms correct schema mappings and metadata packing.
