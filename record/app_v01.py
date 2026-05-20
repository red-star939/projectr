import streamlit as st
import os
import sys
import gc
from pathlib import Path
from chromadb.utils import embedding_functions
from llama_cpp import Llama

# [1] 전역 페이지 설정 및 통합 모드 선언
st.set_page_config(page_title="Poket-Asset Terminal v0.1", page_icon="📊", layout="wide")
sys.modules["app_main"] = sys.modules[__name__] # 하위 앱의 중복 set_page_config 방지

# 경로 동기화
BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = str(BASE_DIR / "src" / "news_agent" / "model" / "EXAONE-3.0-7.8B-Instruct-Q4_K_M.gguf")

# 하위 모듈 경로 추가
sys.path.append(str(BASE_DIR))
sys.path.append(str(BASE_DIR / "src" / "news_agent"))
sys.path.append(str(BASE_DIR / "src" / "financial_agent"))
sys.path.append(str(BASE_DIR / "src" / "portfolio_agent"))

# [2] 통합 모델 자동 예열 함수 (기존 로직 유지)
def auto_initialize_engines():
    if st.session_state.get('shutdown_mode', False):
        st.sidebar.warning("⚠️ 엔진 정지 상태")
        return

    with st.sidebar:
        st.write("---")
        st.subheader("⚙️ AI Engine Startup")
        
        if 'embedding_fn' not in st.session_state:
            try:
                with st.spinner("Embedding 로딩 중..."):
                    st.session_state.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                        model_name="jhgan/ko-sroberta-multitask"
                    )
                st.success("✅ Embedding Ready")
            except Exception as e:
                st.error(f"임베딩 오류: {e}")

        if 'llm_engine' not in st.session_state:
            try:
                with st.spinner("EXAONE LLM 로딩 중..."):
                    st.session_state.llm_engine = Llama(
                        model_path=MODEL_PATH, n_ctx=4096, n_gpu_layers=-1,
                        type_k=2, type_v=2, flash_attn=True, verbose=False
                    )
                st.success("✅ EXAONE LLM Ready")
                st.session_state.initialized = True
            except Exception as e:
                st.error(f"LLM 오류: {e}")

# [3] 사이드바: 네비게이션 및 자원 제어
with st.sidebar:
    st.title("Poket-Asset v0.1")
    
    # 에이전트 선택 메뉴 [추가]
    app_mode = st.radio(
        "에이전트 선택",
        ["Dashboard", "Financial Analyst", "News Intelligence", "Portfolio Agent"],
        index=0
    )
    
    auto_initialize_engines()
    
    st.divider()
    if st.button("VRAM 자원 초기화", use_container_width=True):
        for key in ['llm_engine', 'embedding_fn', 'initialized']:
            if key in st.session_state: del st.session_state[key]
        st.session_state.shutdown_mode = True
        gc.collect()
        st.rerun()

# [4] 메인 화면: 에이전트 라우팅 (Routing)
if app_mode == "Dashboard":
    st.title("⚡ Unified Intelligence Dashboard")
    if st.session_state.get('initialized'):
        st.success("Poket-Asset v0.1의 모든 분석 엔진이 준비되었습니다.")
        st.info("사이드바에서 수행할 분석 에이전트를 선택하십시오.")
    else:
        st.warning("엔진을 초기화 중입니다...")

elif app_mode == "Financial Analyst":
    # app_1FS.py 연결
    import app_1FS
    app_1FS.main()

elif app_mode == "News Intelligence":
    # app_1NS.py 연결
    import app_1NS
    app_1NS.main()

elif app_mode == "Portfolio Agent":
    # Portfolio Agent 연결 (app_1PF.py 참조)
    import app_1PF
    app_1PF.main()