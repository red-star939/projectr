import feedparser
import urllib.parse
import requests
from bs4 import BeautifulSoup
import os
import json

# [추가] 기준 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

# [추가] 데이터 저장 함수 예시
def save_news_to_data(keyword, results):
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    file_path = os.path.join(DATA_DIR, f"{keyword}_news.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    print(f"저장 완료: {file_path}")

# 공통 헤더 설정 (차단 방지)
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"}

def fetch_google(keyword):
    encoded = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    return [{'title': e.title, 'link': e.link, 'published': e.published, 'source': 'Google'} for e in feed.entries[:5]]

#네이버는 아직 해결 못함
def fetch_naver(keyword):
    encoded = urllib.parse.quote(keyword)
    url = f"https://search.naver.com/search.naver?where=news&query={encoded}&sm=tab_opt&sort=0"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = []
        news_elements = soup.select("a.news_tit")
        for a in news_elements[:5]:
            title = a.text.strip()
            link = a.get('href')
            items.append({'title': title, 'link': link, 'published': 'Naver News', 'source': 'Naver'})
        return items
    except Exception as e:
        print(f"Naver Scraping Error: {e}") # 터미널에서 오류 확인용
        return []

def fetch_daum(keyword):
    encoded = urllib.parse.quote(keyword)
    url = f"https://search.daum.net/search?w=news&q={encoded}"
    try:
        resp = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(resp.text, 'html.parser')
        items = []
        # 다음 뉴스 구조에 맞춘 셀렉터 (구조 변경 시 업데이트 필요)
        for a in soup.select("div.item-title a")[:5]:
            items.append({'title': a.text, 'link': a.get('href'), 'published': 'Daum News', 'source': 'Daum'})
        return items
    except: return []

def fetch_news(keyword):
    # 모든 소스에서 데이터 수집 후 통합
    results = []
    results.extend(fetch_google(keyword))
    results.extend(fetch_naver(keyword))
    results.extend(fetch_daum(keyword))
    return results