"""
해외 종목용 마크다운 보고서 생성.

fs_report_test.py 의 해외 버전.
YF_FS(재무제표) + YFINANCE(시장지표) + INDICATOR(계산지표) 를 조합하여
영문 템플릿 기반 보고서를 반환한다.
"""
import pandas as pd
from datetime import datetime

from src.financial_agent.Extract_corr import is_suspicious_value

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

# INDICATOR fs_div → 카테고리 영문 제목
_FSDIV_TITLE = {
    'VAL':    'Valuation',
    'PROF':   'Profitability & Efficiency',
    'GROWTH': 'Growth',
    'STAB':   'Stability & Health',
    'CF':     'Cash Flow Quality',
    'DIV':    'Dividend',
    'MKT':    'Market / Sentiment',
}
_FSDIV_ORDER = ['VAL', 'PROF', 'GROWTH', 'STAB', 'CF', 'DIV', 'MKT']


def _yf(yf_info: dict, key: str, default: str = "N/A") -> str:
    v = yf_info.get(key, default)
    return str(v) if v not in (None, "nan", "") else default


def _fmt_indicator(amount, unit, account_nm: str | None = None) -> str:
    """INDICATOR 값을 단위에 맞춰 표시 문자열로 변환. 합리적 범위 이탈 시 ⚠️ 마커."""
    try:
        v = float(amount)
    except (TypeError, ValueError):
        return "N/A"
    if unit == '%':
        s = f"{v:.2f}%"
    elif unit == 'x':
        s = f"{v:.2f}x"
    elif unit == '일':
        s = f"{v:.1f} days"
    elif unit == '점수':
        s = f"{v:.2f}"
    else:
        s = f"{v:,.0f}"

    if account_nm and is_suspicious_value(account_nm, v):
        s += " ⚠️"
    return s


def _build_indicator_sections(ind_df: pd.DataFrame) -> str:
    """INDICATOR DataFrame → 카테고리별 마크다운 테이블 묶음 (영문)."""
    if ind_df is None or ind_df.empty:
        return "*No computed indicators available.*"

    latest = (ind_df.sort_values('target_year', ascending=False)
                    .drop_duplicates(subset=['account_nm'], keep='first'))

    md = ""
    for fs_div in _FSDIV_ORDER:
        rows = latest[latest['fs_div'] == fs_div]
        if rows.empty:
            continue
        title = _FSDIV_TITLE.get(fs_div, fs_div)
        md += f"\n### {title}\n"
        md += "| Metric | Value | Source |\n| :--- | ---: | :--- |\n"
        for _, r in rows.iterrows():
            val = _fmt_indicator(r['amount'], r['sj_div'], r['account_nm'])
            src = str(r.get('report_type', ''))
            md += f"| **{r['account_nm']}** | {val} | `{src}` |\n"
    return md or "*No categorised indicators available.*"


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

    # ── 3. INDICATOR 섹션 ────────────────────────────────────────
    ind_df = df[df["source"] == "INDICATOR"] if "source" in df.columns else pd.DataFrame()
    indicator_md = _build_indicator_sections(ind_df)

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
| **Market Cap** | {m_cap_str} | `yfinance` |

---

## 2. Financial Summary (Annual)
> *Unit: Reporting currency (see Currency above)*

{fs_table_md}

---

## 3. Computed Investment Indicators
> Derived from YF_FS / YFINANCE data via `compute_financial_indicators`.
{indicator_md}

---

**Report Generated**: {today_str}
**Analysis Engine**: International Financial Analyst (Tier 1 · yfinance)
"""
