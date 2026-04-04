from vnstock import Vnstock
import pandas as pd
import numpy as np
import time


non_bank_stock_code = ["HSG", "ELC", "VSC", "ACV", "REE", "SZC", "CSV", "PAN", "BSR", "SGP", "GMD", "ITD","FOX", "KDC", "SBT", "VGC", "HBC", "CTD", "DIG", "SCR", "KBC","MWG", "NHA", "VNM", "HPG", "VHM", "PNJ", "YEG", "FPT","MSN", "GAS", "VRE", "VJC", "VIC", "PLX", "SAB", "POW", "GVR", "BCM", "VPI", "DVM", "KDH", "HDC", "TCH", "CEO", "HUT", "NVL", "DBC", "SAF", "DHT", "VTP", "PVT", "FRT", "DGC", "DCM", "NKG", "CMG", "VGI", "PVC", "CAP", "DTD", "HLD", "L14", "L18", "LAS", "LHC", "NTP", "PLC", "PSD", "PVG", "PVS", "SLS", "TIG", "TMB", "TNG", "TVD", "VC3", "VCS", "DXG"]
bank_stock_code = ["BID", "EIB", "OCB", "CTG", "VCB", "ACB", "MBB", "HDB", "TPB", "VPB",  "STB", "TCB",  "SHB", "VIB", "CTG",  "ABB", "LPB", "NVB"]
securities_stock_code = ["MBS", "VND", "SSI", "VIX", "ORS"]

new = True
if new:
    bank_stock_code += ["EVF", "MSB", "NAB", "SGB", "VAB", "KLB", "BVB", "PGB", "NVB"]
    securities_stock_code += ["VCI", "TVS", "SHS", "DSE", "HCM", "VDS", "APG", "CTS", "AGR"]
    non_bank_stock_code += ["VCG", "LCG", "DPG", "CTI", "TIS", "PSH", "TLH", "STK", "TDG", "TVN", "DRI", "CNG", "SIP", "PVP", "VGS", "VHC", "IJC", "CII", "SJS", "NLG", "NT2", "LBM", "PC1", "HAH", "HAG", "KOS", "RAL", "PHR", "ILB", "AGG", "ASM", "CLL", "CRE", "D2D", "UIC", "TMS", "PPC", "PTB", "VOS", "VIP", "VTO", "NRC", "GEX", "HTN", "VLC", "GEE", "TCM", "PDR", "SCR", "HPX", "LDG", "AAA", "CTR", "SAM", "BWE", "SGT", "BMP", "ITC", "TTN", "VTE", "VHC", "MSH", "TTF", "ANV", "CMX", "IDI", "FMC", "BAF", "HT1", "PVD", "FIT", "ACL", "ABT", "AAM", "PET", "DGW", "DPM", "HDG", "IMP", "MAS"]


symbols = non_bank_stock_code + bank_stock_code + securities_stock_code 

# symbols = ["VNINDEX", "VN"]


def compute_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def get_detailed_stock(stock_code):
    stock = Vnstock().stock(symbol=stock_code, source='VCI')
    df = stock.quote.history(start='2010-01-01', end='2026-01-01')
    
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


dfs = []
dfs_monthly = []
for stock_code in symbols:
    start = time.time()
    df, df_monthly = get_detailed_stock(stock_code)
    dfs.append(df)
    dfs_monthly.append(df_monthly)
    print(f"Processing stock: {stock_code} in {time.time() - start:.2f} seconds")
    time.sleep(1)  # Sleep for 1 second between requests
df_stock_price = pd.concat(dfs, ignore_index=True)
df_stock_price_monthly = pd.concat(dfs_monthly, ignore_index=True)

df_stock_price.to_parquet('../data/vn_stock_price_daily.parquet')
df_stock_price_monthly.to_parquet('../data/vn_stock_price_monthly.parquet')