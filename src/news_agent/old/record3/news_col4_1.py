import time
import json
import re
import feedparser
import urllib.parse
import shutil  # [추가] 폴더 트리 삭제용
from datetime import datetime
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from readability import Document
from bs4 import BeautifulSoup

def sanitize_filename(filename):
    return re.sub(r'[\/:*?"<>|]', '', filename).strip()

def save_results(keyword, result, index, now_obj):
    """시(Hour) 단위 폴더 구조 적용"""
    date_hour_str = now_obj.strftime("%Y_%m_%d_%H")
    output_dir = Path("crawled_news") / sanitize_filename(keyword) / date_hour_str
    output_dir.mkdir(parents=True, exist_ok=True)
    
    numbering = str(index).zfill(2)
    timestamp_min = now_obj.strftime("%M%S")
    base_name = f"{numbering}_{timestamp_min}"

    json_path = output_dir / f"{base_name}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    md_path = output_dir / f"{base_name}.md"
    md_content = f"""# {result['title']}

- **순번**: {numbering}
- **검색 키워드**: {keyword}
- **수집 시각**: {now_obj.strftime("%Y-%m-%d %H:%M:%S")}
- **원문 URL**: [{result['url']}]({result['url']})

---

{result['content']}
"""
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    return json_path, md_path

def crawl_article(driver, url):
    try:
        driver.get(url)
        start_time = time.time()
        while "google.com" in driver.current_url and time.time() - start_time < 8:
            time.sleep(1)
        time.sleep(2)
        
        doc = Document(driver.page_source)
        soup = BeautifulSoup(doc.summary(), 'html.parser')
        lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if len(line.strip()) > 10]
        
        return {
            "title": doc.title(),
            "content": "\n\n".join(lines),
            "url": driver.current_url
        }
    except Exception as e:
        return {"error": str(e)}

def fetch_search_results(keyword, limit=10):
    full_query = f"{keyword} when:1h"
    encoded = urllib.parse.quote(full_query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    
    print(f"[*] 초정밀 실시간 필터링: {full_query}")
    feed = feedparser.parse(url)
    return [e.link for e in feed.entries[:limit]]

if __name__ == "__main__":
    print("\n" + "="*50)
    print("      배트 컴퓨터: 실시간 갱신형 인덱서 v1.5")
    print("="*50)
    
    keyword = input("\n새롭게 분석할 키워드를 입력하세요: ").strip()
    
    if keyword:
        now = datetime.now()
        links = fetch_search_results(keyword, limit=10)
        
        if links:
            # [핵심 로직] 이전 데이터 파기 로직 수행
            kwd_dir = Path("crawled_news") / sanitize_filename(keyword)
            if kwd_dir.exists():
                print(f"[*] 기존 데이터 발견: '{kwd_dir}' 폴더를 파기하고 새로 업데이트합니다.")
                shutil.rmtree(kwd_dir) # 기존 폴더 하위 내용물 전체 삭제
            
            options = Options()
            options.add_argument("--headless")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            
            print(f"[*] 최근 1시간 이내의 최신 기사 {len(links)}개를 수집합니다.")
            
            try:
                for i, link in enumerate(links, 1):
                    print(f"[{i}/{len(links)}] 최신 데이터 동기화 중...")
                    result = crawl_article(driver, link)
                    
                    if "error" not in result:
                        save_results(keyword, result, i, now)
                    else:
                        print(f"    -> {i}번 기사 실패: {result['error']}")
                
                print(f"\n[*] 완료: '{kwd_dir}'에 최신 데이터만 업데이트되었습니다.")
            finally:
                driver.quit()
        else:
            print(f"[*] 최근 1시간 이내에 새로운 뉴스가 없어 기존 데이터를 유지합니다.")