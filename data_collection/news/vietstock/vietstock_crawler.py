from bs4 import BeautifulSoup
from curl_cffi import requests
import re

headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
        # "Referer": "https://vietcv.seedoo.vn/",
        # Đừng quên tham số từ Local Storage bạn đã tìm thấy
    }

session = requests.Session()
channelIDs = [830, 144, ]


def fetch_links(channelID, page):
    url_fetch = 'https://vietstock.vn/StartPage/ChannelContentPage'

    response = session.post(
        url=url_fetch,
        data={
            "channelID": channelID,
            "page": page
        },
        headers=headers
    )
    # Find all links matching the pattern /yyyy/mm/text.htm
    html_content = response.text
    soup = BeautifulSoup(html_content, 'html.parser')

    pattern = r'href="(/\d{4}/\d{2}/[^"]+\.htm)"'
    links = re.findall(pattern, soup.prettify())

    set_links = set(links)
    return list(set_links)