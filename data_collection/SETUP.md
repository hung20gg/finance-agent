# Google Cloud BigQuery Setup

## Prerequisites

1. **Create a Google Cloud Project**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select an existing one

2. **Enable BigQuery API**
   - In your project, go to "BigQuery" in the left menu
   - The API should be enabled automatically
   - The dataset and table will be created automatically when you run the crawler

3. **Set up Authentication**
   - Go to "IAM & Admin" > "Service Accounts"
   - Click "Create Service Account"
   - Give it a name (e.g., "bigquery-crawler")
   - Grant it the "BigQuery Data Editor" and "BigQuery Job User" roles
   - Click "Done"
   - Click on the created service account
   - Go to "Keys" tab
   - Click "Add Key" > "Create new key"
   - Choose "JSON" format
   - Download the key file

4. **Set Environment Variable**
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
   ```
   
   Or add it to your `~/.zshrc`:
   ```bash
   echo 'export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"' >> ~/.zshrc
   source ~/.zshrc
   ```

## Installation

Install the required packages:
```bash
cd /Users/quanghung20gg/code/wtf/data_collection
uv pip install -r requirements.txt
```

## Usage

Run the crawler:
```bash
cd /Users/quanghung20gg/code/wtf/data_collection/crawler/cafef
python cafef_link_crawler.py
```

## BigQuery Structure

The data is stored in a dataset called `crawler_data` with a table `crawled_urls` containing the following columns:

- **url**: The crawled URL
- **source**: Always "cafef" for this crawler
- **channel_name**: Name of the channel (e.g., "Xã hội", "Chứng khoán")
- **channel_id**: Numeric ID of the channel
- **created_at**: Timestamp when the document was created
- **updated_at**: Timestamp when the document was last updated
- **text**: Article text (to be filled later)
- **summarize**: Article summary (to be filled later)

## Next Steps

After collecting URLs, you can update the text and summarize fields by:
1. Querying rows where `text` is null
2. Fetching the article content
3. Updating the rows with the text and summarize fields using UPDATE statements
