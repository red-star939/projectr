import time
import json
import re
import feedparser
import urllib.parse
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from readability import Document
from bs4 import BeautifulSoup

def sanitize_filename(filename):
    """파일명으로 사용할 수 없는 특수문자 제거"""
    return re.sub(r'[\/:*?"<>|]', '', filename).strip()

def save_results(keyword, result, index):
    output_dir = Path("crawled_news") / sanitize_filename(keyword)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # [수정] 파일명을 '01', '02' 등 순수 넘버링으로 설정
    numbering = str(index).zfill(2)
    base_name = numbering 

    # 1. JSON 저장 (01.json)
    json_path = output_dir / f"{base_name}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    # 2. Markdown 저장 (01.md)
    md_path = output_dir / f"{base_name}.md"
    md_content = f"""# {result['title']}

- **순번**: {numbering}
- **검색 키워드**: {keyword}
- **수집 시각**: {time.strftime("%Y-%m-%d %H:%M:%S")}
- **원문 URL**: [{result['url']}]({result['url']})

---

{result['content']}
"""
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    return json_path, md_path

def crawl_article(driver, url):
    """개별 기사 본문 추출 (v4.2 로직 유지)"""
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
    """구글 RSS 색인 (v2.0 로직 통합)"""
    encoded = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    return [e.link for e in feed.entries[:limit]]

if __name__ == "__main__":
    print("\n" + "="*50)
    print("      배트 컴퓨터: 넘버링 아카이브 시스템 v1.1")
    print("="*50)
    
    keyword = input("\n색인할 키워드를 입력하세요: ").strip()
    
    if keyword:
        # 10개까지 수집하도록 상향 조정
        links = fetch_search_results(keyword, limit=10)
        
        if links:
            options = Options()
            options.add_argument("--headless")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            
            print(f"[*] 총 {len(links)}개의 기사를 넘버링하여 저장합니다.")
            
            try:
                for i, link in enumerate(links, 1): # 1번부터 넘버링 시작
                    print(f"[{i}/{len(links)}] 처리 중...")
                    result = crawl_article(driver, link)
                    
                    if "error" not in result:
                        # [인자 추가] 루프의 i 값을 전달하여 넘버링 수행
                        save_results(keyword, result, i)
                    else:
                        print(f"    -> {i}번 기사 추출 실패: {result['error']}")
                
                print(f"\n[*] 완료: 'crawled_news/{keyword}' 폴더에 순차적으로 저장되었습니다.")
            finally:
                driver.quit()