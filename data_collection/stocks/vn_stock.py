import pandas as pd
import numpy as np
import time
from dotenv import load_dotenv
import os
load_dotenv()

from vnstock import register_user
# register_user(api_key=os.getenv('VNSTOCK_API_KEY'))

from vnstock.api.company import Company
from vnstock.api.listing import Listing
from vnstock.api.quote import Quote


bank_stock_code = [
    "ABB", "ACB", "BAB", "BID", "BVB", "CTG", "EIB", "HDB", "KLB", "LPB", "MBB", "MSB", "NAB", "NVB", "OCB",
    "PGB", "SGB", "SHB", "SSB", "STB", "TCB", "TPB", "VAB", "VCB", "VIB", "VPB"
]

securities_stock_code = [
    "ABW", "AGR", "APG", "CTS", "DSE", "HCM", "MBS", "ORS", "SBS", "SHS", "SSI", "TCI", "TCX", "TVB", "TVS",
    "VCI", "VDS", "VIX", "VND", "UPS",
]

corp_stock_code = [
    "AAA", "AAM", "ABC", "ACC", "ACG", "ACL", "ACV", "ADP", "ADS", "AFX", "AGG", "AMS", "ANT", "ANV",
    "APF", "ASM", "AST", "AVC", "BAF", "BCA", "BCM", "BDG", "BDT", "BSL", "BSR", "BWE", "C32", "C4G",
    "CAG", "CAP", "CCA", "CCL", "CCM", "CDN", "CEO", "CHP", "CIG", "CII", "CKG", "CLH", "CLL",
    "CMG", "CMX", "CNG", "CRE", "CTB", "CTD", "CTP", "CTR", "CVT", "D2D", "DAH", "DBC", "DBD",
    "DC4", "DDV", "DGC", "DHA", "DHC", "DHG", "DHT", "DIG", "DMC", "DNA", "DNH", "DP3", "DPG", "DPM", "DQC",
    "DRC", "DRI", "DRL", "DSN", "DVM", "DVN", "DXG", "DXP", "EBS", "ELC", "EVE", "FCN", "FCS",
    "FMC", "FOC", "FOX", "FPT", "GAS", "GEX", "GHC", "GIL", "GMD", "GSP", "GVR", "HAG", "HAH", "HAN", "HAP",
    "HAX", "HBC", "HDC", "HDG", "HGM", "HHP", "HHV", "HKT", "HLC", "HMR", "HND", "HNG", "HPG", "HPX", "HQC",
    "HSA", "HSG", "HSV", "HTC", "HTG", "HTN", "HUT", "HVX", "ICN", "IDC", "IDI", "IDV", "IFS", "ILB", "IMP",
    "ITA", "ITD", "JVC", "KBC", "KDC", "KDH", "KTS", "L14", "L18", "LCG", "LDG", "LGL", "LHG", "LSS", "MBG",
    "MCG", "MH3", "MML", "MPC", "MSH", "MSN", "MVN", "MWG", "NAF", "NCG", "NCT", "NHA", "NHH", "NKG",
    "NLG", "NT2", "NTC", "NTP", "OIL", "PAN", "PAP", "PC1", "PDN", "PDR", "PFL", "PGD", "PHC", "PHP", "PHR",
    "PIV", "PJT", "PLC", "PLX", "POS", "POW", "PPC", "PSB", "PSE", "PTC", "PTL", "PVB", "PVC", "PVD", "PVM",
    "PVP", "PVS", "PVT", "QCG", "QNC", "QPH", "REE", "SAB", "SAM", "SAV", "SBB", "SBG", "SBT", "SCI",
    "SCR", "SCS", "SGI", "SGP", "SGT", "SHC", "SIP", "SJS", "SLS", "SMC", "SNZ", "SRF", "SSG", "STC", "STD",
    "STH", "STK", "STP", "SVC", "SZC", "SZE", "SZG", "TA9", "TAL", "TAR", "TCH", "TCL", "TCM", "TCR", "TCT",
    "TDM", "TDP", "THG", "TID", "TIG", "TIP", "TLH", "TMS", "TMT", "TNG", "TNI", "TOS", "TRA", "TRC", "TSA",
    "TT6", "TTH", "TTN", "TV3", "TVN", "TYA", "UDJ", "UPH",  "VC3", "VCG", "VGC", "VGI", "VGR", "VGS",
    "VGT", "VHC", "VHM", "VIC", "VIP", "VIW", "VJC", "VLB", "VLC", "VNF", "VNM", "VNZ", "VOS", "VPD",
    "VPH", "VPI", "VPL", "VRE", "VRG", "VSC", "VSN", "VTE", "VTO", "VTP"
]
symbols = corp_stock_code + bank_stock_code + securities_stock_code 

# symbols = ["VNINDEX", "VN"]

industry_trans = {
    "Ngân hàng": "Banking",
    "Bất động sản": "Real Estate",
    "Xây dựng và Vật liệu": "Construction and Materials",
    "Thực phẩm và đồ uống": "Food and Beverages",
    "Hóa chất": "Chemicals",
    "Dịch vụ tài chính": "Financial Services",
    "Tài nguyên Cơ bản": "Basic Resources",
    "Bán lẻ": "Retail",
    "Dầu khí": "Oil and Gas",
    "Điện, nước & xăng dầu khí đốt": "Utilities (Electricity, Water & Gas)",
    "Hàng cá nhân & Gia dụng": "Personal and Household Goods",
    "Công nghệ Thông tin": "Information Technology",
    "Hàng & Dịch vụ Công nghiệp": "Industrial Goods and Services",
    "Truyền thông": "Media",
    "Du lịch và Giải trí": "Travel and Leisure",
    "Y tế": "Healthcare",
    "Ô tô và phụ tùng": "Automobiles and Parts",
    "Viễn thông": "Telecommunications"
}


def compute_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def get_detailed_stock(stock_code):
    quote = Quote(symbol=stock_code, source='VCI')
    df = quote.history(start='2016-01-01', end='2026-01-01')
    
    # EMA
    
    df = df.drop(columns=['open', 'high', 'low'])
    df['stock_code'] = stock_code
    
    # Set time as index for resampling
    df = df.set_index('time')
    
    df_monthly = df.resample('ME').last()
    df_monthly = df_monthly.reset_index()
    df_monthly['time'] = df_monthly['time']
    df_monthly = df_monthly.set_index(df_monthly.index)
    
    df_monthly['EMA12'] = compute_ema(df_monthly['close'], span=12)
    df_monthly['EMA26'] = compute_ema(df_monthly['close'], span=26)
    
    
    df['EMA20'] = compute_ema(df['close'], span=20)
    df['EMA50'] = compute_ema(df['close'], span=50)
    df['EMA200'] = compute_ema(df['close'], span=200)
    
    # Reset index to make time a column again
    df = df.reset_index()
    
    return df, df_monthly


def get_company_info(symbols):
    company_overviews = []
# Iterate through each symbol and print company information
    for symbol in symbols:
        company = Company(symbol=symbol, source='VCI')
        try:
            company_overview = company.overview()
            company_overview['symbol'] = symbol
            company_overviews.append(company_overview)
        except Exception as e:
            print(e)
            print(f"Error at {symbol}")
        time.sleep(2)

    df_company_overviews = pd.concat(company_overviews, ignore_index=True)
    # Display the concatenated DataFrame
    # df_company_overviews.head()

    listing = Listing(source='VCI')
    vn30 = listing.symbols_by_group('VN30').values
    hnx30 = listing.symbols_by_group('HNX30').values

    mask_vn30 = df_company_overviews['symbol'].isin(vn30)
    mask_hnx30 = df_company_overviews['symbol'].isin(hnx30)

    df_company_overviews['stock_indices'] = 'OTHER'
    df_company_overviews.loc[mask_vn30, 'stock_indices'] = 'VN30'
    df_company_overviews.loc[mask_hnx30, 'stock_indices'] = 'HNX30'

    if 'sector' in df_company_overviews.columns and 'industry' not in df_company_overviews.columns:
        df_company_overviews.rename(columns={'sector': 'industry'}, inplace=True)
    if 'industry' not in df_company_overviews.columns:
        df_company_overviews['industry'] = np.nan
    else:
        df_company_overviews['industry'] = df_company_overviews['industry'].map(industry_trans)

    df_company_overviews.drop(columns = ['company_type','outstanding_share','established_year','no_employees','delta_in_week','delta_in_month','delta_in_year','industry_id','industry_id_v2'], inplace = True, errors='ignore')
    if 'issue_share' in df_company_overviews.columns:
        df_company_overviews['issue_share'] *= 1_000_000

    profile_columns = [
        'company_profile',
        'history_dev',
        'company_promise',
        'business_risk',
        'key_developments',
        'business_strategies',
    ]
    available_profile_columns = [col for col in profile_columns if col in df_company_overviews.columns]
    df_company_overviews['combine_profile'] = df_company_overviews.apply(
        lambda row: '\n '.join(
            [f"{col}: {row[col]}" for col in available_profile_columns if pd.notna(row[col])]
        ),
        axis=1
    )
    df_company_overviews.drop(columns=available_profile_columns, inplace=True, errors='ignore')

    df_company_info = df_company_overviews
    df_company_info['is_bank'] = np.where(df_company_info['symbol'].isin(bank_stock_code), True, False)
    df_company_info['is_securities'] = np.where(df_company_info['symbol'].isin(securities_stock_code), True, False)

    name = listing.symbols_by_exchange(lang='en')
    name.rename(columns={'organ_name': 'en_organ_name', 'organ_short_name': 'en_organ_short_name'}, inplace=True)
    name = name.reindex(columns=['symbol', 'en_organ_name', 'en_organ_short_name'])
    df_company_info = pd.merge(df_company_info, name, on='symbol', how='left')

    if 'organ_name' in df_company_info.columns and 'company_name' not in df_company_info.columns:
        df_company_info.rename(columns={'organ_name': 'company_name'}, inplace=True)
    df_company_info.rename(columns = {'symbol':'stock_code',  'en_organ_name':'en_company_name', 'en_organ_short_name':'en_short_name'}, inplace = True)
    for col in ['company_name', 'short_name', 'en_company_name', 'en_short_name', 'combine_profile', 'industry', 'exchange', 'foreign_percent', 'issue_share', 'no_shareholders', 'stock_rating', 'website']:
        if col not in df_company_info.columns:
            df_company_info[col] = np.nan
    df_company_info= df_company_info[['stock_code','company_name', 'short_name','en_company_name','en_short_name','combine_profile','industry','exchange','foreign_percent','issue_share','no_shareholders','stock_rating','website', 'stock_indices', 'is_bank', 'is_securities']]
    return df_company_info


dfs = []
dfs_monthly = []
for stock_code in symbols:
    start = time.time()
    df, df_monthly = get_detailed_stock(stock_code)
    dfs.append(df)
    dfs_monthly.append(df_monthly)
    print(f"Processing stock: {stock_code} in {time.time() - start:.2f} seconds")
    time.sleep(2)  # Sleep for 1 second between requests
# df_stock_price = pd.concat(dfs, ignore_index=True)
# df_stock_price_monthly = pd.concat(dfs_monthly, ignore_index=True)

# df_stock_price.to_parquet('../data/vn_stock_price_daily.parquet')
# df_stock_price_monthly.to_parquet('../data/vn_stock_price_monthly.parquet')

# df_company_info = get_company_info(symbols)
# df_company_info.to_csv('../financial_statement/transform/metadata/df_company_info.csv', index=False)

listing = Listing(source='VCI')
print(listing.symbols_by_exchange(lang='en'))