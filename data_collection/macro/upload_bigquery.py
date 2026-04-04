from google.cloud import bigquery
import os
import time
import pandas as pd


KEY_PATH = os.path.join(os.path.dirname(__file__), '../keys/big-query.json').replace('\\', '/')
bq_client = bigquery.Client.from_service_account_json(KEY_PATH)


# Update these with your project and dataset
PROJECT_ID = 'neusolution'
DATASET_ID = 'ktln'
TABLE_MACRO = f'{PROJECT_ID}.{DATASET_ID}.macro'
TABLE_BOND = f'{PROJECT_ID}.{DATASET_ID}.bond'


def create_table_if_not_exists(table_full_id: str):
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
    

    # Define table schema
    schema = [
        bigquery.SchemaField("datetime", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("duration", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("indicator_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("country", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("value", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("unit", "STRING", mode="REQUIRED"),
    ]
    
    # Create table if it doesn't exist
    try:
        table = bq_client.get_table(table_full_id)
        print(f"Table {table_full_id} already exists")

    except Exception as e:
        print(f"Table doesn't exist, creating: {e}")
        table = bigquery.Table(table_full_id, schema=schema)

        table = bq_client.create_table(table)
        print(f"Created table {table_full_id} with schema, please wait...")
        
        time.sleep(30)  # Wait for table to be fully ready
        
        
        
def upload_dataframe_to_bigquery(df: pd.DataFrame, table_full_id: str):
    """Upload DataFrame to BigQuery table"""
    # Clean data: remove rows with null close values
    original_len = len(df)
    df = df.dropna(subset=['value'])
    if len(df) < original_len:
        print(f"Dropped {original_len - len(df)} rows with null close values")
    
    # Convert time column to datetime if it's not already
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
    
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
    create_table_if_not_exists(TABLE_MACRO)
    create_table_if_not_exists(TABLE_BOND)

    
    df_stock_daily = pd.read_parquet('../data/annual_2010_2025.parquet')
    upload_dataframe_to_bigquery(df_stock_daily, TABLE_MACRO)
    
    df_stock_monthly = pd.read_parquet('../data/monthly_bond.parquet')
    upload_dataframe_to_bigquery(df_stock_monthly, TABLE_BOND)

if __name__ == "__main__":
    main()