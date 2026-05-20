import streamlit as st
import sys
from pathlib import Path

# [1] 전역 페이지 설정 (Streamlit 규격 상 최상단 위치 필수)
st.set_page_config(
    page_title="General Speed News Terminal",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# [2] Pathlib 기반 상대 경로 연산 및 탐색 우선순위 지정 (OS 독립형 바인딩)
BASE_DIR = Path(__file__).resolve().parent

# 하위 패키지 상대 경로 매핑 명세
PATH_EXTENSIONS = [
    BASE_DIR / "src" / "general",          # general_news_agent.py 위치 명시적 추가
    BASE_DIR / "src" / "news_agent",       # BatExaoneReporter 위치
    BASE_DIR / "src" / "financial_agent"   # ui_search 위치
]

for path_dir in PATH_EXTENSIONS:
    if str(path_dir) not in sys.path:
        # insert(0) 기법을 적용하여 가상환경 venv 패키지보다 최우선 탐색하도록 제어
        sys.path.insert(0, str(path_dir))

# [3] 상대 경로 설정 완료 후 안전하게 핵심 의존성 모듈 임포트
from news_sum4_3 import BatExaoneReporter
from src.financial_agent import ui_search
from general_news_agent import GeneralFastNewsAgent  # 상대 경로를 통해 무결하게 인출 완료

def main():
    st.title("👤 General Speed News Terminal")
    st.markdown("백엔드 수치 자가 어텐션 연산 시퀀스가 실시간 시각화 처리되는 관리자 연동형 패널입니다.")
    st.markdown("---")
    
    # 통합 검색창 컴포넌트 매핑
    keyword = ui_search.render_search(
        "분석 키워드 또는 회사명 입력",
        mode='unified',
        key='general_speed_ns_search',
    )
    
    submit_btn = st.button("초고속 트렌드 인텔리전스 가동", use_container_width=True, disabled=not keyword)
    
    if submit_btn and keyword:
        reporter = BatExaoneReporter()
        agent = GeneralFastNewsAgent()
        
        # 상태 표시 박스 가동
        with st.status(f"[{keyword}] 메모리 내 뉴스 인덱스 최적화 알고리즘 가동 중...", expanded=True) as status:
            def streamlit_logger(message: str):
                st.write(message)
                
            snippets = agent.fetch_news_snippets_optimized(keyword, reporter=reporter, status_callback=streamlit_logger)
            
            if snippets:
                st.write(f"📊 **최종 연산 결과:** 아래의 {len(snippets)}개 고밀도 압축 뉴스가 모델 컨텍스트 버퍼에 직렬 주입됩니다:")
                # 하이퍼링크 옆 날짜 표기 소거 규격 엄격 준수
                for idx, snip in enumerate(snippets, 1):
                    st.markdown(f"{idx}. [{snip['title']}]({snip['link']})")
                
                status.update(label="자가 어텐션 풀링 기반 데이터 최적화 알고리즘 완전 정제 성공", state="complete", expanded=True)
            else:
                status.update(label="❌ 데이터 확보 실패", state="error")
                st.warning("최근 24시간 내에 수집된 유효 뉴스 팩트 데이터가 존재하지 않습니다.")
                st.stop()
            
        # 3. 데이터 컨텍스트 구조화
        context_lines = [f"[{idx}] {s['title']} ({s['date']})" for idx, s in enumerate(snippets, 1)]
        raw_context = "\n".join(context_lines)
        
        st.divider()
        st.subheader(f"📊 {keyword} 실시간 시장 트렌드 리포트")
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
            st.toast(f"📄 보고서 내보내기 완료: {Path(md_path).name}", icon="📄")
            st.success("💾 일반 사용자용 지식 베이스(NS_DB) 및 마크다운 문서 빌드가 완료되었습니다.")
        except Exception as e:
            st.warning(f"⚠️ 마크다운 파일 저장 실패 (NS_DB 영구 인덱싱은 안전하게 완료됨): {e}")

if __name__ == "__main__":
    main()