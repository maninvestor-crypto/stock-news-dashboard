import feedparser
import requests
from bs4 import BeautifulSoup
import urllib.parse
import time

def get_news_links(keyword, max_items=5):
    """지정된 키워드로 구글 뉴스 RSS를 검색하여 뉴스 링크 목록을 반환합니다."""
    # 한국어 구글 뉴스 RSS 엔드포인트
    encoded_keyword = urllib.parse.quote(keyword)
    rss_url = f"https://news.google.com/rss/search?q={encoded_keyword}&hl=ko&gl=KR&ceid=KR:ko"
    
    feed = feedparser.parse(rss_url)
    articles = []
    
    for entry in feed.entries[:max_items]:
        articles.append({
            "title": entry.title,
            "link": entry.link,
            "published": entry.published
        })
        
    return articles

def extract_article_text(url):
    """주어진 URL의 뉴스 기사 본문을 추출합니다."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
        }
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # Google News RSS 링크는 실제 기사로 리다이렉트 됩니다.
        # 대부분의 뉴스 사이트에서 리드 문단 혹은 본문은 <p> 태그 안에 있습니다.
        paragraphs = soup.find_all('p')
        
        # 지나치게 짧은 문장(예: 광고성 텍스트, 저작권 문구)은 제외하고 합칩니다.
        text = " ".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 20])
        
        # 텍스트가 너무 길면 자르기 (Gemini 프롬프트 효율성을 위해)
        return text[:3000]
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return ""
