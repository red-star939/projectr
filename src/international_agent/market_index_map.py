"""
거래소 코드 → 벤치마크 지수 매핑.

yfinance info['exchange'] 값을 키로 사용하며,
DB에 저장된 exchange 값을 우선 조회하고 없을 때만 yfinance를 한 번 호출한다.
"""
import yfinance as yf
from src.financial_agent import conSQL

# yfinance info['exchange'] → 벤치마크 지수 티커
EXCHANGE_TO_INDEX: dict[str, str] = {
    # 한국
    "KSC": "^KS11",      # KOSPI
    "KOE": "^KQ11",      # KOSDAQ
    # 미국
    "NMS": "^GSPC",      # NASDAQ
    "NYQ": "^GSPC",      # NYSE
    "NGM": "^GSPC",      # NASDAQ Global Market
    "NCM": "^GSPC",      # NASDAQ Capital Market
    "PCX": "^GSPC",      # NYSE ARCA
    "BTS": "^GSPC",      # BATS
    # 일본
    "TYO": "^N225",      # 니케이 225
    # 영국
    "LSE": "^FTSE",      # FTSE 100
    # 독일
    "FRA": "^GDAXI",     # DAX
    # 홍콩
    "HKG": "^HSI",       # 항셍
    # 캐나다
    "TOR": "^GSPTSE",    # TSX Composite
    # 호주
    "ASX": "^AXJO",      # ASX 200
    # 기본값 (알 수 없는 거래소)
    "DEFAULT": "^GSPC",
}

# 지수 티커 → 사람이 읽기 좋은 표시명
INDEX_DISPLAY_NAME: dict[str, str] = {
    "^KS11":    "KOSPI",
    "^KQ11":    "KOSDAQ",
    "^GSPC":    "S&P 500",
    "^N225":    "Nikkei 225",
    "^FTSE":    "FTSE 100",
    "^GDAXI":   "DAX",
    "^HSI":     "Hang Seng",
    "^GSPTSE":  "TSX",
    "^AXJO":    "ASX 200",
}


def get_benchmark_index(corp_ticker: str) -> str:
    """
    종목 티커에 대응하는 벤치마크 지수 티커를 반환한다.

    DB에 이미 저장된 exchange 값을 우선 사용하며,
    없을 때만 yfinance를 한 번 호출한다 (추가 API 호출 최소화).
    """
    db = conSQL.FS(init_sectors=False)
    df = db.search_sql(corp_ticker)
    db.close()

    exchange = None
    if df is not None and not df.empty:
        mask = (df["source"] == "YFINANCE") & (df["account_nm"] == "exchange")
        sub = df[mask]
        if not sub.empty:
            val = str(sub.iloc[0]["amount"])
            if val and val != "nan":
                exchange = val

    if not exchange:
        try:
            exchange = yf.Ticker(corp_ticker).info.get("exchange", "DEFAULT")
        except Exception as e:
            print(f"⚠️ [{corp_ticker}] 거래소 조회 실패: {e}")
            exchange = "DEFAULT"

    return EXCHANGE_TO_INDEX.get(exchange, EXCHANGE_TO_INDEX["DEFAULT"])


def get_current_index_value(index_ticker: str) -> float | None:
    """지수의 최신 종가를 반환한다."""
    try:
        hist = yf.Ticker(index_ticker).history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception as e:
        print(f"🚨 [{index_ticker}] 지수 현재가 조회 중 에러: {e}")
    return None
