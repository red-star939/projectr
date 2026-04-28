import streamlit as st
import os
import sys
import time
import re
import shutil
from datetime import datetime
from pathlib import Path

# 기존 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), "src", "news_agent"))

# 소스 코드에서 핵심 클래스 및 함수 임포트
from src.news_agent.news_col4_1 import fetch_search_results, crawl_article, save_results, sanitize_filename
from src.news_agent.news_db_sync import BatNewsSync
from src.news_agent.news_sum4_1 import BatExaoneReporter, sanitize_collection_name

# 페이지 설정
st.set_page_config(page_title="Real-time Economic Intelligence", page_icon="🦇", layout="wide")

# 사이드바 설정 시작
with st.sidebar:
    st.title("🖥️ System Specs")
    st.info(f"**Target:** RTX 4050 (6GB VRAM)\n\n**RAM:** 32GB\n\n**Model:** EXAONE-3.0-7.8B")
    st.write(f"**Current Date:** {datetime.now().strftime('%Y-%m-%d')}")
    st.divider()
    
    # 처리 과정을 표기할 사이드바 전용 컨테이너 생성
    st.subheader("⚙️ Processing Pipeline")
    status_container = st.empty() # 상태 메시지용 공간
    sidebar_progress = st.empty() # 프로그레스 바용 공간
    collection_log = st.container() # 수집 제목 로그용 공간

st.title("Real-time Economic Intelligence")
st.markdown("---")

# 1. 키워드 입력 섹션
keyword = st.text_input("분석할 경제 키워드를 입력하세요", placeholder="예: 엔비디아, 삼성전자")

if st.button("분석 시작", use_container_width=True):
    if not keyword:
        st.sidebar.warning("키워드를 입력해 주십시오.")
    else:
        # 사이드바 상태 박스 가동
        with st.sidebar:
            status_box = st.status("시스템 가동 중..", expanded=True)
        
        try:
            # [Step 1] 뉴스 수집 및 이전 데이터 파기
            status_box.write("실시간 뉴스 검색 및 이전 데이터 파기 중..")
            now = datetime.now()
            links = fetch_search_results(keyword, limit=10)
            
            if not links:
                status_box.update(label="⚠️ 수집 실패", state="error")
                st.sidebar.error("최근 1시간 이내에 새로운 뉴스가 없습니다.")
            else:
                kwd_dir = Path("src/news_agent/crawled_news") / sanitize_filename(keyword)
                if kwd_dir.exists():
                    shutil.rmtree(kwd_dir)
                    status_box.write(f"기존 '{keyword}' 데이터 파기 완료")

                # 크롤링 수행
                from selenium import webdriver
                from selenium.webdriver.chrome.service import Service
                from selenium.webdriver.chrome.options import Options
                from webdriver_manager.chrome import ChromeDriverManager
                
                options = Options()
                options.add_argument("--headless")
                driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
                
                progress_bar = sidebar_progress.progress(0)
                collection_log.markdown("#### 수집된 기사 제목")
                
                for i, link in enumerate(links, 1):
                    result = crawl_article(driver, link)
                    if "error" not in result:
                        # 사이드바 로그에 제목 표시
                        collection_log.write(f"✅ **[{i}]** {result['title']}")
                        save_results(keyword, result, i, now)
                    else:
                        collection_log.error(f"❌ {i}번 기사 수집 실패")
                    progress_bar.progress(i / len(links))
                
                driver.quit()
                status_box.write("✅ 뉴스 수집 완료")

                # [Step 2] DB 동기화
                status_box.write("ChromaDB 업데이트 중..")
                syncer = BatNewsSync()
                syncer.sync_all()
                status_box.write("✅ DB 동기화 완료")

                # [Step 3] AI 분석 및 요약
                status_box.write("뉴스 리포트 AI 분석 중..")
                reporter = BatExaoneReporter()
                
                # 메인 화면 리포트 영역
                st.markdown(f"### {keyword} 실시간 분석 리포트")
                report_placeholder = st.empty()
                
                col_name = sanitize_collection_name(keyword)
                collection = reporter.client.get_collection(name=col_name)
                docs = collection.get()['documents']
                
                summaries = []
                today_str = now.strftime('%Y-%m-%d')
                
                # Map Phase
                for i, doc in enumerate(docs, 1):
                    status_box.write(f"기사 {i} 분석 중...")
                    sys_msg = reporter.prompt_cfg['prompts']['map_phase']['system'].format(today=today_str)
                    user_msg = reporter.prompt_cfg['prompts']['map_phase']['user_template'].format(document=doc, today=today_str)
                    res = reporter._generate(sys_msg, user_msg)
                    summaries.append(f"기사 {i} 요약: {res['choices'][0]['text'].strip()}")
                
                # Reduce Phase (Streaming)
                combined = "\n\n".join(summaries)
                sys_msg_f = reporter.prompt_cfg['prompts']['reduce_phase']['system'].format(today=today_str)
                user_msg_f = reporter.prompt_cfg['prompts']['reduce_phase']['user_template'].format(keyword=keyword, summaries=combined, today=today_str)
                
                full_report = ""
                stream_res = reporter._generate(sys_msg_f, user_msg_f, stream=True)
                for chunk in stream_res:
                    token = chunk['choices'][0]['text']
                    full_report += token
                    report_placeholder.markdown(full_report + "▌")
                
                report_placeholder.markdown(full_report)
                
                final_path = reporter._save_to_md(keyword, full_report, today_str)
                status_box.update(label="분석 완료", state="complete", expanded=False)
                st.sidebar.success(f"리포트 추출 완료: {os.path.basename(final_path)}")

        except Exception as e:
            st.sidebar.error(f"연산 오류 발생: {str(e)}")
            if 'status_box' in locals():
                status_box.update(label="❌ 오류 발생", state="error")