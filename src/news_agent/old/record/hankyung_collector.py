import os
import json
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# [환경 설정] 배트 컴퓨터 저장소 경로
TARGET_DIR = r"C:\Users\USER\projectr\data\News_Reports\hankyung"

def setup_bat_driver():
    """안정적인 크롤링을 위한 드라이버 환경 설정"""
    options = Options()
    options.add_argument("--headless")  # 백그라운드 실행
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    return driver

def run_hankyung_agent():
    keyword = input("알프레드에게 수집할 키워드를 입력하세요: ")
    print(f"\n[*] '{keyword}' 타겟팅 시작. 검색 쿼리 주입 중...")
    
    driver = setup_bat_driver()
    # 홍 님이 제시해주신 검색 쿼리 구조 적용
    target_url = f"https://search.hankyung.com/search/news?query={keyword}"
    
    try:
        driver.get(target_url)
        wait = WebDriverWait(driver, 15)
        
        # 기사 목록 요소가 나타날 때까지 대기
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".news_list li")))
        
        # 1. 기사 링크 10건 수집
        items = driver.find_elements(By.CSS_SELECTOR, ".news_list li")
        article_links = []
        for item in items:
            try:
                link_tag = item.find_element(By.CSS_SELECTOR, ".tit a")
                article_links.append({
                    "title": link_tag.text.strip(),
                    "url": link_tag.get_attribute('href')
                })
                if len(article_links) >= 10: break
            except: continue

        print(f"[*] {len(article_links)}개의 타겟 문서 확인. 본문 정밀 추출을 시작합니다.")

        # 2. 각 링크 접속 및 본문 수집
        for i, article in enumerate(article_links, 1):
            driver.get(article['url'])
            time.sleep(1.5) # 페이지 로딩 안정화 시간
            
            try:
                # 한국경제 본문 전용 ID 타겟팅
                content_area = driver.find_element(By.ID, "articletxt")
                content = content_area.text.strip()
            except:
                content = "본문 영역 추출 실패 (구조 상이)"

            # 3. 데이터 패키징 및 저장
            save_data = {
                "keyword": keyword,
                "title": article['title'],
                "url": article['url'],
                "date": str(datetime.now()),
                "content": content
            }
            
            if not os.path.exists(TARGET_DIR): os.makedirs(TARGET_DIR)
            fname = f"H{len([f for f in os.listdir(TARGET_DIR) if f.endswith('.json')]) + 1:04d}"
            
            # JSON 저장
            with open(os.path.join(TARGET_DIR, f"{fname}.json"), "w", encoding="utf-8") as j:
                json.dump(save_data, j, ensure_ascii=False, indent=4)
            # TXT 저장
            with open(os.path.join(TARGET_DIR, f"{fname}.txt"), "w", encoding="utf-8") as t:
                t.write(f"INDEX: {fname}\nTITLE: {article['title']}\nURL: {article['url']}\n\n{content}")
            
            print(f"[{i}/10] {fname} 시스템 저장 완료: {article['title'][:20]}...")

        print(f"\n[+] 모든 데이터가 {TARGET_DIR}에 성공적으로 아카이빙되었습니다.")

    except Exception as e:
        print(f"\n[오류 발생] 현재 페이지에서 요소를 포착하지 못했습니다. 추정 원인: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    run_hankyung_agent()