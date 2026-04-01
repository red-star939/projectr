import feedparser
import urllib.parse
import os
import json
import time

# [설정] 기준 경로 및 데이터 디렉토리
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

def save_news_to_data(keyword, results):
    """수집된 뉴스 데이터를 JSON으로 저장"""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    file_path = os.path.join(DATA_DIR, f"{keyword}_news.json")
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    print(f"[*] 아카이브 저장 완료: {file_path} (총 {len(results)}건)")

def fetch_news(keyword):
    """
    구글 뉴스 RSS 엔진 단일 운용 로직
    - 중복 방지 및 표준 데이터 확보 목적
    """
    encoded = urllib.parse.quote(keyword)
    # 구글 뉴스 RSS 검색 URL (한국어 설정)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    
    print(f"[정보] '{keyword}' 키워드로 구글 엔진 탐색 중...")
    feed = feedparser.parse(url)
    
    results = []
    for e in feed.entries[:10]:  # 상위 10개 기사 수집
        results.append({
            'title': e.title,
            'link': e.link,
            'published': e.published,
            'source': 'Google News',
            'collected_at': time.strftime("%Y-%m-%d %H:%M:%S")
        })
    
    return results

if __name__ == "__main__":
    target_keyword = input("검색할 뉴스 키워드를 입력하세요: ").strip()
    if target_keyword:
        news_data = fetch_news(target_keyword)
        if news_data:
            save_news_to_data(target_keyword, news_data)
        else:
            print("[경고] 수집된 뉴스 데이터가 없습니다.")