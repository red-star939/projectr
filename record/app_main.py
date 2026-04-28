import streamlit as st
import sys
import os
from pathlib import Path

# [시스템 경로 설정] 
# 두 에이전트의 경로를 모두 등록하여 임포트 충돌을 방지합니다.
ROOT_DIR = Path(__file__).resolve().parent
FS_AGENT_DIR = ROOT_DIR / "src" / "financial_agent"
NEWS_AGENT_DIR = ROOT_DIR / "src" / "news_agent"

for path in [str(ROOT_DIR), str(FS_AGENT_DIR), str(NEWS_AGENT_DIR)]:
    if path not in sys.path:
        sys.path.insert(0, path)

# 전역 페이지 설정 (단 한 번만 실행되어야 함)
st.set_page_config(
    page_title="Poket-Asset v0.1",
    page_icon="📊",
    layout="wide"
)

# [앱 로직 래핑]
def run_financial_analyst():
    # 기존 app_fs.py의 내용을 함수로 구현하거나 모듈로 호출
    # 여기서는 가독성을 위해 기존 로직을 함수화하여 호출하는 방식을 권장합니다.
    try:
        from app_fs import run_fs_ui
        run_fs_ui()
    except ImportError:
        st.error("Financial Analyst 모듈을 로드할 수 없습니다. 경로를 확인하세요.")

def run_news_agent():
    try:
        from app_news import run_news_ui
        run_news_ui()
    except ImportError:
        st.error("News Agent 모듈을 로드할 수 없습니다. 경로를 확인하세요.")

# 사이드바 메인 메뉴
st.sidebar.title("Poket-Asset v0.1")
st.sidebar.subheader("Integrated Operations")

app_mode = st.sidebar.radio(
    "운용 에이전트 선택",
    ["Main Dashboard", "Financial Analyst", "News Intelligence"]
)

if app_mode == "Main Dashboard":
    st.title("Poket-Asset Terminal")
    st.info("각 에이전트 전환 시 VRAM 자원 점유 상태를 확인하시기 바랍니다.")

elif app_mode == "Financial Analyst":
    # app_fs.py 로직 실행
    import app_fs_integrated 
    app_fs_integrated.main()

elif app_mode == "News Intelligence":
    # app_news.py 로직 실행
    import app_news_integrated
    app_news_integrated.main()