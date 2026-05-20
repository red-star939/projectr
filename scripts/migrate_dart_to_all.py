"""
DART_ALL 일괄 수집 스크립트 (관리자 일회성 도구).

목적:
    정식 서비스 전, FS.db 내 모든 회사를 fnlttSinglAcntAll API 로 일괄 재수집.
    source='DART_ALL' 로 저장되며 기존 'DART' (fnlttSinglAcnt) 와 공존한다.

사용:
    py scripts/migrate_dart_to_all.py             # FS.db 내 모든 회사
    py scripts/migrate_dart_to_all.py 삼성전자 LG전자   # 특정 회사만

cache-aware:
    기 수집된 JSON 캐시는 재호출 없이 활용. 강제 재수집을 원하면
    data/Financial_Statement_all/<회사>/ 폴더를 직접 삭제 후 재실행.
"""
from __future__ import annotations

import sys
import time
import sqlite3
from pathlib import Path

# Windows cp949 콘솔 이모지 출력 보호
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 프로젝트 루트를 sys.path 에 추가 (scripts/ 하위에서 실행되는 경우 대비)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.financial_agent.dart_all import ensure_company_data_all


def list_corps_in_db() -> list[str]:
    """FS.db 의 SECTORS 마스터 테이블에서 한국 회사 목록을 가져온다."""
    db_path = PROJECT_ROOT / "data" / "FS.db"
    if not db_path.exists():
        print(f"🚨 FS.db 없음: {db_path}")
        return []
    con = sqlite3.connect(str(db_path))
    try:
        cur = con.execute("SELECT corp_name FROM SECTORS WHERE sector NOT LIKE '해외%'")
        return [row[0] for row in cur.fetchall()]
    except sqlite3.Error:
        # SECTORS 없으면 실제 테이블 목록에서 추정
        cur = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' "
            "AND name NOT IN ('SECTORS', 'COLLECTION_LOG')"
        )
        return [row[0] for row in cur.fetchall()]
    finally:
        con.close()


def main():
    args = sys.argv[1:]

    if args:
        corps = args
        print(f"📋 지정된 회사 {len(corps)}개 처리: {corps}")
    else:
        corps = list_corps_in_db()
        print(f"📋 FS.db 내 회사 {len(corps)}개 일괄 처리: {corps}")

    if not corps:
        print("⚠️ 처리할 회사가 없습니다.")
        return

    t_start = time.time()
    results = ensure_company_data_all.run_many(corps, years=10)
    elapsed = time.time() - t_start

    # 결과 요약
    print("\n" + "=" * 60)
    print("📊 결과 요약")
    print("=" * 60)
    total_api = sum(r.get('api_calls', 0) for r in results)
    total_cache = sum(r.get('cache_hits', 0) for r in results)
    total_rows = sum(r.get('rows_saved', 0) for r in results)
    total_err = sum(r.get('errors', 0) for r in results)

    print(f"  대상 회사:   {len(corps)}개")
    print(f"  API 호출:    {total_api}건")
    print(f"  캐시 활용:   {total_cache}건")
    print(f"  DB 적재 rows: {total_rows}개")
    print(f"  에러:        {total_err}건")
    print(f"  소요 시간:   {elapsed:.1f}초")

    # 회사별 결과
    print("\n[회사별 상세]")
    for r in results:
        corp = r.get('corp', '?')
        if 'exception' in r:
            print(f"  ❌ {corp}: {r['exception']}")
        else:
            api = r.get('api_calls', 0)
            cache = r.get('cache_hits', 0)
            rows = r.get('rows_saved', 0)
            log = "✓" if r.get('updated_log') else "-"
            print(f"  {corp:15s}  API={api:3d}  cache={cache:3d}  rows={rows:5d}  log={log}")


if __name__ == "__main__":
    main()
