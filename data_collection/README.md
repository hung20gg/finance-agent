# Data Collection Pipeline (Crawler)

This module handles the automated collection of financial data from various sources to populate the system's database.

## Crawlers

The project includes several specialized crawlers:

1.  **Stock Crawler**: Fetches real-time and historical stock prices for tickers on the HOSE, HNX, and UPCOM exchanges.
2.  **Financial Statement Crawler**: Extracts data from quarterly and annual reports (Balance Sheets, Income Statements, Cash Flow Statements).
3.  **Macroeconomic Crawler**: Collects indicators such as Inflation (CPI), Unemployment rates, GDP, and Gold prices.
4.  **News Crawler**: Scrapes financial news from major Vietnamese news portals to provide context for AI agents.

## Technology Stack

- **Python**: Core logic for all crawlers.
- **Selenium/Playwright**: Used for scraping dynamic content and single-page applications.
- **BeautifulSoup**: Used for parsing static HTML.
- **PostgreSQL**: Destination for all collected and cleaned data.

## Usage

Each crawler can be run independently or as part of a scheduled pipeline. 
Refer to the individual scripts in the `src/` directory for specific parameters and configurations.

### Setup
```bash
uv venv
uv pip install -r requirements.txt
```

## Maintenance
Check the logs in the root `logs/` directory for any crawling failures or schema changes on target websites.