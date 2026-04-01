import os
import sys
import shutil

# 상위 경로 모듈 임포트
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from data_DBsave import NewsDBManager

NEWS_BASE_DIR = os.path.join(PROJECT_ROOT, "data", "News_Reports")

def run_db_manager():
    db_manager = NewsDBManager()
    
    while True:
        print("\n" + "="*60)
        print("🦇 배트 컴퓨터 DB 제어 센터 (ChromaDB Control Terminal)")
        print("="*60)
        
        # 1단계: 현재 DB 상태 출력
        stats = db_manager.get_all_collection_stats()
        if not stats:
            print("현재 데이터베이스에 적재된 컬렉션이 없습니다.")
        else:
            print("[데이터베이스 실시간 적재 현황]")
            for stat in stats:
                print(f" - 키워드 컬렉션: {stat['Keyword']} (총 {stat['Count']}건)")
                
        print("-" * 60)
        print("1. 특정 키워드(컬렉션) 전체 삭제 및 로컬 폴더 파기")
        print("2. 특정 문서 ID 개별 삭제 (DB 핀셋 제거)")
        print("3. 데이터베이스 및 로컬 파일 전체 초기화 (경고: 복구 불가)")
        print("4. 제어 터미널 종료")
        print("-" * 60)
        
        choice = input("원하시는 작업 번호를 입력하십시오: ")
        
        if choice == '1':
            keyword = input("삭제할 키워드를 입력하십시오 (예: 삼성): ")
            confirm = input(f"⚠️ '{keyword}'의 DB 컬렉션과 로컬 원본 폴더를 모두 파기합니까? (y/n): ")
            if confirm.lower() == 'y':
                # 2단계: DB 컬렉션 삭제 및 로컬 폴더 동기화 파기
                if db_manager.delete_keyword_collection(keyword):
                    target_dir = os.path.join(NEWS_BASE_DIR, keyword)
                    if os.path.exists(target_dir):
                        shutil.rmtree(target_dir)
                        print(f"✅ 물리적 원본 폴더 파기 완료: {target_dir}")
                    
        elif choice == '2':
            keyword = input("작업할 키워드를 입력하십시오: ")
            doc_id = input("삭제할 문서 ID를 입력하십시오 (예: Google_G0001): ")
            confirm = input(f"⚠️ '{keyword}' 컬렉션에서 '{doc_id}' 문서를 삭제합니까? (y/n): ")
            if confirm.lower() == 'y':
                # 3단계: DB 내 벡터 고유 ID 삭제
                db_manager.delete_document_by_id(keyword, doc_id)
                print("✅ 안내: 데이터베이스 내 벡터 정보가 제거되었습니다. (해당 문서의 검색이 차단됩니다)")
                
        elif choice == '3':
            confirm = input("🚨 [위험] DB와 모든 물리적 로컬 데이터를 포맷합니다. 계속하시겠습니까? (y/n): ")
            if confirm.lower() == 'y':
                db_manager.reset_all_data()
                if os.path.exists(NEWS_BASE_DIR):
                    shutil.rmtree(NEWS_BASE_DIR)
                    os.makedirs(NEWS_BASE_DIR)
                print("✅ 시스템 완전 초기화가 성공적으로 완료되었습니다.")
                
        elif choice == '4':
            print("DB 제어 터미널을 안전하게 종료합니다.")
            break
        else:
            print("❌ 잘못된 입력입니다. 메뉴의 번호를 다시 선택해 주십시오.")

if __name__ == "__main__":
    run_db_manager()