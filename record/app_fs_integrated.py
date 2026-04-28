import streamlit as st
import pandas as pd
import sys
import os
from pathlib import Path
from datetime import datetime

# [단계 1] 경로 설정 - 모듈 임포트 호환성 유지
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# 핵심 모듈 임포트
from src.financial_agent import utils_, conSQL, FS_to_SQL, yfinance_api, Sector, Extract_corr, fs_report_test, chroma_manager

def main():
    """
    통합 앱에서 호출되는 Financial Analyst 메인 진입점입니다.
    기존의 st.set_page_config는 호출하지 않습니다.
    """
    # 사이드바 구성
    with st.sidebar:
        st.divider()
        st.subheader("📊 Financial Analyst")
        st.info("DART 및 시장 데이터 통합 분석 시스템")
        
        all_corps = list(utils_.corp_code.keys())
        # 세션 상태 유지를 위해 고유 key('fs_corp_select') 부여
        target_corp = st.selectbox(
            "분석할 기업을 선택하세요", 
            all_corps, 
            index=all_corps.index("삼성전자") if "삼성전자" in all_corps else 0,
            key="fs_corp_select"
        )
        
        # 통합 앱 환경에 맞춰 use_container_width 적용
        analyze_btn = st.button("정밀 분석 시작", use_container_width=True)

    # 메인 화면
    st.title(f"🔍 {target_corp} 기업 가치 분석 리포트")

    if analyze_btn:
        # 상태 표시기 (Bat-Computer 연산 루틴)
        with st.status(f"{target_corp} 데이터 분석 및 지식화 진행 중...", expanded=True) as status:
            st.write("1. DART 공시 데이터 확인 및 자동 수집 중...")
            FS_to_SQL.ensure_company_data(target_corp)
            
            st.write("2. yfinance 시장 실시간 지표 업데이트 중...")
            yfinance_api.fetch_and_save_yfinance_info([target_corp])
            
            # 데이터 로드 및 분석
            db = conSQL.FS()
            df = db.search_sql(target_corp)
            sector_nm = Sector.get_sector(target_corp)
            c_code = utils_.call_corp_code(target_corp)
            s_code = utils_.call_stock_code(target_corp)
            
            st.write("3. 분석 리포트 생성 및 지식 베이스 인덱싱 중...")
            report_md = fs_report_test.create_markdown_template(
                corp=target_corp,
                sector=sector_nm,
                corp_code=c_code,
                stock_code=s_code,
                df=df
            )
            
            # ChromaDB 동기화 (최적화된 임베딩 모델 적용)
            save_success = chroma_manager.save_report_to_db(
                corp=target_corp,
                content=report_md,
                sector=sector_nm,
                stock_code=s_code
            )
            
            status.update(label="전 공정 완료!", state="complete", expanded=False)

        if df is not None and not df.empty:
            # 결과 렌더링
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("📊 주요 재무 지표 (최근)")
                st.dataframe(df.tail(10), use_container_width=True)
                
            with col2:
                st.subheader("📈 섹터 및 시장 상태")
                kospi_val = Extract_corr.get_current_kospi()
                corr = Extract_corr.correlation_with_KOSPI(target_corp, kospi_val)
                st.metric("KOSPI 상관계수", f"{corr if corr else '계산 중'}")
                st.write(f"소속 섹터: **{sector_nm}**")
                st.write(f"종목 코드: **{s_code}**")

            st.divider()
            st.subheader("📝 종합 분석 리포트")
            st.markdown(report_md)
            
            if save_success:
                st.toast(f"✅ {target_corp} 분석 결과가 ChromaDB에 저장되었습니다.", icon="💾")
            
            st.download_button(
                label="💾 리포트 파일(.md) 다운로드",
                data=report_md,
                file_name=f"{target_corp}_Report_{datetime.now().strftime('%Y%m%d')}.md",
                mime="text/markdown",
                use_container_width=True
            )
        else:
            st.error("데이터를 불러오는 데 실패했습니다.")
    else:
        st.info("사이드바에서 기업을 선택하고 '정밀 분석 시작' 버튼을 클릭하십시오.")