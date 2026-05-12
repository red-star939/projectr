"""
DART 사업보고서 전체계정 API (fnlttSinglAcntAll) 호출자.

기존 DART_API.py 의 fnlttSinglAcnt (주요계정 ~25개) 와 달리,
이 모듈은 fnlttSinglAcntAll 을 호출하여 전체 세부계정을 받아온다.

특징:
    - fs_div 파라미터가 필수 ('CFS'=연결재무제표, 'OFS'=별도재무제표)
    - 회사·연도·fs_div 당 1회 호출
    - 결과는 data/Financial_Statement_all/{corp}/ 에 캐시
    - 캐시 hit 여부를 반환값으로 알려 호출자가 COLLECTION_LOG 갱신 여부 판단 가능
"""
from __future__ import annotations

import os
import json
import requests
from config import DART_API_KEY
from src.financial_agent import utils_

URL = "https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json"

REPRT_CODES = {
    '사업보고서':   '11011',
    '반기보고서':   '11012',
    '1분기보고서':  '11013',
    '3분기보고서':  '11014',
}

FS_DIVS = ('CFS', 'OFS')  # 연결재무제표 / 별도재무제표

# 기존 캐시 (data/Financial_Statement/) 와 분리
CACHE_ROOT = "data/Financial_Statement_all"


def _cache_path(corp: str, year: int, report: str, fs_div: str) -> str:
    """캐시 파일 경로."""
    return os.path.join(
        CACHE_ROOT, corp, f"{corp}_{year}_{report}_{fs_div}.json"
    )


def call_fin_description_all(
    corp: str,
    year: int = 2025,
    report: str = "사업보고서",
    fs_div: str = "CFS",
) -> tuple[str | None, bool]:
    """
    DART fnlttSinglAcntAll 호출 (단일 회사·연도·fs_div).

    :param corp:   회사명 (CORPCODE.xml 등록)
    :param year:   사업연도
    :param report: 보고서 종류 ('사업보고서' 등)
    :param fs_div: 'CFS' (연결) | 'OFS' (별도)
    :return: (cache_file_path | None, was_api_call: bool)
             - cache_file_path: 성공 시 캐시 JSON 경로, 실패/데이터 없음 시 None
             - was_api_call:    True 면 실제 HTTP 호출 발생, False 면 캐시 hit
    """
    if fs_div not in FS_DIVS:
        raise ValueError(f"fs_div must be 'CFS' or 'OFS', got {fs_div!r}")
    if report not in REPRT_CODES:
        raise ValueError(f"unknown report {report!r}")

    if corp not in utils_.corp_code:
        print(f"⚠️ [{corp}] CORPCODE.xml 에 등록되지 않은 회사입니다.")
        return None, False

    file_path = _cache_path(corp, year, report, fs_div)

    # 캐시 hit
    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                json.load(f)  # 손상 검사만
            return file_path, False
        except json.JSONDecodeError:
            print(f"🚨 캐시 파일 손상: {file_path} (삭제 후 재수집 시도)")
            os.remove(file_path)

    # 실제 API 호출
    corp_code = f"{utils_.corp_code[corp]:0>8}"
    params = {
        'crtfc_key': DART_API_KEY,
        'corp_code': corp_code,
        'bsns_year': year,
        'reprt_code': REPRT_CODES[report],
        'fs_div':     fs_div,
    }

    try:
        response = requests.get(URL, params=params, timeout=30)
    except requests.RequestException as e:
        print(f"🚨 [{corp} {year} {fs_div}] HTTP 요청 실패: {e}")
        return None, True

    if response.status_code != 200:
        print(f"🚨 [{corp} {year} {fs_div}] HTTP {response.status_code}")
        return None, True

    try:
        data = response.json()
    except json.JSONDecodeError as e:
        print(f"🚨 [{corp} {year} {fs_div}] 응답 파싱 실패: {e}")
        return None, True

    # DART status 코드 처리
    status = data.get('status')
    if status != '000':
        # 013 = 조회된 데이터 없음 (정상적인 빈 응답, 예: 단독사의 CFS)
        if status == '013':
            return None, True
        msg = data.get('message', 'unknown')
        print(f"⚠️ [{corp} {year} {fs_div}] DART 응답 코드 {status}: {msg}")
        return None, True

    # 정상 응답 → 캐시 저장
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"   ✅ [{corp} {year} {fs_div}] 수집 완료 → {file_path}")
    return file_path, True
