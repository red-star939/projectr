import time
import json
import re
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

def save_results(result):
    """결과를 JSON 및 MD 파일로 저장"""
    # 저장 디렉토리 생성
    output_dir = Path("crawled_news")
    output_dir.mkdir(exist_ok=True)
    
    safe_title = sanitize_filename(result['title'][:50]) # 제목이 너무 길면 자름
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    base_name = f"{safe_title}_{timestamp}"

    # 1. JSON 저장
    json_path = output_dir / f"{base_name}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=4)

    # 2. Markdown 저장
    md_path = output_dir / f"{base_name}.md"
    md_content = f"""# {result['title']}

- **작성일(수집일)**: {time.strftime("%Y-%m-%d %H:%M:%S")}
- **출처 URL**: [{result['url']}]({result['url']})

---

{result['content']}
"""
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)

    return json_path, md_path

def crawl_with_readability_engine(url):
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        driver.get(url)
        start_time = time.time()
        while "google.com" in driver.current_url and time.time() - start_time < 10:
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
    finally:
        driver.quit()

if __name__ == "__main__":
    print("\n" + "="*50)
    print("      뉴스 아카이빙 시스템 v4.2")
    print("="*50)
    
    user_url = input("\nURL 입력 (Q 종료): ").strip()
    
    if user_url.lower() != 'q' and user_url.startswith("http"):
        print("\n[분석 중] 읽기 모드 데이터 추출 및 파일 저장 중...")
        result = crawl_with_readability_engine(user_url)
        
        if "error" not in result:
            # 파일 저장 실행
            json_file, md_file = save_results(result)
            
            print(f"\n[완료] {result['title']}")
            print(f"- JSON 저장 완료: {json_file}")
            print(f"- MD 저장 완료: {md_file}")
        else:
            print(f"\n[오류]: {result['error']}")