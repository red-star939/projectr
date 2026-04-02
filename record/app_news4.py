import streamlit as st
import os
import sys
import time
import re
import shutil
import gc  # [추가] 가비지 컬렉션을 통한 메모리 해제
from datetime import datetime
from pathlib import Path

# 기존 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "src", "news_agent"))

# 소스 코드에서 핵심 클래스 및 함수 임포트
from src.news_agent.news_col4_2 import fetch_search_results, crawl_article, save_results, sanitize_filename
from src.news_agent.news_db_sync3 import BatNewsFreshSync
from src.news_agent.news_sum4_2 import BatExaoneReporter, sanitize_collection_name

# 페이지 설정
st.set_page_config(page_title="Real-time Economic Intelligence", page_icon="📈", layout="wide")

# [핵심] 모델 해제 로직 정의
def unload_model():
    if 'reporter' in st.session_state:
        # llama-cpp 인스턴스 파기 및 메모리 해제
        del st.session_state.reporter
        gc.collect() # 파이썬 가비지 컬렉터 강제 실행
        st.session_state.model_loaded = False
        st.sidebar.success("✅ VRAM 자원이 해제되었습니다.")
    else:
        st.sidebar.info("현재 메모리에 로드된 모델이 없습니다.")

# 사이드바: 시스템 스펙 및 메모리 관리
with st.sidebar:
    st.title("🖥️ System Specs")
    st.info(f"**Target:** RTX 4050 (6GB VRAM)\n\n**RAM:** 32GB\n\n**Model:** EXAONE-3.0-7.8B")
    
    # [추가] 모델 상태 표시 및 해제 버튼
    st.divider()
    st.subheader("Memory Management")
    if st.button("모델 내리기 (VRAM 해제)", use_container_width=True):
        unload_model()
    
    st.divider()
    st.subheader("⚙️ Pipeline Status")
    status_container = st.empty() 
    sidebar_progress = st.empty() 

st.title("📊 Real-time Economic Intelligence")
st.markdown("---")

# 1. 키워드 입력 섹션
keyword = st.text_input("분석할 경제 키워드를 입력하세요", placeholder="예: 엔비디아, 삼성전자")

# 메인 보드용 수집 로그 컨테이너
main_log_container = st.container()

if st.button("분석 시작", use_container_width=True):
    if not keyword:
        st.sidebar.warning("키워드를 입력해 주십시오.")
    else:
        with st.sidebar:
            status_box = st.status("시스템 가동 중..", expanded=True)
        
        try:
            # [Step 1] 뉴스 수집 (생략 없이 유지)
            status_box.write("실시간 뉴스 검색 및 데이터 파기 중..")
            now = datetime.now()
            links = fetch_search_results(keyword, limit=10)
            
            if not links:
                status_box.update(label="❌ 수집 실패", state="error")
                st.sidebar.error("최근 1시간 이내에 새로운 뉴스가 없습니다.")
            else:
                kwd_dir = Path("src/news_agent/crawled_news") / sanitize_filename(keyword)
                if kwd_dir.exists():
                    shutil.rmtree(kwd_dir)

                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service
                from selenium.webdriver.chrome.options import Options
                from webdriver_manager.chrome import ChromeDriverManager
                
                options = Options()
                options.add_argument("--headless")
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
                
                progress_bar = sidebar_progress.progress(0)
                with main_log_container:
                    st.markdown(f"#### 📝 최근 1시간 이내 수집된 '{keyword}' 뉴스")
                    title_list = st.container(border=True)
                
                for i, link in enumerate(links, 1):
                    result = crawl_article(driver, link)
                    if "error" not in result:
                        title_list.write(f"✅ **[{i}]** {result['title']}")
                        save_results(keyword, result, i, now)
                    progress_bar.progress(i / len(links))
                driver.quit()

                # [Step 2] DB 동기화
                status_box.write("ChromaDB 업데이트 중..")
                syncer = BatNewsSync()
                syncer.sync_all()

                # [Step 3] AI 분석 (세션 상태 활용)
                status_box.write("뉴스 리포트 AI 분석 중..")
                
                # 모델이 로드되어 있지 않거나 없으면 새로 로드
                if 'reporter' not in st.session_state:
                    st.session_state.reporter = BatExaoneReporter()
                    st.session_state.model_loaded = True
                
                reporter = st.session_state.reporter
                
                st.markdown("---")
                st.markdown(f"### 📊 {keyword} 실시간 분석 리포트")
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
                
                combined = "\n\n".join(summaries)
                sys_msg_f = reporter.prompt_cfg['prompts']['reduce_phase']['system'].format(today=today_str)
                user_msg_f = reporter.prompt_cfg['prompts']['reduce_phase']['user_template'].format(keyword=keyword, summaries=combined, today=today_str)
                
                full_report = ""
                for chunk in reporter._generate(sys_msg_f, user_msg_f, stream=True):
                    token = chunk['choices'][0]['text']
                    full_report += token
                    report_placeholder.markdown(full_report + "▌")
                
                report_placeholder.markdown(full_report)
                reporter._save_to_md(keyword, full_report, today_str)
                status_box.update(label="분석 완료", state="complete", expanded=False)

        except Exception as e:
            st.sidebar.error(f"연산 오류 발생: {str(e)}")