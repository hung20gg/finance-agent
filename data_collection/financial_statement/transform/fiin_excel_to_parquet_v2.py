import pandas as pd
import numpy as np
from tqdm import tqdm

import os
import glob


current_dir = os.path.dirname(os.path.abspath(__file__))


def calculate_industry_financial_statement(df_fs):
    company_table = pd.read_csv(os.path.join(current_dir, 'metadata', 'df_company_info.csv'))
    df_fs = pd.merge(df_fs, company_table[['stock_code', 'industry']], on='stock_code', how='left')

    df_industry_fs = df_fs.groupby(['industry', 'year', 'quarter', 'category_code', 'date_added'])['data'].agg([ 'mean']).reset_index()
    df_industry_fs.rename(columns={'mean': 'data', 'industry': 'stock_code'}, inplace=True)

    return df_industry_fs


def calculate_industry_financial_statement_explaination(df_tm):
    company_table = pd.read_csv(os.path.join(current_dir, 'metadata', 'df_company_info.csv'))
    df_tm = pd.merge(df_tm, company_table[['stock_code', 'industry']], on='stock_code', how='left')

    df_industry_tm = (
        df_tm.groupby(['industry', 'year', 'quarter', 'category_code', 'date_added'])['data']
        .mean()
        .reset_index()
    )
    df_industry_tm.rename(columns={'industry': 'stock_code', 'data': 'data'}, inplace=True)

    return df_industry_tm


mapping_file = pd.ExcelFile(os.path.join(current_dir, 'metadata', 'vietnames_to_fiin_2026.xlsx'))

df_map_bank = mapping_file.parse('fiin_bank')
df_map_sec = mapping_file.parse('fiin_sec')
df_map_corp = mapping_file.parse('fiin_corp')

df_map_tm_bank = mapping_file.parse('fiin_TM_bank')
df_map_tm_sec = mapping_file.parse('fiin_TM_sec')
df_map_tm_corp = mapping_file.parse('fiin_TM_corp')

df_map_sec.dropna(subset=['category_code'], inplace=True)
df_map_bank.dropna(subset=['category_code'], inplace=True)
df_map_corp.dropna(subset=['category_code'], inplace=True)

df_map_tm_bank['category_code'] = df_map_tm_bank['category_code'].apply(lambda x: "Bank_" + x)
df_map_tm_sec['category_code'] = df_map_tm_sec['category_code'].apply(lambda x: "Sec_" + x)
df_map_tm_corp['category_code'] = df_map_tm_corp['category_code'].apply(lambda x: "Corp_" + x)


df_bs = mapping_file.parse('Standard BS').dropna(subset=['universal_code'])
df_is = mapping_file.parse('Standard IS').dropna(subset=['universal_code'])
df_cf = mapping_file.parse('Standard CF').dropna(subset=['universal_code'])

df_bs['Universal_caption'] = df_bs['Universal_caption'].apply(lambda x: f'(Balance sheet) {x}')
df_is['Universal_caption'] = df_is['Universal_caption'].apply(lambda x: f'(Income statement) {x}')
df_cf['Universal_caption'] = df_cf['Universal_caption'].apply(lambda x: f'(Cash flow) {x}')
df = pd.concat([df_bs, df_is, df_cf], ignore_index=True)

df.rename(columns={'Universal_caption': 'en_caption', 'universal_code':'category_code'}, inplace=True)

# df.to_csv('../csv/v3/map_category_code_universal.csv', index=False)

df.rename(columns={'category_code': 'universal_code'}, inplace=True)


def get_source(text):
    if isinstance(text, str):
        return text.split('_')[0]
    return text

df_map_bank['source'] = df_map_bank['category_code'].apply(get_source)
df_map_sec['source'] = df_map_sec['category_code'].apply(get_source)    
df_map_corp['source'] = df_map_corp['category_code'].apply(get_source)  


df_map_bank_bs = df_map_bank[df_map_bank['source'] == 'BS']
df_map_bank_is = df_map_bank[df_map_bank['source'] == 'IS']
df_map_bank_cf = df_map_bank[df_map_bank['source'] == 'CF']

df_map_corp_bs = df_map_corp[df_map_corp['source'] == 'BS']
df_map_corp_is = df_map_corp[df_map_corp['source'] == 'IS']
df_map_corp_cf = df_map_corp[df_map_corp['source'] == 'CF']

df_map_sec_bs = df_map_sec[df_map_sec['source'] == 'BS']
df_map_sec_is = df_map_sec[df_map_sec['source'] == 'IS']
df_map_sec_cf = df_map_sec[df_map_sec['source'] == 'CF']

bank_args = {
    'Kết quả Kinh doanh': {
        'nrows': 30,
        'mapping': df_map_bank_is
    },
    'Cân đối kế toán': {
        'nrows': 92,
        'mapping': df_map_bank_bs
    },
    'Lưu chuyển tiền tệ': {
        'nrows': 62,
        'mapping': df_map_bank_cf
    }
    
}

corp_args = {
    'Kết quả Kinh doanh': {
        'nrows': 29,
        'mapping': df_map_corp_is
    },
    'Cân đối kế toán': {
        'nrows': 126,
        'mapping': df_map_corp_bs
    },
    'Lưu chuyển tiền tệ': {
        'Gián tiếp': {
                'nrows': 45,
                'mapping': df_map_corp_cf
        },
        'Trực tiếp': {
                'nrows': 32,
                'mapping': df_map_corp_cf[17:]
        }
        
    }
    
}

sec_args = {
    'Kết quả Kinh doanh': {
        'nrows': 93,
        'mapping': df_map_sec_is
    },
    'Cân đối kế toán': {
        'nrows': 216,
        'mapping': df_map_sec_bs
    },
    'Lưu chuyển tiền tệ': {
        'Gián tiếp': {
                'nrows': 159,
                'mapping': df_map_sec_cf
        },
        'Trực tiếp': {
                'nrows': 103,
                'mapping': df_map_sec_cf[:31]
        }
        
    }
    
}

bank_args_tm = {
    
        'nrows': 223,
        'mapping': df_map_tm_bank
    
}

corp_args_tm = {
        'nrows': 161,
        'mapping': df_map_tm_corp
    
    
}

sec_args_tm = {
        'nrows': 646,
        'mapping': df_map_tm_sec
    
}



map_share_sec = ~df_map_tm_sec['share_code'].isna()
map_share_corp = ~df_map_tm_corp['share_code'].isna()

df_map_tm_sec.loc[map_share_sec, 'category_code'] = df_map_tm_sec.loc[map_share_sec, 'share_code']
df_map_tm_corp.loc[map_share_corp, 'category_code'] = df_map_tm_corp.loc[map_share_corp, 'share_code']

df_map_tm_bank = df_map_tm_bank[['category_code', 'vi_caption', 'en_caption', 'parent_code']]
df_map_tm_sec = df_map_tm_sec[['category_code', 'vi_caption', 'en_caption', 'parent_code']]
df_map_tm_corp = df_map_tm_corp[['category_code', 'vi_caption', 'en_caption', 'parent_code']]

df_map_tm_sec.dropna(subset=['en_caption'], inplace=True)
df_map_tm_bank.dropna(subset=['en_caption'], inplace=True)
df_map_tm_corp.dropna(subset=['en_caption'], inplace=True)

df_tm_map = pd.concat([df_map_tm_bank, df_map_tm_sec, df_map_tm_corp], ignore_index=True)
df_tm_map.drop_duplicates(subset=['category_code'], inplace=True)
df_tm_map['en_caption'] = df_tm_map['en_caption'].apply(lambda x: "(Explaination) " + x if x else x)

def get_data(excel_file, type_):
    
    dfs = []
    dfs_sheet_names = []
    if type_ == 'bank':
        args = bank_args
    elif type_ == 'corp':
        args = corp_args
    else:
        args = sec_args
       
    sheet_names = list(args.keys())
    for sheet_name in sheet_names:

        if sheet_name == 'Lưu chuyển tiền tệ' and type_ != 'bank':
            temp_df = excel_file.parse(sheet_name=sheet_name, usecols=[0], header=None)
            gian_tiep_idx = temp_df.index[temp_df[0].astype(str).str.contains('Gián tiếp', case=False, na=False)].tolist()
            truc_tiep_idx = temp_df.index[temp_df[0].astype(str).str.contains('Trực tiếp', case=False, na=False)].tolist()
            
            if gian_tiep_idx:
                method = 'Gián tiếp'
                skiprows = gian_tiep_idx[0]
            elif truc_tiep_idx:
                method = 'Trực tiếp'
                skiprows = truc_tiep_idx[0]
            else:
                method = 'Gián tiếp'
                skiprows = 10
            curr_args = args[sheet_name][method]
        else:
            skiprows = 10
            curr_args = args[sheet_name]

        df_bs = excel_file.parse(
            sheet_name = sheet_name,
            skiprows=skiprows,
            nrows=curr_args['nrows'],
        )

        df_bs = df_bs.iloc[3:]
        fiin_cate = df_bs.iloc[:, 0].astype(str).values.tolist()
        map_cate = curr_args['mapping'][['category_code', 'vi_caption']].values.tolist()

        # Map the corresponding category code

        map_index = 0
        cate_index = 0
        cate_code = []
        for i in range(len(fiin_cate)):
            cate_index = i
            if fiin_cate[i].strip() == map_cate[map_index][1].strip():
                
                cate_code.append(map_cate[map_index][0])
                map_index += 1
            else:
                cate_code.append(np.nan)
            if map_index == len(map_cate):
                break
            

        cate_code.extend([np.nan]*(len(fiin_cate) - len(cate_code)))


        df_bs['category_code'] = cate_code
    #     dfs.append(df_bs)
    # return dfs
    
        # Convert to table

        table = []
        df_bs.dropna(subset=['category_code'], inplace=True)
        df_bs.drop(columns=[df_bs.columns[0]], inplace=True)

        for index, row in df_bs.iterrows():
            
            for col in df_bs.columns:
                if 'VND' in col or col == 'category_code':
                    continue
                
                time = col 
                data = row[col]
                cate = row['category_code']
                
                table.append([cate, time, data])
                
        df = pd.DataFrame(table, columns=['category_code', 'time', 'data'])
        dfs.append(df)
        dfs_sheet_names.append(sheet_name)

    empty_indices = [i for i, d in enumerate(dfs) if d.empty]
    all_na_indices = [i for i, d in enumerate(dfs) if d.isna().all().any()]
    if empty_indices or all_na_indices:
        file_id = getattr(excel_file, "io", None)
        print("get_data debug for", file_id)
        print("get_data: concat inputs", [d.shape for d in dfs])
        print("get_data: empty dfs", empty_indices)
        print("get_data: all-NA columns", all_na_indices)
        for i, df in enumerate(dfs):
            print("get_data: sheet", dfs_sheet_names[i])
            print(df)

    # dfs = [d for d in dfs if not d.empty and not d.isna().all().all()]
    df = pd.concat(dfs)
    return df

def get_tm(excel_file, type_):
    if type_ == 'bank':
        args = bank_args_tm
    elif type_ == 'corp':
        args = corp_args_tm
    else:
        args = sec_args_tm
       
    df = excel_file.parse(
        sheet_name = 'Thuyết minh',
        skiprows=10,
        nrows=args['nrows'],
    )
    
    df = df.iloc[3:]
    df.reset_index(drop=True, inplace=True)
    columns = df.columns.tolist()
    columns += args['mapping'].columns.tolist()
    
    df = pd.concat([df, args['mapping']], ignore_index=True, axis=1)
    df.columns = columns
    df.dropna(subset=['vi_caption'], inplace=True)
    df.drop(columns=[df.columns[0]], inplace=True)
    df.reset_index(drop=True, inplace=True)

    
    # df_mapping = args['mapping']
    # df.rename(columns={'Chỉ tiêuTriệu VND': 'vi_caption'}, inplace=True)
    
    columns = df.columns
    get_column = []
    for col in columns:

        if col.isnumeric() or col.split('/')[-1].isnumeric():
            get_column.append(col)
    
    # # df = pd.merge(df, df_mapping, how='left', on='vi_caption')
    # # df.dropna(subset=['category_code'], inplace=True)
    
    
    # # df= df[get_column + ['category_code']]
    
    data = []
    for index, row in df.iterrows():
        for col in get_column:
            if row['en_caption'] is not np.nan and not pd.isna(row['category_code']):
                data.append([row['category_code'], col, row[col]])
            
            
    df = pd.DataFrame(data, columns=['category_code', 'time', 'data'])
    
    return df


non_bank_stock_code = ["HSG", "ELC", "VSC", "ACV", "REE", "SZC", "CSV", "PAN", "BSR", "SGP", "GMD", "ITD","FOX", "KDC", "SBT", "VGC", "HBC", "CTD", "DIG", "SCR", "KBC","MWG", "NHA", "VNM", "HPG", "VHM", "PNJ", "YEG", "FPT","MSN", "GAS", "VRE", "VJC", "VIC", "PLX", "SAB", "POW", "GVR", "BCM", "VPI", "DVM", "KDH", "HDC", "TCH", "CEO", "HUT", "NVL", "DBC", "SAF", "DHT", "VTP", "PVT", "FRT", "DGC", "DCM", "NKG", "CMG", "VGI", "PVC", "CAP", "DTD", "HLD", "L14", "L18", "LAS", "LHC", "NTP", "PLC", "PSD", "PVG", "PVS", "SLS", "TIG", "TMB", "TNG", "TVD", "VC3", "VCS", "DXG"]
bank_stock_code = ["BID", "EIB", "OCB", "CTG", "VCB", "ACB", "MBB", "HDB", "TPB", "VPB",  "STB", "TCB",  "SHB", "VIB", "CTG",  "ABB", "LPB", "NVB"]
securities_stock_code = ["MBS", "VND", "SSI", "VIX", "ORS"]

new = True
if new:
    bank_stock_code += ["EVF", "MSB", "NAB", "SGB", "VAB", "KLB", "BVB", "PGB", "NVB"]
    securities_stock_code += ["VCI", "TVS", "SHS", "DSE", "HCM", "VDS", "APG", "CTS", "AGR"]
    non_bank_stock_code += ["VCG", "LCG", "DPG", "CTI", "TIS", "PSH", "TLH", "STK", "TDG", "TVN", "DRI", "CNG", "SIP", "PVP", "VGS", "VHC", "IJC", "CII", "SJS", "NLG", "NT2", "LBM", "PC1", "HAH", "HAG", "KOS", "RAL", "PHR", "ILB", "AGG", "ASM", "CLL", "CRE", "D2D", "UIC", "TMS", "PPC", "PTB", "VOS", "VIP", "VTO", "NRC", "GEX", "HTN", "VLC", "GEE", "TCM", "PDR", "SCR", "HPX", "LDG", "AAA", "CTR", "SAM", "BWE", "SGT", "BMP", "ITC", "TTN", "VTE", "VHC", "MSH", "TTF", "ANV", "CMX", "IDI", "FMC", "BAF", "HT1", "PVD", "FIT", "ACL", "ABT", "AAM", "PET", "DGW", "DPM", "HDG", "IMP", "MAS"]


root_dir = r'/Users/quanghung20gg/Downloads/drive-download-20260314T182941Z-3-001'
file_dir_pattern = "FiinProX_DuLieuTaiChinh_BaoCaoTaiChinh_Yearly_Hop_nhat_{code}_*.xlsx"
file_dir_quarter_pattern = "FiinProX_DuLieuTaiChinh_BaoCaoTaiChinh_Quarterly_Hop_nhat_{code}_*.xlsx"


def find_latest_file(root, pattern):
    matches = glob.glob(os.path.join(root, pattern))
    if not matches:
        return None
    return max(matches, key=os.path.getmtime)

    
dfs_corp = []
dfs_corp_tm = []
for code in tqdm(non_bank_stock_code):
    file_path = find_latest_file(root_dir, file_dir_pattern.format(code=code))
    if file_path and os.path.exists(file_path):
        print(f"Processing {code}...")
        excel_file = pd.ExcelFile(file_path, engine="openpyxl")
        df_corp_y = get_data(excel_file, 'corp')
        df_corp_y['stock_code'] = code
        dfs_corp.append(df_corp_y)
        
        df_corp_tm = get_tm(excel_file, 'corp')
        df_corp_tm['stock_code'] = code
        dfs_corp_tm.append(df_corp_tm)
        
dfs_bank = []
dfs_bank_tm = []
for code in tqdm(bank_stock_code):
    file_path = find_latest_file(root_dir, file_dir_pattern.format(code=code))
    if file_path and os.path.exists(file_path):
        print(f"Processing {code}...")
        excel_file = pd.ExcelFile(file_path, engine="openpyxl")
        df_bank_y = get_data(excel_file, 'bank')
        df_bank_y['stock_code'] = code
        dfs_bank.append(df_bank_y)
        
        df_bank_tm = get_tm(excel_file, 'bank')
        df_bank_tm['stock_code'] = code

        print(df_bank_y.head())
        dfs_bank_tm.append(df_bank_tm)
    
dfs_sec = []
dfs_sec_tm = []
for code in tqdm(securities_stock_code):
    file_path = find_latest_file(root_dir, file_dir_pattern.format(code=code))
    if file_path and os.path.exists(file_path):
        print(f"Processing {code}...")
        excel_file = pd.ExcelFile(file_path, engine="openpyxl")
        df_sec_y = get_data(excel_file, 'sec')
        df_sec_y['stock_code'] = code
        dfs_sec.append(df_sec_y)
        
        df_sec_tm = get_tm(excel_file, 'sec')
        df_sec_tm['stock_code'] = code
        dfs_sec_tm.append(df_sec_tm)
    
    
    
for code in tqdm(non_bank_stock_code):
    file_path = find_latest_file(root_dir, file_dir_quarter_pattern.format(code=code))
    if file_path and os.path.exists(file_path):
        excel_file = pd.ExcelFile(file_path, engine="openpyxl")
        df_corp_q = get_data(excel_file, 'corp')
        df_corp_q['stock_code'] = code
        dfs_corp.append(df_corp_q)
        
        df_corp_tm = get_tm(excel_file, 'corp')
        df_corp_tm['stock_code'] = code
        dfs_corp_tm.append(df_corp_tm)
    
for code in tqdm(bank_stock_code):
    file_path = find_latest_file(root_dir, file_dir_quarter_pattern.format(code=code))
    if file_path and os.path.exists(file_path):
        excel_file = pd.ExcelFile(file_path, engine="openpyxl")
        df_bank_q = get_data(excel_file, 'bank')
        df_bank_q['stock_code'] = code
        dfs_bank.append(df_bank_q)
        
        df_bank_tm = get_tm(excel_file, 'bank')
        df_bank_tm['stock_code'] = code
        dfs_bank_tm.append(df_bank_tm)
    
for code in tqdm(securities_stock_code):
    file_path = find_latest_file(root_dir, file_dir_quarter_pattern.format(code=code))
    if file_path and os.path.exists(file_path):
        excel_file = pd.ExcelFile(file_path, engine="openpyxl")
        df_sec_q = get_data(excel_file, 'sec')
        df_sec_q['stock_code'] = code
        dfs_sec.append(df_sec_q)
        
        df_sec_tm = get_tm(excel_file, 'sec')
        df_sec_tm['stock_code'] = code
        dfs_sec_tm.append(df_sec_tm)
        
    
    
df_bank = pd.concat(dfs_bank)
df_corp = pd.concat(dfs_corp)
df_sec = pd.concat(dfs_sec)

df_bank_tm = pd.concat(dfs_bank_tm)
df_corp_tm = pd.concat(dfs_corp_tm)
df_sec_tm = pd.concat(dfs_sec_tm)

df_bank.drop_duplicates(subset=['stock_code', 'category_code', 'time'], inplace=True)
df_corp.drop_duplicates(subset=['stock_code', 'category_code', 'time'], inplace=True)
df_sec.drop_duplicates(subset=['stock_code', 'category_code', 'time'], inplace=True)

df_sec_tm.drop_duplicates(subset=['stock_code', 'category_code', 'time'], inplace=True)
df_bank_tm.drop_duplicates(subset=['stock_code', 'category_code', 'time'], inplace   =True)
df_corp_tm.drop_duplicates(subset=['stock_code', 'category_code', 'time'], inplace=True)


print(df_bank[df_bank['time'] == 'Q4/2024'].head())   
print(df_sec[df_sec['time'] == 'Q4/2024'].head())
print(df_corp[df_corp['time'] == 'Q4/2024'].head())


def get_quarter_time(text):
    if '/' not in text:
        return 0, int(text)
    
    quarter, year = text.split('/')
    return int(quarter[1]), int(year)


df_bank['quarter'], df_bank['year'] = zip(*df_bank['time'].apply(get_quarter_time))
df_corp['quarter'], df_corp['year'] = zip(*df_corp['time'].apply(get_quarter_time))
df_sec['quarter'], df_sec['year'] = zip(*df_sec['time'].apply(get_quarter_time))

df_sec_tm['quarter'], df_sec_tm['year'] = zip(*df_sec_tm['time'].apply(get_quarter_time))
df_bank_tm['quarter'], df_bank_tm['year'] = zip(*df_bank_tm['time'].apply(get_quarter_time))
df_corp_tm['quarter'], df_corp_tm['year'] = zip(*df_corp_tm['time'].apply(get_quarter_time))


df_bank.drop(columns=['time'], inplace=True)
df_corp.drop(columns=['time'], inplace=True)
df_sec.drop(columns=['time'], inplace=True)

df_sec_tm.drop(columns=['time'], inplace=True)
df_bank_tm.drop(columns=['time'], inplace=True)
df_corp_tm.drop(columns=['time'], inplace=True)

quarter_to_month = {
    0: 12,  # Quarter 0 is December of the same year
    1: 3,
    2: 6,
    3: 9,
    4: 12
}

df_sec['date_added'] = pd.to_datetime(df_sec.apply(lambda row: f"{row['year']}-{quarter_to_month[row['quarter']]}-30", axis=1))
df_bank['date_added'] = pd.to_datetime(df_bank.apply(lambda row: f"{row['year']}-{quarter_to_month[row['quarter']]}-30", axis=1))
df_corp['date_added'] = pd.to_datetime(df_corp.apply(lambda row: f"{row['year']}-{quarter_to_month[row['quarter']]}-30", axis=1))

df_sec_tm['date_added'] = pd.to_datetime(df_sec_tm.apply(lambda row: f"{row['year']}-{quarter_to_month[row['quarter']]}-30", axis=1))
df_bank_tm['date_added'] = pd.to_datetime(df_bank_tm.apply(lambda row: f"{row['year']}-{quarter_to_month[row['quarter']]}-30", axis=1))
df_corp_tm['date_added'] = pd.to_datetime(df_corp_tm.apply(lambda row: f"{row['year']}-{quarter_to_month[row['quarter']]}-30", axis=1))

pivot_df  = df_bank[df_bank['category_code'].isin(['BS_160', 'BS_180', 'BS_131', 'BS_139'])].pivot_table(
    index=["stock_code", "year", "quarter", "date_added"], 
    columns="category_code", 
    values="data"
).reset_index()

pivot_df['BS_200'] = pivot_df['BS_160'] + pivot_df['BS_180'] - pivot_df['BS_131'] - pivot_df['BS_139']

new_rows = pivot_df.melt(
    id_vars=["stock_code", "year", "quarter", "date_added"], 
    value_vars=["BS_200"], 
    var_name="category_code", 
    value_name="data"
)

df_bank = pd.concat([df_bank, new_rows], ignore_index=True)


pivot_df  = df_bank[df_bank['category_code'].isin(['BS_310', 'BS_320', 'BS_321', 'BS_322', 'BS_330', 'BS_340', 'BS_350', 'BS_360'])].pivot_table(
    index=["stock_code", "year", "quarter", "date_added"], 
    columns="category_code", 
    values="data"
).reset_index()

pivot_df['BS_361'] = pivot_df['BS_310'] + pivot_df['BS_320'] + pivot_df['BS_321'] + pivot_df['BS_322'] + pivot_df['BS_330'] + pivot_df['BS_340'] + pivot_df['BS_350'] + pivot_df['BS_360']

new_rows = pivot_df.melt(
    id_vars=["stock_code", "year", "quarter", "date_added"], 
    value_vars=["BS_361"], 
    var_name="category_code", 
    value_name="data"
)

df_bank = pd.concat([df_bank, new_rows], ignore_index=True)


pivot_df = df_sec[df_sec['category_code'].isin(['IS_040.1', 'IS_050', 'IS_060', 'IS_061', 'IS_062'])].pivot_table(
    index=["stock_code", "year", "quarter", "date_added"], 
    columns="category_code", 
    values="data"
).reset_index()

pivot_df['IS_070'] = pivot_df['IS_040.1'] + pivot_df['IS_050'] - pivot_df['IS_060'] - pivot_df['IS_061'] - pivot_df['IS_062']

new_rows = pivot_df.melt(
    id_vars=["stock_code", "year", "quarter", "date_added"], 
    value_vars=["IS_040.1"], 
    var_name="category_code", 
    value_name="data"
)
df_sec = pd.concat([df_sec, new_rows], ignore_index=True)



pivot_df = df_sec[df_sec['category_code'].isin(['IS_050', 'IS_060', 'IS_061', 'IS_062'])].pivot_table(
    index=["stock_code", "year", "quarter", "date_added"], 
    columns="category_code", 
    values="data"
).reset_index()

pivot_df['IS_095'] =  pivot_df['IS_060'] - pivot_df['IS_050'] + pivot_df['IS_061'] + pivot_df['IS_062']

new_rows = pivot_df.melt(
    id_vars=["stock_code", "year", "quarter", "date_added"], 
    value_vars=["IS_095"], 
    var_name="category_code", 
    value_name="data"
)
df_sec = pd.concat([df_sec, new_rows], ignore_index=True)


pivot_df = df_corp[df_corp['category_code'].isin(['IS_021', 'IS_022', 'IS_024', 'IS_025', 'IS_026'])].pivot_table(
    index=["stock_code", "year", "quarter", "date_added"], 
    columns="category_code", 
    values="data"
).reset_index()

pivot_df['IS_027'] =  pivot_df['IS_022'] - pivot_df['IS_021'] + pivot_df['IS_024'] + pivot_df['IS_025'] + pivot_df['IS_026']

new_rows = pivot_df.melt(
    id_vars=["stock_code", "year", "quarter", "date_added"], 
    value_vars=["IS_027"], 
    var_name="category_code", 
    value_name="data"
)
df_corp = pd.concat([df_corp, new_rows], ignore_index=True)


df_sec = df_sec[df_sec['year']>=2010]
df_bank = df_bank[df_bank['year']>=2010]
df_corp = df_corp[df_corp['year']>=2010]


df_sec_tm = df_sec_tm[df_sec_tm['year']>=2010]
df_bank_tm = df_bank_tm[df_bank_tm['year']>=2010]
df_corp_tm = df_corp_tm[df_corp_tm['year']>=2010]

df_bank['segment'] = 'bank'
df_corp['segment'] = 'corp'
df_sec['segment'] = 'sec'




df_sec.dropna(subset=['data'], inplace=True)
df_bank.dropna(subset=['data'], inplace=True)
df_corp.dropna(subset=['data'], inplace=True)
df_sec_tm.dropna(subset=['data'], inplace=True)
df_bank_tm.dropna(subset=['data'], inplace=True)
df_corp_tm.dropna(subset=['data'], inplace=True)


df_sec.to_parquet(os.path.join(current_dir, '..', '..', 'data', 'securities_financial_report.parquet'), index=False)
df_bank.to_parquet(os.path.join(current_dir, '..', '..', 'data', 'bank_financial_report.parquet'), index=False)
df_corp.to_parquet(os.path.join(current_dir, '..', '..', 'data', 'corp_financial_report.parquet'), index=False)

df_bank.rename(columns={'category_code': 'bank_code'}, inplace=True)
df_sec.rename(columns={'category_code': 'sec_code'}, inplace=True)
df_corp.rename(columns={'category_code': 'corp_code'}, inplace=True)

df_bank = pd.merge(df_bank, df[['bank_code', 'universal_code']], how='outer', on='bank_code')
df_sec = pd.merge(df_sec, df[['sec_code', 'universal_code']], how='left', on='sec_code')
df_corp = pd.merge(df_corp, df[['corp_code', 'universal_code']], how='outer', on='corp_code')

df_bank.drop(columns=['bank_code'], inplace=True)
df_sec.drop(columns=['sec_code'], inplace=True)
df_corp.drop(columns=['corp_code'], inplace=True)

df_fs = pd.concat([df_bank, df_sec, df_corp], ignore_index=True)

df_fs.rename(columns={'universal_code': 'category_code'}, inplace=True)


df_fs.dropna(subset=['data', 'category_code'], inplace=True)

df_industry_fs = calculate_industry_financial_statement(df_fs)

df_industry_fs['segment'] = 'industry'



pivot_df = df_bank_tm[df_bank_tm['category_code'].isin(['Bank_TM_68', 'Bank_TM_69', 'Bank_TM_70'])].pivot_table(
    index=["stock_code", "year", "quarter"], 
    columns="category_code", 
    values="data"
).reset_index()

pivot_df['Bank_TM_65'] =  pivot_df['Bank_TM_68'] + pivot_df['Bank_TM_69'] + pivot_df['Bank_TM_70']

new_rows = pivot_df.melt(
    id_vars=["stock_code", "year", "quarter"], 
    value_vars=["Bank_TM_65"], 
    var_name="category_code", 
    value_name="data"
)
df_bank_tm = pd.concat([df_bank_tm, new_rows], ignore_index=True)

df_bank_tm['segment'] = 'bank'
df_corp_tm['segment'] = 'corp'
df_sec_tm['segment'] = 'sec'

df_bank_tm.to_parquet(os.path.join(current_dir, '..', '..', 'data', 'bank_explaination.parquet'), index=False)
df_sec_tm.to_parquet(os.path.join(current_dir, '..', '..', 'data', 'securities_explaination.parquet'), index=False)
df_corp_tm.to_parquet(os.path.join(current_dir, '..', '..', 'data', 'corp_explaination.parquet'), index=False)


df_tm = pd.concat([df_bank_tm, df_sec_tm, df_corp_tm], ignore_index=True)

df_tm_industry = calculate_industry_financial_statement_explaination(df_bank_tm)
df_tm_industry['segment'] = 'industry'

# df_tm = pd.concat([df_tm, df_tm_industry], ignore_index=True)

df_tm.to_parquet(os.path.join(current_dir, '..', '..', 'data', 'financial_statement_explaination_v3.parquet'), index=False)

df_fs = pd.concat([df_fs, df_industry_fs, df_tm, df_tm_industry], ignore_index=True)

df_fs.to_parquet(os.path.join(current_dir, '..', '..', 'data', 'financial_statement_v3.parquet'), index=False)
print(df_fs.head())

# 
# crop CF_020, sec CF_060