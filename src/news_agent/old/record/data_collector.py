import os
import re
import time
import json
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def clean_filename(filename):
    """파일명 및 폴더명에서 특수문자 제거 (보조용)"""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def save_article_to_txt(keyword, title, url, source):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

    # [Step 1] 상대 경로 계산 (src/news_agent -> projectr/data/News_Reports)
    CURRENT_DIR = os.path.dirname(os.path.abspath(__file__)) 
    PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
    TARGET_BASE_DIR = os.path.join(PROJECT_ROOT, 'data', 'News_Reports')
    
    TARGET_DIR = os.path.join(TARGET_BASE_DIR, clean_filename(keyword), source)
    os.makedirs(TARGET_DIR, exist_ok=True)

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get(url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 본문 추출 로직
        content = ""
        targets = ['#dic_area', '#articleBodyContents', '.article_view', '#newsct_article', 'article', '.content']
        for target in targets:
            element = soup.select_one(target)
            if element:
                content = element.get_text(separator="\n", strip=True)
                if len(content) > 100: break # 충분한 내용 확보 시 중단
        
        # [수정] 본문 내용이 적어도 통과되도록 길이 제한 해제
        # if len(content) < 100: return False, "본문 부족" # 기존 제한 로직 제거

        # [Step 2] 소스별 접두사 + 숫자 기반 파일명 생성
        # 소스명(Google, Naver, Daum 등)의 첫 글자를 접두사로 사용
        prefix = source[0].upper()
        existing_files = [f for f in os.listdir(TARGET_DIR) if f.endswith('.json')]
        next_index = len(existing_files) + 1
        base_filename = f"{prefix}{next_index:04d}" # 예: G0001, N0001, D0001

        # [Step 3] 데이터 저장 (JSON & TXT)
        # 1. JSON 저장 (구조화 데이터)
        json_data = {
            "index": base_filename,
            "keyword": keyword,
            "source": source,
            "title": title,
            "url": url,
            "date": str(datetime.now()),
            "content": content
        }
        with open(os.path.join(TARGET_DIR, f"{base_filename}.json"), "w", encoding="utf-8") as jf:
            json.dump(json_data, jf, ensure_ascii=False, indent=4)

        # 2. TXT 저장 (가독성 중심)
        with open(os.path.join(TARGET_DIR, f"{base_filename}.txt"), "w", encoding="utf-8") as tf:
            tf.write(f"INDEX: {base_filename}\nTITLE: {title}\nURL: {url}\nDATE: {datetime.now()}\n")
            tf.write("-" * 50 + "\n" + content)
            
        return True, base_filename
    except Exception as e:
        return False, str(e)
    finally:
        driver.quit()