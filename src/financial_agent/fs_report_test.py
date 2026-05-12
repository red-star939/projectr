import pandas as pd
from datetime import datetime

# 카테고리 → 한글 섹션 제목
_FSDIV_TITLE = {
    'VAL':    '밸류에이션',
    'PROF':   '수익성·효율성',
    'GROWTH': '성장성',
    'STAB':   '재무 안정성',
    'CF':     '현금흐름',
    'DIV':    '배당',
    'MKT':    '시장·심리',
}

# 보고서에 노출할 카테고리 순서
_FSDIV_ORDER = ['VAL', 'PROF', 'GROWTH', 'STAB', 'CF', 'DIV', 'MKT']


def _fmt_indicator(amount, unit) -> str:
    """INDICATOR 값을 단위에 맞춰 표시 문자열로 변환."""
    try:
        v = float(amount)
    except (TypeError, ValueError):
        return "N/A"
    if unit == '%':
        return f"{v:.2f}%"
    if unit == 'x':
        return f"{v:.2f}x"
    if unit == '일':
        return f"{v:.1f}일"
    if unit == '점수':
        return f"{v:.2f}점"
    # 원 단위 등 절댓값
    return f"{v:,.0f}"


def _build_indicator_section(ind_df: pd.DataFrame) -> str:
    """INDICATOR DataFrame → 카테고리별 마크다운 테이블 묶음."""
    if ind_df is None or ind_df.empty:
        return "*계산된 투자 지표가 없습니다. compute_financial_indicators 실행 여부를 확인하세요.*"

    # 같은 account_nm 이 여러 번 저장됐을 수 있으므로 최신 연도 한 건만 유지
    latest = (ind_df.sort_values('target_year', ascending=False)
                    .drop_duplicates(subset=['account_nm'], keep='first'))

    section_md = ""
    for fs_div in _FSDIV_ORDER:
        rows = latest[latest['fs_div'] == fs_div]
        if rows.empty:
            continue
        title = _FSDIV_TITLE.get(fs_div, fs_div)
        section_md += f"\n### {title}\n"
        section_md += "| 지표 | 값 | 출처 |\n| :--- | ---: | :--- |\n"
        for _, r in rows.iterrows():
            val = _fmt_indicator(r['amount'], r['sj_div'])
            src = str(r.get('report_type', ''))
            section_md += f"| **{r['account_nm']}** | {val} | `{src}` |\n"

    return section_md or "*분류 가능한 투자 지표가 없습니다.*"


def create_markdown_template(corp, sector, corp_code, stock_code, df):
    """
    DB에서 가져온 DataFrame을 바탕으로 마크다운 보고서를 생성합니다.
    포함 섹션: 메타 → DART 재무추이 → yfinance 시장지표 → INDICATOR 카테고리별 → 종합 의견
    """
    today_str = datetime.now().strftime("%Y-%m-%d")

    # 1. DART 재무 데이터 정리
    dart_df = df[df['fs_div'].isin(['CFS', 'OFS'])]
    target_accounts = ['매출액', '영업이익', '당기순이익', '자산총계', '부채총계', '자본총계']
    summary_df = dart_df[dart_df['account_nm'].isin(target_accounts)]

    if not summary_df.empty:
        pivot_df = summary_df.pivot_table(
            index='target_year', columns='account_nm', values='amount', aggfunc='last'
        ).sort_index(ascending=False)
        fs_table_md = pivot_df.to_markdown()
    else:
        fs_table_md = "*수집된 재무제표 데이터가 없습니다.*"

    # 2. 시장 데이터 정리 (yfinance)
    yf_df = df[df['fs_div'] == 'YF']
    yf_info = dict(zip(yf_df['account_nm'], yf_df['amount']))

    try:
        m_cap = float(yf_info.get('marketCap', 0))
    except (ValueError, TypeError):
        m_cap = 0

    per = yf_info.get('forwardPE', 'N/A')
    pbr = yf_info.get('priceToBook', 'N/A')

    try:
        div_yield = float(yf_info.get('dividendYield', 0)) * 100
    except (ValueError, TypeError):
        div_yield = 0

    # 3. INDICATOR 섹션
    ind_df = df[df['source'] == 'INDICATOR'] if 'source' in df.columns else pd.DataFrame()
    indicator_md = _build_indicator_section(ind_df)

    # 4. 템플릿 조합
    md_content = f"""# 📊 기업 가치 분석 보고서: {corp}

## 1. 기업 기본 정보 (Metadata)
| 항목 | 내용 | 데이터 출처 |
| :--- | :--- | :--- |
| **기업 명칭** | {corp} | `CORPCODE.xml` |
| **섹터(산업)** | {sector} | `Sector.py` |
| **종목 코드** | {stock_code} | `utils_.py` |
| **DART 코드** | {corp_code} | `utils_.py` |

---

## 2. 주요 재무 추이 (DART 공시 정보)
> **출처**: DART (단위: 원)

{fs_table_md}

---

## 3. 실시간 시장 지표 (yfinance 정보)
* **현재 시가총액**: 약 {m_cap:,.0f} 원
* **수익성 지표**: PER `{per}` / PBR `{pbr}`
* **배당 수익률**: `{div_yield:.2f}%`

---

## 4. 투자 지표 (계산값)
> compute_financial_indicators 가 DART/yfinance 데이터로부터 직접 산출한 지표입니다.
{indicator_md}

---

## 5. 시스템 종합 의견
* 본 리포트는 **Financial_agent** 금융 에이전트에 의해 자동 생성되었습니다.
* 해당 기업은 **{sector}** 섹터에 소속되어 있으며, 현재 분석 시점의 데이터 무결성이 확인되었습니다.

---
**보고서 생성 일시**: {today_str}
**분석 도구**: Financial Analyst (v0.2)
"""
    return md_content
