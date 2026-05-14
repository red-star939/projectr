"""
DART CORPCODE → ChromaDB 회사명 인덱스 1회 구축 스크립트 (Phase 4).

사용:
    py scripts/build_company_index.py             # KRX 상장사만 (~2,500개)
    py scripts/build_company_index.py --all       # 비상장 포함 전체 (~107k개)

상장사만으로도 일반 분석에 필요한 모든 거래 가능 종목이 커버됨.
--all 옵션은 인덱싱 시간이 길고 노이즈 (해산사·자회사 등) 가 많아 비추.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from src.financial_agent import company_index


def main():
    listed_only = '--all' not in sys.argv
    scope = "KRX 상장사만" if listed_only else "비상장 포함 전체"
    print(f"📋 CompanyIndex 구축 시작 ({scope})")

    t_start = time.time()
    count = company_index.build_index(listed_only=listed_only)
    elapsed = time.time() - t_start

    print(f"\n📊 결과")
    print(f"  적재 회사 수: {count}개")
    print(f"  소요 시간:   {elapsed:.1f}초")
    print(f"\n💡 검증: scripts/test_company_search.py 또는 Python REPL 에서")
    print(f"        from src.financial_agent import company_index")
    print(f"        company_index.search('삼선전자', max_results=5)")


if __name__ == "__main__":
    main()
