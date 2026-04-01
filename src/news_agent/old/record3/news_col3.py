import time
import json
import re
import feedparser
import urllib.parse
import calendar
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from readability import Document
from bs4 import BeautifulSoup

def sanitize_filename(filename):
    return re.sub(r'[\/:*?"<>|]', '', filename).strip()

def save_results(keyword, result, index, year, month):
    # 폴더 구조에 연도/월 추가하여 관리 용이성 증대
    output_dir = Path("crawled_news") / sanitize_filename(keyword) / f"{year}_{str(month).zfill(2)}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    numbering = str(index).zfill(2)
    base_name = numbering 

    json_path = output_dir / f"{base_name}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    md_path = output_dir / f"{base_name}.md"
    md_content = f"""# {result['title']}

- **순번**: {numbering}
- **검색 키워드**: {keyword}
- **대상 기간**: {year}년 {month}월
- **수집 시각**: {time.strftime("%Y-%m-%d %H:%M:%S")}
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

def fetch_search_results(keyword, year, month, limit=10):
    """[업데이트] 특정 연도/월 필터링 연산자 추가"""
    # 해당 월의 마지막 날짜 계산
    last_day = calendar.monthrange(int(year), int(month))[1]
    
    # 구글 뉴스 검색 연산자 생성
    date_filter = f"after:{year}-{str(month).zfill(2)}-01 before:{year}-{str(month).zfill(2)}-{last_day}"
    full_query = f"{keyword} {date_filter}"
    
    encoded = urllib.parse.quote(full_query)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    
    print(f"[*] 검색 쿼리: {full_query}")
    feed = feedparser.parse(url)
    return [e.link for e in feed.entries[:limit]]

if __name__ == "__main__":
    print("\n" + "="*50)
    print("      배트 컴퓨터: 기간 한정 뉴스 인덱서 v1.2")
    print("="*50)
    
    keyword = input("\n색인할 키워드를 입력하세요: ").strip()
    year = input("검색 연도 (예: 2026): ").strip()
    month = input("검색 월 (예: 3): ").strip()
    
    if keyword and year and month:
        links = fetch_search_results(keyword, year, month, limit=10)
        
        if links:
            options = Options()
            options.add_argument("--headless")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            
            print(f"[*] {year}년 {month}월 기사 총 {len(links)}개를 수집합니다.")
            
            try:
                for i, link in enumerate(links, 1):
                    print(f"[{i}/{len(links)}] 본문 추출 중...")
                    result = crawl_article(driver, link)
                    
                    if "error" not in result:
                        save_results(keyword, result, i, year, month)
                    else:
                        print(f"    -> {i}번 기사 추출 실패: {result['error']}")
                
                print(f"\n[*] 완료: 'crawled_news/{keyword}/{year}_{month}' 폴더를 확인하십시오.")
            finally:
                driver.quit()