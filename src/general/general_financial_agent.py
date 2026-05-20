import streamlit as st
import sys
import os
import time
import pandas as pd
from pathlib import Path

# [1] 에이전트 자체 상대 경로 연산 세팅 (OS 독립형 최상위 바인딩)
AGENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AGENT_DIR.parent.parent

REL_PATHS = [
    PROJECT_ROOT,
    PROJECT_ROOT / "src" / "news_agent",
    PROJECT_ROOT / "src" / "financial_agent"
]

for p_dir in REL_PATHS:
    if str(p_dir) not in sys.path:
        sys.path.insert(0, str(p_dir))

# 금융 에이전트 코어 모듈 명시적 인출
from src.financial_agent import conSQL, utils_, Sector, Extract_corr, fs_report_test

class GeneralFastFinancialAgent:
    def __init__(self):
        pass

    def fetch_financial_indicators_optimized(self, corp_name: str, reporter=None, status_callback=None) -> tuple:
        """
        DART 실시간 수집을 배제하고 이미 캐싱된 SQL DB 구조를 고속 탐색하여
        수치 계산 시퀀스를 실시간 로그로 전송하는 일반 사용자용 지표 분석 엔진.
        """
        def log(msg: str):
            if status_callback:
                status_callback(msg)
                time.sleep(0.4) # 수치적 계산 연산 과정 시각화를 위한 고정 타임 슬롯

        log("System: 로컬 금융 데이터베이스(FS.db) 커넥션을 수립합니다.")
        db = conSQL.FS(init_sectors=False)
        
        # 1. 테이블 캐시 존재 여부 검증 (실시간 OpenDART API 통신 원천 차단)
        if not db.has_table(corp_name):
            log(f"System: [{corp_name}] 캐싱된 정량 재무 데이터가 SQL 마스터 테이블에 존재하지 않습니다.")
            db.close()
            return None, None, "사전 적재된 데이터가 없습니다."

        log(f"System: [{corp_name}] 마스터 테이블 인덱스 매핑을 확인했습니다. 고속 쿼리를 집행합니다.")
        
        # 2. 정량 데이터셋 인출 및 데이터 차원 로깅
        df = db.search_sql(corp_name)
        db.close()
        
        if df is None or df.empty:
            log("System: 데이터베이스 쿼리 결과 반환된 레코드가 결손되었습니다.")
            return None, None, "레코드 결손"
            
        n_rows, n_cols = df.shape
        log(f"Financial Layer: 데이터 인출 완료. 추출된 DataFrame Matrix 차원: {n_rows} x {n_cols}")

        # 3. 주가 상관관계 통계 행렬 수치 분석 및 로깅
        log("Financial Layer: 주가 시계열 및 동종 섹터 경쟁사 상관계수 행렬(Correlation Matrix) 스캔을 시작합니다.")
        benchmark_label = "KOSPI"
        benchmark_account_nm = "KOSPI"
        corr_summary = {"bench_val": None, "competitors": []}

        if "source" in df.columns:
            corr_data = df[df["source"] == "CORRELATION"].copy()
            if not corr_data.empty:
                corr_data["amount"] = pd.to_numeric(corr_data["amount"], errors="coerce")
                corr_data = corr_data.dropna(subset=["amount"]).sort_values(by="amount", ascending=False)
                
                # 벤치마크 수치 인출
                bench_df = corr_data[corr_data["account_nm"] == benchmark_account_nm]
                if not bench_df.empty:
                    corr_summary["bench_val"] = float(bench_df["amount"].values[0])
                    log(f"   ↳ [Correlation Engine] {benchmark_label} 대비 피어슨 상관계수 산출 완료 -> Score: {corr_summary['bench_val']:.4f}")
                
                # 경쟁사 상위 스코어 인출 명세
                sector_df = corr_data[corr_data["account_nm"] != benchmark_account_nm]
                for idx, row in enumerate(sector_df.itertuples()):
                    if idx < 2: # 상위 2개 경쟁사만 수치 명세 로그에 적재
                        corr_summary["competitors"].append((row.account_nm, float(row.amount)))
                        log(f"   ↳ [Correlation Engine] 경쟁사 경쟁사 연관도 산출 완료 -> {row.account_nm}: {float(row.amount):.4f}")

        # 4. 7대 지표 카테고리 구조 결합 및 템플릿 컴팩션 명세
        log("Financial Layer: 7대 금융 공학 지표 컴포넌트(VAL, PROF, GROWTH, STAB, CF, DIV, MKT) 바인딩을 집행합니다.")
        sector_nm = Sector.get_sector(corp_name)
        c_code = utils_.call_corp_code(corp_name)
        s_code = utils_.call_stock_code(corp_name)
        
        # fs_report_test 표준 템플릿 엔진 연동을 통한 마크다운 합성
        report_md = fs_report_test.create_markdown_template(
            corp=corp_name, sector=sector_nm, corp_code=c_code, stock_code=s_code, df=df
        )
        
        # 카테고리 필터링 정합성 내부 계측 및 출력
        for cat in fs_report_test._FSDIV_ORDER:
            cat_df = df[df['fs_div'] == cat] if 'fs_div' in df.columns else pd.DataFrame()
            log(f"   ↳ [Template Builder] 카테고리 [{fs_report_test._FSDIV_TITLE.get(cat)}] 바인딩 상태 -> 가용 데이터 수: {len(cat_df)}개")

        log("System: 데이터베이스 지표 분석 시퀀스 및 리포트 빌더 구조 합성을 정상 종료합니다.")
        return df, report_md, corr_summary

def main():
    # 단독 모듈 가동 테스트 시의 가시성 락 세팅 (사이드바 제어 배제)
    st.title("Financial Analyst - General Stub Panel")
    st.info("본 모듈은 일반 사용자용 통합 환경 내에서 탭 형식으로 호출되어 기동하는 본문 전용 엔진입니다.")

if __name__ == "__main__":
    main()