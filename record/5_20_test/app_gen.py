import streamlit as st
import sys
import concurrent.futures
from pathlib import Path
from datetime import datetime
import pandas as pd

# [1] 전역 레이아웃 및 환경 경로 동기화
st.set_page_config(page_title="Parallel Intelligence Terminal", layout="wide")

BASE_DIR = Path(__file__).resolve().parent
for path_dir in [BASE_DIR, BASE_DIR / "src" / "news_agent", BASE_DIR / "src" / "financial_agent"]:
    if str(path_dir) not in sys.path:
        sys.path.append(str(path_dir))

# 의존성 핵심 모듈 로드
from src.financial_agent import utils_, conSQL, FS_to_SQL, yfinance_api, Sector, Extract_corr, fs_report_test, chroma_manager, ui_search
from news_fast_stream import BatFastStreamer
from news_sum4_3 import BatExaoneReporter

# ── 백엔드 전용 워커 함수 (UI 컴포넌트 호출 배제) ──────────────────────
def bg_financial_pipeline(keyword: str):
    """Financial Analyst 백엔드 연산 및 데이터 보존"""
    try:
        FS_to_SQL.ensure_company_data(keyword)
        yfinance_api.fetch_and_save_yfinance_info([keyword])
        
        db = conSQL.FS()
        sector_nm = Sector.get_sector(keyword)
        c_code = utils_.call_corp_code(keyword)
        s_code = utils_.call_stock_code(keyword)
        
        corp_hist = Extract_corr.get_5y_history(keyword)
        kospi_hist = Extract_corr.get_5y_history("KOSPI")
        corp_close = corp_hist['Close'].dropna() if not corp_hist.empty else None
        kospi_close = kospi_hist['Close'].dropna() if not kospi_hist.empty else None
        
        kospi_corr = Extract_corr.correlation_with_KOSPI(keyword, corp_close=corp_close, kospi_close=kospi_close)
        sector_corrs = Extract_corr.compare_with_sector(keyword)
        
        curr_year = datetime.now().year
        corr_records = []
        if kospi_corr is not None:
            corr_records.append({
                "source": "CORRELATION", "report_type": "5Y", "corp_code": c_code, "stock_code": s_code,
                "fs_div": "N/A", "sj_div": "N/A", "account_nm": "KOSPI", "target_year": curr_year, "amount": kospi_corr
            })
        if sector_corrs:
            for comp, corr in sector_corrs:
                if corr is not None:
                    corr_records.append({
                        "source": "CORRELATION", "report_type": "5Y", "corp_code": c_code, "stock_code": s_code,
                        "fs_div": "N/A", "sj_div": "N/A", "account_nm": comp, "target_year": curr_year, "amount": corr
                    })
        if corr_records:
            db.to_sql(keyword, pd.DataFrame(corr_records))
            
        Extract_corr.compute_financial_indicators(keyword)
        Extract_corr.compute_technical_indicators(keyword, hist=corp_hist)
        
        df = db.search_sql(keyword)
        report_md = fs_report_test.create_markdown_template(
            corp=keyword, sector=sector_nm, corp_code=c_code, stock_code=s_code, df=df
        )
        
        chroma_manager.save_report_to_db(corp=keyword, content=report_md, sector=sector_nm, stock_code=s_code)
        db.close()
        return {"success": True, "report_md": report_md, "df": df}
    except Exception as e:
        return {"success": False, "error": str(e)}

def bg_news_pipeline(keyword: str):
    """News Intelligence 백엔드 연산 및 데이터 보존"""
    try:
        reporter = BatExaoneReporter()
        streamer = BatFastStreamer()
        
        results = streamer.run(keyword, reporter)
        if not results or not results['documents']:
            return {"success": False, "error": "뉴스 데이터 확보 실패"}
            
        combined_summaries = "\n\n".join(results['documents'])
        full_report = ""
        sys_msg = "제공된 요약본들을 바탕으로 시장의 흐름과 마스터를 위한 시사점을 도출하십시오."
        
        for chunk in reporter._generate(sys_msg, combined_summaries, stream=False):
            full_report += chunk['choices'][0]['text']
            
        reporter._save_to_db(keyword, full_report)
        today_str = datetime.now().strftime("%Y-%m-%d")
        reporter._save_to_md(keyword, full_report, today_str)
        return {"success": True, "report_md": full_report}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ── 메인 인터페이스 컨트롤러 ──────────────────────────────────────────
def main():
    st.title("Parallel Processing Preprocessor")
    st.markdown("단일 키워드 입력으로 정량(FS) 및 정성(NS) 지식을 동시에 병렬 처리하여 자원 효율성을 극대화합니다.")
    st.markdown("---")
    
    keyword = ui_search.render_search(
        "분석 키워드 또는 회사명 입력",
        mode='unified',
        key='parallel_preload_search',
    )
    
    execute_btn = st.button(
        "병렬 파이프라인 동시 가동", 
        use_container_width=True, 
        disabled=not keyword
    )
    
    st.write("")
    
    # [2분할 레이아웃 박스 선행 배치]
    col_fs, col_ns = st.columns(2)
    
    with col_fs:
        st.markdown("### Financial Analyst (FS)")
        fs_container = st.container(border=True)
        fs_placeholder = fs_container.empty()
        fs_placeholder.info("대기 중")
        
    with col_ns:
        st.markdown("### News Intelligence (NS)")
        ns_container = st.container(border=True)
        ns_placeholder = ns_container.empty()
        ns_placeholder.info("대기 중")
        
    if execute_btn and keyword:
        fs_placeholder.warning("정량 지표 계산 및 인덱싱 중...")
        ns_placeholder.warning("실시간 뉴스 수집 및 리포트 합성 중...")
        
        # 멀티스레딩 풀 실행 및 비차단 가동
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future_fs = executor.submit(bg_financial_pipeline, keyword)
            future_ns = executor.submit(bg_news_pipeline, keyword)
            
            # 두 프로세스가 모두 종료될 때까지 메인 스레드 대기 (Join)
            fs_res = future_fs.result()
            ns_res = future_ns.result()
            
        # [박스 1: FS 결과 독립 출력]
        if fs_res["success"]:
            fs_placeholder.empty()
            with fs_container:
                st.markdown(fs_res["report_md"])
                # 주가 상관관계 시각화 컴포넌트 추가 배치 영역
                df = fs_res["df"]
                if df is not None and not df.empty and "source" in df.columns:
                    corr_data = df[df["source"] == "CORRELATION"].copy()
                    if not corr_data.empty:
                        st.bar_chart(corr_data[["account_nm", "amount"]].set_index("account_nm"), use_container_width=True)
        else:
            fs_placeholder.error(f"FS 에러: {fs_res['error']}")
            
        # [박스 2: NS 결과 독립 출력]
        if ns_res["success"]:
            ns_placeholder.empty()
            with ns_container:
                st.markdown(ns_res["report_md"])
        else:
            ns_placeholder.error(f"NS 에러: {ns_res['error']}")

if __name__ == "__main__":
    main()