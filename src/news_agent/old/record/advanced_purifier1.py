import os
import json
import sys
import trafilatura

# 상위 디렉토리 모듈 임포트 경로 설정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from data_DBsave import NewsDBManager

NEWS_BASE_DIR = os.path.join(PROJECT_ROOT, "data", "News_Reports")

def recover_and_purify(url):
    """밀도 기반 구조 분석을 통해 URL에서 순수 본문을 추출합니다."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if downloaded is None:
            return None
        
        # 구조 분석 및 밀도 기반 추출 (댓글, 표 등은 제외)
        result = trafilatura.extract(downloaded, include_comments=False, include_tables=False)
        return result
    except Exception as e:
        print(f"⚠️ 추출 중 에러 발생: {e}")
        return None

def process_advanced_purification():
    db_manager = NewsDBManager()
    
    if not os.path.exists(NEWS_BASE_DIR):
        print("❌ 저장된 뉴스 폴더를 찾을 수 없습니다.")
        return

    print("🦇 배트 컴퓨터 밀도 기반 구조 분석 및 데이터 복원 프로토콜 가동 중...")
    
    for keyword in os.listdir(NEWS_BASE_DIR):
        keyword_dir = os.path.join(NEWS_BASE_DIR, keyword)
        if not os.path.isdir(keyword_dir):
            continue
        
        print(f"\n[{keyword}] 키워드 데이터 구조 분석 및 복원 시작...")
        
        # DB 재구축을 위한 기존 컬렉션 초기화
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
                
                # 1단계 & 2단계: 내용이 부족한 경우 URL 재접속 및 구조 분석 시도
                if not content or len(content) < 200:
                    print(f"  -> 누락 감지 [{file}]. URL 재접속 및 밀도 분석 시도 중...")
                    new_content = recover_and_purify(url)
                    
                    if new_content and len(new_content) >= 200:
                        content = new_content
                        print(f"  -> 복원 성공: {file}")
                        recovered_count += 1
                    
                # 3단계: 복원 시도 후에도 유효하지 않다면 파일 폐기
                if not content or len(content) < 200:
                    os.remove(json_path)
                    if os.path.exists(txt_path):
                        os.remove(txt_path)
                    deleted_count += 1
                    continue
                    
                # 복원 및 정제된 데이터 덮어쓰기
                data['content'] = content
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                    
                if os.path.exists(txt_path):
                    with open(txt_path, 'w', encoding='utf-8') as tf:
                        tf.write(f"INDEX: {data.get('index', '')}\nTITLE: {data.get('title', '')}\nURL: {url}\nDATE: {data.get('date', '')}\n")
                        tf.write("-" * 50 + "\n" + content)
                
                valid_count += 1
                
        # 유효한 파일들로 DB 재색인
        if valid_count > 0:
            db_manager.index_keyword_folder(keyword)
            
        print(f"✅ 정제 완료: {valid_count}건 유지 (알고리즘 복원 {recovered_count}건 포함) / {deleted_count}건 영구 삭제 및 DB 갱신 완료.")

if __name__ == "__main__":
    process_advanced_purification()