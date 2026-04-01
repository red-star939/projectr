import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def solve_news_extraction(url):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # 실제 브라우저처럼 보이기 위한 User-Agent 설정
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get(url)
        
        # [단계 1] 최종 목적지 URL로 리다이렉트 될 때까지 대기 (최대 10초)
        start_time = time.time()
        while "google.com" in driver.current_url and time.time() - start_time < 10:
            time.sleep(1)
        
        # 페이지 로딩 완료 대기
        time.sleep(2) 
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # [단계 2] 불용 노드 제거
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'button']):
            s.decompose()

        # [단계 3] 텍스트 밀도 + 시맨틱 태그 점수제
        candidates = []
        # 주요 컨텐츠 블록 탐색
        for tag in soup.find_all(['div', 'article', 'section', 'main']):
            text = tag.get_text(" ", strip=True)
            if len(text) < 100: continue
            
            link_text_len = sum(len(a.get_text(strip=True)) for a in tag.find_all('a'))
            # 텍스트 밀도: 링크를 제외한 순수 텍스트 비중
            density = (len(text) - link_text_len) / len(text) if len(text) > 0 else 0
            
            # 가중치 계산
            score = len(text) * density
            if tag.name == 'article': score += 500
            
            # 클래스/ID 기반 보너스 점수
            attr_val = (str(tag.get('class')) + str(tag.get('id'))).lower()
            if any(key in attr_val for key in ['article', 'content', 'post', 'body', 'view']):
                score += 300
                
            candidates.append((tag, score))

        if not candidates:
            return "최종 페이지에서 본문 블록을 식별하지 못했습니다."

        # 점수가 가장 높은 노드 선택
        candidates.sort(key=lambda x: x[1], reverse=True)
        best_tag = candidates[0][0]
        
        # [단계 4] 결과 정리 (기사 본문 내의 불필요한 공백/줄바꿈 정리)
        lines = [line.strip() for line in best_tag.get_text("\n").splitlines() if len(line.strip()) > 20]
        return "\n".join(lines)

    finally:
        driver.quit()

# 실행 테스트
target = "https://news.google.com/rss/articles/CBMic0FVX3lxTFBJZGJ4VEJFWVc5N2RuaS1hTDQ1NE1kLS1pQ2lQWGl0blAxWEtWOFhyS1p0V1pEeTItMnNWX09yd0dpU21mLXZnY0FtZmNBbjFJYWEyazNfUkE5c0NiZ0huVHlIVVpTZlB3ajYzT1YwU19FOVk?oc=5"
print(solve_news_extraction(target))