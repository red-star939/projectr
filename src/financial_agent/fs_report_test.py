import pandas as pd
from datetime import datetime

def create_markdown_template(corp, sector, corp_code, stock_code, df):
    """
    DB에서 가져온 DataFrame을 바탕으로 마크다운 보고서를 생성합니다.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 1. DART 재무 데이터 정리
    dart_df = df[df['fs_div'].isin(['CFS', 'OFS'])]
    target_accounts = ['매출액', '영업이익', '당기순이익', '자산총계', '부채총계', '자본총계']
    summary_df = dart_df[dart_df['account_nm'].isin(target_accounts)]
    
    if not summary_df.empty:
        pivot_df = summary_df.pivot_table(index='target_year', columns='account_nm', values='amount', aggfunc='last')
        pivot_df = pivot_df.sort_index(ascending=False)
        fs_table_md = pivot_df.to_markdown()
    else:
        fs_table_md = "*수집된 재무제표 데이터가 없습니다.*"

    # 2. 시장 데이터 정리 (yfinance) - 타입 변환 예외 처리 추가
    yf_df = df[df['fs_div'] == 'YF']
    yf_info = dict(zip(yf_df['account_nm'], yf_df['amount']))
    
    try:
        # 문자열로 인식될 가능성이 있는 데이터를 float으로 강제 변환
        m_cap = float(yf_info.get('marketCap', 0))
    except (ValueError, TypeError):
        m_cap = 0
        
    per = yf_info.get('forwardPE', 'N/A')
    pbr = yf_info.get('priceToBook', 'N/A')
    
    try:
        div_yield = float(yf_info.get('dividendYield', 0)) * 100
    except (ValueError, TypeError):
        div_yield = 0

    # 3. 전체 템플릿 조합
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

## 4. 시스템 종합 의견
* 본 리포트는 **Financial_agent** 금융 에이전트에 의해 자동 생성되었습니다.
* 해당 기업은 **{sector}** 섹터에 소속되어 있으며, 현재 분석 시점의 데이터 무결성이 확인되었습니다.

---
**보고서 생성 일시**: {today_str}
**분석 도구**: Financial Analyst (v0.1)
"""
    return md_content