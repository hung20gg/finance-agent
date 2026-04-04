from bs4 import BeautifulSoup
from curl_cffi import requests
import re
from google.cloud import bigquery
from datetime import datetime
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    }




def fetch_links(session: requests.Session, channel_info: tuple[int, str], page_num: int):

    channelID, channelname = channel_info

    url_fetch = f'https://cafef.vn/timelinelist/{channelID}/{page_num}.chn'

    response = session.get(
        url=url_fetch,
        headers=headers,
        timeout=30
    )
    # Find all links matching the pattern /yyyy/mm/text.htm
    html_content = response.text
    soup = BeautifulSoup(html_content, 'html.parser')

    pattern = r'href="([^"]+\.chn)"'
    links = re.findall(pattern, soup.prettify())

    set_links = set(links)
    return list(set_links)




def crawl_and_save(session: requests.Session, channel_info: tuple[int, str], page_num: int) -> list[tuple[str, str, int]]:
    """Fetch links and save them to BigQuery in batch"""
    channel_id, channel_name = channel_info
    
    links = fetch_links(session, channel_info, page_num)
    
    # Prepare batch of URLs
    url_batch = []
    for link in links:
        # Convert relative URLs to absolute if needed
        if not link.startswith('http'):
            link = f'https://cafef.vn{link}'
        url_batch.append((link, channel_name, channel_id))
    
    return url_batch
