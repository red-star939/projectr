import streamlit as st
import sys
from pathlib import Path

# [1] 전역 페이지 설정
if "app_main" not in sys.modules:
    st.set_page_config(
        page_title="General Intelligence Terminal",
        layout="wide",
        initial_sidebar_state="collapsed"
    )

# [2] 경로 설정 및 모듈 탐색 우선순위 지정
BASE_DIR = Path(__file__).resolve().parent
PATH_EXTENSIONS = [
    BASE_DIR / "src" / "general",
    BASE_DIR / "src" / "news_agent",
    BASE_DIR / "src" / "financial_agent",
    BASE_DIR / "src" / "portfolio_agent"
]

for path_dir in PATH_EXTENSIONS:
    if str(path_dir) not in sys.path:
        sys.path.insert(0, str(path_dir))

# [3] 에이전트 및 엔진 임포트
from news_sum4_3 import BatExaoneReporter
from src.financial_agent import ui_search
from general_news_agent import GeneralFastNewsAgent
from general_financial_agent import GeneralFastFinancialAgent
from general_portfolio_agent import GeneralFastPortfolioAgent

def main():
    st.title("General User Terminal")
    st.markdown("일반 사용자를 위한 지능형 자산 분석 및 포트폴리오 생성 패널입니다.")
    st.markdown("---")
    
    # 통합 검색창
    keyword = ui_search.render_search(
        "분석 키워드 또는 회사명 입력",
        mode='unified',
        key='general_integrated_search',
    )
    
    submit_btn = st.button("최종 인텔리전스 분석", use_container_width=True, disabled=not keyword)
    
    if submit_btn and keyword:
        # 1. 에이전트 초기화
        reporter = BatExaoneReporter()
        news_agent = GeneralFastNewsAgent()
        finance_agent = GeneralFastFinancialAgent()
        portfolio_agent = GeneralFastPortfolioAgent()
        
        # 2. 데이터 정제 시퀀스 (st.status)
        with st.status(f"[{keyword}] 통합 자산 데이터 정제 및 수치 연산 집행 중...", expanded=True) as status:
            
            def streamlit_logger(message: str):
                st.caption(message)
            
            # [시퀀스 A] 금융 지표 인출
            df, finance_md, corr_summary = finance_agent.fetch_financial_indicators_optimized(
                corp_name=keyword, 
                reporter=reporter, 
                status_callback=streamlit_logger
            )
            
            # [시퀀스 B] 뉴스 스니펫 인출
            snippets = news_agent.fetch_news_snippets_optimized(
                keyword=keyword, 
                reporter=reporter, 
                status_callback=streamlit_logger
            )
            
            # [시퀀스 C] 포트폴리오 컨텍스트 준비
            portfolio_context = portfolio_agent.render_portfolio_pipeline(
                keyword=keyword,
                reporter=reporter,
                status_callback=streamlit_logger
            )
            
            if snippets or (df is not None and not df.empty):
                status.update(label="데이터 인출 및 파이프라인 준비 완료", state="complete", expanded=False)
            else:
                status.update(label="데이터 확보 실패", state="error")
                st.stop()
                
        # 3. 탭 인터페이스 (포트폴리오 생성 탭을 첫 번째로 배치)
        tab_portfolio, tab_news, tab_finance = st.tabs([
            "💼 포트폴리오 생성", 
            "📊 뉴스 분석", 
            "📈 지표 분석"
        ])
        
        # [중요: 실행 순서 제어]
        # 사용자가 첫 번째 탭(포트폴리오)을 보고 있더라도, 
        # 내부적으로 뉴스 분석과 지표 분석이 먼저 실행되어 DB를 업데이트해야 합니다.

        # --- [실행 1] 뉴스 분석 (Tab 2) ---
        with tab_news:
            if snippets:
                st.subheader("뉴스 목록")
                for idx, snip in enumerate(snippets, 1):
                    st.markdown(f"{idx}. [{snip['title']}]({snip['link']})")
                
                st.divider()
                st.subheader("실시간 시장 트렌드 통합 분석 리포트")
                news_placeholder = st.empty()
                
                sys_msg_ns = f"당신은 보편적 사용자를 위한 뉴스 분석가입니다. {keyword} 관련 주요 시장 트렌드를 쉽게 설명하세요."
                context_lines = [f"[{i}] {s['title']} ({s['date']})" for i, s in enumerate(snippets, 1)]
                raw_context_ns = "\n".join(context_lines)
                
                full_report_ns = ""
                for chunk in reporter._generate(sys_msg_ns, raw_context_ns, stream=True):
                    full_report_ns += chunk['choices'][0]['text']
                    news_placeholder.markdown(full_report_ns + "▌")
                news_placeholder.markdown(full_report_ns)
                
                # 분석 결과를 DB에 저장 (포트폴리오 에이전트가 이를 참조함)
                reporter._save_to_db(f"GENERAL_{keyword}", full_report_ns)
            else:
                st.info("뉴스 정보가 없습니다.")

        # --- [실행 2] 지표 분석 (Tab 3) ---
        with tab_finance:
            if df is not None and finance_md:
                st.subheader(f"{keyword} 핵심 투자 지표")
                if corr_summary and corr_summary["bench_val"] is not None:
                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        st.metric(label="KOSPI 상관계수", value=f"{corr_summary['bench_val']:.4f}")
                    with col_m2:
                        if corr_summary["competitors"]:
                            top_comp, top_val = corr_summary["competitors"][0]
                            st.metric(label=f"경쟁사 동조화({top_comp})", value=f"{top_val:.4f}")
                st.markdown(finance_md)
            else:
                st.info("재무 데이터가 없습니다.")

        # --- [실행 3] 포트폴리오 생성 (Tab 1) ---
        with tab_portfolio:
            # 앞선 분석들이 완료된 후 최종 전략 생성
            portfolio_agent.display_portfolio_interface(
                keyword=keyword,
                context=portfolio_context,
                reporter=reporter
            )
                
        st.toast(f"통합 인텔리전스 분석 완료", icon="💾")

if __name__ == "__main__":
    main()