import streamlit as st
import os
import sys
import time
import shutil # [추가] 물리적 폴더 삭제를 위한 모듈

# [Step 1] 상대 경로 및 에이전트 패키지 루트 등록
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.append(src_dir)

# [Step 2] 에이전트 모듈 임포트
try:
    from news_agent.news_collector import fetch_news
    from news_agent.data_collector import save_article_to_txt
    from news_agent.data_DBsave import NewsDBManager 
except ImportError as e:
    st.error(f"❌ 모듈 로드 실패: {e}")
    st.stop()

# DB 매니저 인스턴스 초기화
if 'db_manager' not in st.session_state:
    st.session_state.db_manager = NewsDBManager()

# [Step 3] 스트림릿 UI 설정
st.set_page_config(
    page_title="Project R", 
    page_icon="🦇", 
    layout="wide"
)

# 사이드바: 제어 센터
with st.sidebar:
    st.title("Stock Search&Summary Center")
    menu = st.radio("OPERATIONS", ["NEWS AGENT", "ARCHIVE STATUS"])
    st.markdown("---")
    st.success("SYSTEM: ONLINE")
    st.write(f"User: **{os.getlogin() if hasattr(os, 'getlogin') else 'Hong'}**") 

# [Step 4] NEWS AGENT: 자동 수집 및 실시간 색인 (내용 유지)
if menu == "NEWS AGENT":
    st.header("🌐 NEWS COLLECT & INDEXING")
    st.write("키워드 입력 시 뉴스 검색, 본문 수집, DB 색인이 자동으로 진행됩니다.")

    keyword = st.text_input("Enter Search Intel", placeholder="예: 삼성전자, 하이닉스, 엔비디아...")

    if keyword:
        with st.status(f"Scanning for '{keyword}'...", expanded=True) as status:
            st.write("뉴스 소스(Google, Naver, Daum)에 접속 중...")
            results = fetch_news(keyword) 
            
            if results:
                total = len(results)
                st.write(f"🔍 {total}건의 정보를 찾았습니다. 자동 아카이빙을 시작합니다.")
                
                progress_bar = st.progress(0)
                
                for idx, item in enumerate(results):
                    st.write(f"[{idx+1}/{total}] 수집 중: {item['title'][:45]}...")
                    success, result_msg = save_article_to_txt(
                        keyword, 
                        item['title'], 
                        item['link'], 
                        item['source']
                    )
                    
                    if success:
                        st.caption(f"✅ {item['source']} 저장 완료 ({result_msg})")
                    else:
                        st.caption(f"⚠️ 실패({item['source']}): {result_msg}")
                    
                    progress_bar.progress((idx + 1) / total)

                st.write("수집된 데이터를 ChromaDB에 색인 중입니다...")
                indexed_count = st.session_state.db_manager.index_keyword_folder(keyword)
                
                status.update(label="Scanning, Archiving & Indexing Complete.", state="complete")
                st.success(f"'{keyword}' 관련 {indexed_count}건의 데이터가 `data/News_Reports` 및 DB에 저장되었습니다.")
            else:
                status.update(label="No Intel Found.", state="error")
                st.warning("검색 결과가 없습니다. 키워드를 확인하십시오.")

# [Step 5] ARCHIVE STATUS: 선택적 삭제 기능 추가
elif menu == "ARCHIVE STATUS":
    st.header("📂 Local DB")
    report_path = os.path.join(current_dir, 'data', 'News_Reports')
    
    if os.path.exists(report_path):
        st.subheader("Local Database Status")
        st.write(f"보관소 경로: `{report_path}`")
        
        keywords = [d for d in os.listdir(report_path) if os.path.isdir(os.path.join(report_path, d))]
        if keywords:
            # 키워드 선택
            selected_kwd = st.selectbox("상세 확인 데이터 선택", keywords)
            kwd_path = os.path.join(report_path, selected_kwd)
            sources = os.listdir(kwd_path)
            
            c1, c2, c3 = st.columns([1, 1, 1])
            c1.metric("Sources", len(sources))
            total_files = sum([len(os.listdir(os.path.join(kwd_path, s))) for s in sources])
            c2.metric("Stored Files", total_files)
            
            # [추가] 특정 키워드 데이터 삭제 버튼
            with c3:
                st.write("") # 간격 조정
                if st.button(f"Delete '{selected_kwd}'", help=f"'{selected_kwd}'의 모든 파일과 DB 데이터를 삭제합니다."):
                    # 1. 벡터 DB 데이터 삭제
                    db_success = st.session_state.db_manager.delete_keyword_collection(selected_kwd)
                    
                    # 2. 물리적 파일 삭제
                    try:
                        shutil.rmtree(kwd_path)
                        file_success = True
                    except Exception as e:
                        st.error(f"파일 삭제 실패: {e}")
                        file_success = False
                    
                    if db_success and file_success:
                        st.toast(f"'{selected_kwd}' 데이터 완전 삭제 완료", icon="🔥")
                        time.sleep(1)
                        st.rerun() # UI 갱신

            # ChromaDB 색인 현황
            st.markdown("---")
            st.subheader("Vector Database Status")
            db_stats = st.session_state.db_manager.get_all_collection_stats() #
            if db_stats:
                st.table(db_stats)
            else:
                st.info("DB에 색인된 데이터가 없습니다.")
        else:
            st.info("보관된 키워드 데이터가 없습니다.")
    else:
        st.error("데이터 저장소(`data/News_Reports`)가 아직 생성되지 않았습니다.")