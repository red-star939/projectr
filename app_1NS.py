import streamlit as st
import sys
from pathlib import Path
from datetime import datetime

# standalone 실행 호환 — project root + src/news_agent 를 sys.path 에
_ROOT = Path(__file__).resolve().parent
for _p in (str(_ROOT), str(_ROOT / "src" / "news_agent")):
    if _p not in sys.path:
        sys.path.append(_p)

from news_fast_stream import BatFastStreamer
from news_sum4_3 import BatExaoneReporter
from src.financial_agent import ui_search

def main():
    st.title("📊 Pipeline News Intelligence")

    # type-ahead 자동완성: 회사명 + 키워드(섹터) 통합
    keyword = ui_search.render_search(
        "분석 키워드 또는 회사명",
        mode='unified',
        key='ns_search',
    )
    submit = st.button("뉴스 분석", use_container_width=True, disabled=not keyword)

    if submit and keyword:
        # [단계 1] 엔진 로드 및 스트리머 초기화
        reporter = BatExaoneReporter()
        streamer = BatFastStreamer()

        # 데이터 수집 및 1차 처리 가시화 (상태 박스 내부)
        with st.status(f"[{keyword}] 데이터 수집 및 분석 준비 중...", expanded=True) as status:
            st.write("📡 뉴스 수집 및 실시간 요약(Map Phase) 가동...")
            results = streamer.run(keyword, reporter)
            
            if not results or not results['documents']:
                status.update(label="❌ 데이터 확보 실패", state="error")
                st.stop()
            
            st.write("최종 전략 분석 리포트 생성 준비 완료")
            status.update(label="✅ 데이터 수집 및 1차 요약 완료", state="complete", expanded=False)

        # [단계 2] 리포트 합성 및 실시간 생성 처리 (상태 박스 외부로 분리)
        combined_summaries = "\n\n".join(results['documents'])
        
        st.divider()
        st.subheader(f"📊 {keyword} 뉴스 인텔리전스 분석")
        report_placeholder = st.empty()
        
        full_report = ""
        sys_msg = "제공된 요약본들을 바탕으로 시장의 흐름과 시사점을 도출하십시오."
        
        # 메인 화면 영역에서 실시간 스트리밍 출력 수행
        for chunk in reporter._generate(sys_msg, combined_summaries, stream=True):
            full_report += chunk['choices'][0]['text']
            report_placeholder.markdown(full_report + "▌")
        report_placeholder.markdown(full_report)
        
        # [단계 3] 영구 저장 및 최종 결과 보고 (상태 박스 외부)
        reporter._save_to_db(keyword, full_report)
        today_str = datetime.now().strftime("%Y-%m-%d")
        try:
            md_path = reporter._save_to_md(keyword, full_report, today_str)
            st.toast(f"📄 보고서 저장: {md_path}", icon="📄")
            st.success("✅ 분석 완료 및 NS_DB·Markdown 저장 성공")
        except Exception as e:
            st.warning(f"⚠️ Markdown 저장 실패 (NS_DB 는 정상 저장됨): {e}")

if __name__ == "__main__":
    main()