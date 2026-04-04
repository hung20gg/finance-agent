import yfinance as yf
import pandas as pd
from datetime import datetime
import os

class CommodityPriceFetcher:
    """Class để lấy giá commodity từ Yahoo Finance và lưu theo format chuẩn"""
    
    # Danh sách các mã commodity
    COMMODITIES = {
        # Kim loại quý (Precious Metals)
        'GC=F': 'Gold',
        'SI=F': 'Silver',
        'PL=F': 'Platinum',
        'PA=F': 'Palladium',
        
        # Năng lượng (Energy)
        'CL=F': 'Crude Oil WTI',
        'BZ=F': 'Brent Crude Oil',
        'NG=F': 'Natural Gas',
        'RB=F': 'Gasoline',
        'HO=F': 'Heating Oil',
        
        # Kim loại công nghiệp (Industrial Metals)
        'HG=F': 'Copper',
        'ALI=F': 'Aluminum',
        'TIO=F': 'Iron Ore',
        
        # Nông sản (Agricultural)
        'ZC=F': 'Corn',
        'ZW=F': 'Wheat',
        'ZS=F': 'Soybeans',
        'KC=F': 'Coffee',
        'SB=F': 'Sugar',
        'CC=F': 'Cocoa',
        'CT=F': 'Cotton',
        'ZO=F': 'Oats',
        'LE=F': 'Live Cattle',
        'HE=F': 'Lean Hogs',
        'ZL=F': 'Soybean Oil',
        'OJ=F': 'Orange Juice',
        
        # Khác (Others)
        'LBS=F': 'Lumber',
    }
    
    def __init__(self):
        self.all_data = {}
    
    def get_historical_data(self, symbol, start_date='2010-01-01', end_date=None):
        """
        Lấy dữ liệu lịch sử của một commodity
        
        Returns:
        --------
        pd.DataFrame
            Dữ liệu lịch sử với index là datetime
        """
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date)
            
            if not hist.empty:
                print(f"✓ Đã lấy {len(hist)} ngày dữ liệu cho {self.COMMODITIES.get(symbol, symbol)}")
                return hist
            else:
                print(f"✗ Không có dữ liệu cho {symbol}")
                return pd.DataFrame()
        
        except Exception as e:
            print(f"✗ Lỗi khi lấy dữ liệu {symbol}: {str(e)}")
            return pd.DataFrame()
    
    def convert_to_monthly(self, daily_data):
        """
        Chuyển đổi dữ liệu daily sang monthly
        
        Parameters:
        -----------
        daily_data : pd.DataFrame
            Dữ liệu daily với index là datetime
        
        Returns:
        --------
        pd.DataFrame
            Dữ liệu monthly (lấy cuối tháng)
        """
        if daily_data.empty:
            return pd.DataFrame()
        
        # Resample theo tháng, lấy giá cuối tháng
        monthly = daily_data.resample('ME').agg({
            'Open': 'first',      # Giá mở cửa đầu tháng
            'High': 'max',        # Giá cao nhất trong tháng
            'Low': 'min',         # Giá thấp nhất trong tháng
            'Close': 'last',      # Giá đóng cửa cuối tháng
            'Volume': 'sum'       # Tổng volume trong tháng
        })
        
        return monthly
    
    def calculate_ema(self, data, periods):
        """
        Tính EMA (Exponential Moving Average) cho nhiều periods
        
        Parameters:
        -----------
        data : pd.DataFrame
            Dữ liệu với cột 'Close'
        periods : list
            List các periods cần tính EMA (e.g., [12, 26, 20, 50])
        
        Returns:
        --------
        pd.DataFrame
            DataFrame với các cột EMA được thêm vào
        """
        if data.empty:
            return data
        
        data_with_ema = data.copy()
        
        for period in periods:
            ema_col = f'EMA{period}'
            data_with_ema[ema_col] = data_with_ema['Close'].ewm(span=period, adjust=False).mean()
        
        return data_with_ema
    
    def fetch_all_commodities(self, start_date='2010-01-01', end_date=None):
        """
        Lấy dữ liệu tất cả commodities
        
        Returns:
        --------
        dict
            Dictionary với key là symbol, value là DataFrame
        """
        print(f"\nĐang lấy dữ liệu từ {start_date} đến {end_date or 'hôm nay'}")
        print("=" * 80)
        
        all_data = {}
        
        for symbol in self.COMMODITIES.keys():
            data = self.get_historical_data(symbol, start_date, end_date)
            if not data.empty:
                all_data[symbol] = data
        
        self.all_data = all_data
        return all_data
    
    def create_long_format(self, data_dict, duration='daily'):
        """
        Chuyển đổi dữ liệu sang format dạng long
        
        Parameters:
        -----------
        data_dict : dict
            Dictionary chứa dữ liệu commodity
        duration : str
            'daily' hoặc 'monthly'
        
        Returns:
        --------
        pd.DataFrame
            DataFrame với cấu trúc:
            - time
            - duration
            - indicator_code
            - indicator_name
            - value
            - volume
            - ema12, ema26 (for monthly)
            - ema20, ema50 (for daily)
        """
        all_records = []
        
        # Determine which EMAs to calculate based on duration
        ema_periods = [20, 50] if duration == 'daily' else [12, 26]
        
        for symbol, data in data_dict.items():
            if data.empty:
                continue
            
            indicator_name = self.COMMODITIES.get(symbol, symbol)
            
            # Chuyển đổi sang monthly nếu cần
            if duration == 'monthly':
                data = self.convert_to_monthly(data)
            
            # Calculate EMAs
            data = self.calculate_ema(data, ema_periods)
            
            # Tạo records cho format long
            for timestamp, row in data.iterrows():
                record = {
                    'time': timestamp,
                    'duration': duration,
                    'indicator_code': symbol,
                    'indicator_name': indicator_name,
                    'value': row['Close'],  # Giá đóng cửa
                    'volume': row['Volume']
                }
                
                # Add EMAs based on duration
                if duration == 'daily':
                    record['ema20'] = row.get('EMA20', None)
                    record['ema50'] = row.get('EMA50', None)
                else:  # monthly
                    record['ema12'] = row.get('EMA12', None)
                    record['ema26'] = row.get('EMA26', None)
                
                all_records.append(record)
        
        df = pd.DataFrame(all_records)
        
        # Sắp xếp theo time và indicator_code
        df = df.sort_values(['time', 'indicator_code']).reset_index(drop=True)
        
        return df
    
    def save_to_parquet(self, df, filename):
        """
        Lưu DataFrame vào file Parquet
        
        Parameters:
        -----------
        df : pd.DataFrame
            DataFrame cần lưu
        filename : str
            Tên file (không cần thêm .parquet)
        """
        if not filename.endswith('.parquet'):
            filename = filename + '.parquet'
        
        df.to_parquet(filename, engine='pyarrow', compression='snappy', index=False)
        print(f"✓ Đã lưu: {filename} ({len(df):,} rows)")


# ==================== MAIN FUNCTION ====================

def main(start_date='2010-01-01', end_date=None, output_dir='commodity_output'):
    """
    Hàm chính để lấy và lưu dữ liệu commodity
    
    Parameters:
    -----------
    start_date : str
        Ngày bắt đầu (YYYY-MM-DD)
    end_date : str
        Ngày kết thúc (YYYY-MM-DD), None = hôm nay
    output_dir : str
        Thư mục lưu output
    """
    print("=" * 80)
    print("COMMODITY PRICE FETCHER - VERSION 2.0")
    print("=" * 80)
    
    # Tạo thư mục output
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Khởi tạo fetcher
    fetcher = CommodityPriceFetcher()
    
    # 1. Lấy dữ liệu tất cả commodities
    all_data = fetcher.fetch_all_commodities(start_date, end_date)
    
    if not all_data:
        print("\n✗ Không lấy được dữ liệu nào!")
        return
    
    print("\n" + "=" * 80)
    print("ĐANG XỬ LÝ VÀ LƯU DỮ LIỆU...")
    print("=" * 80)
    
    # 2. Tạo Daily format
    print("\n[1/2] Tạo dữ liệu DAILY...")
    daily_df = fetcher.create_long_format(all_data, duration='daily')
    
    # Lưu daily
    fetcher.save_to_parquet(daily_df, f'{output_dir}/commodities_daily')    
    # 3. Tạo Monthly format
    print("\n[2/2] Tạo dữ liệu MONTHLY...")
    monthly_df = fetcher.create_long_format(all_data, duration='monthly')
    
    # Lưu monthly
    fetcher.save_to_parquet(monthly_df, f'{output_dir}/commodities_monthly')
    

    return daily_df, monthly_df



if __name__ == "__main__":
    # Chạy chương trình
    main(start_date='2010-01-01', output_dir='../data')