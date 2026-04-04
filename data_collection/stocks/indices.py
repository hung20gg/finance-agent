import yfinance as yf
import pandas as pd
import numpy as np
import time
from vnstock import Vnstock


# Global indices with their yfinance ticker symbols
global_indices = {
    "SP500": "^GSPC",      # S&P 500
    "NASDAQ": "^IXIC",     # NASDAQ Composite
    "FTSE": "^FTSE",       # FTSE 100
    "NIKKEI": "^N225",     # Nikkei 225
    "SSEC": "^SSEC",       # Shanghai Composite
    "HSI": "^HSI",         # Hang Seng Index (Hong Kong)
    "KOSPI": "^KS11",      # KOSPI (South Korea)
    "STI": "^STI",         # Straits Times Index (Singapore)
}


vnindex = ["VNINDEX", "VN30"]
symbols = list(global_indices.keys())


def compute_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()

def get_detailed_index(index_name):
    """
    Get historical data for a global index using yfinance
    """
    ticker = global_indices[index_name]
    
    # Download data from yfinance
    df = yf.download(ticker, start='2010-01-01', end='2026-01-01', progress=False)
    
    # Reset index to make Date a column
    df = df.reset_index()
    
    # Handle the case where yfinance returns a multi-level column structure FIRST
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Now rename columns to match the original structure
    df.columns = df.columns.str.lower()
    df = df.rename(columns={'date': 'time'})
    
    # Use Adj Close if available, otherwise use Close
    if 'adj close' in df.columns:
        df = df.drop(columns=['open', 'high', 'low', 'close'], errors='ignore')
        df = df.rename(columns={'adj close': 'close'})
    else:
        df = df.drop(columns=['open', 'high', 'low'], errors='ignore')
    
    df['index_name'] = index_name
    
    # Set time as index for resampling
    df = df.set_index('time')
    
    df_monthly = df.resample('ME').last()
    df_monthly = df_monthly.reset_index()
    df_monthly['time'] = df_monthly['time']
    
    # Monthly data
    df_monthly = df.resample('ME').last()
    df_monthly['EMA12'] = compute_ema(df_monthly['close'], span=12)
    df_monthly['EMA26'] = compute_ema(df_monthly['close'], span=26)
    
    # Daily EMAs
    df['EMA20'] = compute_ema(df['close'], span=20)
    df['EMA50'] = compute_ema(df['close'], span=50)
    df['EMA200'] = compute_ema(df['close'], span=200)
    
    # Reset index to make time a column again
    df = df.reset_index()
    df_monthly = df_monthly.reset_index()
    
    return df, df_monthly


def get_vn_index(stock_code):
    stock = Vnstock().stock(symbol=stock_code, source='VCI')
    df = stock.quote.history(start='2010-01-01', end='2026-01-01')
    
    # EMA
    
    df = df.drop(columns=['open', 'high', 'low'])
    df['index_name'] = stock_code
    
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
for index_name in symbols:
    start = time.time()
    try:
        df, df_monthly = get_detailed_index(index_name)
        dfs.append(df)
        dfs_monthly.append(df_monthly)
        print(f"Processing index: {index_name} ({global_indices[index_name]}) in {time.time() - start:.2f} seconds")
    except Exception as e:
        print(f"Error processing {index_name}: {e}")
    time.sleep(1)  # Sleep for 1 second between requests

for vn_code in vnindex:
    start = time.time()
    try:
        df, df_monthly = get_vn_index(vn_code)
        dfs.append(df)
        dfs_monthly.append(df_monthly)
        print(f"Processing index: {vn_code} in {time.time() - start:.2f} seconds")
    except Exception as e:
        print(f"Error processing {vn_code}: {e}")
    time.sleep(1)  # Sleep for 1 second between requests

df_index_price = pd.concat(dfs, ignore_index=True)
df_index_price_monthly = pd.concat(dfs_monthly, ignore_index=True)

print(df_index_price.head())

# Save to CSV files
df_index_price.to_parquet('../data/global_indices_daily.parquet', index=False)
df_index_price_monthly.to_parquet('../data/global_indices_monthly.parquet', index=False)

print(f"\nData saved successfully!")
print(f"Daily data shape: {df_index_price.shape}")
print(f"Monthly data shape: {df_index_price_monthly.shape}")
