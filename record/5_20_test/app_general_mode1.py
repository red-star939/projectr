import streamlit as st
import sys
from pathlib import Path

# [1] 전역 페이지 설정 (Streamlit 규격에 따라 항상 최상단 배치)
st.set_page_config(
    page_title="General Intelligence Terminal",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# [2] Pathlib 기반 상대 경로 연산 및 탐색 우선순위 지정 (ModuleNotFoundError 방지)
BASE_DIR = Path(__file__).resolve().parent

PATH_EXTENSIONS = [
    BASE_DIR / "src" / "general",          # 일반 사용자용 에이전트 패키지 경로
    BASE_DIR / "src" / "news_agent",       # BatExaoneReporter 의존성 경로
    BASE_DIR / "src" / "financial_agent"   # ui_search 및 conSQL 의존성 경로
]

for path_dir in PATH_EXTENSIONS:
    if str(path_dir) not in sys.path:
        # insert(0) 기법을 적용하여 로컬 패키지를 venv 라이브러리보다 최우선 순위로 지정
        sys.path.insert(0, str(path_dir))

# [3] 상대 경로 설정 확인 후 백엔드 공용 엔진 및 고속 에이전트 모듈 임포트
from news_sum4_3 import BatExaoneReporter
from src.financial_agent import ui_search
from general_news_agent import GeneralFastNewsAgent
from general_financial_agent import GeneralFastFinancialAgent

def main():
    st.title("General Intelligence Terminal")
    st.markdown("정량적 지표 분석과 정성적 뉴스 자가 어텐션 파이프라인을 일체화한 고성능 통합 패널입니다.")
    st.markdown("---")
    
    # 통합 검색창 컴포넌트 매핑
    keyword = ui_search.render_search(
        "분석 키워드 또는 회사명 입력",
        mode='unified',
        key='general_integrated_search',
    )
    
    submit_btn = st.button("통합 인텔리전스 파이프라인 가동", use_container_width=True, disabled=not keyword)
    
    if submit_btn and keyword:
        # 1. 공용 지식화 백엔드 엔진 및 일반용 고속 에이전트 초기화
        reporter = BatExaoneReporter()
        news_agent = GeneralFastNewsAgent()
        finance_agent = GeneralFastFinancialAgent()
        
        # 2. 통합 진행 가드 작동 (단일 st.status 내부에 모든 계산 시퀀스 집중)
        with st.status(f"[{keyword}] 통합 자산 데이터 정제 및 수치 연산 집행 중...", expanded=True) as status:
            
            # 흐린 글자(st.caption) 출력을 위한 통일된 인라인 로거 바인딩
            def streamlit_logger(message: str):
                st.caption(message)
            
            # [시퀀스 A] 금융 지표 분석 에이전트 구동 (SQL 캐시 고속 탐색)
            df, finance_md, corr_summary = finance_agent.fetch_financial_indicators_optimized(
                corp_name=keyword, 
                reporter=reporter, 
                status_callback=streamlit_logger
            )
            
            # [시퀀스 B] 초고속 뉴스 에이전트 구동 (메모리 자가 어텐션 풀링 행렬 계산)
            snippets = news_agent.fetch_news_snippets_optimized(
                keyword=keyword, 
                reporter=reporter, 
                status_callback=streamlit_logger
            )
            
            # 파이프라인 정합성 최종 검증 및 결론 도출
            if snippets or (df is not None and not df.empty):
                status.update(label="통합 자가 어텐션 및 금융 지표 수치 정제 완료", state="complete", expanded=False)
            else:
                status.update(label="데이터 확보 실패", state="error")
                st.warning("선택한 키워드에 대해 처리 가능한 유효 데이터가 존재하지 않습니다.")
                st.stop()
                
        # 3. 탭(Tabs) 인터페이스 분할 배치를 통한 UI 컨텍스트 격리
        tab_news, tab_finance = st.tabs(["📊 뉴스 트렌드 인텔리전스", "📈 정량적 재무 지표"])
        
        # [Tab 1: 뉴스 에이전트 출력 영역]
        with tab_news:
            if snippets:
                st.subheader("자가 어텐션 풀링 인덱스 원천 기사 목록")
                # 기사 링크 옆 날짜 표기 소거 규격 준수
                for idx, snip in enumerate(snippets, 1):
                    st.markdown(f"{idx}. [{snip['title']}]({snip['link']})")
                
                st.divider()
                st.subheader("실시간 시장 트렌드 통합 분석 리포트")
                news_placeholder = st.empty()
                
                sys_msg_ns = (
                    f"당신은 보편적 사용자를 위한 뉴스 분석가입니다. 제시된 {keyword} 관련 정제 뉴스 목록을 기반으로 "
                    "주요 시장 트렌드와 시사점을 일반 사용자가 이해하기 쉽도록 명확하게 작성하십시오. 원천 데이터에 없는 사실은 추정하지 마십시오."
                )
                
                context_lines = [f"[{i}] {s['title']} ({s['date']})" for i, s in enumerate(snippets, 1)]
                raw_context_ns = "\n".join(context_lines)
                
                full_report_ns = ""
                # 본문 화면 폭을 백분 활용한 고속 토큰 스트리밍 출력
                for chunk in reporter._generate(sys_msg_ns, raw_context_ns, stream=True):
                    full_report_ns += chunk['choices'][0]['text']
                    news_placeholder.markdown(full_report_ns + "▌")
                news_placeholder.markdown(full_report_ns)
                
                # 뉴스 백엔드 영구 지식화 기입
                reporter._save_to_db(f"GENERAL_{keyword}", full_report_ns)
                from datetime import datetime
                today_str = datetime.now().strftime("%Y-%m-%d")
                reporter._save_to_md(f"GENERAL_{keyword}", full_report_ns, today_str)
            else:
                st.info("표출 가능한 실시간 뉴스 정보가 없습니다.")
                
        # [Tab 2: 금융 지표 에이전트 출력 영역]
        with tab_finance:
            if df is not None and finance_md:
                st.subheader(f"{keyword} 핵심 투자 지표 분석 보고서")
                
                # 통계 상관관계 요약 지표 가시화 파트 추가 (Metric 컴포넌트 활용)
                if corr_summary and corr_summary["bench_val"] is not None:
                    col_m1, col_m2 = st.columns(2)
                    with col_m1:
                        st.metric(label="KOSPI 주가 상관계수 (5Y)", value=f"{corr_summary['bench_val']:.4f}")
                    with col_m2:
                        if corr_summary["competitors"]:
                            top_comp, top_val = corr_summary["competitors"][0]
                            st.metric(label=f"최대 경쟁사 동조화 ({top_comp})", value=f"{top_val:.4f}")
                    st.divider()
                
                # 7대 재무 카테고리 마크다운 문서 자동 인출
                st.markdown(finance_md)
            else:
                st.info("사전 적재된 재무 지표 데이터프레임 구조가 발견되지 않았습니다. 백엔드 배치를 점검하십시오.")
                
        # 최종 백엔드 처리 완료 피드백 알림
        st.toast(f"지식 베이스(NS_DB) 및 마크다운 리포트 영구 저장 완료", icon="💾")

if __name__ == "__main__":
    main()