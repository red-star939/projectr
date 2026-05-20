"""
keyword_index ChromaDB 1회 구축 스크립트 (Phase 2).

SECTORS 테이블에서 시드를 추출하여 의미 검색 인덱스를 구축한다.
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

from src.financial_agent import keyword_index


def main():
    print("📋 KeywordIndex 구축 시작 (SECTORS 기반)")
    t_start = time.time()
    count = keyword_index.build_index()
    elapsed = time.time() - t_start

    print(f"\n📊 결과")
    print(f"  적재 키워드 수: {count}개")
    print(f"  소요 시간:     {elapsed:.1f}초")


if __name__ == "__main__":
    main()
