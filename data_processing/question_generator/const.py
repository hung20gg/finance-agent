INDUSTRY_VN = {
    "Basic Resources": "Tài nguyên Cơ bản",
    "Financial Services": "Dịch vụ Tài chính",
    "Utilities (Electricity, Water & Gas)": "Tiện ích (Điện, Nước & Khí đốt)",
    "Banking": "Ngân hàng",
    "Food and Beverages": "Thực phẩm và Đồ uống",
    "Retail": "Bán lẻ",
    "Travel and Leisure": "Du lịch và Giải trí",
    "Chemicals": "Hóa chất",
    "Information Technology": "Công nghệ Thông tin",
    "Oil and Gas": "Dầu khí",
    "Real Estate": "Bất động sản",
}

INDEX_NAMES = [
    "FTSE",
    "HSI",
    "KOSPI",
    "NASDAQ",
    "NIKKEI",
    "SP500",
    "STI",
    "VN30",
    "VNINDEX",
]

DEFAULT_COMMODITY_DISPLAY = {
    "Gold": "Vàng",
    "Silver": "Bạc",
    "Brent Crude Oil": "Dầu Brent",
    "Crude Oil WTI": "Dầu WTI",
    "Natural Gas": "Khí tự nhiên",
    "Gasoline": "Xăng",
}

MACRO_INDICATORS = [
    "Exports_%_GDP",
    "GDP",
    "GDP_Growth_%",
    "GNI",
    "GNI_per_capita",
    "Imports_%_GDP",
    "Inflation_%",
    "Lending_Rate_%",
    "Unemployment_%",
]

MACRO_METRIC_MAP = {
    "Exports_%_GDP": "exports_pct_gdp",
    "GDP": "gdp",
    "GDP_Growth_%": "gdp_growth_pct",
    "GNI": "gni",
    "GNI_per_capita": "gni_per_capita",
    "Imports_%_GDP": "imports_pct_gdp",
    "Inflation_%": "inflation_pct",
    "Lending_Rate_%": "lending_rate_pct",
    "Unemployment_%": "unemployment_pct",
}

MACRO_DISPLAY = {
    "exports_pct_gdp": "xuất khẩu trên GDP",
    "gdp": "GDP",
    "gdp_growth_pct": "tăng trưởng GDP",
    "gni": "GNI",
    "gni_per_capita": "GNI bình quân đầu người",
    "imports_pct_gdp": "nhập khẩu trên GDP",
    "inflation_pct": "lạm phát",
    "lending_rate_pct": "lãi suất cho vay",
    "unemployment_pct": "tỷ lệ thất nghiệp",
}

# Dùng lại tinh thần peer group cũ để có thêm nhóm câu hỏi ngoài industry.
PEER_GROUPS = {
    "ngân hàng": ["ACB", "BID", "CTG", "HDB", "MBB", "SHB", "SSB", "STB", "TCB", "TPB", "VCB", "VIB", "VPB"],
    "dầu khí": ["BSR", "GAS", "OIL", "PLX", "PVD", "PVS", "PVC", "POW"],
    "công nghệ": ["CMG", "ELC", "FPT", "FOX"],
    "bất động sản": ["DIG", "DXG", "KDH", "NLG", "NVL", "PDR", "VHM", "VIC", "VPI"],
    "bán lẻ": ["DGW", "FRT", "MWG", "PET", "PNJ"],
    "thực phẩm": ["DBC", "KDC", "MCH", "MSN", "SAB", "VNM"],
}

VN30_TICKERS = {
    "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
    "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
    "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
}

LINKED_COMMODITY_BY_TICKER = {
    "GAS": ["Brent Crude Oil", "Crude Oil WTI", "Natural Gas"],
    "PLX": ["Brent Crude Oil", "Crude Oil WTI", "Gasoline"],
    "PVD": ["Brent Crude Oil", "Crude Oil WTI"],
    "PVS": ["Brent Crude Oil", "Crude Oil WTI"],
    "BSR": ["Brent Crude Oil", "Crude Oil WTI", "Gasoline"],
    "POW": ["Natural Gas"],
}

FINANCIAL_CATEGORY_MAP = {
    "IS_020": "revenue",
    "IS_036": "cogs",
    "IS_100": "net_income",
    "BS_100": "current_assets",
    "BS_125": "loan_customer",
    "BS_270": "total_assets",
    "BS_300": "liabilities",
    "BS_305": "customer_deposits",
    "BS_329": "short_term_borrowings",
    "BS_350": "long_term_borrowings",
    "BS_400": "equity",
    "Bank_TM_68": "_substandard_debt",
    "Bank_TM_69": "_doubtful_debt",
    "Bank_TM_70": "_loss_debt",
    "Bank_TM_85": "loan_customer_state_owned",
    "Bank_TM_86": "_loan_limited_joint_stock",
    "Bank_TM_87": "deposit_customer_foreign_business",
    "Bank_TM_88": "_loan_private_cooperative",
    "Bank_TM_89": "loan_customer_individual",
    "Bank_TM_121": "casa",
    "Bank_TM_131": "loan_customer_private_business",
    "Bank_TM_132": "_deposit_foreign_enterprises",
    "Bank_TM_133": "deposit_customer_individual",
    "Bank_TM_45": "loan_construction",
    "Bank_TM_61": "loan_real_estate",
    "Corp_TM_27": "real_estate_goods",
    "Share_TM_1": "holding_cash",
    "CF_130": "cash_equiv",
}

FINANCIAL_DERIVED_SUM_MAP = {
    "bad_debt_amount": ["_substandard_debt", "_doubtful_debt", "_loss_debt"],
}

FINANCIAL_FLOW_METRICS = [
    metric
    for category_code, metric in FINANCIAL_CATEGORY_MAP.items()
    if category_code.startswith(("IS_", "CF_"))
]

FINANCIAL_INDUSTRY_SHARE_METRICS = [
    "revenue",
    "current_assets",
    "total_assets",
    "liabilities",
    "equity",
]

BANK_FINANCIAL_INDUSTRY_SHARE_METRICS = [
    "loan_customer",
    "customer_deposits",
    "bad_debt_amount",
    "loan_customer_individual",
    "loan_customer_private_business",
    "loan_customer_state_owned",
    "deposit_customer_individual",
    "deposit_customer_foreign_business",
    "deposit_customer_private_business",
]

REAL_ESTATE_FINANCIAL_INDUSTRY_SHARE_METRICS = [
    "real_estate_goods",
]

CORP_FINANCIAL_INDUSTRY_SHARE_METRICS = [
    "short_term_borrowings",
    "long_term_borrowings",
]

FINANCIAL_NAMES = {
    "revenue": "doanh thu",
    "cogs": "giá vốn hàng bán",
    "net_income": "lợi nhuận sau thuế",
    "current_assets": "tài sản ngắn hạn",
    "total_assets": "tổng tài sản",
    "loan_customer": "dư nợ cho vay khách hàng",
    "liabilities": "tổng nợ phải trả",
    "customer_deposits": "tiền gửi khách hàng",
    "short_term_borrowings": "nợ phải trả ngắn hạn",
    "long_term_borrowings": "nợ phải trả dài hạn",
    "equity": "vốn chủ sở hữu",
    "bad_debt_amount": "nợ xấu",
    "loan_customer_individual": "lượng tiền cho vay khách hàng cá nhân",
    "loan_customer_private_business": "lượng tiền cho vay doanh nghiệp tư nhân",
    "loan_customer_state_owned": "lượng tiền cho vay doanh nghiệp nhà nước",
    "deposit_customer_individual": "lượng tiền gửi khách hàng cá nhân",
    "deposit_customer_foreign_business": "tiền gửi/huy động từ doanh nghiệp nước ngoài",
    "deposit_customer_private_business": "lượng tiền gửi doanh nghiệp tư nhân",
    "casa": "tiền gửi không kỳ hạn",
    "loan_construction": "lượng tiền cho vay ngành xây dựng",
    "loan_real_estate": "lượng tiền cho vay bất động sản và tư vấn",
    "real_estate_goods": "tài sản bất động sản hiện có",
    "holding_cash": "lượng tiền mặt thực có",
    "cash_equiv": "tiền và tương đương tiền cuối kỳ",
}

RATIO_NAMES = {
    "NIM": "NIM",
    "BDR": "tỷ lệ nợ xấu",
    "ROE": "ROE",
    "ROA": "ROA",
    "EBITDA": "EBITDA",
    "DTTCR": "nợ trên vốn chủ sở hữu",
    "QR": "khả năng thanh toán nhanh",
    "CashR": "khả năng thanh toán bằng tiền mặt",
}

MARKET_NAMES = {
    "return_pct": "Tỷ lệ tăng trưởng về giá trị/điểm sổ",
    "daily_close": "giá đóng cửa",
    "avg_close": "giá đóng cửa trung bình",
    "std_close": "độ lệch chuẩn giá đóng cửa",
    "ema20": "EMA20",
    "ema50": "EMA50",
    "ema200": "EMA200",
    "excess_return_vs_vnindex": "mức sinh lời vượt VNINDEX",
    "excess_return_vs_vn30": "mức sinh lời vượt VN30",
}

DERIVED_NAMES = {
    "revenue_yoy": "tăng trưởng YoY doanh thu",
    "cogs_yoy": "tăng trưởng YoY giá vốn hàng bán",
    "net_income_yoy": "tăng trưởng YoY lợi nhuận ròng",
    "return_pct_yoy": "tăng trưởng YoY tỷ suất sinh lời",
}

METRIC_DISPLAY = {
    **FINANCIAL_NAMES,
    **RATIO_NAMES,
    **MARKET_NAMES,
    **DERIVED_NAMES,
    **MACRO_DISPLAY,
}
