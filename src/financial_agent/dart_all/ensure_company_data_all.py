"""
한 회사의 10년치 사업보고서를 fnlttSinglAcntAll 로 일괄 수집하는 통합 함수.

cache-aware:
    - 캐시 JSON 이 모두 존재하면 API 호출 0건
    - 일부만 있으면 누락분만 호출
    - 실제 API 호출이 1건이라도 발생하면 COLLECTION_LOG 의 (corp, 'DART_ALL') 시각 갱신

기존 FS_to_SQL.ensure_company_data (Simple API 버전) 와 같은 인터페이스를 제공.
검증 단계에서는 source='DART_ALL' 로 별도 저장되어 기존 'DART' 와 충돌하지 않는다.
"""
from __future__ import annotations

import datetime

from src.financial_agent import conSQL, utils_
from src.financial_agent.dart_all.DART_API_all import call_fin_description_all, FS_DIVS
from src.financial_agent.dart_all.FSpreproc_all import parse_all_response


def run(corp: str, years: int = 10, report: str = "사업보고서") -> dict:
    """
    한 회사의 최근 N년치 사업보고서를 CFS + OFS 모두 수집·적재한다.

    :param corp:  회사명
    :param years: 수집할 연도 수 (기본 10)
    :param report: 보고서 종류 (현재는 '사업보고서'만 지원)
    :return: 결과 요약 dict
        {
            'corp': 회사명,
            'api_calls':   실제 HTTP 호출 수,
            'cache_hits':  캐시 활용 횟수,
            'rows_saved':  DB 에 저장된 row 수,
            'errors':      에러 카운트,
            'updated_log': COLLECTION_LOG 갱신 여부,
        }
    """
    current_year = datetime.datetime.now().year
    start_year = current_year - (years - 1)

    summary = {
        'corp':        corp,
        'api_calls':   0,
        'cache_hits':  0,
        'rows_saved':  0,
        'errors':      0,
        'updated_log': False,
    }

    # stock_code 1회만 조회하여 모든 row 에 동일 적용
    stock_code = str(utils_.call_stock_code(corp) or "")

    db = conSQL.FS(init_sectors=False)

    any_api_called = False
    all_dfs = []

    for year in range(start_year, current_year + 1):
        for fs_div in FS_DIVS:
            file_path, was_api = call_fin_description_all(
                corp=corp, year=year, report=report, fs_div=fs_div,
            )
            if was_api:
                summary['api_calls'] += 1
                any_api_called = True
            else:
                summary['cache_hits'] += 1

            if file_path is None:
                # 빈 응답(013) 또는 에러 — 정상 진행 (단독사의 CFS 빈 경우 등)
                continue

            df = parse_all_response(
                file_path, fs_div_filter=fs_div, stock_code=stock_code,
            )
            if df.empty:
                continue
            all_dfs.append(df)

    if all_dfs:
        import pandas as pd
        combined = pd.concat(all_dfs, ignore_index=True)
        # 중복 제거 (동일 fs_div 안에서)
        subset = ['source', 'corp_code', 'fs_div', 'sj_div', 'account_nm', 'target_year']
        combined = combined.drop_duplicates(subset=subset, keep='last')

        # account_id 컬럼은 기존 테이블에 없을 수 있으므로 conSQL 호환을 위해 분리
        # → to_sql 은 pandas to_sql 을 사용하므로 신규 컬럼이 있으면 자동으로 ALTER 됨
        ok = db.to_sql(corp, combined, subset=subset)
        if ok:
            summary['rows_saved'] = len(combined)
        else:
            summary['errors'] += 1

    if any_api_called:
        db.log_collection(corp, 'DART_ALL')
        summary['updated_log'] = True

    db.close()
    return summary


def run_many(corps: list[str], years: int = 10) -> list[dict]:
    """여러 회사를 순차 처리. 회사 단위 try/except 로 한 회사 실패해도 진행."""
    results = []
    for i, corp in enumerate(corps, 1):
        print(f"\n[{i}/{len(corps)}] {corp} 수집 시작...")
        try:
            summary = run(corp, years=years)
            print(
                f"  → API {summary['api_calls']}건, 캐시 {summary['cache_hits']}건, "
                f"DB row {summary['rows_saved']}개"
            )
            results.append(summary)
        except Exception as e:
            print(f"  🚨 [{corp}] 수집 실패: {e}")
            results.append({'corp': corp, 'errors': 1, 'exception': str(e)})
    return results
