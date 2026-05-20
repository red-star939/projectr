import streamlit as st
import sys
from pathlib import Path

# [1] 전역 레이아웃 설정 및 서브 모듈 충돌 방지
st.set_page_config(
    page_title="Poket-Asset Terminal", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 하위 앱의 중복 set_page_config 실행 방지용 앵커
sys.modules["app_main"] = sys.modules[__name__]

# 모듈 로딩 경로 동기화
BASE_DIR = Path(__file__).resolve().parent
for path_dir in [BASE_DIR, BASE_DIR / "src" / "news_agent", BASE_DIR / "src" / "financial_agent", BASE_DIR / "src" / "portfolio_agent"]:
    if str(path_dir) not in sys.path:
        sys.path.append(str(path_dir))

# [2] 사용자 권한 상태 초기화 및 쿼리 매개변수 동기화
if "user_role" not in st.session_state:
    st.session_state.user_role = None

# URL 쿼리 매개변수 변경 감지 및 세션 바인딩
query_params = st.query_params
if "role" in query_params and st.session_state.user_role is None:
    st.session_state.user_role = query_params["role"]

def main():
    # [3] 전문가/일반 모드 진입 시 최상단에 메인 복귀 컨트롤러 배치
    if st.session_state.user_role is not None:
        if st.button("◀ 메인 화면으로 돌아가기", use_container_width=False):
            st.session_state.user_role = None
            st.query_params.clear()
            st.rerun()

    # ── CASE 1: 초기 진입 메인 화면 (역할 선택 전) ──────────────────
    if st.session_state.user_role is None:
        st.title("Poket-Asset v0.3")
        st.markdown("Poket-Asset 자산 분석 시스템의 메인 터미널입니다. 아래의 박스를 클릭하십시오.")
        st.write("") 
        
        # 입체적 클릭 효과용 Custom CSS
        st.markdown("""
            <style>
                .card-link {
                    text-decoration: none !important;
                    color: inherit !important;
                    display: block;
                    margin-bottom: 1rem;
                }
                .clickable-card {
                    background-color: #f0f2f6;
                    border-radius: 15px;
                    padding: 25px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1), 0 1px 3px rgba(0, 0, 0, 0.08);
                    transition: all 0.2s ease-in-out;
                    cursor: pointer;
                }
                @media (prefers-color-scheme: dark) {
                    .clickable-card {
                        background-color: #262730;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
                    }
                }
                .card-link:hover .clickable-card {
                    transform: translateY(-5px);
                    box-shadow: 0 10px 20px rgba(0, 0, 0, 0.15), 0 6px 6px rgba(0, 0, 0, 0.1);
                }
                .card-link:active .clickable-card {
                    transform: translateY(1px);
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
                }
                .card-title {
                    margin-top: 0;
                    margin-bottom: 10px;
                    font-weight: 700;
                }
                .card-content {
                    font-size: 14px;
                    line-height: 1.6;
                    margin-bottom: 0;
                }
            </style>
        """, unsafe_allow_html=True)

        col_general, col_expert = st.columns(2)
        
        with col_general:
            st.markdown(f"""
                <a href="/?role=general" target="_self" class="card-link">
                    <div class="clickable-card">
                        <h3 class="card-title">일반 사용자용 터미널</h3>
                        <p class="card-content">
                            - <b>핵심:</b> 실시간 시장 이슈 모니터링 및 뉴스 요약<br>
                            - 복잡한 정량 연산 없이 시장의 트렌드와 거시적 핵심 시사점을 신속하게 인덱싱하는 환경입니다.
                        </p>
                    </div>
                </a>
            """, unsafe_allow_html=True)
                    
        with col_expert:
            st.markdown(f"""
                <a href="/?role=expert" target="_self" class="card-link">
                    <div class="clickable-card">
                        <h3 class="card-title">전문가용 터미널</h3>
                        <p class="card-content">
                            - <b>핵심:</b> DART 공시 추적, 지표 계산, 포트폴리오 합성<br>
                            - 고성능 모델을 가동하여 주가 상관관계 분석 및 하이브리드 지식 베이스를 제어하는 환경입니다.
                        </p>
                    </div>
                </a>
            """, unsafe_allow_html=True)

    # ── CASE 2: 전문가용 터미널 활성화 상태 ──────────────────────
    elif st.session_state.user_role == "expert":
        st.title("Expert User Terminal")
        st.markdown("자산 가치 평가, 뉴스 인텔리전스, 포트폴리오 생성을 세분화해서 분석할 수 있습니다.")
        
        # 전문가용 하위 에이전트 3개를 수평 탭으로 분기 연결
        tab_fs, tab_ns, tab_pf = st.tabs([
            "기업 가치 분석 (Financial Analyst)", 
            "뉴스 인텔리전스 (News Intelligence)",
            "포트폴리오 생성 (Portfolio Agent)"
        ])
        
        with tab_fs:
            import app_1FS
            app_1FS.main()
            
        with tab_ns:
            import app_1NS
            app_1NS.main()
            
        with tab_pf:
            import app_1PF
            app_1PF.main()

    # ── CASE 3: 일반 사용자용 터미널 활성화 상태 ────────────────────
    elif st.session_state.user_role == "general":
        st.title("General User Terminal")
        st.info("일반 사용자용 파이프라인 인터페이스 연결 대기 중입니다.")

if __name__ == "__main__":
    main()