from qdrant_client import QdrantClient
from google.cloud import storage
import os
import time
from datetime import datetime
import requests

# Configuration
QDRANT_HOST = 'http://127.0.0.1:6333'
COLLECTION_NAME = 'news_embedding'
GCS_BUCKET_NAME = 'news_embedding'  # Replace with your bucket name
GCS_CREDENTIALS_PATH = os.path.join(os.path.dirname(__file__), '../keys/big-query.json')

# Initialize clients
qdrant_client = QdrantClient(url=QDRANT_HOST)
storage_client = storage.Client.from_service_account_json(GCS_CREDENTIALS_PATH)


def create_qdrant_snapshot(collection_name: str) -> str:
    """
    Create a snapshot of the Qdrant collection.
    Returns the snapshot name.
    """
    print(f"Creating snapshot for collection: {collection_name}")
    snapshot_info = qdrant_client.create_snapshot(collection_name=collection_name)
    snapshot_name = snapshot_info.name
    print(f"Snapshot created: {snapshot_name}")
    return snapshot_name


def download_snapshot(collection_name: str, snapshot_name: str, local_path: str) -> str:
    """
    Download the snapshot from Qdrant to local filesystem using HTTP API.
    """
    print(f"Downloading snapshot: {snapshot_name}")
    
    # Use HTTP API to download snapshot
    snapshot_url = f"{QDRANT_HOST}/collections/{collection_name}/snapshots/{snapshot_name}"
    response = requests.get(snapshot_url, stream=True)
    response.raise_for_status()
    
    # Save to local file
    local_file = os.path.join(local_path, snapshot_name)
    with open(local_file, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    print(f"Snapshot downloaded to: {local_file}")
    return local_file


def upload_to_gcs(local_file: str, bucket_name: str, gcs_path: str = None):
    """
    Upload snapshot file to Google Cloud Storage.
    """
    bucket = storage_client.bucket(bucket_name)
    
    # Generate GCS path with timestamp if not provided
    if gcs_path is None:
        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"news_embedding_{timestamp}.snapshot"
        gcs_path = f"qdrant_snapshots/{filename}"
    
    blob = bucket.blob(gcs_path)
    
    print(f"Uploading to gs://{bucket_name}/{gcs_path}")
    blob.upload_from_filename(local_file)
    print(f"Upload complete: gs://{bucket_name}/{gcs_path}")
    
    return f"gs://{bucket_name}/{gcs_path}"


def cleanup_local_snapshot(local_file: str):
    """
    Remove local snapshot file after upload.
    """
    if os.path.exists(local_file):
        os.remove(local_file)
        print(f"Cleaned up local file: {local_file}")


def main():
    # Create temporary directory for snapshots
    snapshot_dir = '/tmp/qdrant_snapshots'
    os.makedirs(snapshot_dir, exist_ok=True)
    
    try:
        # Step 1: Create snapshot
        snapshot_name = create_qdrant_snapshot(COLLECTION_NAME)
        
        # Step 2: Download snapshot
        local_file = download_snapshot(COLLECTION_NAME, snapshot_name, snapshot_dir)
        
        # Step 3: Upload to GCS
        gcs_uri = upload_to_gcs(local_file, GCS_BUCKET_NAME)
        
        # Step 4: Cleanup
        cleanup_local_snapshot(local_file)
        
        print(f"\n✓ Snapshot successfully uploaded to: {gcs_uri}")
        
    except Exception as e:
        print(f"Error during snapshot export: {e}")
        raise


if __name__ == "__main__":
    main()
