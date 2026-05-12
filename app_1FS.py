import streamlit as st
import pandas as pd
import sys
import os
from pathlib import Path
from datetime import datetime

# [단계 1] 경로 및 모듈 설정
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# 핵심 금융 모듈 로드
from src.financial_agent import utils_, conSQL, FS_to_SQL, yfinance_api, Sector, Extract_corr, fs_report_test, chroma_manager

# 해외 종목 모듈 로드
from src.international_agent import intl_utils
from src.international_agent import yf_financials as intl_yf
from src.international_agent import market_index_map
from src.international_agent.intl_fs_report import create_intl_markdown_template

# [단계 2] 통합 대시보드 호환성 설정
if "app_main" not in sys.modules:
    st.set_page_config(page_title="Financial Analyst", page_icon="📊", layout="wide")

def main():
    st.title("🔍 기업 가치 분석 및 지식화")

    # ── 시장 선택 (국내 / 해외) ──────────────────────────────────────
    market_mode = st.sidebar.radio(
        "시장 선택",
        ["🇰🇷 국내 기업 (DART)", "🌍 해외 기업 (Ticker)"],
        key="fs_market_mode",
    )
    is_intl = market_mode == "🌍 해외 기업 (Ticker)"

    if not is_intl:
        all_corps = list(utils_.corp_code.keys())
        target_corp = st.sidebar.selectbox(
            "분석 대상 기업",
            all_corps,
            index=all_corps.index("삼성전자") if "삼성전자" in all_corps else 0,
            key="fs_target_select",
        )
    else:
        raw_input = st.sidebar.text_input(
            "티커 입력 (예: AAPL, MSFT, 7203.T)",
            value="AAPL",
            key="fs_ticker_input",
        )
        target_corp = raw_input.strip().upper()

    analyze_btn = st.sidebar.button("정밀 분석 및 DB 저장 시작", use_container_width=True)

    # ── 결과 컨텍스트 초기화 ────────────────────────────────────────
    df = None
    report_md = None
    save_success = False
    benchmark_label = "KOSPI"
    benchmark_account_nm = "KOSPI"

    if analyze_btn:
        if is_intl:
            # ── 해외 종목 분석 흐름 ──────────────────────────────────
            if not target_corp:
                st.sidebar.error("티커를 입력해주세요.")
            else:
                with st.status(f"[{target_corp}] 해외 종목 분석 중...", expanded=True) as status:
                    # 1. 재무제표 수집 (YF_FS source)
                    st.write("yfinance 재무제표 수집 중...")
                    intl_yf.ensure_intl_data(target_corp)

                    # 2. 시장 지표 수집 (YFINANCE source)
                    st.write("yfinance 시장 지표 수집 중...")
                    intl_yf.fetch_and_save_intl_yf_info(target_corp)

                    # 3. 섹터 동기화 및 조회
                    intl_utils.sync_intl_sector(target_corp)
                    sector_nm = Sector.get_sector(target_corp)

                    # 4. 5년 OHLCV 시계열 1회 수집 (상관계수 + 기술적 지표 공유)
                    st.write("5년 주가 시계열 수집 중...")
                    benchmark_idx = market_index_map.get_benchmark_index(target_corp)
                    corp_hist = Extract_corr.get_5y_history(target_corp)
                    bench_hist = Extract_corr.get_5y_history(benchmark_idx)
                    corp_close = corp_hist['Close'].dropna() if not corp_hist.empty else None
                    bench_close = bench_hist['Close'].dropna() if not bench_hist.empty else None

                    # 5. 벤치마크 상관계수 계산 및 DB 저장
                    st.write("벤치마크 상관계수 계산 중...")
                    bench_corr = Extract_corr.correlation_with_benchmark(
                        target_corp, benchmark_idx,
                        corp_close=corp_close, benchmark_close=bench_close,
                    )

                    db = conSQL.FS(init_sectors=False)
                    curr_year = datetime.now().year
                    if bench_corr is not None:
                        db.to_sql(target_corp, pd.DataFrame([{
                            "source": "CORRELATION", "report_type": "5Y",
                            "corp_code": target_corp, "stock_code": target_corp,
                            "fs_div": "N/A", "sj_div": "N/A",
                            "account_nm": benchmark_idx,
                            "target_year": curr_year, "amount": bench_corr,
                        }]))

                    # 6. 투자 지표 계산 (펀더멘털 + 기술적)
                    st.write("투자 지표(PER·PBR·ROE 등) 계산 중...")
                    Extract_corr.compute_financial_indicators(target_corp)

                    st.write("기술적 지표(RSI·MACD·BB 등) 계산 중...")
                    Extract_corr.compute_technical_indicators(target_corp, hist=corp_hist)

                    # 7. 보고서 생성
                    df = db.search_sql(target_corp)
                    db.close()
                    report_md = create_intl_markdown_template(target_corp, sector_nm, df)

                    # 7. ChromaDB 저장
                    st.write("지식 베이스(FS_DB) 인덱싱 중...")
                    save_success = chroma_manager.save_report_to_db(
                        corp=target_corp, content=report_md,
                        sector=sector_nm, stock_code=target_corp,
                    )

                    benchmark_label = market_index_map.INDEX_DISPLAY_NAME.get(benchmark_idx, benchmark_idx)
                    benchmark_account_nm = benchmark_idx

                    status.update(
                        label=f"✅ {target_corp} 분석 완료",
                        state="complete", expanded=False,
                    )

        else:
            # ── 국내 종목 분석 흐름 ──────────────────────────────────
            with st.status(f"[{target_corp}] 지능형 데이터 처리 중...", expanded=True) as status:
                # 1. 원천 데이터 수집
                st.write("DART 공시 및 yfinance 데이터 동기화...")
                FS_to_SQL.ensure_company_data(target_corp)
                yfinance_api.fetch_and_save_yfinance_info([target_corp])

                db = conSQL.FS()
                sector_nm = Sector.get_sector(target_corp)
                c_code = utils_.call_corp_code(target_corp)
                s_code = utils_.call_stock_code(target_corp)

                # 2. 5년 OHLCV 시계열 1회 수집 (상관계수 + 기술적 지표 공유)
                st.write("5년 주가 시계열 수집 중...")
                corp_hist = Extract_corr.get_5y_history(target_corp)
                kospi_hist = Extract_corr.get_5y_history("KOSPI")
                corp_close = corp_hist['Close'].dropna() if not corp_hist.empty else None
                kospi_close = kospi_hist['Close'].dropna() if not kospi_hist.empty else None

                # 3. 상관관계 분석 (사전 수집 시계열 재사용)
                st.write("시장 및 섹터 상관관계 분석 중...")
                kospi_corr = Extract_corr.correlation_with_KOSPI(
                    target_corp, corp_close=corp_close, kospi_close=kospi_close
                )
                sector_corrs = Extract_corr.compare_with_sector(target_corp)

                curr_year = datetime.now().year
                corr_records = []
                if kospi_corr is not None:
                    corr_records.append({
                        "source": "CORRELATION", "report_type": "5Y",
                        "corp_code": c_code, "stock_code": s_code,
                        "fs_div": "N/A", "sj_div": "N/A",
                        "account_nm": "KOSPI",
                        "target_year": curr_year, "amount": kospi_corr,
                    })
                if sector_corrs:
                    for comp, corr in sector_corrs:
                        if corr is not None:
                            corr_records.append({
                                "source": "CORRELATION", "report_type": "5Y",
                                "corp_code": c_code, "stock_code": s_code,
                                "fs_div": "N/A", "sj_div": "N/A",
                                "account_nm": comp,
                                "target_year": curr_year, "amount": corr,
                            })
                if corr_records:
                    db.to_sql(target_corp, pd.DataFrame(corr_records))

                # 4. 투자 지표 계산 (INDICATOR/펀더멘털)
                st.write("투자 지표(PER·PBR·ROE 등) 계산 중...")
                Extract_corr.compute_financial_indicators(target_corp)

                # 5. 기술적 지표 계산 (INDICATOR/MKT — 사전 수집 시계열 재사용)
                st.write("기술적 지표(RSI·MACD·BB 등) 계산 중...")
                Extract_corr.compute_technical_indicators(target_corp, hist=corp_hist)

                df = db.search_sql(target_corp)
                report_md = fs_report_test.create_markdown_template(
                    corp=target_corp, sector=sector_nm,
                    corp_code=c_code, stock_code=s_code, df=df,
                )

                # 6. ChromaDB 저장
                st.write("지식 베이스(FS_DB) 인덱싱 중...")
                save_success = chroma_manager.save_report_to_db(
                    corp=target_corp, content=report_md,
                    sector=sector_nm, stock_code=s_code,
                )

                benchmark_label = "KOSPI"
                benchmark_account_nm = "KOSPI"

                db.close()
                status.update(
                    label=f"✅ {target_corp} 분석 및 지식화 완료",
                    state="complete", expanded=False,
                )

    # ── 결과 시각화 섹션 ────────────────────────────────────────────
    if df is not None and not df.empty and report_md is not None:
        st.markdown(report_md)

        if "source" in df.columns:
            corr_data = df[df["source"] == "CORRELATION"].copy()
            if not corr_data.empty:
                st.divider()
                st.subheader("📊 주가 상관관계 분석 (최근 5년)")
                st.caption(
                    f"{benchmark_label} 지수 및 동종 섹터 경쟁사와의 주가 수익률 상관계수입니다."
                )

                corr_data["amount"] = pd.to_numeric(corr_data["amount"], errors="coerce")
                corr_data = corr_data.dropna(subset=["amount"]).sort_values(
                    by="amount", ascending=False
                )

                if not corr_data.empty:
                    bench_data = corr_data[corr_data["account_nm"] == benchmark_account_nm]
                    if not bench_data.empty:
                        k_val = bench_data["amount"].values[0]
                        st.metric(
                            f"📈 {benchmark_label} 대비 상관계수",
                            f"{k_val:.3f}",
                            help=f"1에 가까울수록 {benchmark_label} 지수와 유사하게 움직입니다.",
                        )

                    sector_data = corr_data[corr_data["account_nm"] != benchmark_account_nm]
                    if not sector_data.empty:
                        st.write("**섹터 내 주요 경쟁사 상관계수**")
                        chart_df = sector_data[["account_nm", "amount"]].set_index("account_nm")
                        st.bar_chart(chart_df, use_container_width=True)

        if save_success:
            st.toast(f"💾 {target_corp} 지식 베이스 최신화 완료")
    elif analyze_btn:
        st.error("데이터 로드에 실패했습니다.")


# 통합 실행 대응
if __name__ == "__main__":
    main()
