"""
DART (fnlttSinglAcnt) vs DART_ALL (fnlttSinglAcntAll) 결과 비교 스크립트.

목적:
    1. 동일 회사·연도에서 양 API 가 보고하는 공통 계정의 수치가 일치하는지 확인 (A-3: CFS/OFS 빈 케이스 포함)
    2. DART_ALL 에만 있는 신규 계정 카운트
    3. account_alias 사전에 매칭되지 않은 unmatched 계정 출력 (A-1 부담 파악)

사용:
    py scripts/compare_dart_simple_vs_all.py            # FS.db 내 한국 회사 전체
    py scripts/compare_dart_simple_vs_all.py 삼성전자       # 특정 회사
"""
from __future__ import annotations

import sys
from pathlib import Path
from collections import Counter

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from src.financial_agent import conSQL
from src.financial_agent.dart_all.account_alias import DART_ACCOUNT_ALIAS, normalize_account_name


def _latest_simple(df_corp: pd.DataFrame, account: str) -> tuple[float | None, int | None]:
    """기존 DART (Simple) 에서 최신 연도 값."""
    sub = df_corp[(df_corp['source'] == 'DART') & (df_corp['account_nm'] == account)]
    if sub.empty:
        return None, None
    for fs_type in ('CFS', 'OFS'):
        t = sub[sub['fs_div'] == fs_type]
        if not t.empty:
            row = t.sort_values('target_year', ascending=False).iloc[0]
            try:
                return float(row['amount']), int(row['target_year'])
            except (TypeError, ValueError):
                pass
    return None, None


def _latest_all(df_corp: pd.DataFrame, account: str, fs_div: str = 'CFS') -> tuple[float | None, int | None]:
    """신규 DART_ALL 에서 특정 fs_div 의 최신 연도 값."""
    sub = df_corp[
        (df_corp['source'] == 'DART_ALL')
        & (df_corp['account_nm'] == account)
        & (df_corp['fs_div'] == fs_div)
    ]
    if sub.empty:
        return None, None
    row = sub.sort_values('target_year', ascending=False).iloc[0]
    try:
        return float(row['amount']), int(row['target_year'])
    except (TypeError, ValueError):
        return None, None


# 비교 대상 핵심 계정 (양 API 에 모두 존재해야 정상)
COMMON_ACCOUNTS = [
    '매출액', '영업이익', '당기순이익',
    '자산총계', '부채총계', '자본총계',
    '유동자산', '유동부채',
]


def compare_corp(corp: str):
    """단일 회사의 Simple vs All 결과 비교."""
    db = conSQL.FS(init_sectors=False)
    df = db.search_sql(corp)
    db.close()

    if df is None or df.empty:
        print(f"  ⚠️ [{corp}] DB 에 데이터 없음")
        return

    has_simple = not df[df['source'] == 'DART'].empty
    has_all = not df[df['source'] == 'DART_ALL'].empty

    print(f"\n┌─ [{corp}] " + "─" * (54 - len(corp)))
    print(f"│  Simple(DART) rows: {len(df[df['source'] == 'DART']):4d}   |   "
          f"All(DART_ALL) rows: {len(df[df['source'] == 'DART_ALL']):4d}")

    if not has_simple:
        print(f"│  ⚠️ Simple 데이터 없음 — 비교 스킵")
        return
    if not has_all:
        print(f"│  ⚠️ All 데이터 없음 — migrate_dart_to_all.py 먼저 실행")
        return

    # 1. CFS/OFS 가용성 (A-3)
    cfs_cnt = len(df[(df['source'] == 'DART_ALL') & (df['fs_div'] == 'CFS')])
    ofs_cnt = len(df[(df['source'] == 'DART_ALL') & (df['fs_div'] == 'OFS')])
    print(f"│  All CFS rows: {cfs_cnt:4d}   |   All OFS rows: {ofs_cnt:4d}")
    if cfs_cnt == 0:
        print(f"│  💡 단독사 케이스 (CFS 없음) — OFS 만 사용됨")
    if ofs_cnt == 0 and cfs_cnt > 0:
        print(f"│  💡 연결재무제표만 있는 회사 — OFS 없음")

    # 2. 공통 계정 수치 비교
    print(f"│  ── 공통 계정 수치 비교 (Simple CFS vs All CFS) ──")
    mismatches = 0
    for acct in COMMON_ACCOUNTS:
        s_val, s_yr = _latest_simple(df, acct)
        a_val, a_yr = _latest_all(df, acct, fs_div='CFS')
        if s_val is None and a_val is None:
            continue
        if s_val is None:
            print(f"│    {acct:10s}  Simple=N/A     All={a_val:>20,.0f}({a_yr})  ← NEW")
            continue
        if a_val is None:
            # All CFS 가 비어있으면 OFS 도 확인
            a_val, a_yr = _latest_all(df, acct, fs_div='OFS')
            if a_val is None:
                print(f"│    {acct:10s}  Simple={s_val:>20,.0f}({s_yr})  All=N/A")
                mismatches += 1
                continue
        # 수치 일치 확인 (1% 오차 허용)
        if s_val != 0:
            diff_pct = abs(a_val - s_val) / abs(s_val) * 100
        else:
            diff_pct = 0 if a_val == 0 else 100
        ok = '✓' if diff_pct < 1.0 else '⚠️'
        if diff_pct >= 1.0:
            mismatches += 1
        print(f"│    {acct:10s}  Simple={s_val:>20,.0f}({s_yr})  "
              f"All={a_val:>20,.0f}({a_yr})  diff={diff_pct:5.2f}% {ok}")

    # 3. unmatched (정규화 안 된) 계정 카운트 (A-1)
    raw_unmatched_count = 0
    canonical_set = set(DART_ACCOUNT_ALIAS.keys())
    all_df = df[df['source'] == 'DART_ALL']
    all_accounts = set(all_df['account_nm'].unique())
    unmatched = all_accounts - canonical_set
    raw_unmatched_count = len(unmatched)

    print(f"│  All-만 추가 계정 수: {len(all_accounts - {a for a in all_accounts if a in canonical_set}):4d}")
    print(f"│  ALIAS 사전 미등록 계정 수: {raw_unmatched_count:4d}")
    if raw_unmatched_count > 0:
        sample = sorted(unmatched)[:10]
        print(f"│    샘플 10개: {sample}")
    if mismatches > 0:
        print(f"│  ⚠️ 수치 불일치 {mismatches}건 발견 — 상세 위 표 참조")
    else:
        print(f"│  ✅ 모든 공통 계정 수치 일치")
    print("└" + "─" * 60)


def collect_unmatched_summary(corps: list[str]):
    """전체 회사에서 unmatched 계정명을 빈도순으로 집계."""
    all_unmatched = Counter()
    canonical_set = set(DART_ACCOUNT_ALIAS.keys())

    for corp in corps:
        db = conSQL.FS(init_sectors=False)
        df = db.search_sql(corp)
        db.close()
        if df is None or df.empty:
            continue
        all_df = df[df['source'] == 'DART_ALL']
        if all_df.empty:
            continue
        for acct in all_df['account_nm']:
            if acct not in canonical_set:
                all_unmatched[acct] += 1

    if not all_unmatched:
        print("\n✅ 모든 회사에서 ALIAS 사전이 완전히 커버됨")
        return

    print(f"\n[전체 unmatched 빈도 Top 30]")
    print(f"  (사전 추가 검토 대상)")
    for acct, cnt in all_unmatched.most_common(30):
        print(f"  {cnt:4d}건  '{acct}'")


def main():
    args = sys.argv[1:]
    if args:
        corps = args
    else:
        # FS.db 의 한국 회사 자동 탐지
        db = conSQL.FS(init_sectors=False)
        try:
            tables = pd.read_sql_query(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' AND name NOT IN ('SECTORS', 'COLLECTION_LOG')",
                db.conn,
            )['name'].tolist()
        finally:
            db.close()
        corps = tables

    print(f"📋 비교 대상 {len(corps)}개 회사")

    for corp in corps:
        compare_corp(corp)

    collect_unmatched_summary(corps)


if __name__ == "__main__":
    main()
