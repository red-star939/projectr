import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

def refined_news_extractor(url):
    options = Options()
    options.add_argument("--headless")
    options.add_argument("user-agent=Mozilla/5.0 ...") # 생략 가능
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    
    try:
        driver.get(url)
        # 리다이렉트 대기 로직 (생략, 이전과 동일)
        time.sleep(3) 
        
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 1. 불필요한 레이아웃 강제 제거
        for s in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form', 'button', 'iframe']):
            s.decompose()

        # 2. 본문 후보군 탐색 및 점수 산정
        candidates = []
        for tag in soup.find_all(['div', 'article', 'section']):
            all_text = tag.get_text(" ", strip=True)
            if len(all_text) < 100: continue
            
            link_text = "".join([a.get_text(strip=True) for a in tag.find_all('a')])
            link_density = len(link_text) / len(all_text) if len(all_text) > 0 else 0
            
            # 링크 밀도가 40% 이상이면 광고/메뉴판으로 간주하여 제외
            if link_density > 0.4: continue 
            
            score = len(all_text) * (1 - link_density)
            if tag.name == 'article': score += 1000
            
            candidates.append((tag, score))

        if not candidates: return "본문 추출 실패"

        # 최적 노드 선택
        candidates.sort(key=lambda x: x[1], reverse=True)
        main_node = candidates[0][0]
        
        # 3. 본문 정제 및 종결 지점 커팅
        raw_lines = main_node.get_text("\n", strip=True).splitlines()
        clean_body = []
        
        # 본문 종결을 알리는 키워드들
        stop_keywords = ['저작권자', '무단전재', '재배포 금지', 'ⓒ', 'Copyright', '관련기사', '기사 더보기']
        
        for line in raw_lines:
            line = line.strip()
            if len(line) < 5: continue # 너무 짧은 줄 제외
            
            # 종결 키워드 발견 시 루프 중단 (하단 광고/목록 제거)
            if any(kw in line for kw in stop_keywords):
                break
            
            # 중간 광고 문구(다이어트, 비만균 등) 제거를 위한 정규식
            if re.search(r'다이어트|감량|무료|최저가|렌트|위약금', line):
                continue
                
            clean_body.append(line)

        return "\n\n".join(clean_body)

    finally:
        driver.quit()

print(refined_news_extractor("사용자_제공_URL"))