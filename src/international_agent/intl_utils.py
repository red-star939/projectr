"""
해외 종목 식별·조회 유틸리티.

- 한국 기업(DART/KRX 기반) vs 해외 기업(ticker 기반) 구분
- yfinance sector 값을 SECTORS 마스터 테이블에 단건 동기화
- yfinance 재무제표 계정명 → DART 스타일 한국어 계정명 매핑 테이블

SECTORS 동기화는 INSERT OR REPLACE 를 사용하므로
기존 한국 기업 데이터에 영향을 주지 않는다.
"""
import re
import sqlite3
from src.financial_agent import utils_
from src.financial_agent import conSQL

# ──────────────────────────────────────────────────────────────
# yfinance 재무제표 계정명 → DART 스타일 계정명 매핑
# (compute_financial_indicators 와 호환되도록 한국어 이름으로 정규화)
# ──────────────────────────────────────────────────────────────
YF_FS_ACCOUNT_MAP: dict[str, str] = {
    # 손익계산서 (IS)
    "Total Revenue":                            "매출액",
    "Operating Revenue":                        "매출액",
    "Operating Income":                         "영업이익",
    "Operating Income Loss":                    "영업이익",
    "EBIT":                                     "영업이익",
    "Net Income":                               "당기순이익",
    "Net Income Common Stockholders":           "당기순이익",
    "Net Income Continuous Operations":         "당기순이익",
    "Net Income Including Noncontrolling Interests": "당기순이익",
    "Gross Profit":                             "매출총이익",
    # 재무상태표 (BS)
    "Total Assets":                             "자산총계",
    "Total Liabilities Net Minority Interest":  "부채총계",
    "Total Debt":                               "부채총계",
    "Stockholders Equity":                      "자본총계",
    "Common Stock Equity":                      "자본총계",
    "Total Equity Gross Minority Interest":     "자본총계",
    "Current Assets":                           "유동자산",
    "Current Liabilities":                      "유동부채",
    # 현금흐름표 (CF) — 현재 compute_financial_indicators 에서는 직접 미사용이나 저장해 둠
    "Operating Cash Flow":                      "영업활동현금흐름",
    "Free Cash Flow":                           "잉여현금흐름",
    "Capital Expenditure":                      "자본적지출",
}


def is_korean_corp(name_or_ticker: str) -> bool:
    """
    DART 코드북에 존재하거나 KRX 종목코드 형식이면 한국 기업으로 판별.
    그 외 모든 입력은 해외 ticker 로 처리한다.
    """
    if name_or_ticker in utils_.corp_code:
        return True
    if re.match(r"^\d{6}$", name_or_ticker):
        return True
    if name_or_ticker.upper().endswith((".KS", ".KQ")):
        return True
    return False


def sync_intl_sector(ticker: str) -> None:
    """
    DB(YFINANCE source)에 저장된 sector 값을 SECTORS 마스터 테이블에
    INSERT OR REPLACE 로 동기화한다.

    기존 한국 기업 행은 절대 덮어쓰지 않으며,
    해당 ticker 행만 삽입/갱신한다.
    """
    db = conSQL.FS(init_sectors=False)
    df = db.search_sql(ticker)

    sector = "해외기업/미분류"
    if df is not None and not df.empty:
        mask = (df["source"] == "YFINANCE") & (df["account_nm"] == "sector")
        sub = df[mask]
        if not sub.empty:
            raw = str(sub.iloc[0]["amount"])
            if raw and raw.lower() != "nan":
                sector = raw

    try:
        cursor = db.conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO SECTORS (corp_name, sector) VALUES (?, ?)",
            (ticker, sector),
        )
        db.conn.commit()
        print(f"✅ [{ticker}] 섹터 동기화 완료: {sector}")
    except sqlite3.Error as e:
        print(f"🚨 [{ticker}] 섹터 동기화 실패: {e}")
    finally:
        db.close()
