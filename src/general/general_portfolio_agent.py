import streamlit as st
from portfolio_manager import BatPortfolioAgent
from news_sum4_3 import BatExaoneReporter

class GeneralFastPortfolioAgent:
    def __init__(self):
        """일반 사용자용 고속 포트폴리오 에이전트 UI 레이어 초기화"""
        self.engine = BatPortfolioAgent()

    def render_portfolio_pipeline(self, keyword: str, reporter: BatExaoneReporter, status_callback):
        """
        메인 파이프라인의 st.status 내부에서 호출되어 
        하이브리드 지식 베이스(NS_DB, FS_DB) 연산을 수행하는 핵심 정제 메소드
        """
        # app_general_mode.py의 인자 전달 규격에 맞춰 'reporter' 파라미터를 시그니처에 명확히 명시합니다.
        status_callback("[*] 포트폴리오 에이전트: 자가 어텐션 기반 하이브리드 지식 교차 검증 인출 중...")
        
        # portfolio_manager.py의 원천 메소드 규격(get_company_context)에 맞추어 인출 집행
        context = self.engine.get_company_context(keyword)
        return context

    def display_portfolio_interface(self, keyword: str, context: dict, reporter: BatExaoneReporter):
        """tab_portfolio 내부에서 호출되어 최종 결과를 스트리밍 렌더링하는 UI 메소드"""
        st.subheader(f"💼 {keyword} 기반 자산 배분 전략 보고서")
        
        # 1. 지식 베이스 동기화 맵 상태 가시화
        db_status = context.get("status", {})
        c_ns, c_fs = st.columns(2)
        with c_ns:
            st.checkbox("뉴스 인텔리전스 동기화 (NS_DB)", value=db_status.get("ns", False), disabled=True)
        with c_fs:
            st.checkbox("정량 재무 데이터 동기화 (FS_DB)", value=db_status.get("fs", False), disabled=True)
        
        st.divider()
        
        # 2. 포트폴리오 최적화 제안서 스트리밍 출력
        portfolio_placeholder = st.empty()
        full_strategy = ""
        
        strategy_stream = self.engine.generate_strategy(
            target_corp=keyword,
            context=context,
            reporter_instance=reporter
        )
        
        for chunk in strategy_stream:
            full_strategy += chunk['choices'][0]['text']
            portfolio_placeholder.markdown(full_strategy + "▌")
        portfolio_placeholder.markdown(full_strategy)
        
        # 3. 마크다운 결과 파일 영구 저장 집행
        file_path = self.engine.save_portfolio_report(keyword, full_strategy)
        st.caption(f"💾 포트폴리오 보고서 저장 완료: {file_path}")