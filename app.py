import streamlit as st
import pandas as pd
import os
import sys

# [Step 1] 상대 경로를 위한 시스템 경로 등록
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(current_dir, 'src')
if src_dir not in sys.path:
    sys.path.append(src_dir)

# [Step 2] 필요한 모듈만 임포트 
try:
    from news_agent.news_collector import fetch_news
    # from news_agent.data_collector import save_article_to_txt # 필요시 활성화
except ImportError as e:
    st.error(f"Module Import Error: {e}")

# 페이지 설정
st.set_page_config(page_title="Project R", page_icon="BAT", layout="wide")

# 사이드바 설정
with st.sidebar:
    st.title("Stock Control Center")
    menu = st.radio("OPERATIONS", ["NEWS COLLECTOR"])
    st.markdown("---")
    st.info(f"STATUS: **NEWS_ONLY_MODE**")

if menu == "NEWS COLLECTOR":
    st.header("🌐 Intelligence Gathering: News Stream")
    st.write("실시간 주식 정보를 수집하여 디스플레이합니다.")

    keyword = st.text_input("Enter Keyword and Press Enter", placeholder="Search intel...")

    if keyword:
        with st.status(f"Scanning Intelligence for '{keyword}'...", expanded=True) as status:
            results = fetch_news(keyword)
            
            if results:
                st.write(f"🔍 {len(results)}건의 정보를 입수했습니다.")
                
                # 결과 요약 탭
                tab_g, tab_n, tab_d = st.tabs(["🔍 Google News", "🟢 Naver News", "🔵 Daum News"])
                
                def show_summary(source_name, tab_obj):
                    source_data = [n for n in results if n['source'] == source_name]
                    with tab_obj:
                        if source_data:
                            for item in source_data:
                                st.markdown(f"- [{item['title']}]({item['link']})")
                        else:
                            st.info("해당 소스의 데이터가 없습니다.")

                show_summary("Google", tab_g)
                show_summary("Naver", tab_n)
                show_summary("Daum", tab_d)
                status.update(label="Gathering Complete.", state="complete")
            else:
                status.update(label="No Data Found.", state="error")
