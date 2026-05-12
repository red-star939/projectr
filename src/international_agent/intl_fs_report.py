"""
해외 종목용 마크다운 보고서 생성.

fs_report_test.py 의 해외 버전.
YF_FS(재무제표) + YFINANCE(시장지표) + INDICATOR(계산지표) 를 조합하여
영문 템플릿 기반 보고서를 반환한다.
"""
import pandas as pd
from datetime import datetime

# DART 정규화 계정명 → 보고서 표시 영문 레이블
_ACCOUNT_LABEL: dict[str, str] = {
    "매출액":     "Revenue",
    "매출총이익": "Gross Profit",
    "영업이익":   "Operating Income",
    "당기순이익": "Net Income",
    "자산총계":   "Total Assets",
    "부채총계":   "Total Liabilities",
    "자본총계":   "Equity",
    "유동자산":   "Current Assets",
    "유동부채":   "Current Liabilities",
}


def _yf(yf_info: dict, key: str, default: str = "N/A") -> str:
    v = yf_info.get(key, default)
    return str(v) if v not in (None, "nan", "") else default


def _ind(indicators: dict, key: str) -> str:
    v = indicators.get(key)
    try:
        return f"{float(v):.2f}"
    except (TypeError, ValueError):
        return "N/A"


def create_intl_markdown_template(ticker: str, sector: str, df: pd.DataFrame) -> str:
    """
    해외 종목 분석 마크다운 보고서를 생성한다.

    :param ticker:  yfinance 티커 (예: "AAPL")
    :param sector:  섹터명 (SECTORS 테이블 또는 yfinance sector)
    :param df:      FS.db 에서 읽어온 해당 종목의 전체 DataFrame
    :return:        마크다운 문자열
    """
    today_str = datetime.now().strftime("%Y-%m-%d")

    # ── 1. 재무제표 피벗 (YF_FS source) ──────────────────────────
    fs_df = df[df["source"] == "YF_FS"].copy()
    target_accounts = list(_ACCOUNT_LABEL.keys())
    summary_df = fs_df[fs_df["account_nm"].isin(target_accounts)]

    if not summary_df.empty:
        pivot = summary_df.pivot_table(
            index="target_year", columns="account_nm", values="amount", aggfunc="last"
        ).sort_index(ascending=False)
        pivot = pivot.rename(columns=_ACCOUNT_LABEL)
        # 열 순서 고정
        ordered_cols = [v for v in _ACCOUNT_LABEL.values() if v in pivot.columns]
        pivot = pivot[ordered_cols]
        fs_table_md = pivot.to_markdown()
    else:
        fs_table_md = "*No financial statement data available.*"

    # ── 2. 시장 지표 (YFINANCE source) ───────────────────────────
    yf_df = df[df["source"] == "YFINANCE"]
    yf_info = dict(zip(yf_df["account_nm"], yf_df["amount"].astype(str)))

    try:
        m_cap = float(yf_info.get("marketCap", 0))
        m_cap_str = f"{m_cap:,.0f} {_yf(yf_info, 'financialCurrency')}"
    except (ValueError, TypeError):
        m_cap_str = "N/A"

    # ── 3. 투자 지표 (INDICATOR source) ──────────────────────────
    ind_df = df[df["source"] == "INDICATOR"]
    indicators = {}
    for _, row in ind_df.iterrows():
        try:
            indicators[row["account_nm"]] = float(row["amount"])
        except (ValueError, TypeError):
            pass

    # ── 4. 보고서 조립 ────────────────────────────────────────────
    return f"""# 📊 Equity Analysis Report: {ticker}

## 1. Company Overview
| Field | Value | Source |
| :--- | :--- | :--- |
| **Ticker** | {ticker} | `yfinance` |
| **Name** | {_yf(yf_info, 'longName', ticker)} | `yfinance` |
| **Sector** | {sector} | `SECTORS` |
| **Industry** | {_yf(yf_info, 'industryDisp')} | `yfinance` |
| **Exchange** | {_yf(yf_info, 'fullExchangeName')} | `yfinance` |
| **Currency** | {_yf(yf_info, 'financialCurrency')} | `yfinance` |

---

## 2. Financial Summary (Annual)
> *Unit: Reporting currency (see Currency above)*

{fs_table_md}

---

## 3. Valuation
| Metric | Value |
| :--- | :--- |
| **PER (Forward)** | {_ind(indicators, 'PER')}x |
| **PBR** | {_ind(indicators, 'PBR')}x |
| **PSR** | {_ind(indicators, 'PSR')}x |
| **PEG** | {_ind(indicators, 'PEG')}x |
| **EV / EBITDA** | {_ind(indicators, 'EV/EBITDA')}x |
| **Market Cap** | {m_cap_str} |

---

## 4. Profitability & Stability
| Metric | Value |
| :--- | :--- |
| **ROE** | {_ind(indicators, 'ROE')}% |
| **ROA** | {_ind(indicators, 'ROA')}% |
| **Operating Margin** | {_ind(indicators, '영업이익률')}% |
| **Debt Ratio** | {_ind(indicators, '부채비율')}% |
| **Current Ratio** | {_ind(indicators, '유동비율')}% |
| **Operating CF Quality** | {_ind(indicators, '영업CF품질비율')}x |

---

## 5. Dividend
| Metric | Value |
| :--- | :--- |
| **Dividend Yield** | {_ind(indicators, '배당수익률')}% |
| **Payout Ratio** | {_ind(indicators, '배당성향')}% |

---

**Report Generated**: {today_str}
**Analysis Engine**: International Financial Analyst (Tier 1 · yfinance)
"""
