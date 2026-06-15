import pandas as pd
import numpy as np
import time
import yfinance as yf
from dotenv import load_dotenv
import os
load_dotenv()


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

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
EXISTING_COMPANY_INFO_PATH = os.path.join(
    CURRENT_DIR,
    '..',
    'financial_statement',
    'transform',
    'metadata',
    'df_company_info.csv',
)
OUTPUT_COMPANY_INFO_PATH = os.path.join(
    CURRENT_DIR,
    '..',
    'financial_statement',
    'transform',
    'metadata',
    'df_company_info_yahoo.csv',
)
OUTPUT_DAILY_PRICE_PATH = os.path.join(CURRENT_DIR, '..', 'data', 'vn_stock_price_daily_yahoo.parquet')
OUTPUT_MONTHLY_PRICE_PATH = os.path.join(CURRENT_DIR, '..', 'data', 'vn_stock_price_monthly_yahoo.parquet')


def compute_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def get_yahoo_symbol_with_history(stock_code):
    yahoo_symbols = [f"{stock_code}.VN", f"{stock_code}.HN"]
    for yahoo_symbol in yahoo_symbols:
        try:
            df = yf.download(
                yahoo_symbol,
                start='2016-01-01',
                end='2026-01-01',
                progress=False,
                auto_adjust=False,
            )
            if not df.empty:
                return yahoo_symbol, df
        except Exception as e:
            print(f"Yahoo Finance price error at {yahoo_symbol}: {e}")

    return None, pd.DataFrame()


def normalize_yahoo_price(df):
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.reset_index()
    df.columns = [str(col).lower().replace(' ', '_') for col in df.columns]
    df.rename(columns={'date': 'time', 'adj_close': 'adj_close'}, inplace=True)

    column_map = {
        'time': 'time',
        'close': 'close',
        'volume': 'volume',
    }
    available_columns = [col for col in column_map if col in df.columns]
    return df[available_columns].rename(columns=column_map)


def get_detailed_stock_yahoo(stock_code):
    yahoo_symbol, df = get_yahoo_symbol_with_history(stock_code)
    if df.empty:
        raise ValueError(f"No Yahoo Finance price data for {stock_code}")

    df = normalize_yahoo_price(df)
    df['stock_code'] = stock_code
    df['yahoo_symbol'] = yahoo_symbol
    df = df.set_index('time')

    df_monthly = df.resample('ME').last()
    df_monthly = df_monthly.reset_index()
    df_monthly = df_monthly.set_index(df_monthly.index)

    df_monthly['EMA12'] = compute_ema(df_monthly['close'], span=12)
    df_monthly['EMA26'] = compute_ema(df_monthly['close'], span=26)

    df['EMA20'] = compute_ema(df['close'], span=20)
    df['EMA50'] = compute_ema(df['close'], span=50)
    df['EMA200'] = compute_ema(df['close'], span=200)

    df = df.reset_index()
    return df, df_monthly


def get_stock_prices_yahoo(symbols):
    dfs = []
    dfs_monthly = []
    missing_prices = []
    for stock_code in symbols:
        start = time.time()
        try:
            df, df_monthly = get_detailed_stock_yahoo(stock_code)
            dfs.append(df)
            dfs_monthly.append(df_monthly)
        except Exception as e:
            missing_prices.append(stock_code)
            print(f"Warning: Missing Yahoo price data for {stock_code}: {e}")

        print(f"Processing Yahoo stock price: {stock_code} in {time.time() - start:.2f} seconds")
        time.sleep(0.5)

    if missing_prices:
        print(f"Warning: Missing Yahoo stock prices for {len(missing_prices)} symbols: {missing_prices}")

    if not dfs:
        raise ValueError("No Yahoo Finance price data was collected.")

    return pd.concat(dfs, ignore_index=True), pd.concat(dfs_monthly, ignore_index=True)


def load_existing_company_info():
    if not os.path.exists(EXISTING_COMPANY_INFO_PATH):
        return pd.DataFrame(columns=['stock_code', 'company_name', 'stock_indices'])

    df = pd.read_csv(EXISTING_COMPANY_INFO_PATH)
    return df.reindex(columns=['stock_code', 'company_name', 'stock_indices'])


def get_yahoo_company_name(stock_code):
    yahoo_symbols = [f"{stock_code}.VN", f"{stock_code}.HN"]
    for yahoo_symbol in yahoo_symbols:
        try:
            info = yf.Ticker(yahoo_symbol).get_info()
            company_name = info.get('longName') or info.get('shortName')
            if company_name:
                return company_name
        except Exception as e:
            print(f"Yahoo Finance error at {yahoo_symbol}: {e}")

    return np.nan


def get_company_info_yahoo(symbols):
    existing_company_info = load_existing_company_info()
    existing_company_info = existing_company_info.drop_duplicates(subset=['stock_code'])
    existing_company_info = existing_company_info.set_index('stock_code')

    rows = []
    missing_company_name = []
    missing_stock_indices = []
    missing_en_company_name = []
    for symbol in symbols:
        start = time.time()
        en_company_name = get_yahoo_company_name(symbol)

        if symbol in existing_company_info.index:
            existing_row = existing_company_info.loc[symbol]
            company_name = existing_row.get('company_name', np.nan)
            stock_indices = existing_row.get('stock_indices', np.nan)
        else:
            company_name = np.nan
            stock_indices = np.nan

        if pd.isna(company_name):
            missing_company_name.append(symbol)
            company_name = 'MISSING_VI_COMPANY_NAME'
        if pd.isna(stock_indices):
            missing_stock_indices.append(symbol)
            stock_indices = 'MISSING_STOCK_INDICES'
        if pd.isna(en_company_name):
            missing_en_company_name.append(symbol)

        rows.append({
            'stock_code': symbol,
            'company_name': company_name,
            'en_company_name': en_company_name,
            'stock_indices': stock_indices,
        })
        print(f"Processing Yahoo company info: {symbol} in {time.time() - start:.2f} seconds")
        time.sleep(0.5)

    if missing_company_name:
        print(f"Warning: Missing Vietnamese company_name for {len(missing_company_name)} symbols: {missing_company_name}")
    if missing_stock_indices:
        print(f"Warning: Missing stock_indices for {len(missing_stock_indices)} symbols: {missing_stock_indices}")
    if missing_en_company_name:
        print(f"Warning: Missing Yahoo en_company_name for {len(missing_en_company_name)} symbols: {missing_en_company_name}")

    return pd.DataFrame(rows)


if __name__ == '__main__':
    df_stock_price, df_stock_price_monthly = get_stock_prices_yahoo(symbols)
    df_stock_price.to_parquet(OUTPUT_DAILY_PRICE_PATH, index=False)
    df_stock_price_monthly.to_parquet(OUTPUT_MONTHLY_PRICE_PATH, index=False)

    df_company_info = get_company_info_yahoo(symbols)
    df_company_info.to_csv(OUTPUT_COMPANY_INFO_PATH, index=False)
