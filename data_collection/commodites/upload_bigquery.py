from google.cloud import bigquery
import os
import time
import pandas as pd


KEY_PATH = os.path.join(os.path.dirname(__file__), '../keys/big-query.json').replace('\\', '/')
bq_client = bigquery.Client.from_service_account_json(KEY_PATH)


# Update these with your project and dataset
PROJECT_ID = 'neusolution'
DATASET_ID = 'ktln'
TABLE_COMMODITIES_DAILY = f'{PROJECT_ID}.{DATASET_ID}.commodities_daily'
TABLE_COMMODITIES_MONTHLY = f'{PROJECT_ID}.{DATASET_ID}.commodities_monthly'

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
    
    if 'monthly' in table_full_id:
        span_ema_fields = [
            bigquery.SchemaField("EMA12", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("EMA26", "FLOAT64", mode="NULLABLE"),
        ]
    else:
        span_ema_fields = [
            bigquery.SchemaField("EMA20", "FLOAT64", mode="NULLABLE"),
            bigquery.SchemaField("EMA50", "FLOAT64", mode="NULLABLE"),
        ]
    
    # Define table schema
    schema = [
        bigquery.SchemaField("time", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("indicator_code", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("indicator_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("value", "FLOAT64", mode="REQUIRED"),
        bigquery.SchemaField("volume", "INTEGER", mode="NULLABLE")
    ] + span_ema_fields
    
    # Create table if it doesn't exist
    try:
        table = bq_client.get_table(table_full_id)
        print(f"Table {table_full_id} already exists")
        
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.MONTH,
            field="time"
        )
        
        # Clustering
        table.clustering_fields = ["indicator_name"]
        
        # # Update clustering if not set
        # if not table.clustering_fields or "url" not in table.clustering_fields:
        #     print("Adding URL clustering to existing table...")
        #     table.clustering_fields = ["url"]
        #     table = bq_client.update_table(table, ["clustering_fields"])
        #     print("URL clustering added successfully")
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
    if 'time' in df.columns:
        df['time'] = pd.to_datetime(df['time'])
        
    if 'duration' in df.columns:
        df = df.drop(columns=['duration'])
    
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
    create_table_if_not_exists(TABLE_COMMODITIES_DAILY)
    create_table_if_not_exists(TABLE_COMMODITIES_MONTHLY)
    
    df_commodities_daily = pd.read_parquet('../data/commodities_daily.parquet')
    upload_dataframe_to_bigquery(df_commodities_daily, TABLE_COMMODITIES_DAILY)
    
    df_commodities_monthly = pd.read_parquet('../data/commodities_monthly.parquet')
    upload_dataframe_to_bigquery(df_commodities_monthly, TABLE_COMMODITIES_MONTHLY)
    
if __name__ == "__main__":
    main()