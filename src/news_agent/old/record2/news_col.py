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

def save_results(keyword, result):
    """키워드별 폴더에 JSON 및 MD 파일 저장"""
    # 저장 디렉토리 설정 (crawled_news/키워드)
    output_dir = Path("crawled_news") / sanitize_filename(keyword)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    safe_title = sanitize_filename(result['title'][:50])
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    base_name = f"{safe_title}_{timestamp}"

    # 1. JSON 저장
    json_path = output_dir / f"{base_name}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    # 2. Markdown 저장
    md_path = output_dir / f"{base_name}.md"
    md_content = f"""# {result['title']}

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
    """개별 기사 URL에서 본문 추출"""
    try:
        driver.get(url)
        # 구글 리다이렉트 대기
        start_time = time.time()
        while "google.com" in driver.current_url and time.time() - start_time < 8:
            time.sleep(1)
        time.sleep(2) # 렌더링 대기
        
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

def fetch_search_results(keyword, limit=5):
    """구글 RSS를 통해 기사 목록 가져오기"""
    encoded = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
    feed = feedparser.parse(url)
    return [e.link for e in feed.entries[:limit]]

if __name__ == "__main__":
    print("\n" + "="*50)
    print("      배트 컴퓨터: 통합 뉴스 인덱싱 시스템 v1.0")
    print("="*50)
    
    keyword = input("\n색인할 키워드를 입력하세요: ").strip()
    
    if keyword:
        # 1. 색인 목록 확보
        print(f"[*] '{keyword}' 관련 최신 기사 목록 확보 중...")
        links = fetch_search_results(keyword, limit=5) # 5개 기사 수집
        
        if not links:
            print("[!] 검색 결과가 없습니다.")
        else:
            # 2. 셀레니움 드라이버 초기화 (한 번만 실행)
            options = Options()
            options.add_argument("--headless")
            options.add_argument("user-agent=Mozilla/5.0 ...")
            driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
            
            print(f"[*] 총 {len(links)}개의 기사 분석을 시작합니다.")
            
            try:
                for i, link in enumerate(links, 1):
                    print(f"\n[{i}/{len(links)}] 본문 추출 중...")
                    result = crawl_article(driver, link)
                    
                    if "error" not in result:
                        json_p, md_p = save_results(keyword, result)
                        print(f"    -> 성공: {result['title'][:30]}...")
                    else:
                        print(f"    -> 실패: {result['error']}")
                
                print("\n" + "="*50)
                print(f"모든 작업이 완료되었습니다. 'crawled_news/{keyword}' 폴더를 확인하세요.")
            
            finally:
                driver.quit()