"""
DART 전체계정(fnlttSinglAcntAll) 기반 재무제표 수집 패키지.

기존 src/financial_agent/DART_API.py (fnlttSinglAcnt, 주요계정 ~25개) 와
독립적으로 동작하며, source='DART_ALL' 태그로 FS.db 에 저장된다.

모듈 구성:
    account_alias       — DART 계정명 표기 변동 정규화 사전
    DART_API_all        — fnlttSinglAcntAll 호출 (단일 회사·연도·fs_div)
    FSpreproc_all       — 응답 JSON → DataFrame 파싱 + 계정명 정규화
    ensure_company_data_all — cache-aware 한 회사 10년치 일괄 수집

사용 예:
    from src.financial_agent.dart_all import ensure_company_data_all
    ensure_company_data_all.run("삼성전자")
"""
