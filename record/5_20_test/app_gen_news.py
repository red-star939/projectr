import streamlit as st
import sys
from pathlib import Path

# [1] 전역 페이지 설정
st.set_page_config(
    page_title="General Speed News Terminal",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# [2] Pathlib 기반 상대 경로 연산 및 탐색 우선순위 지정
BASE_DIR = Path(__file__).resolve().parent

PATH_EXTENSIONS = [
    BASE_DIR / "src" / "general",
    BASE_DIR / "src" / "news_agent",
    BASE_DIR / "src" / "financial_agent"
]

for path_dir in PATH_EXTENSIONS:
    if str(path_dir) not in sys.path:
        sys.path.insert(0, str(path_dir))

# [3] 상대 경로 유효성 확보 후 모듈 임포트
from news_sum4_3 import BatExaoneReporter
from src.financial_agent import ui_search
from general_news_agent import GeneralFastNewsAgent

def main():
    st.title("General Speed News Terminal")
    st.markdown("자가 어텐션 연산 시퀀스의 수치적 계산 과정이 실시간으로 동적 로깅되는 시스템입니다.")
    st.markdown("---")
    
    # 통합 검색창 컴포넌트 매핑
    keyword = ui_search.render_search(
        "분석 키워드 또는 회사명 입력",
        mode='unified',
        key='general_speed_ns_search',
    )
    
    submit_btn = st.button("트렌드 인텔리전스 가동", use_container_width=True, disabled=not keyword)
    
    if submit_btn and keyword:
        reporter = BatExaoneReporter()
        agent = GeneralFastNewsAgent()
        
        # 상태 표시 박스 가동
        with st.status(f"[{keyword}] 메모리 내 뉴스 인덱스 최적화 가동 중...", expanded=True) as status:
            # [핵심 수정] 백엔드에서 전달되는 정밀 계산 로그를 흐린 글자(st.caption)로 출력
            def streamlit_logger(message: str):
                st.caption(message)
                
            snippets = agent.fetch_news_snippets_optimized(keyword, reporter=reporter, status_callback=streamlit_logger)
            
            if snippets:
                st.write(f"최종 연산 결과: {len(snippets)}개의 고밀도 압축 뉴스가 모델 컨텍스트 버퍼에 주입됩니다.")
                for idx, snip in enumerate(snippets, 1):
                    st.markdown(f"{idx}. [{snip['title']}]({snip['link']})")
                
                status.update(label="자가 어텐션 풀링 기반 데이터 정제 완료", state="complete", expanded=True)
            else:
                status.update(label="데이터 확보 실패", state="error")
                st.warning("최근 24시간 내에 수집된 유효 뉴스 데이터가 존재하지 않습니다.")
                st.stop()
            
        # 3. 데이터 컨텍스트 구조화
        context_lines = [f"[{idx}] {s['title']} ({s['date']})" for idx, s in enumerate(snippets, 1)]
        raw_context = "\n".join(context_lines)
        
        st.divider()
        st.subheader(f"{keyword} 실시간 시장 트렌드 리포트")
        report_placeholder = st.empty()
        
        sys_msg = (
            f"당신은 보편적 사용자를 위한 뉴스 분석가입니다. 제시된 {keyword} 관련 정제 뉴스 목록을 기반으로 "
            "주요 시장 트렌드와 시사점을 일반 사용자가 이해하기 쉽도록 명확하게 작성하십시오. 원천 데이터에 없는 사실은 추정하지 마십시오."
        )
        
        full_report = ""
        for chunk in reporter._generate(sys_msg, raw_context, stream=True):
            full_report += chunk['choices'][0]['text']
            report_placeholder.markdown(full_report + "▌")
        report_placeholder.markdown(full_report)
        
        # 4. 백엔드 영구 지식화 처리 파이프라인
        reporter._save_to_db(f"GENERAL_{keyword}", full_report)
        from datetime import datetime
        today_str = datetime.now().strftime("%Y-%m-%d")
        try:
            md_path = reporter._save_to_md(f"GENERAL_{keyword}", full_report, today_str)
            st.toast(f"보고서 내보내기 완료: {Path(md_path).name}")
            st.success("일반 사용자용 지식 베이스(NS_DB) 및 마크다운 문서 빌드가 완료되었습니다.")
        except Exception as e:
            st.warning(f"Markdown 저장 실패 (NS_DB 영구 인덱싱은 안전하게 완료됨): {e}")

if __name__ == "__main__":
    main()