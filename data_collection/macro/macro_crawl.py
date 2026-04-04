import wbgapi as wb
import pandas as pd
import pandas_datareader as pdr
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

# ============================================================================
# 1. ANNUAL ECONOMIC DATA (2010-2025) - ALL COUNTRIES
# ============================================================================

def convert_to_long_format(data_dict, indicator_metadata):
    """
    Convert wide format data to long format with datetime, duration, indicator_name, country, value, unit
    
    Args:
        data_dict: Dictionary with indicator names as keys and DataFrames as values
        indicator_metadata: Dictionary mapping indicator names to (code, divisor, unit)
    """
    all_records = []
    
    for indicator_name, df in data_dict.items():
        # Get the unit for this indicator
        unit = indicator_metadata[indicator_name][2]
        
        # Reset index to make country a column
        df_reset = df.reset_index()
        df_reset = df_reset.rename(columns={'economy': 'country'})
        
        # Melt to convert years from columns to rows
        df_long = pd.melt(
            df_reset,
            id_vars=['country'],
            var_name='duration',
            value_name='value'
        )
        
        # Extract year from column names (e.g., 'YR2018' -> 2018)
        df_long['duration'] = df_long['duration'].str.replace('YR', '').astype(int)
        
        # Convert year to datetime (January 1st of each year)
        df_long['datetime'] = pd.to_datetime(df_long['duration'], format='%Y')
        df_long['duration'] = 'annually'
        
        # Add metadata columns
        df_long['indicator_name'] = indicator_name
        df_long['unit'] = unit
        
        # Reorder columns
        df_long = df_long[['datetime', 'duration', 'indicator_name', 'country', 'value', 'unit']]
        
        all_records.append(df_long)
    
    # Combine all indicators
    result = pd.concat(all_records, ignore_index=True)
    
    return result

def get_annual_economic_data(country, start_year=2010, end_year=2024):
    """
    Get GDP, GNI, Trade, Unemployment for all countries (2010-2025)
    Note: 2025 data likely incomplete
    """
    
    indicators = {
        'GDP': ('NY.GDP.MKTP.CD', 1e9, 'Billion USD'),
        'GDP_Growth_%': ('NY.GDP.MKTP.KD.ZG', 1, 'Percentage'),
        'GNI': ('NY.GNP.MKTP.CD', 1e9, 'Billion USD'),
        'GNI_per_capita': ('NY.GNP.PCAP.CD', 1, 'USD'),
        'Exports_%_GDP': ('NE.EXP.GNFS.ZS', 1, 'Percentage'),
        'Imports_%_GDP': ('NE.IMP.GNFS.ZS', 1, 'Percentage'),
        'Unemployment_%': ('SL.UEM.TOTL.ZS', 1, 'Percentage'),
        'Lending_Rate_%': ('FR.INR.LEND', 1, 'Percentage'),
        'Inflation_%': ('FP.CPI.TOTL.ZG', 1, 'Percentage')
    }
    
    all_data = {}
    time_range = range(start_year, end_year + 1)
    
    print(f"Downloading Annual Economic Data ({start_year}-{end_year})...")
    for indicator_name, (code, divisor, unit) in indicators.items():
        try:
            df = wb.data.DataFrame(code, country, time=time_range)
            df = df / divisor
            
            all_data[indicator_name] = df
            print(f"  ✓ {indicator_name}")
        except Exception as e:
            print(f"  ✗ {indicator_name}: {str(e)[:50]}")

    df_long = convert_to_long_format(all_data, indicators)
    
    return df_long

# ============================================================================
# 2. DAILY US TREASURY RATES (2010-2025)
# ============================================================================

def convert_us_treasury_to_long_format(treasury_df, country='USA'):
    """
    Convert treasury DataFrame to long format
    """
    all_records = []
    
    # Reset index to make DATE a column
    df_reset = treasury_df.reset_index()
    df_reset = df_reset.rename(columns={'DATE': 'datetime'})
    
    # Melt to convert treasury types from columns to rows
    df_long = pd.melt(
        df_reset,
        id_vars=['datetime'],
        var_name='indicator_name',
        value_name='value'
    )
    
    # Add metadata columns
    df_long['duration'] = 'monthly'
    df_long['country'] = country
    df_long['unit'] = 'Percentage'
    
    # Map indicator names to more descriptive names
    df_long['indicator_name'] = df_long['indicator_name'].map({
        '2Y': 'USA_2Y',
        '10Y': 'USA_10Y',
    })
    
    # Reorder columns
    df_long = df_long[['datetime', 'duration', 'indicator_name', 'country', 'value', 'unit']]
    
    return df_long

def get_daily_us_treasury(start_year=2010):
    """Get daily US 2Y and 10Y Treasury yields from 2010-2025"""
    
    start = datetime(start_year, 1, 1)
    end = datetime.now()
    
    print("\nDownloading Daily US Treasury Rates (2010-2025)...")
    
    treasury = pd.DataFrame()
    
    try:
        treasury['2Y'] = pdr.DataReader('DGS2', 'fred', start, end)['DGS2']
        print("  ✓ US 2-Year Treasury (Daily)")
    except Exception as e:
        print(f"  ✗ US 2Y: {e}")
    
    try:
        treasury['10Y'] = pdr.DataReader('DGS10', 'fred', start, end)['DGS10']
        print("  ✓ US 10-Year Treasury (Daily)")
    except Exception as e:
        print(f"  ✗ US 10Y: {e}")

    treasury = treasury.resample('M').mean()

    # Convert to long format
    treasury_long = convert_us_treasury_to_long_format(treasury, country='USA')
    
    return treasury_long
# ============================================================================
# 3. MONTHLY BOND YIELDS - JAPAN, KOREA (2010-2025)
# ============================================================================

def convert_bond_yields_to_long_format(bond_yields_dict):
    """
    Convert bond yields dictionary to long format
    """
    all_records = []
    
    # Mapping from key names to (country, indicator_name)
    mapping = {
        'Japan_10Y': ('JPN', 'JPN_10Y'),
        'Korea_10Y': ('KOR', 'KOR_10Y')
    }
    
    for key, df in bond_yields_dict.items():
        if df.empty:
            continue
            
        country, indicator_name = mapping.get(key, (key, 'Bond_Yield'))
        
        # Reset index to make DATE a column
        df_reset = df.reset_index()
        df_reset = df_reset.rename(columns={'DATE': 'datetime'})
        
        # Get the value column (first non-DATE column)
        value_col = df_reset.columns[1]
        
        # Create long format
        df_long = pd.DataFrame({
            'datetime': df_reset['datetime'],
            'duration': 'monthly',
            'indicator_name': indicator_name,
            'country': country,
            'value': df_reset[value_col],
            'unit': 'Percentage'
        })
        
        all_records.append(df_long)
    
    # Combine all bond yields
    if all_records:
        result = pd.concat(all_records, ignore_index=True)
        return result
    else:
        return pd.DataFrame()

def get_monthly_bond_yields(start_year=2018):
    """Get monthly 10Y government bond yields for Japan and Korea"""
    
    start = datetime(start_year, 1, 1)
    end = datetime.now()
    
    print("\nDownloading Monthly Bond Yields (2010-2025)...")
    
    bond_yields = {}
    
    # Japan 10Y
    try:
        bond_yields['Japan_10Y'] = pdr.DataReader('IRLTLT01JPM156N', 'fred', start, end)
        print("  ✓ Japan 10-Year (Monthly)")
    except Exception as e:
        print(f"  ✗ Japan: {e}")
    
    # Korea 10Y
    try:
        bond_yields['Korea_10Y'] = pdr.DataReader('IRLTLT01KRM156N', 'fred', start, end)
        print("  ✓ South Korea 10-Year (Monthly)")
    except Exception as e:
        print(f"  ✗ Korea: {e}")
    
    # Convert to long format
    bond_yields_long = convert_bond_yields_to_long_format(bond_yields)
    
    return bond_yields_long



# ============================================================================
# MAIN EXECUTION
# ============================================================================

# Define all countries
countries = [
    'USA', 'CHN', 'JPN', 'DEU', 'IND', 'VNM', 
    'GBR', 'KOR', 'THA', 'SGP', 'FRA', 'CAN', 
]

country_names = {
    'USA': 'United States', 'CHN': 'China', 'JPN': 'Japan', 
    'DEU': 'Germany', 'IND': 'India', 'VNM': 'Vietnam',
    'GBR': 'United Kingdom', 'KOR': 'South Korea', 'THA': 'Thailand',
    'SGP': 'Singapore', 'FRA': 'France', 'CAN': 'Canada',
    'BRA': 'Brazil', 'AUS': 'Australia', 'IDN': 'Indonesia',
    'MEX': 'Mexico', 'ITA': 'Italy', 'ESP': 'Spain'
}

print("="*80)
print("ECONOMIC DATA COLLECTION: 2010-2025")
print("="*80)

# 1. Get annual economic data for all countries

annual_data = []
for country in countries:
    annual_data.append(get_annual_economic_data(country, 2020, 2025))

# 2. Get daily US treasury rates
us_treasury = get_daily_us_treasury(2010)

# 3. Get monthly bond yields (Japan, Korea)
monthly_bonds = get_monthly_bond_yields(2010)


# ============================================================================
# SAVE ALL DATA TO FILES
# ============================================================================

# print("\n" + "="*80)
# print("SAVING DATA TO FILES")
# print("="*80)

df_macro = pd.concat(annual_data)
# Save annual data for each indicator
filename = f'../data/annual_2010_2025.parquet'
df_macro.to_parquet(filename)
# print(f"  ✓ Saved: {filename}")

# Save Treasury rates
df_bond = pd.concat([us_treasury, monthly_bonds])
df_bond.to_parquet('../data/monthly_bond.parquet')