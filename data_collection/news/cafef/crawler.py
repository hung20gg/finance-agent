from cafef_article_crawler import craw_article
from cafef_link_crawler import crawl_and_save
from google.cloud import bigquery
from datetime import datetime
from curl_cffi import requests
from curl_cffi.requests.exceptions import Timeout
import os
import time
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed

KEY_PATH = os.path.join(os.path.dirname(__file__), '../../keys/big-query.json')
bq_client = bigquery.Client.from_service_account_json(KEY_PATH)

# Update these with your project and dataset
PROJECT_ID = 'neusolution'
DATASET_ID = 'ktln'
TABLE_ID = 'news'
TABLE_FULL_ID = f'{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}'

channelIDs = [
     (188112, 'Xã hội'),
     (18831, 'Chứng khoán'),
    (18835, 'Bất động sản'),
    (18836, 'Doanh nghiệp'),
    (18834, 'Ngân hàng'),
    (1882020, 'Smart money'),
    (18832, 'Tài chính quốc tế'),
    (18833, 'Vĩ mô'),
    (188127, 'Kinh tế số'),
    (18839, 'Thị trường')
]

def craw_a_page(session: requests.Session, channel_info: tuple[int, str], page_num: int) -> list[dict]:
    
    try:
        links_batch = crawl_and_save(session, channel_info, page_num)
    except Timeout:
        print(f"Timeout fetching links for page {page_num}, skipping...")
        return []
    except Exception as e:
        print(f"Error fetching links for page {page_num}: {e}, skipping...")
        return []
    
    articles = []
    
    def fetch_article(url, channel_name, channel_id):
        try:
            article_data = craw_article(session, url)
            return {
                "url": url,
                "source": "cafef",
                "title": article_data["title"],
                "pub_date": article_data["pub_date"],
                "text": article_data["text"],
                "channel_name": channel_name,
                "channel_id": channel_id
            }
        except Timeout:
            print(f"Timeout crawling article {url}, skipping...")
            return None
        except Exception as e:
            print(f"Error crawling article {url}: {e}, skipping...")
            return None
    
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(fetch_article, url, channel_name, channel_id) 
                   for url, channel_name, channel_id in links_batch]
        
        for future in as_completed(futures):
            result = future.result()
            if result:
                articles.append(result)
    return articles


def create_table_if_not_exists():
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
        bigquery.SchemaField("url", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("title", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("pub_date", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("channel_name", "STRING", mode="REQUIRED"),
        bigquery.SchemaField("channel_id", "INTEGER", mode="REQUIRED"),
        bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("updated_at", "TIMESTAMP", mode="REQUIRED"),
        bigquery.SchemaField("text", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("summarize", "STRING", mode="NULLABLE"),
        bigquery.SchemaField("vectorized", "BOOL", mode="NULLABLE"),
    ]
    
    # Create table if it doesn't exist
    try:
        table = bq_client.get_table(TABLE_FULL_ID)
        print(f"Table {TABLE_ID} already exists")
        
        # Update clustering if not set
        if not table.clustering_fields or "channel_name" not in table.clustering_fields:
            print("Adding channel_name clustering to existing table...")
            table.clustering_fields = ["channel_name"]
            table = bq_client.update_table(table, ["clustering_fields"])
            print("channel_name clustering added successfully")
    except Exception as e:
        print(f"Table doesn't exist, creating: {e}")
        table = bigquery.Table(TABLE_FULL_ID, schema=schema)
        # Cluster by URL for faster deduplication queries
        table.clustering_fields = ["channel_name", "source"]
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.MONTH,
            field="pub_date"
        )
        table = bq_client.create_table(table)
        print(f"Created table {TABLE_ID} with schema and URL clustering, please wait...")
        
        time.sleep(60)  # Wait for table to be fully ready
        
        
        

def save_urls_batch_to_bigquery(articles: list[dict]) -> int:
    """
    Save multiple URLs to BigQuery in a single batch operation.
    Direct INSERT - allows duplicates for performance.
    
    Args:
        urls: List of tuples (url, channel_name, channel_id)
    
    Returns:
        Number of URLs inserted
    """
    if not articles:
        return 0
    
    now = datetime.now().isoformat()
    
    # Build rows for batch insert
    rows_to_insert = []
    for article in articles:
        rows_to_insert.append({
            "url": article["url"],
            "source": "cafef",
            "title": article["title"],
            "pub_date": article["pub_date"],
            "channel_name": article["channel_name"],
            "channel_id": article["channel_id"],
            "created_at": now,
            "updated_at": now,
            "text": article["text"],
            "summarize": None,
        })
    
    try:
        errors = bq_client.insert_rows_json(TABLE_FULL_ID, rows_to_insert)
        
        if errors:
            print(f"Errors inserting rows: {errors}")
            return 0
        else:
            return len(rows_to_insert)
    except Exception as e:
        print(f"Error in batch insert: {e}")
        return 0
    
    
def find_last_updated_url(channel_id: int) -> datetime | None:
    """
    Find the most recently added URL for a given channel.
    
    Args:
        channel_id: Channel ID to search
    Returns:
        Most recent URL or None if not found
    """
    query = f"""
    SELECT MAX(pub_date) as max_date
    FROM `{TABLE_FULL_ID}`
    WHERE channel_id = @channel_id
    """
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("channel_id", "INT64", channel_id)
        ]
    )
    
    try:
        query_job = bq_client.query(query, job_config=job_config)
        results = query_job.result()
        
        for row in results:
            return row.max_date
        
        return None
    except Exception as e:
        print(f"Error finding last updated date for channel {channel_id}: {e}")
        return None


def main():
    
    session = requests.Session()
    
    create_table_if_not_exists()
    for channel_info in channelIDs:
        channel_id, channel_name = channel_info
        
        last_date = find_last_updated_url(channel_id)
        if last_date:
            last_date = last_date.isoformat()
        print(f"Last updated date for channel {channel_name} (ID: {channel_id}): {last_date}")
        
        # Crawl first 20 pages for each channel
        for page_num in tqdm(range(1000, 1, -1), desc=f"Crawling channel {channel_name}"):
            articles = craw_a_page(session, channel_info, page_num)
            # if not articles:
            #     print(f"No articles found on page {page_num}, stopping.")
            #     break
            
            # Filter articles by last_date
            page_exist = True
            if last_date:
                selected_articles = []
                for article in articles:
                    pub_date = article['pub_date']
                    if pub_date and pub_date > last_date:
                        selected_articles.append(article)
                
                if not selected_articles:
                    page_exist = False
            else:
                selected_articles = articles
            
            if page_exist:
                inserted_count = save_urls_batch_to_bigquery(selected_articles)

                time.sleep(0.5)  # Be polite to the server
            
    print("Crawling complete.")
    
if __name__ == '__main__':
    main()