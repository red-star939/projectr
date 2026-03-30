import os
import json
import re
import sys

# 상위 디렉토리의 모듈 임포트를 위한 경로 설정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

# 기작성된 DB 매니저 임포트
from data_DBsave import NewsDBManager

NEWS_BASE_DIR = os.path.join(PROJECT_ROOT, "data", "News_Reports")

def clean_existing_text(content):
    """1단계 & 2단계: 기존 텍스트 데이터 사후 정제"""
    # 이메일 주소 제거
    content = re.sub(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', '', content)
    # 사진 캡션 패턴 제거
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
        
    # 2단계: 다중 공백 및 연속된 줄바꿈 정규화 압축
    content = re.sub(r'\n{2,}', '\n', content)
    content = re.sub(r' {2,}', ' ', content)
    return content.strip()

def process_saved_data():
    db_manager = NewsDBManager()
    
    if not os.path.exists(NEWS_BASE_DIR):
        print("❌ 저장된 뉴스 폴더를 찾을 수 없습니다.")
        return

    print("🦇 알프레드 사후 정제 프로토콜 가동 중...")
    
    for keyword in os.listdir(NEWS_BASE_DIR):
        keyword_dir = os.path.join(NEWS_BASE_DIR, keyword)
        if not os.path.isdir(keyword_dir):
            continue
        
        print(f"\n[{keyword}] 키워드 데이터 정제 시작...")
        
        # 3단계: 기존 DB 컬렉션을 비우고 정제된 데이터로 다시 채우기 위한 준비
        db_manager.delete_keyword_collection(keyword)
        
        valid_count = 0
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
                    
                original_content = data.get('content', '')
                purified_content = clean_existing_text(original_content)
                
                # 유효성 검사 (200자 미만 시 로컬 파일 삭제)
                if len(purified_content) < 200:
                    os.remove(json_path)
                    if os.path.exists(txt_path):
                        os.remove(txt_path)
                    deleted_count += 1
                    continue
                    
                # 정제 통과 시 JSON 파일 덮어쓰기
                data['content'] = purified_content
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                    
                # TXT 파일도 정제된 본문으로 덮어쓰기
                if os.path.exists(txt_path):
                    with open(txt_path, 'w', encoding='utf-8') as tf:
                        tf.write(f"INDEX: {data['index']}\nTITLE: {data['title']}\nURL: {data['url']}\nDATE: {data['date']}\n")
                        tf.write("-" * 50 + "\n" + purified_content)
                
                valid_count += 1
                
        # 삭제되지 않은 유효한 파일들로 DB 재색인
        if valid_count > 0:
            db_manager.index_keyword_folder(keyword)
            
        print(f"✅ 정제 완료: {valid_count}건 유지 / {deleted_count}건 삭제 및 DB 갱신 완료.")

if __name__ == "__main__":
    process_saved_data()