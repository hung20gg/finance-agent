#!/usr/bin/env python3
"""
Download all parquet files from GCS bucket kltn-dataset to local directory
"""
import os
import sys
from google.cloud import storage
from dotenv import load_dotenv

# Load environment configuration from parent directory
# env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
# load_dotenv(dotenv_path=env_path)


def download_parquet_files():
    """
    Download all .parquet files from GCS bucket kltn-dataset to data_collection/data
    """
    GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'kltn-dataset')
    
    # Get credentials path
    current_dir = os.path.dirname(os.path.abspath(__file__))
    credentials_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS', 'keys/big-query.json')
    
    print('Current directory:', current_dir)
    if credentials_path:
        # Resolve relative path to absolute, relative to project root
        print('Found GCS credentials path in environment variable:', credentials_path)
        credentials_path = os.path.join(current_dir, credentials_path)
        print('Resolved GCS credentials path to:', credentials_path)
    else:
        credentials_path = None
    
    # Verify credentials file exists
    if not credentials_path or not os.path.isfile(credentials_path):
        raise FileNotFoundError(
            f"GCS credentials not found at {credentials_path}"
        )
    
    # Create output directory
    output_dir = os.path.join(current_dir, 'data')
    os.makedirs(output_dir, exist_ok=True)
    
    print("\n=== Downloading Parquet Files from GCS ===")
    print(f"   GCS Bucket: {GCS_BUCKET_NAME}")
    print(f"   Output Directory: {output_dir}")
    
    try:
        # Initialize storage client
        storage_client = storage.Client.from_service_account_json(credentials_path)
        
        # Get bucket
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        
        # List all blobs that end with .parquet
        print(f"\n🔍 Searching for .parquet files in gs://{GCS_BUCKET_NAME}...")
        blobs = [blob for blob in bucket.list_blobs() if blob.name.endswith('.parquet')]
        
        if not blobs:
            print("❌ No .parquet files found in GCS bucket")
            return False
        
        print(f"   Found {len(blobs)} .parquet file(s)")
        
        # Download each file
        downloaded_count = 0
        failed_count = 0
        total_size_mb = 0
        
        for i, blob in enumerate(blobs, 1):
            try:
                local_file = os.path.join(output_dir, os.path.basename(blob.name))
                file_size_mb = blob.size / (1024 * 1024) if blob.size else 0
                total_size_mb += file_size_mb
                
                print(f"\n   [{i}/{len(blobs)}] Downloading: {blob.name}")
                print(f"        Size: {file_size_mb:.2f} MB")
                print(f"        To: {local_file}")
                
                blob.download_to_filename(local_file)
                print(f"        ✅ Downloaded successfully")
                downloaded_count += 1
                
            except Exception as e:
                print(f"        ❌ Failed to download: {e}")
                failed_count += 1
        
        # Summary
        print(f"\n=== Download Summary ===")
        print(f"   ✅ Downloaded: {downloaded_count} file(s)")
        print(f"   ❌ Failed: {failed_count} file(s)")
        print(f"   📊 Total Size: {total_size_mb:.2f} MB")
        print(f"   📁 Output Directory: {output_dir}")
        
        return failed_count == 0
        
    except Exception as e:
        print(f"\n❌ Error during download: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = download_parquet_files()
    sys.exit(0 if success else 1)
