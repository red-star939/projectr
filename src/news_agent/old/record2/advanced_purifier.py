import os
import json
import sys
import time
import re
import trafilatura
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# 상위 디렉토리 모듈 임포트 경로 설정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from data_DBsave import NewsDBManager

NEWS_BASE_DIR = os.path.join(PROJECT_ROOT, "data", "News_Reports")

def clean_extracted_text(content):
    """추출 및 복원된 텍스트의 잔여 노이즈를 정규식으로 최종 세척합니다."""
    if not content:
        return ""
    
    # 이메일 주소 및 사진 캡션 패턴 제거
    content = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '', content)
    content = re.sub(r'\(?사진=.*?\)?', '', content)
    content = re.sub(r'\[.*?사진.*?\]', '', content)
    
    # 자주 등장하는 불필요 문구 일괄 제거
    noise_words = [
        '기자 구독하기', '클린뷰', '프린트', 'ADVERTISEMENT', '무단전재 및 재배포 금지', 
        '공유', '댓글', '좋아요', '싫어요', '후속기사 원해요', '글자크기 조절', '기사 스크랩',
        '입력', '수정', '지면', 'ⓒ 한경닷컴'
    ]
    for word in noise_words:
        content = content.replace(word, '')
        
    # 다중 공백 및 연속된 줄바꿈 정규화 압축
    content = re.sub(r'\n{2,}', '\n', content)
    content = re.sub(r' {2,}', ' ', content)
    return content.strip()

def extract_with_selenium(url):
    """3단계: 셀레니움을 가동하여 마우스 드래그와 동일하게 '보이는 텍스트'를 강제 추출합니다."""
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    try:
        driver.get(url)
        time.sleep(3) # 자바스크립트 렌더링 대기
        body_element = driver.find_element(By.TAG_NAME, "body")
        return body_element.text
    except Exception as e:
        print(f"    ⚠️ 2차 셀레니움 추출 실패: {e}")
        return None
    finally:
        driver.quit()

def recover_and_purify(url):
    """1단계 & 2단계: trafilatura 실패 시 Selenium으로 우회하는 이중 복원 로직"""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded:
            result = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
            if result and len(result) >= 200:
                return result
    except Exception as e:
        pass 

    print("    -> 🔄 정적 파싱 실패. 동적 렌더링(Selenium) 기반 강제 추출로 전환합니다...")
    return extract_with_selenium(url)

def process_advanced_purification():
    db_manager = NewsDBManager()
    
    if not os.path.exists(NEWS_BASE_DIR):
        print("❌ 저장된 뉴스 폴더를 찾을 수 없습니다.")
        return

    print("🦇 배트 컴퓨터 2중 복원 및 최종 정제 프로토콜 가동 중...")
    
    for keyword in os.listdir(NEWS_BASE_DIR):
        keyword_dir = os.path.join(NEWS_BASE_DIR, keyword)
        if not os.path.isdir(keyword_dir):
            continue
        
        print(f"\n[{keyword}] 키워드 데이터 복원 및 검증 시작...")
        db_manager.delete_keyword_collection(keyword)
        
        valid_count = 0
        recovered_count = 0
        deleted_count = 0
        
        for source in os.listdir(keyword_dir):
            source_path = os.path.join(keyword_dir, source)
            if not os.path.isdir(source_path):
                continue
                
            for file in os.listdir(source_path):
                if not file.endswith(".json"):
                    continue
                    
                json_path = os.path.join(source_path, file)
                txt_path = json_path.replace('.json', '.txt')
                
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                content = data.get('content', '')
                url = data.get('url', '')
                
                # 1. 누락 데이터 복원 시도
                if not content or len(content) < 200:
                    print(f"  -> 누락 감지 [{file}]. 데이터 복원 시도 중...")
                    new_content = recover_and_purify(url)
                    if new_content:
                        content = new_content
                        recovered_count += 1
                        print(f"  -> 복원 추출 완료: {file} (정제 대기)")
                
                # 2. 모든 데이터(기존/복원)에 대해 최종 노이즈 세척 실행
                content = clean_extracted_text(content)
                
                # 3. 정제 후 유효성 재검증 (최종 탈락 처리)
                if not content or len(content) < 200:
                    os.remove(json_path)
                    if os.path.exists(txt_path):
                        os.remove(txt_path)
                    deleted_count += 1
                    continue
                    
                # 유효 데이터 덮어쓰기
                data['content'] = content
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                    
                if os.path.exists(txt_path):
                    with open(txt_path, 'w', encoding='utf-8') as tf:
                        tf.write(f"INDEX: {data.get('index', '')}\nTITLE: {data.get('title', '')}\nURL: {url}\nDATE: {data.get('date', '')}\n")
                        tf.write("-" * 50 + "\n" + content)
                
                valid_count += 1
                
        if valid_count > 0:
            db_manager.index_keyword_folder(keyword)
            
        print(f"✅ 정제 완료: {valid_count}건 유지 (복원 {recovered_count}건 포함) / {deleted_count}건 영구 삭제 및 DB 갱신 완료.")

if __name__ == "__main__":
    process_advanced_purification()