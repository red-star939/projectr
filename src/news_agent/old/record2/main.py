import os
import sys

# 모듈 경로 추가 (현재 디렉토리 기준)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

# 기존 모듈 임포트
from news_collector import fetch_news
from data_collector import save_article_to_txt
from advanced_purifier import process_advanced_purification
from db_viewer import run_viewer
from db_manager_cli import run_db_manager
# [추가] 데이터 추출 모듈 임포트 (함수명 중복 방지를 위해 별칭 사용)
from db_extracter import run_viewer as run_extractor

def run_integrated_pipeline():
    """뉴스 수집 -> 수집 -> 정제 -> DB적재 통합 파이프라인"""
    print("\n" + "=[ 뉴스 수집 및 분석 프로토콜 가동 ]".center(55, "="))
    keyword = input("📡 수집 및 분석할 키워드를 입력하십시오: ").strip()
    
    if not keyword:
        print("❌ 키워드가 입력되지 않았습니다.")
        return

    # Phase 1: 뉴스 링크 수집
    print(f"\n[1/3] '{keyword}' 관련 뉴스 링크 검색 중...")
    news_list = fetch_news(keyword)
    print(f"✅ 총 {len(news_list)}개의 뉴스 링크를 확보했습니다.")

    # Phase 2: 본문 상세 스크래핑 및 로컬 저장
    print(f"\n[2/3] 뉴스 본문 스크래핑 및 로컬 저장 시작 (Selenium 가동)...")
    success_count = 0
    for idx, news in enumerate(news_list):
        success, _ = save_article_to_txt(keyword, news['title'], news['link'], news['source'])
        if success:
            success_count += 1
    print(f"✅ 스크래핑 완료: {success_count}/{len(news_list)} 건 성공.")

    # Phase 3: 2중 복원, 정제 및 ChromaDB 색인
    print(f"\n[3/3] 2중 복원 및 데이터베이스(ChromaDB) 적재 프로토콜 실행...")
    process_advanced_purification()
    print(f"\n✨ '{keyword}' 관련 모든 프로세스가 완료되었습니다.")

def main_menu():
    while True:
        print("\n" + "🦇 배트 컴퓨터 통합 뉴스 분석 터미널 🦇".center(50, "="))
        print("1. 신규 뉴스 수집 및 DB 적재 파이프라인 가동")
        print("2. 데이터베이스(ChromaDB) 저장 내역 조회 (Quick Viewer)")
        print("3. 데이터베이스 관리 및 특정 데이터 파기 (Manager)")
        print("4. 데이터 외부 추출 및 TXT 변환 (Extractor) [NEW]")
        print("5. 시스템 종료")
        print("=" * 56)
        
        choice = input("명령을 선택하십시오: ").strip()
        
        if choice == '1':
            run_integrated_pipeline()
        elif choice == '2':
            run_viewer()
        elif choice == '3':
            run_db_manager()
        elif choice == '4':
            # [추가] 추출 모듈 실행
            run_extractor()
        elif choice == '5':
            print("👋 배트 컴퓨터 시스템을 안전하게 종료합니다. 안녕히 가십시오, 홍 님.")
            break
        else:
            print("❌ 잘못된 입력입니다. 메뉴의 번호를 선택해 주십시오.")

if __name__ == "__main__":
    main_menu()