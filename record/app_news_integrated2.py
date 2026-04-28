import streamlit as st
import os
import sys
import time
import gc
from datetime import datetime
from pathlib import Path

# [단계 1] 상대 경로 및 모듈 로드 설정
ROOT_DIR = Path(__file__).resolve().parent
sys.path.append(str(ROOT_DIR / "src" / "news_agent"))

from news_fast_stream import BatFastStreamer
from news_sum4_3 import BatExaoneReporter, sanitize_collection_name

st.set_page_config(page_title="Bat-News Fast Intelligence", page_icon="⚡", layout="wide")

# 사이드바 및 VRAM 관리 로직
def unload_model():
    if 'reporter' in st.session_state:
        del st.session_state.reporter
        gc.collect()
        st.session_state.model_loaded = False
        st.sidebar.success("✅ VRAM 자원이 해제되었습니다.")

with st.sidebar:
    st.title("🖥️ Operation Specs")
    st.info("**GPU:** RTX 4050 (6GB)\n\n**Storage:** News_DB & NS_DB")
    if st.button("모델 내리기 (VRAM 해제)", use_container_width=True):
        unload_model()
    st.divider()
    status_area = st.empty()

st.title("📊 Real-time Fast News Intelligence")
st.markdown("---")

with st.form("fast_analysis_form", clear_on_submit=False):
    keyword = st.text_input("분석할 경제 키워드를 입력하세요", placeholder="예: 엔비디아, 삼성전자")
    submit_button = st.form_submit_button("초고속 분석 가동", use_container_width=True)

if submit_button:
    if not keyword:
        st.warning("키워드를 입력해 주십시오.")
    else:
        try:
            with st.status("배트 컴퓨터 파이프라인 가동 중...", expanded=True) as status:
                # 1. 뉴스 수집
                st.write("🛰️ 뉴스 병렬 수집 및 News_DB 동기화 중...")
                streamer = BatFastStreamer(limit=10)
                streamer.run(keyword)

                # 2. 분석 엔진 로드
                if 'reporter' not in st.session_state:
                    st.write("🤖 EXAONE 분석 엔진 VRAM 로딩 중...")
                    st.session_state.reporter = BatExaoneReporter()
                reporter = st.session_state.reporter

                # 3. 데이터 로드 확인
                col_name = sanitize_collection_name(keyword)
                collection = reporter.client.get_collection(name=col_name)
                docs = collection.get()['documents']
                
                if not docs:
                    status.update(label="❌ 수집 데이터 없음", state="error")
                    st.stop()

                # 4. 개별 요약 (Map Phase)
                st.write(f"🔄 {len(docs)}개 기사 분석 및 요약 중...")
                summaries = []
                today_str = datetime.now().strftime("%Y-%m-%d")
                for i, doc in enumerate(docs, 1):
                    sys_msg = reporter.prompt_cfg['prompts']['map_phase']['system'].format(today=today_str)
                    user_msg = reporter.prompt_cfg['prompts']['map_phase']['user_template'].format(document=doc[:2500], today=today_str)
                    res = reporter._generate(sys_msg, user_msg)
                    summaries.append(f"기사 {i} 요약: {res['choices'][0]['text'].strip()}")
                
                status.update(label="분석 완료", state="complete", expanded=False)

            # [Step 3] 통합 리포트 출력
            st.divider()
            st.subheader(f"📊 {keyword} 실시간 통합 전략 리포트")
            report_placeholder = st.empty()
            
            combined = "\n\n".join(summaries)
            sys_msg_f = reporter.prompt_cfg['prompts']['reduce_phase']['system'].format(today=today_str)
            user_msg_f = reporter.prompt_cfg['prompts']['reduce_phase']['user_template'].format(
                keyword=keyword, summaries=combined, today=today_str
            )
            
            full_report = ""
            for chunk in reporter._generate(sys_msg_f, user_msg_f, stream=True):
                token = chunk['choices'][0]['text']
                full_report += token
                report_placeholder.markdown(full_report + "▌")
            report_placeholder.markdown(full_report)

            # [Step 4] 결과 이중 저장 (신규 NS_DB + File)
            reporter._save_to_db(keyword, full_report) # [수정] NS_DB로 저장됨
            report_file = reporter._save_to_md(keyword, full_report, today_str)
            
            st.success(f"💾 리포트가 NS_DB에 영구 저장되었으며 파일로 추출되었습니다.")
            st.toast("✅ 분석 공정 완료")

        except Exception as e:
            st.error(f"알프레드, 연산 오류 발생: {str(e)}")