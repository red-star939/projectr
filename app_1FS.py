import streamlit as st
import pandas as pd
import sys
import os
from pathlib import Path
from datetime import datetime # [확인] NameError 방지를 위한 명시적 임포트

# [단계 1] 경로 및 모듈 설정
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# 핵심 금융 모듈 로드
from src.financial_agent import utils_, conSQL, FS_to_SQL, yfinance_api, Sector, Extract_corr, fs_report_test, chroma_manager

# [단계 2] 통합 대시보드 호환성 설정
if "app_main" not in sys.modules:
    st.set_page_config(page_title="Financial Analyst", page_icon="📊", layout="wide")

def main():
    st.title("🔍 기업 가치 분석 및 지식화")
    
    # 사이드바에서 기업 선택 (통합 앱 환경 고려)
    all_corps = list(utils_.corp_code.keys())
    target_corp = st.sidebar.selectbox(
        "분석 대상 기업", 
        all_corps, 
        index=all_corps.index("삼성전자") if "삼성전자" in all_corps else 0,
        key="fs_target_select"
    )
    
    analyze_btn = st.sidebar.button("정밀 분석 및 DB 저장 시작", use_container_width=True)

    if analyze_btn:
        with st.status(f"[{target_corp}] 지능형 데이터 처리 중...", expanded=True) as status:
            # 1. 원천 데이터 수집
            st.write("DART 공시 및 yfinance 데이터 동기화...")
            FS_to_SQL.ensure_company_data(target_corp)
            yfinance_api.fetch_and_save_yfinance_info([target_corp])
            
            # 2. 데이터 분석 및 리포트 생성
            db = conSQL.FS()
            df = db.search_sql(target_corp)
            sector_nm = Sector.get_sector(target_corp)
            c_code = utils_.call_corp_code(target_corp)
            s_code = utils_.call_stock_code(target_corp)
            
            report_md = fs_report_test.create_markdown_template(
                corp=target_corp, sector=sector_nm, corp_code=c_code, stock_code=s_code, df=df
            )
            
            # 3. [핵심] ChromaDB 저장 (이미 로드된 임베딩 모델 사용)
            st.write("지식 베이스(FS_DB) 인덱싱 중...")
            save_success = chroma_manager.save_report_to_db(
                corp=target_corp, content=report_md, sector=sector_nm, stock_code=s_code
            )
            
            status.update(label=f"✅ {target_corp} 분석 및 지식화 완료", state="complete", expanded=False)

        # 결과 시각화 섹션 (기존 로직 유지)
        if df is not None and not df.empty:
            st.markdown(report_md)
            if save_success:
                st.toast(f"💾 {target_corp} 지식 베이스 최신화 완료")
        else:
            st.error("데이터 로드에 실패했습니다.")

# 통합 실행 대응
if __name__ == "__main__":
    main()