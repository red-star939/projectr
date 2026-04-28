import streamlit as st
import os
import sys
import time
import re
import shutil
import gc
from datetime import datetime
from pathlib import Path

# [단계 1] 경로 설정 - 통합 앱 위치 기준
BASE_DIR = Path(__file__).resolve().parent
AGENT_DIR = BASE_DIR / "src" / "news_agent"
if str(AGENT_DIR) not in sys.path:
    sys.path.append(str(AGENT_DIR))

# 핵심 모듈 임포트
try:
    from news_col4_2 import fetch_search_results, crawl_article, save_results, sanitize_filename
    from news_db_sync3 import BatNewsFreshSync
    from news_sum4_2 import BatExaoneReporter, sanitize_collection_name
except ImportError as e:
    st.error(f"뉴스 에이전트 모듈 임포트 실패: {e}")

def unload_model():
    """VRAM 자원 해제 로직"""
    if 'reporter' in st.session_state:
        del st.session_state.reporter
        gc.collect()
        st.sidebar.success("✅ EXAONE 모델이 VRAM에서 해제되었습니다.")
    else:
        st.sidebar.info("현재 로드된 모델이 없습니다.")

def main():
    """
    통합 앱에서 호출되는 News Intelligence 메인 진입점입니다.
    """
    st.title("📊 Real-time Economic Intelligence")
    st.markdown("---")

    # 사이드바 구성 (통합 앱 사이드바 하단에 추가됨)
    with st.sidebar:
        st.divider()
        st.subheader("🖥️ News Agent Specs")
        st.info("**GPU:** RTX 4050 (6GB)\n\n**Model:** EXAONE-3.0-7.8B")
        
        if st.button("모델 내리기 (VRAM 해제)", use_container_width=True, key="unload_news_vram"):
            unload_model()
        
        st.divider()
        st.subheader("⚙️ Pipeline Status")
        sidebar_progress = st.empty()

    # [핵심] 검색 폼 구성
    with st.form("analysis_form", clear_on_submit=False):
        keyword = st.text_input("분석할 경제 키워드를 입력하세요", placeholder="예: 엔비디아, 삼성전자", key="news_keyword_input")
        submit_button = st.form_submit_button("실시간 분석 시작", use_container_width=True)

    main_log_container = st.container()

    if submit_button:
        if not keyword:
            st.sidebar.warning("키워드를 입력해 주십시오.")
        else:
            with st.sidebar:
                status_box = st.status("배트 컴퓨터 연산 가동 중..", expanded=True)
            
            try:
                # [Step 1] 뉴스 수집
                status_box.write("실시간 뉴스 검색 및 이전 데이터 파기 중..")
                now = datetime.now()
                links = fetch_search_results(keyword, limit=10)
                
                if not links:
                    status_box.update(label="❌ 수집 실패", state="error")
                    st.error("최근 1시간 이내에 새로운 뉴스가 없습니다.")
                else:
                    kwd_dir = AGENT_DIR / "crawled_news" / sanitize_filename(keyword)
                    if kwd_dir.exists():
                        shutil.rmtree(kwd_dir)
                    
                    # Selenium 설정 및 수집
                    from selenium import webdriver
                    from selenium.webdriver.chrome.service import Service
                    from selenium.webdriver.chrome.options import Options
                    from webdriver_manager.chrome import ChromeDriverManager
                    
                    options = Options()
                    options.add_argument("--headless")
                    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)            
                    progress_bar = sidebar_progress.progress(0)

                    with main_log_container:
                        st.markdown(f"#### 📝 수집된 '{keyword}' 뉴스 헤드라인")
                        title_list = st.container(border=True)
                    
                    for i, link in enumerate(links, 1):
                        result = crawl_article(driver, link)
                        if "error" not in result:
                            title_list.write(f"✅ **[{i}]** {result['title']}")
                            save_results(keyword, result, i, now)
                        progress_bar.progress(i / len(links))
                    driver.quit()

                    # [Step 2] DB 최신화
                    status_box.write("ChromaDB(Fresh Sync) 업데이트 중..")
                    syncer = BatNewsFreshSync()
                    syncer.sync_latest_only()

                    # [Step 3] AI 분석 (VRAM 점유 발생)
                    status_box.write("EXAONE 모델 로드 및 리포트 분석 중..")
                    if 'reporter' not in st.session_state:
                        st.session_state.reporter = BatExaoneReporter()
                    reporter = st.session_state.reporter
                    
                    st.divider()
                    st.subheader(f"📊 {keyword} 실시간 분석 결과")
                    report_placeholder = st.empty()
                    
                    col_name = sanitize_collection_name(keyword)
                    collection = reporter.client.get_collection(name=col_name)
                    docs = collection.get()['documents']
                    
                    summaries = []
                    today_str = now.strftime('%Y-%m-%d')
                    
                    for i, doc in enumerate(docs, 1):
                        status_box.write(f"🔄 기사 {i} 분석 중...")
                        sys_msg = reporter.prompt_cfg['prompts']['map_phase']['system'].format(today=today_str)
                        user_msg = reporter.prompt_cfg['prompts']['map_phase']['user_template'].format(document=doc, today=today_str)
                        res = reporter._generate(sys_msg, user_msg)
                        summaries.append(f"기사 {i} 요약: {res['choices'][0]['text'].strip()}")
                    
                    # 최종 리포트 생성 (Streaming)
                    combined = "\n\n".join(summaries)
                    sys_msg_f = reporter.prompt_cfg['prompts']['reduce_phase']['system'].format(today=today_str)
                    user_msg_f = reporter.prompt_cfg['prompts']['reduce_phase']['user_template'].format(keyword=keyword, summaries=combined, today=today_str)
                    
                    full_report = ""
                    for chunk in reporter._generate(sys_msg_f, user_msg_f, stream=True):
                        token = chunk['choices'][0]['text']
                        full_report += token
                        report_placeholder.markdown(full_report + "▌")
                    
                    report_placeholder.markdown(full_report)
                    status_box.update(label="분석 완료", state="complete", expanded=False)
                    st.success(f"✅ 리포트 생성 완료 (저장 경로: {AGENT_DIR / 'reports'})")

            except Exception as e:
                st.sidebar.error(f"연산 오류 발생: {str(e)}")
                if 'status_box' in locals():
                    status_box.update(label="❌ 오류 발생", state="error")
    else:
        st.info("키워드를 입력하고 '실시간 분석 시작' 버튼을 클릭하십시오.")