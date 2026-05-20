"""
yfinance 재무제표(income_stmt / balance_sheet / cashflow) 및
시장 지표(info)를 FS.db 에 적재하는 해외 종목 전용 모듈.

저장 스키마 (DART 스키마와 동일하게 맞춤):
    source      = 'YF_FS'
    report_type = 'Annual'
    corp_code   = ticker
    stock_code  = ticker
    fs_div      = 'IS' / 'BS' / 'CF'
    sj_div      = fs_div 와 동일
    account_nm  = YF_FS_ACCOUNT_MAP 으로 정규화된 이름
                  (compute_financial_indicators 가 DART 계정명과 동일하게 조회 가능)
    target_year = 연도(int)
    amount      = float

캐시 우선:
    DB 에 이미 YF_FS 데이터가 있으면 수집을 건너뛴다.
    ensure_intl_data() 를 진입점으로 사용할 것.
"""
import yfinance as yf
import pandas as pd

from src.financial_agent import conSQL
from src.international_agent.intl_utils import YF_FS_ACCOUNT_MAP

# yfinance attribute 이름 → FS.db fs_div 매핑
_ATTR_TO_FS_DIV: dict[str, str] = {
    "income_stmt":   "IS",
    "balance_sheet": "BS",
    "cashflow":      "CF",
}


def _parse_statement(ticker_obj: yf.Ticker, attr: str, corp_ticker: str) -> pd.DataFrame:
    """
    yfinance 재무제표 DataFrame 한 장을 FS.db 스키마 DataFrame 으로 변환한다.

    YF_FS_ACCOUNT_MAP 에 있는 계정은 DART 스타일 이름으로 정규화하여 저장하고,
    매핑에 없는 계정은 원문 그대로 저장한다.
    """
    fs_div: str = _ATTR_TO_FS_DIV[attr]
    raw: pd.DataFrame | None = getattr(ticker_obj, attr, None)

    if raw is None or raw.empty:
        return pd.DataFrame()

    records: list[dict] = []
    for account_raw in raw.index:
        account_nm = YF_FS_ACCOUNT_MAP.get(str(account_raw), str(account_raw))

        for date_col in raw.columns:
            value = raw.loc[account_raw, date_col]
            if pd.isna(value):
                continue
            try:
                year = date_col.year if hasattr(date_col, "year") else int(str(date_col)[:4])
                amount = float(value)
            except (ValueError, TypeError):
                continue

            records.append({
                "source":      "YF_FS",
                "report_type": "Annual",
                "corp_code":   corp_ticker,
                "stock_code":  corp_ticker,
                "fs_div":      fs_div,
                "sj_div":      fs_div,
                "account_nm":  account_nm,
                "target_year": year,
                "amount":      amount,
            })

    return pd.DataFrame(records)


def fetch_and_save_intl_financials(corp_ticker: str) -> bool:
    """
    yfinance 에서 재무제표 3종(손익/재무상태/현금흐름)을 수집하여 FS.db 에 저장한다.

    :param corp_ticker: yfinance 티커 (예: "AAPL", "MSFT", "7203.T")
    :return: 1건 이상 저장 성공 시 True
    """
    print(f"⏳ [{corp_ticker}] 해외 재무제표 수집 중 (yfinance)...")
    try:
        ticker_obj = yf.Ticker(corp_ticker)
        db = conSQL.FS(init_sectors=False)
        subset = ["source", "corp_code", "fs_div", "account_nm", "target_year"]
        total = 0

        for attr, label in [
            ("income_stmt",   "손익계산서(IS)"),
            ("balance_sheet", "재무상태표(BS)"),
            ("cashflow",      "현금흐름표(CF)"),
        ]:
            df = _parse_statement(ticker_obj, attr, corp_ticker)
            if df.empty:
                print(f"   ⚠️ {label}: 데이터 없음 (yfinance 미지원 또는 비상장)")
                continue
            db.to_sql(corp_ticker, df, subset=subset)
            total += len(df)
            print(f"   ✅ {label}: {len(df)}건 저장")

        db.close()

        if total > 0:
            print(f"✅ [{corp_ticker}] 재무제표 총 {total}건 DB 저장 완료")
            return True
        else:
            print(f"⚠️ [{corp_ticker}] 수집된 재무제표 데이터가 없습니다.")
            return False

    except Exception as e:
        print(f"🚨 [{corp_ticker}] 재무제표 수집 중 에러: {e}")
        return False


def _coerce_to_series(obj):
    """DataFrame/Series 둘 다 받아들여 항상 Series 로 반환. 변환 불가면 None."""
    if obj is None:
        return None
    if isinstance(obj, pd.Series):
        return obj
    if isinstance(obj, pd.DataFrame):
        if obj.empty:
            return None
        return obj.iloc[:, 0]
    return None


def _collect_intl_dividend_history(ticker_obj, ticker: str, n_years: int = 5) -> list:
    """해외 종목 연간 배당 이력 수집 (yfinance .dividends).

    yfinance 버전에 따라 Series/DataFrame 으로 다르게 반환될 수 있어 강제 변환.
    """
    try:
        divs = _coerce_to_series(ticker_obj.dividends)
        if divs is None or divs.empty:
            return []
        if not hasattr(divs.index, 'year'):
            return []
        annual = _coerce_to_series(divs.groupby(divs.index.year).sum())
        if annual is None or annual.empty:
            return []
        annual = annual.tail(n_years)

        records = []
        for year, amount in annual.items():
            try:
                v = float(amount)
            except (TypeError, ValueError):
                continue
            if pd.isna(v):
                continue
            records.append({
                "source":      "YFINANCE",
                "report_type": "배당이력",
                "corp_code":   ticker,
                "stock_code":  ticker,
                "fs_div":      "YF",
                "sj_div":      "DIV_HIST",
                "account_nm":  "연간배당",
                "target_year": int(year),
                "amount":      v,
            })
        return records
    except Exception as e:
        print(f"   ⚠️ [{ticker}] 배당 이력 수집 실패: {e}")
        return []


def fetch_and_save_intl_yf_info(corp_ticker: str) -> bool:
    """
    해외 종목의 yfinance info 시장 지표 + 배당 이력을 FS.db 에 저장.

    yfinance_api.fetch_and_save_yfinance_info 의 해외 종목 버전으로,
    .KS/.KQ 변환 없이 ticker 를 직접 사용한다.
    """
    import datetime as _dt
    print(f"⏳ [{corp_ticker}] yfinance 시장 지표 수집 중...")
    try:
        ticker_obj = yf.Ticker(corp_ticker)
        info = ticker_obj.info
        if not info or (
            'regularMarketPrice' not in info and 'previousClose' not in info
        ):
            print(f"⚠️ [{corp_ticker}] yfinance 시장 지표를 찾을 수 없습니다.")
            return False

        current_year = _dt.datetime.now().year
        parsed_data = [
            {
                "source":      "YFINANCE",
                "report_type": "기본지표",
                "corp_code":   corp_ticker,
                "stock_code":  corp_ticker,
                "fs_div":      "YF",
                "sj_div":      "INFO",
                "account_nm":  key,
                "target_year": current_year,
                "amount":      value,
            }
            for key, value in info.items()
            if isinstance(value, (int, float, str, bool))
        ]

        if not parsed_data:
            print(f"⚠️ [{corp_ticker}] 유효한 지표가 없습니다.")
            return False

        db = conSQL.FS(init_sectors=False)
        subset = ['source', 'report_type', 'corp_code', 'fs_div', 'sj_div', 'account_nm', 'target_year']
        df = pd.DataFrame(parsed_data)
        db.to_sql(corp_ticker, df, subset=subset)
        print(f"✅ [{corp_ticker}] yfinance 시장 지표 {len(df)}개 저장 완료")

        # 배당 이력 (Phase 3)
        div_records = _collect_intl_dividend_history(ticker_obj, corp_ticker)
        if div_records:
            db.to_sql(corp_ticker, pd.DataFrame(div_records), subset=subset)
            print(f"   ✅ [{corp_ticker}] 연간 배당 {len(div_records)}건 저장")

        db.close()
        return True

    except Exception as e:
        print(f"🚨 [{corp_ticker}] yfinance 시장 지표 수집 중 에러: {e}")
        return False


def ensure_intl_data(corp_ticker: str) -> bool:
    """
    해외 종목 재무제표가 DB 에 없을 때만 수집한다 (캐시 우선).

    YF_FS source 의 레코드가 하나라도 있으면 수집을 건너뛴다.
    """
    db = conSQL.FS(init_sectors=False)
    has_tbl = db.has_table(corp_ticker)
    df_existing = db.search_sql(corp_ticker) if has_tbl else None
    db.close()

    if df_existing is not None and not df_existing.empty:
        if not df_existing[df_existing["source"] == "YF_FS"].empty:
            print(f"💡 [{corp_ticker}] 재무제표가 이미 DB에 있습니다. 수집을 건너뜁니다.")
            return True

    return fetch_and_save_intl_financials(corp_ticker)
