"""
fnlttSinglAcntAll 응답 JSON → FS.db DataFrame 파싱.

기존 FS_to_SQL.FSpreproc 와 응답 구조가 달라 별도 파서를 둔다.

응답 필드 차이:
    fnlttSinglAcnt (Simple):
        sj_div, account_nm, fs_div, thstrm_amount, frmtrm_amount, bfefrmtrm_amount
    fnlttSinglAcntAll (All):
        sj_div, account_id (XBRL), account_nm, account_detail,
        fs_div, fs_nm, thstrm_amount, frmtrm_amount, bfefrmtrm_amount, ord

저장 스키마: 기존 to_sql 형식과 동일하되 source='DART_ALL' 태그.
    source      = 'DART_ALL'
    report_type = '사업보고서'
    corp_code   = DART corp_code
    stock_code  = KRX 종목코드
    fs_div      = 'CFS' | 'OFS'  (요청한 값과 동일)
    sj_div      = 응답 그대로 (BS1/IS1/CF1 등)
    account_nm  = normalize_account_name() 으로 정규화된 표준 한국어 계정명
    account_id  = XBRL 표준계정ID (참고용)  ← 신규 컬럼
    target_year = 연도(int)
    amount      = float
"""
from __future__ import annotations

import json
import pandas as pd

from src.financial_agent.dart_all.account_alias import normalize_account_name

# 일반 지표 계산에서 제외할 sj_div
#   SCE (Statement of Changes in Equity, 자본변동표): "자본총계" 시작잔액·기말잔액 등이
#                                                    BS 의 "자본총계" 와 동일 account_nm 으로 충돌
#                                                    → 별도 분석 필요 시 SKIP_SJ_DIVS 에서 제거
SKIP_SJ_DIVS: set[str] = {'SCE'}


def _to_int(amount_str) -> int | None:
    """DART 의 콤마 포함 amount 문자열 → int. 빈값/'-'/공백이면 None."""
    if amount_str is None:
        return None
    s = str(amount_str).strip().replace(',', '')
    if s in ('', '-', 'nan', 'NaN'):
        return None
    # 음수 표기 (1,234) 처리
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    try:
        return int(float(s))
    except (ValueError, TypeError):
        return None


def parse_all_response(
    json_path: str,
    fs_div_filter: str | None = None,
    stock_code: str = "",
) -> pd.DataFrame:
    """
    fnlttSinglAcntAll JSON 파일 → DataFrame.

    응답 row 에는 stock_code 와 fs_div 가 없으므로:
        - fs_div: 호출자가 fs_div_filter 인자로 명시 ('CFS' or 'OFS')
        - stock_code: 호출자가 별도 전달 (utils_.call_stock_code 결과)

    :param json_path:      DART_API_all 가 저장한 캐시 JSON 파일 경로
    :param fs_div_filter:  'CFS' | 'OFS' — 캐시 파일이 어느 fs_div 요청 결과인지
    :param stock_code:     KRX 종목코드 (FS.db 스키마 일관성 위해 채워줌)
    :return: pd.DataFrame  conSQL.to_sql 에 그대로 넘길 수 있는 형식
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"🚨 파싱 실패 ({json_path}): {e}")
        return pd.DataFrame()

    if data.get('status') != '000':
        return pd.DataFrame()

    items = data.get('list', [])
    if not items:
        return pd.DataFrame()

    fs_div_value = fs_div_filter or ""

    records: list[dict] = []
    for item in items:
        sj_div = item.get('sj_div', '')
        if sj_div in SKIP_SJ_DIVS:
            continue
        corp_code  = item.get('corp_code', '')
        raw_acct   = item.get('account_nm', '')
        account_id = item.get('account_id', '')   # XBRL 표준ID (참고)
        account_nm = normalize_account_name(raw_acct)

        try:
            base_year = int(item.get('bsns_year'))
        except (ValueError, TypeError):
            continue

        # 당기/전기/전전기 → 3개 행으로 분리
        periods = [
            (base_year,     item.get('thstrm_amount')),
            (base_year - 1, item.get('frmtrm_amount')),
            (base_year - 2, item.get('bfefrmtrm_amount')),
        ]

        for year, amount_str in periods:
            amount = _to_int(amount_str)
            if amount is None:
                continue
            records.append({
                "source":      "DART_ALL",
                "report_type": "사업보고서",
                "corp_code":   corp_code,
                "stock_code":  stock_code,
                "fs_div":      fs_div_value,
                "sj_div":      sj_div,
                "account_nm":  account_nm,
                "account_id":  account_id,  # 추가 컬럼 — 사후 분석용
                "target_year": year,
                "amount":      amount,
            })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    # 동일 (source, corp_code, fs_div, sj_div, account_nm, target_year) 조합 중복 제거
    subset = ['source', 'corp_code', 'fs_div', 'sj_div', 'account_nm', 'target_year']
    df = df.drop_duplicates(subset=subset, keep='last')
    return df
