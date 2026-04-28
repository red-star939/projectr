import streamlit as st
import sys
import os
from pathlib import Path

# [상대 경로 설정] 프로젝트 루트 확보
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "src" / "portfolio_agent"))
sys.path.append(str(BASE_DIR / "src" / "news_agent"))

from portfolio_manager import BatPortfolioAgent
from news_sum4_3 import BatExaoneReporter # 최신 요약 엔진 로더 활용

def main():
    st.title("💼 Portfolio Central Terminal")
    st.info("재무(FS_DB) 및 뉴스 지능(NS_DB) 통합 분석 엔진")
    st.markdown("---")
    
    # 1. EXAONE 모델 로딩 섹션
    if 'reporter' not in st.session_state:
        if st.button("투자 분석 지능(EXAONE) 가동", use_container_width=True):
            with st.spinner("VRAM에 통합 분석 모델 로딩 중..."):
                st.session_state.reporter = BatExaoneReporter()
                st.success("분석 준비 완료.")

    # 2. 분석 실행 섹션
    if 'reporter' in st.session_state:
        target_corp = st.text_input("전략 수립 대상 기업명", value="삼성전자", key="port_target")
        
        if st.button("통합 전략 생성 및 마크다운 저장", use_container_width=True):
            agent = BatPortfolioAgent()
            
            # [단계 1] 분산된 지식 데이터 인출 가시화
            with st.status("지능형 데이터베이스(NS/FS) 탐색 중...", expanded=True) as status:
                st.write("🔍 분석된 지식 리포트 추출 중...")
                ctx = agent.get_company_context(target_corp)
                
                # DB 연동 상태 보고
                ns_icon = "✅" if ctx['status']['ns'] else "❌"
                fs_icon = "✅" if ctx['status']['fs'] else "❌"
                
                st.write(f"{ns_icon} 뉴스 요약 지능(NS_DB) 데이터 확보")
                st.write(f"{fs_icon} 재무 가치 지능(FS_DB) 데이터 확보")
                
                if not ctx['status']['ns'] or not ctx['status']['fs']:
                    st.warning("⚠️ 일부 데이터가 부족하여 분석 정밀도가 떨어질 수 있습니다.")
                
                status.update(label="지식 데이터 통합 완료", state="complete", expanded=False)
            
            # [단계 2] 실시간 통합 전략 리포트 출력
            st.divider()
            st.subheader(f"📊 {target_corp} 최종 통합 투자 전략")
            
            report_placeholder = st.empty()
            full_res = ""
            
            # EXAONE 연산 및 스트리밍 (NS/FS 데이터 교차 분석)
            for chunk in agent.generate_strategy(target_corp, ctx, st.session_state.reporter):
                full_res += chunk['choices'][0]['text']
                report_placeholder.markdown(full_res + "▌")
            
            report_placeholder.markdown(full_res)
            
            # [단계 3] 영구 문서화 및 보고
            file_path = agent.save_portfolio_report(target_corp, full_res)
            st.success(f"💾 최종 전략 보고서가 저장되었습니다: {os.path.basename(file_path)}")
            st.toast(f"✅ {target_corp} 포트폴리오 수립 완료")

if __name__ == "__main__":
    if "app_main" not in sys.modules:
        st.set_page_config(page_title="Portfolio Agent", layout="wide")
        main()