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
    "IS_100": "net_income",
    "BS_125": "loan_customer",
    "BS_300": "liabilities",
    "Bank_TM_121": "casa",
    "Bank_TM_45": "loan_construction",
    "Bank_TM_61": "loan_real_estate",
    "CF_130": "cash_equiv",
}

FINANCIAL_NAMES = {
    "revenue": "doanh thu",
    "net_income": "lợi nhuận ròng",
    "loan_customer": "dư nợ cho vay khách hàng",
    "liabilities": "tổng nợ phải trả",
    "casa": "tiền gửi không kỳ hạn",
    "loan_construction": "cho vay ngành xây dựng",
    "loan_real_estate": "cho vay bất động sản và tư vấn",
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
    "return_pct": "tỷ suất sinh lời",
    "avg_close": "giá đóng cửa trung bình",
    "std_close": "độ lệch chuẩn giá đóng cửa",
    "excess_return_vs_vnindex": "mức sinh lời vượt VNINDEX",
    "excess_return_vs_vn30": "mức sinh lời vượt VN30",
}

DERIVED_NAMES = {
    "revenue_yoy": "tăng trưởng YoY doanh thu",
    "net_income_yoy": "tăng trưởng YoY lợi nhuận ròng",
    "return_pct_yoy": "tăng trưởng YoY tỷ suất sinh lời",
}

METRIC_DISPLAY = {
    **FINANCIAL_NAMES,
    **RATIO_NAMES,
    **MARKET_NAMES,
    **DERIVED_NAMES,
}