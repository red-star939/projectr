import streamlit as st
from datetime import datetime
from news_fast_stream import BatFastStreamer
from news_sum4_3 import BatExaoneReporter

def main():
    st.title("📊 Pipeline News Intelligence")
    
    with st.form("news_form"):
        keyword = st.text_input("분석 키워드", placeholder="예: 양자 컴퓨팅")
        submit = st.form_submit_button("초고속 파이프라인 가동")

    if submit and keyword:
        # [단계 1] 엔진 로드 및 스트리머 초기화
        reporter = BatExaoneReporter()
        streamer = BatFastStreamer()

        with st.status(f"[{keyword}] 분석 중...", expanded=True) as status:
            st.write("📡 뉴스 수집 및 실시간 요약(Map Phase) 가동...")
            results = streamer.run(keyword, reporter)
            
            if not results or not results['documents']:
                status.update(label="❌ 데이터 확보 실패", state="error")
                st.stop()
            
            # [단계 2] 리포트 합성 (Reduce Phase)
            status.update(label="최종 전략 분석 리포트 생성 중...", state="running")
            combined_summaries = "\n\n".join(results['documents'])
            
            st.divider()
            st.subheader(f"📊 {keyword} 통합 전략 인텔리전스")
            report_placeholder = st.empty()
            
            full_report = ""
            sys_msg = "제공된 요약본들을 바탕으로 시장의 흐름과 마스터를 위한 시사점을 도출하십시오."
            for chunk in reporter._generate(sys_msg, combined_summaries, stream=True):
                full_report += chunk['choices'][0]['text']
                report_placeholder.markdown(full_report + "▌")
            report_placeholder.markdown(full_report)
            
            reporter._save_to_db(keyword, full_report)
            status.update(label="분석 완료 및 NS_DB 저장 성공", state="complete")

if __name__ == "__main__":
    main()