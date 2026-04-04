from bs4 import BeautifulSoup
from curl_cffi import requests
from datetime import datetime

headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    }

def clean_article(html: str) -> dict:
    """Clean HTML content to extract text"""
    soup = BeautifulSoup(html, 'html.parser')
    
    title_block = soup.find('h1', class_='title')
    if title_block:
        title = title_block.get_text(strip=True)
    else:
        title = ""
     
    time_str = ""   
    big_time_block = soup.find('div', class_='sharemxh')
    if big_time_block:
        time_block = big_time_block.find('span', class_='pdate')
        if time_block:
            time_str = time_block.get_text(strip=True) # Format: "22-11-2025 - 08:11 AM"        
    # Convert time string to datetime
    if time_str:
        try:
            # Parse format: "24-07-2024 - 15:20 PM" (24-hour format with AM/PM)
            pub_date = datetime.strptime(time_str, "%d-%m-%Y - %H:%M %p")
        except ValueError:
            pub_date = None
    else:
        pub_date = None
    
    content = soup.find('div', class_='contentdetail')
    
    p_blocks = content.find_all('p') if content else []
    text_str = ""
    for p in p_blocks:
        # Remove unwanted tags within paragraphs
        for tag in p.find_all(['strong', 'em', 'span', 'a']):
            tag.unwrap()
        text_str += p.get_text(strip=True) + "\n"
    
            
        
    
    return {
        "title": title,
        "pub_date": pub_date.isoformat() if pub_date else None,
        "text": text_str.strip()
    }


def craw_article(session: requests.Session, url: str) -> dict:
    """Crawl article content from the given URL"""
    
    response = session.get(
        url=url,
        headers=headers,
        timeout=20
    )
    
    html_content = response.text

    return clean_article(html_content)


if __name__ == "__main__":
    test_url = "https://cafef.vn/khong-thi-hanh-ky-luat-uy-vien-thuong-vu-truong-ban-tuyen-giao-huyen-uy-nguyen-bi-thu-dang-uy-chu-nhiem-uy-ban-kiem-tra-dang-uy-xa-188240724143033472.chn"
    
    with requests.Session() as session:
        article = craw_article(session, test_url)
        print(article)