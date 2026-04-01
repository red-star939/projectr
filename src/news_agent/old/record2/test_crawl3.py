import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from readability import Document  # 읽기 모드 핵심 엔진
from bs4 import BeautifulSoup

def crawl_with_readability_engine(url):
    # 1. 셀레니움 헤드리스 설정
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    
    try:
        # 2. 페이지 접속 및 리다이렉트 대기
        driver.get(url)
        
        # 구글 뉴스 RSS의 경우 최종 목적지로 이동할 때까지 대기
        start_time = time.time()
        while "google.com" in driver.current_url and time.time() - start_time < 10:
            time.sleep(1)
            
        # 자바스크립트 렌더링 완료를 위한 추가 대기
        time.sleep(2)
        
        # 3. 읽기 모드 엔진(Readability) 적용
        # 브라우저에서 가져온 전체 HTML을 엔진에 주입합니다.
        raw_html = driver.page_source
        doc = Document(raw_html)
        
        # doc.summary()는 알고리즘이 판단한 '본문 데이터'만 담긴 HTML을 반환합니다.
        readable_html = doc.summary()
        title = doc.title()
        
        # 4. BeautifulSoup을 이용한 텍스트 최종 정제
        soup = BeautifulSoup(readable_html, 'html.parser')
        
        # 읽기 모드 결과물 내에서도 남아있을 수 있는 이미지 캡션 등을 정리
        clean_text = soup.get_text("\n", strip=True)
        
        # 의미 없는 짧은 줄(광고 잔재) 필터링
        lines = [line.strip() for line in clean_text.splitlines() if len(line.strip()) > 10]
        final_content = "\n\n".join(lines)
        
        return {
            "title": title,
            "content": final_content,
            "url": driver.current_url
        }

    except Exception as e:
        return {"error": str(e)}
    finally:
        driver.quit()

# --- 실행부 ---
# --- [수정된 실행부] ---
if __name__ == "__main__":
    print("\n" + "="*50)
    print("      실시간 뉴스 추출 시스템 v4.1")
    print("="*50)
    
    # 1. 사용자로부터 직접 주소 입력 받기
    user_url = input("\n크롤링할 뉴스 URL을 입력하세요 (Q 입력 시 종료): ").strip()
    
    # 종료 조건 처리
    if user_url.lower() == 'q':
        print("시스템을 종료합니다.")
    elif not user_url.startswith("http"):
        print("[경고] 올바른 URL 형식이 아닙니다. (http:// 또는 https:// 포함 필요)")
    else:
        print("\n[작동] 읽기 모드 엔진을 가동하여 분석 중입니다. 잠시만 기다려 주십시오...")
        
        # 2. 입력받은 주소로 함수 호출
        result = crawl_with_readability_engine(user_url)
        
        if "error" in result:
            print(f"\n[오류 발생]: {result['error']}")
        else:
            print(f"\n[기사 제목]: {result['title']}")
            print("-" * 50)
            print(result['content'])
            print("-" * 50)
            print(f"[최종 경로]: {result['url']}")