from google.cloud import bigquery
import os
import time
import pandas as pd
from concurrent.futures import ThreadPoolExecutor


KEY_PATH = os.path.join(os.path.dirname(__file__), '../keys/big-query.json').replace('\\', '/')
bq_client = bigquery.Client.from_service_account_json(KEY_PATH)


# Update these with your project and dataset
PROJECT_ID = 'neusolution'
DATASET_ID = 'ktln'
TABLE_FINANCIAL_STATEMENT = f'{PROJECT_ID}.{DATASET_ID}.financial_statement'
TABLE_FINANCIAL_RATIO = f'{PROJECT_ID}.{DATASET_ID}.financial_ratio'

TABLE_FINANCIAL_STATEMENT_DIM = f'{PROJECT_ID}.{DATASET_ID}.financial_statement_dim'
TABLE_FINANCIAL_RATIO_DIM = f'{PROJECT_ID}.{DATASET_ID}.financial_ratio_dim'

TABLE_COMPANY_INFO = f'{PROJECT_ID}.{DATASET_ID}.company_info'


def schema_for_financial_statement():
    """Define schema for financial statement table"""
    schema = [
        bigquery.SchemaField("stock_code", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("category_code", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("data", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("year", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("quarter", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("date_added", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("segment", "STRING", mode="REQUIRED"),
    ]
    return schema

def schema_for_financial_ratio():
    """Define schema for financial ratio table"""
    schema = [
        bigquery.SchemaField("stock_code", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("ratio_code", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("data", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("year", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("quarter", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("date_added", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("segment", "STRING", mode="REQUIRED"),

    ]
    return schema


def schema_for_company_info():
    """Define schema for company info table"""
    schema = [
        bigquery.SchemaField("stock_code", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("company_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("short_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("en_company_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("en_short_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("combine_profile", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("industry", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("exchange", "STRING", mode="NULLABLE"),        
        bigquery.SchemaField("foreign_percent", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("issue_share", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("no_shareholders", "INTEGER", mode="NULLABLE"),
        bigquery.SchemaField("stock_rating", "FLOAT64", mode="NULLABLE"),
        bigquery.SchemaField("website", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("stock_indices", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("is_bank", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("is_securities", "BOOLEAN", mode="NULLABLE"),
        bigquery.SchemaField("market_cap", "FLOAT64", mode="NULLABLE"),
    ]
    return schema


def schema_for_financial_statement_dim():
    """Define schema for financial statement dimension table"""
    schema = [
        bigquery.SchemaField("category_code", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("category_name", "STRING", mode="NULLABLE"),
    ]
    return schema

def schema_for_financial_ratio_dim():
    """Define schema for financial ratio dimension table"""
    schema = [
        bigquery.SchemaField("ratio_code", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("ratio_name", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("function_name", "STRING", mode="NULLABLE"),
    ]
    return schema


def create_table_if_not_exists(table_full_id: str, schema: list[bigquery.SchemaField]):
    print(table_full_id)
    """Create BigQuery table if it doesn't exist"""
    dataset_ref = bigquery.DatasetReference(PROJECT_ID, DATASET_ID)
    
    # Create dataset if it doesn't exist
    try:
        bq_client.get_dataset(dataset_ref)
        print(f"Dataset {DATASET_ID} already exists")
    except Exception as e:
        print(f"Dataset doesn't exist, creating: {e}")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "asia-southeast1"
        bq_client.create_dataset(dataset)
        print(f"Created dataset {DATASET_ID}")
    
    # Create table if it doesn't exist
    try:
        table = bq_client.get_table(table_full_id)
        print(f"Table {table_full_id} already exists")

    except Exception as e:
        print(f"Table doesn't exist, creating: {e}")
        table = bigquery.Table(table_full_id, schema=schema)
        
        if table_full_id == TABLE_FINANCIAL_STATEMENT:
            table.clustering_fields = ["stock_code", "year", "quarter"]
        elif table_full_id == TABLE_FINANCIAL_RATIO:
            table.clustering_fields = ["ratio_code", "year", "quarter"]

        table = bq_client.create_table(table)
        print(f"Created table {table_full_id} with schema, please wait...")
        
        time.sleep(30)  # Wait for table to be fully ready
        
        
        
def upload_dataframe_to_bigquery(df: pd.DataFrame, table_full_id: str):
    print(f"Uploading DataFrame to {table_full_id}")
    """Upload DataFrame to BigQuery table"""
    # Clean data: remove rows with null close values

    # Convert time column to datetime if it's not already
    if 'date_added' in df.columns:
        df['date_added'] = pd.to_datetime(df['date_added'])
        
        df = df.dropna(subset=['date_added'])
    
    job_config = bigquery.LoadJobConfig(
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )
    
    job = bq_client.load_table_from_dataframe(
        df, table_full_id, job_config=job_config
    )
    
    job.result()  # Wait for the job to complete
    print(f"Uploaded {len(df)} rows to {table_full_id}")
    
    
def main():
    # Example usage
    tables_to_create = [
        (TABLE_FINANCIAL_STATEMENT, schema_for_financial_statement()),
        (TABLE_FINANCIAL_RATIO, schema_for_financial_ratio()),
        (TABLE_COMPANY_INFO, schema_for_company_info()),
        (TABLE_FINANCIAL_STATEMENT_DIM, schema_for_financial_statement_dim()),
        (TABLE_FINANCIAL_RATIO_DIM, schema_for_financial_ratio_dim()),
    ]
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(lambda x: create_table_if_not_exists(x[0], x[1]), tables_to_create)

    
    df_fs = pd.read_parquet('../data/financial_statement_v3.parquet')
    upload_dataframe_to_bigquery(df_fs, TABLE_FINANCIAL_STATEMENT)
    
    df_fr = pd.read_parquet('../data/financial_ratio_v3.parquet')
    upload_dataframe_to_bigquery(df_fr, TABLE_FINANCIAL_RATIO)
    
    df_fs_dim = pd.read_csv('transform/metadata/map_category_code.csv')
    upload_dataframe_to_bigquery(df_fs_dim, TABLE_FINANCIAL_STATEMENT_DIM)
    
    df_fr_dim = pd.read_csv('transform/metadata/map_ratio_code.csv')
    upload_dataframe_to_bigquery(df_fr_dim, TABLE_FINANCIAL_RATIO_DIM)
    
    df_company_info = pd.read_csv('transform/metadata/df_company_info.csv')
    upload_dataframe_to_bigquery(df_company_info, TABLE_COMPANY_INFO)

if __name__ == "__main__":
    main()