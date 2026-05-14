"""
회사명·티커 입력 → 정규화된 식별자(canonical id) 변환 엔진.

본 모듈은 사용자가 자연스럽게 입력하는 다양한 표기를 처리한다:
    - "Intel"       → "INTC"     (해외 별칭)
    - "삼성"          → "삼성전자"   (한국 별칭, 부분 일치)
    - "005930"      → "삼성전자"   (KRX 종목코드 직접)
    - "현대차"        → "현대자동차"  (한국 통칭 → DART 정식명)
    - "AAPL"        → "AAPL"     (이미 유효 티커, 그대로 통과)

설계:
    - resolve_korean(query):       국내 분석 컨텍스트
    - resolve_international(query): 해외 분석 컨텍스트
    - 둘 다 ResolveResult 또는 None 반환

향후 Phase 4~6 (Yahoo Search, ChromaDB 임베딩, LLM disambiguation) 통합 시
이 모듈의 resolve_* 가 메인 진입점이 되도록 설계되었다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

import requests

from src.financial_agent import utils_


@dataclass
class ResolveResult:
    """resolve 함수의 결과 컨테이너."""
    canonical: str       # KR: DART 정식 회사명 / INTL: yfinance 티커
    label: str           # UI 표시용 이름 (보통 canonical 과 동일)
    source: str          # 'exact' | 'alias' | 'krx_code' | 'ticker_pass' | 'partial'


# ──────────────────────────────────────────────────────────────
# 입력 정규화
# ──────────────────────────────────────────────────────────────
def normalize_query(s: str) -> str:
    """공백 제거 + 소문자 변환. 빈 입력은 빈 문자열 반환."""
    if not s:
        return ""
    return re.sub(r'\s+', '', str(s)).lower()


# ──────────────────────────────────────────────────────────────
# 해외 종목 별칭 (자연어 → yfinance 티커)
#   정규화된 키 (normalize_query 적용 후 형태) 로 작성
# ──────────────────────────────────────────────────────────────
TICKER_ALIASES: dict[str, str] = {
    # ── 미국 빅테크 ──
    'apple':            'AAPL',
    '애플':              'AAPL',
    'microsoft':        'MSFT',
    '마이크로소프트':       'MSFT',
    'ms':               'MSFT',
    'google':           'GOOGL',
    'googl':            'GOOGL',
    'alphabet':         'GOOGL',
    '구글':              'GOOGL',
    '알파벳':             'GOOGL',
    'amazon':           'AMZN',
    '아마존':             'AMZN',
    'meta':             'META',
    'facebook':         'META',  # 사명 변경 (2021)
    'fb':               'META',
    '페이스북':            'META',
    '메타':              'META',
    'tesla':            'TSLA',
    '테슬라':             'TSLA',
    'nvidia':           'NVDA',
    '엔비디아':            'NVDA',
    'netflix':          'NFLX',
    '넷플릭스':            'NFLX',

    # ── 미국 반도체·하드웨어 ──
    'intel':            'INTC',
    '인텔':              'INTC',
    'amd':              'AMD',
    'broadcom':         'AVGO',
    'qualcomm':         'QCOM',
    '퀄컴':              'QCOM',
    'tsmc':             'TSM',
    'asml':             'ASML',
    'cisco':            'CSCO',
    'oracle':           'ORCL',
    '오라클':             'ORCL',
    'ibm':              'IBM',
    'dell':             'DELL',
    'hp':               'HPQ',

    # ── 미국 금융 ──
    'jpmorgan':         'JPM',
    'jpmorganchase':    'JPM',
    'jpm':              'JPM',
    'berkshirehathaway':'BRK-B',
    'berkshire':        'BRK-B',
    'bankofamerica':    'BAC',
    'visa':             'V',
    '비자':              'V',
    'mastercard':       'MA',
    '마스터카드':           'MA',
    'goldmansachs':     'GS',
    'morganstanley':    'MS',

    # ── 미국 소비재·제약 ──
    'walmart':          'WMT',
    '월마트':             'WMT',
    'costco':           'COST',
    '코스트코':            'COST',
    'homedepot':        'HD',
    'cocacola':         'KO',
    '코카콜라':            'KO',
    'pepsi':            'PEP',
    'pepsico':          'PEP',
    '펩시':              'PEP',
    'nike':             'NKE',
    '나이키':             'NKE',
    'mcdonalds':        'MCD',
    '맥도날드':            'MCD',
    'starbucks':        'SBUX',
    '스타벅스':            'SBUX',
    'disney':           'DIS',
    '디즈니':             'DIS',
    'pfizer':           'PFE',
    '화이자':             'PFE',
    'johnsonandjohnson':'JNJ',
    'jnj':              'JNJ',
    'unitedhealth':     'UNH',
    'eli lilly':        'LLY',
    'ellilly':          'LLY',
    'lilly':            'LLY',
    'merck':            'MRK',
    'abbvie':           'ABBV',
    'procter&gamble':   'PG',
    'proctergamble':    'PG',
    'p&g':              'PG',

    # ── 미국 산업·에너지 ──
    'boeing':           'BA',
    '보잉':              'BA',
    'caterpillar':      'CAT',
    'exxon':            'XOM',
    'exxonmobil':       'XOM',
    '엑손모빌':            'XOM',
    'chevron':          'CVX',
    '쉐브론':             'CVX',

    # ── 일본 ──
    'toyota':           '7203.T',
    '토요타':             '7203.T',
    '도요타':             '7203.T',
    'sony':             '6758.T',
    '소니':              '6758.T',
    'softbank':         '9984.T',
    '소프트뱅크':           '9984.T',
    'nintendo':         '7974.T',
    '닌텐도':             '7974.T',
    'honda':            '7267.T',
    '혼다':              '7267.T',

    # ── 중화권 ──
    'tencent':          '0700.HK',
    '텐센트':             '0700.HK',
    'alibaba':          'BABA',
    '알리바바':            'BABA',
    'baidu':            'BIDU',
    '바이두':             'BIDU',
    'jd':               'JD',
    'pinduoduo':        'PDD',
    'nio':              'NIO',
    'byd':              '1211.HK',

    # ── 영국·유럽 ──
    'shell':            'SHEL',
    'bp':               'BP',
    'astrazeneca':      'AZN',
    'novartis':         'NVS',
    'roche':            'ROG.SW',
    'nestle':           'NESN.SW',
    'lvmh':             'MC.PA',
    'sap':              'SAP.DE',

    # ── 한국 ADR (해외 모드에서 한국 종목을 찾을 때) ──
    'samsung':          '005930.KS',
    'samsungelectronics':'005930.KS',
    'skhynix':          '000660.KS',
    'lgenergysolution': '373220.KS',
    'lges':             '373220.KS',
    'hyundai':          '005380.KS',
    'kia':              '000270.KS',
    'naver':            '035420.KS',
    'kakao':            '035720.KS',
}


# ──────────────────────────────────────────────────────────────
# 한국 종목 별칭 (자연어 → DART 정식 회사명)
# ──────────────────────────────────────────────────────────────
KOREAN_NAME_ALIASES: dict[str, str] = {
    # 통칭 → 정식명
    '현대차':            '현대자동차',
    '기아차':            '기아',          # 사명 변경 (2021: 기아자동차 → 기아)
    '엘지에너지솔루션':      'LG에너지솔루션',
    'lg엔솔':           'LG에너지솔루션',
    '엘지엔솔':           'LG에너지솔루션',
    '엘지화학':           'LG화학',
    '엘지전자':           'LG전자',
    '엘지':             'LG',           # 지주사
    'sk이노':           'SK이노베이션',
    '에스케이하이닉스':       'SK하이닉스',
    '에스케이텔레콤':        'SK텔레콤',
    '한화에어로':          '한화에어로스페이스',
    '삼성바이오':          '삼성바이오로직스',
    '삼성생명':           '삼성생명보험',
    'kt&g':            'KT&G',
    'kb금융':           'KB금융지주',
    '신한':             '신한지주',
    '신한금융':           '신한지주',
    '하나금융':           '하나금융지주',
    '우리금융':           '우리금융지주',
    '셀트리온헬스':         '셀트리온헬스케어',
    '카뱅':             '카카오뱅크',
    '카페이':            '카카오페이',
    '엔씨':             '엔씨소프트',
    '하이브':            '하이브',
    'sm':              '에스엠',
    '에스엠엔터':          '에스엠',

    # 한글 외래어 → 한국 정식명
    '네이버':            'NAVER',
    '카카오뱅크':          '카카오뱅크',
    '셀트리온':           '셀트리온',
    '포스코':            'POSCO홀딩스',
    '포스코홀딩스':         'POSCO홀딩스',

    # 영문 → 한국 정식명
    'samsung':          '삼성전자',
    'samsungelectronics':'삼성전자',
    'skhynix':          'SK하이닉스',
    'naver':            'NAVER',
    'kakao':            '카카오',
    'hyundai':          '현대자동차',
    'hyundaimotor':     '현대자동차',
    'kia':              '기아',
    'lg':               'LG',
    'lgelectronics':    'LG전자',
    'lgchem':           'LG화학',
    'celltrion':        '셀트리온',
    'posco':            'POSCO홀딩스',
}


# ──────────────────────────────────────────────────────────────
# 정규식 패턴
# ──────────────────────────────────────────────────────────────
_KRX_CODE_RE = re.compile(r'^\d{6}$')
_TICKER_RE = re.compile(r'^[A-Z][A-Z0-9\.\-]{0,9}$')   # AAPL / 7203.T / BRK-B 등


# 정규화된 corp_name 캐시 — 매 호출마다 dict 순회 비용 절감
_NORMALIZED_CORP_NAMES: dict[str, str] = {
    normalize_query(name): name for name in utils_.corp_code.keys()
}


# ──────────────────────────────────────────────────────────────
# 한국 컨텍스트 resolver
# ──────────────────────────────────────────────────────────────
def resolve_korean(query: str) -> ResolveResult | None:
    """
    한국 종목 분석 컨텍스트에서 입력 → DART 정식 회사명 변환.

    매칭 순서:
        1. KRX 6자리 종목코드 정확 일치 → 회사명 lookup
        2. DART corp_name 정확 일치 (대소문자·공백 무시)
        3. KOREAN_NAME_ALIASES 별칭 사전
    """
    if not query:
        return None
    raw = str(query).strip()
    n = normalize_query(raw)
    if not n:
        return None

    # 1) KRX 6자리 종목코드
    if _KRX_CODE_RE.match(raw):
        corp = utils_.call_corp_name_by_stock_code(raw)
        if corp:
            return ResolveResult(corp, corp, 'krx_code')

    # 2) DART corp_name 정확 일치 (정규화 후)
    canonical = _NORMALIZED_CORP_NAMES.get(n)
    if canonical:
        return ResolveResult(canonical, canonical, 'exact')

    # 3) 한국 별칭 사전
    alias_target = KOREAN_NAME_ALIASES.get(n)
    if alias_target:
        # 별칭이 가리키는 표준명이 실제 DART 에 있는지 한 번 더 확인
        if alias_target in utils_.corp_code:
            return ResolveResult(alias_target, alias_target, 'alias')
        # DART 미등록일 수도 있음 — 그래도 반환은 함 (사용자 의도 추론용)
        return ResolveResult(alias_target, alias_target, 'alias')

    return None


# ──────────────────────────────────────────────────────────────
# 해외 컨텍스트 resolver
# ──────────────────────────────────────────────────────────────
def resolve_international(query: str) -> ResolveResult | None:
    """
    해외 종목 분석 컨텍스트에서 입력 → yfinance 티커 변환.

    매칭 순서:
        1. TICKER_ALIASES 별칭 사전 (Intel → INTC 등)
        2. 입력이 이미 티커 형태이면 그대로 통과 (AAPL, 7203.T, BRK-B 등)
    """
    if not query:
        return None
    raw = str(query).strip()
    n = normalize_query(raw)
    if not n:
        return None

    # 1) 별칭 사전
    ticker = TICKER_ALIASES.get(n)
    if ticker:
        return ResolveResult(ticker, ticker, 'alias')

    # 2) 티커 형태 그대로 통과
    upper = raw.upper()
    if _TICKER_RE.match(upper):
        return ResolveResult(upper, upper, 'ticker_pass')

    return None


# ──────────────────────────────────────────────────────────────
# 통합 resolver (Phase 5 통합 검색용)
# ──────────────────────────────────────────────────────────────
def resolve(query: str) -> tuple[ResolveResult | None, str | None]:
    """
    market 라디오 없는 통합 검색.
    한국·해외 순으로 시도하여 더 신뢰도 높은 결과 반환.

    :return: (result, market) — market 은 'KR' | 'INTL' | None
    """
    kr = resolve_korean(query)
    if kr and kr.source in ('krx_code', 'exact', 'alias'):
        return kr, 'KR'
    intl = resolve_international(query)
    if intl and intl.source == 'alias':
        return intl, 'INTL'
    if kr:
        return kr, 'KR'
    if intl:
        return intl, 'INTL'
    return None, None


# ══════════════════════════════════════════════════════════════
# Phase 4 — ChromaDB 의미 검색 폴백 (한국)
# ══════════════════════════════════════════════════════════════
def search_korean(query: str, max_results: int = 5) -> list[ResolveResult]:
    """
    한국 종목 의미 검색 폴백. resolve_korean 정확 매칭 실패 시 사용.

    company_index ChromaDB (KRX 상장사 ~2,500개 임베딩) 에 의미 검색.
    오타 / 부분어 / 영문 회사명 모두 대응.

    :return: ResolveResult 리스트 (distance 오름차순). 인덱스 미구축 시 빈 리스트
    """
    if not query or not str(query).strip():
        return []

    try:
        from src.financial_agent import company_index
    except Exception as e:
        print(f"⚠️ company_index 모듈 로드 실패: {e}")
        return []

    hits = company_index.search(query, max_results=max_results)
    if not hits:
        return []

    return [
        ResolveResult(
            canonical=h['corp_name'],
            label=h['corp_name'],
            source=f"embedding(d={h['distance']:.3f})" if h.get('distance') is not None else 'embedding',
        )
        for h in hits
    ]


# ══════════════════════════════════════════════════════════════
# Phase 5 — Yahoo Finance Search 폴백 (해외)
# ══════════════════════════════════════════════════════════════
_YAHOO_SEARCH_URL = "https://query1.finance.yahoo.com/v1/finance/search"
_YAHOO_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)
# 주식 외 종목 제외 (옵션·선물·통화·암호화폐 등)
_VALID_QUOTE_TYPES = {'EQUITY', 'ETF', 'INDEX', 'MUTUALFUND'}


@lru_cache(maxsize=256)
def _yahoo_search_raw(query: str, max_results: int = 10) -> tuple:
    """
    Yahoo Finance Search API 호출 (캐시 적용).

    lru_cache 를 위해 tuple 형태로 반환.
    실패 시 빈 tuple.
    """
    if not query:
        return tuple()
    try:
        resp = requests.get(
            _YAHOO_SEARCH_URL,
            params={
                'q': query,
                'quotesCount': max_results,
                'newsCount': 0,
                'lang': 'en-US',
                'region': 'US',
            },
            headers={'User-Agent': _YAHOO_USER_AGENT},
            timeout=8,
        )
    except requests.RequestException as e:
        print(f"⚠️ Yahoo Search 호출 실패: {e}")
        return tuple()

    if resp.status_code != 200:
        print(f"⚠️ Yahoo Search HTTP {resp.status_code}")
        return tuple()

    try:
        data = resp.json()
    except ValueError:
        return tuple()

    quotes = data.get('quotes', []) or []
    # 주식형만 필터
    filtered = [
        q for q in quotes
        if q.get('quoteType', '').upper() in _VALID_QUOTE_TYPES
    ]
    return tuple(filtered)


def search_international(query: str, max_results: int = 5) -> list[ResolveResult]:
    """
    해외 종목 의미 검색 폴백. resolve_international 별칭 매칭 실패 시 사용.

    Yahoo Finance Search API 로 글로벌 종목 자동 발견:
        "Salesforce" → CRM, "Nestle" → NESN.SW, "POSCO" → PKX 등

    :return: ResolveResult 리스트 (relevance 순)
    """
    if not query or not str(query).strip():
        return []

    raw_quotes = _yahoo_search_raw(query.strip(), max_results=max_results * 2)
    if not raw_quotes:
        return []

    results: list[ResolveResult] = []
    for q in raw_quotes[:max_results]:
        symbol = q.get('symbol', '')
        if not symbol:
            continue
        # 표시 라벨: "AAPL — Apple Inc. (NMS)" 형태
        long_name = q.get('longname') or q.get('shortname') or symbol
        exchange = q.get('exchDisp') or q.get('exchange') or ''
        label = f"{symbol} — {long_name}"
        if exchange:
            label += f" ({exchange})"
        results.append(ResolveResult(
            canonical=symbol,
            label=label,
            source='yahoo_search',
        ))
    return results


# ══════════════════════════════════════════════════════════════
# 통합 검색 (resolve + search 조합)
# ══════════════════════════════════════════════════════════════
def resolve_or_search_korean(query: str, max_candidates: int = 5
                              ) -> tuple[ResolveResult | None, list[ResolveResult]]:
    """
    한국 종목: resolve (Phase 1-3) → search (Phase 4) 순으로 시도.

    :return: (best_match | None, candidates_list)
        - best_match: 정확 매칭 (krx_code/exact) 발견 시. 자동 확정용
        - candidates_list: 의미 검색 결과. UI dropdown 후보로 사용
                           best_match 가 있어도 추가 후보 포함됨
    """
    if not query or not str(query).strip():
        return None, []

    best = resolve_korean(query)
    # 정확 매칭 (krx_code / exact) 은 단독 확정 가능
    if best and best.source in ('krx_code', 'exact'):
        return best, []
    # alias 매칭은 신뢰도 중간 — 추가 후보도 함께 제시
    candidates = search_korean(query, max_results=max_candidates)
    return best, candidates


def resolve_or_search_international(query: str, max_candidates: int = 5
                                     ) -> tuple[ResolveResult | None, list[ResolveResult]]:
    """
    해외 종목: resolve (Phase 1-3) → search (Phase 5 Yahoo) 순으로 시도.

    :return: (best_match | None, candidates_list)
        - best_match: 별칭 매칭 (alias) 시 자동 확정 후보
        - candidates_list: Yahoo Search 결과 (best 가 약하면 검증/대안용)
    """
    if not query or not str(query).strip():
        return None, []

    best = resolve_international(query)
    # alias 는 강한 매칭 — 단독 확정
    if best and best.source == 'alias':
        return best, []
    # ticker_pass 는 약한 매칭 — Yahoo Search 로 검증 + 대안 제시
    candidates = search_international(query, max_results=max_candidates)
    return best, candidates
