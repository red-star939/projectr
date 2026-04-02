import os
import sys

# 현재 파일(_test_pipeline.py)이 위치한 폴더의 상위->상위(즉, 프로젝트 루트)를 시스템 경로에 추가
# 이렇게 하면 실행 위치에 상관없이 패키지를 깔끔하게 불러올 수 있습니다.
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(project_root)

from src.financial_agent import DART_API
from src.financial_agent import FS_to_SQL
from src.financial_agent import conSQL
from src.financial_agent import yfinance_api
from src.financial_agent import sql_to_json

def run_simulation():
    corp = "SK하이닉스"
    year = 2024
    report = "반기보고서"
    
    print("\n" + "="*60)
    print(f"▶ STEP 1: DART에서 '{corp}' {year}년 {report} 가져오기 및 DB 저장")
    print("="*60)
    
    DART_API.CallFinDescription(corp=corp, report=report, year=year)
    
    # 다운로드된 원본 JSON 경로
    json_path = os.path.join("data", "Financial_Statement", corp, f"{corp}_{year}_{report}.json")
    
    # 전처리 및 SQL 형식의 DataFrame으로 가공
    df_dart = FS_to_SQL.FSpreproc(json_path, source="DART", report_type=report)
    
    # DB 적재
    db = conSQL.FS()
    db.to_sql(corp, df_dart)
    db.close()
    print(f"✅ [{corp}] 1단계 - DART 재무제표 파싱 및 SQL DB 적재 완료!")

    print("\n" + "="*60)
    print(f"▶ STEP 2: yfinance에서 '{corp}' 최신 주식 지표 수집 및 DB 합치기")
    print("="*60)
    
    yfinance_api.fetch_and_save_yfinance_info([corp])

    print("\n" + "="*60)
    print("▶ STEP 3: DB에 모인 모든 데이터를 JSON 기반으로 분할 내보내기")
    print("="*60)
    
    sql_to_json.save_company_data_to_jsonDB(corp)
    
    print("\n🎉 모든 파이프라인 시뮬레이션 종료: 'data/jsonDB/' 폴더를 확인해 주세요!")

if __name__ == "__main__":
    run_simulation()
