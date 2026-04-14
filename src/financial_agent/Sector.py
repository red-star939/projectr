import pandas as pd
import FinanceDataReader as fdr
import sys

# 패키지 임포트를 위한 경로 설정 (터미널 단독 실행 및 외부 호출 모두 지원)
from pathlib import Path
current_file_path = Path(__file__).resolve()
if str(current_file_path.parent.parent.parent) not in sys.path:
    sys.path.append(str(current_file_path.parent.parent.parent))

from src.financial_agent import utils_
from src.financial_agent import conSQL

def _load_sectors():
    """
    (초기화 스크립트) CORPCODE.xml의 전체 회사 리스트와 FinanceDataReader의 산업 정보를 조인하여
    DB의 'SECTORS' 마스터 테이블에 삽입(초기화/갱신)합니다.
    1회성으로 호출되어 DB 구조를 세팅하는 용도이며, 별도의 메모리 구조를 유지하지 않습니다.
    """
    print("🔄 섹터-회사 매핑 구축 중 (FS.db 마스터 테이블 적재)...")
    try:
        # 1. CORPCODE.xml 정보 로드 (utils_)
        # dartCodes 내 corp_name 칼럼만을 온전히 가져옵니다.
        dart_df = utils_.dartCodes[['corp_name']].copy()
        
        # 2. FinanceDataReader 산업 정보 로드
        fdr_df = fdr.StockListing('KRX-DESC')
        fdr_subset = fdr_df[['Name', 'Industry']].copy()
        fdr_subset.rename(columns={'Name': 'corp_name', 'Industry': 'sector'}, inplace=True)
        
        # 3. 조인 (CORPCODE.xml에 있는 10만개 이상의 모든 회사들 기준)
        merged_df = pd.merge(dart_df, fdr_subset, on='corp_name', how='left')
        
        # 비상장사 및 fdr 미지원 섹터는 '비상장/기타'로 단일화
        merged_df['sector'] = merged_df['sector'].fillna('비상장/기타')
        
        # 최종 포맷 지정 및 중복 제거
        final_table = merged_df[['corp_name', 'sector']].copy()
        final_table.drop_duplicates(subset=['corp_name'], keep='first', inplace=True)
        
        # 4. conSQL을 경유하여 DB에 저장 (초기화 중 무한루프 방지를 위해 init_sectors=False 전달)
        db = conSQL.FS(init_sectors=False)
        success = db.insert_sector_map(final_table)
        db.close()
        
        if success:
            print(f"✅ 총 {len(final_table)}개 상장/비상장 회사의 계층 정보가 FS.db에 성공적으로 적재되었습니다!")
        else:
            print("❌ DB 저장 실패.")
            
    except Exception as e:
        print(f"Sector 마스터 테이블 초기화 중 에러 발생: {e}")

# ==============================================
# 모든 비즈니스 로직은 철저하게 conSQL에 전적으로 의존합니다.
# ==============================================

def get_sector(corp: str) -> str:
    """
    conSQL을 경유하여 DB(FS.db)에 기록된 회사의 섹터를 반환합니다.
    """
    db = conSQL.FS()
    sec = db.get_sector(corp)
    db.close()
    return sec

def get_corps_in_sector(sector: str) -> list:
    """
    conSQL을 경유하여 DB(FS.db)에 기록된 특정 섹터 하위의 모든 회사 이름 목록을 리스트로 반환합니다.
    """
    db = conSQL.FS()
    corps = db.get_corps_by_sector(sector)
    db.close()
    return corps

if __name__ == "__main__":
    # 처음 구축하거나 정보를 갱신할 때만 이 스크립트를 직접 실행(run)합니다.
    _load_sectors()
    
    print("\n--- DB 연동 테스트 ---")
    print("삼성전자 섹터:", get_sector("삼성전자"))
    print("비상장회사(예: 알수없는회사) 섹터:", get_sector("알수없는회사"))
    
    sample_sector = "통신 및 방송 장비 제조업"
    corps = get_corps_in_sector(sample_sector)
    print(f"\n[{sample_sector}] 에 포함된 회사들 (일부 5개 표기):")
    print(corps[:5] if len(corps) > 5 else corps)
