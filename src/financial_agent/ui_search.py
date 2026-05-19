"""
통합 자동완성 검색 UI 컴포넌트 (Streamlit).

세 가지 모드 제공:
    company  — 회사명·티커 자동완성 (Phase 1~5 resolver 활용)
    keyword  — 키워드(섹터·테마) 자동완성 (keyword_index 활용)
    unified  — 위 두 가지 통합 (회사 + 키워드)

내부적으로 streamlit-searchbox 를 사용해 type-ahead UX 를 제공한다.
선택된 결과는 단순 문자열(canonical id 또는 키워드)을 반환.

사용 예:
    from src.financial_agent import ui_search

    # Financial Agent — 회사명만
    target = ui_search.render_search("분석 대상", mode='company', key='fs_t')

    # News Agent — 회사 + 키워드 통합
    keyword = ui_search.render_search("분석 키워드", mode='unified', key='ns_kw')
"""
from __future__ import annotations

from streamlit_searchbox import st_searchbox

from src.financial_agent import company_resolver, keyword_index


# ──────────────────────────────────────────────────────────────
# 내부 search functions — st_searchbox 콜백
# 반환 형식: [(label, value), ...]  label 은 UI 표시, value 는 선택 반환값
# ──────────────────────────────────────────────────────────────
def _search_company(query: str) -> list[tuple[str, str]]:
    """회사명·티커 검색 (KR + INTL 통합)."""
    if not query or not query.strip():
        return []

    results: list[tuple[str, str]] = []
    seen: set[str] = set()

    # 1) 한국 우선
    best_kr, cand_kr = company_resolver.resolve_or_search_korean(query, max_candidates=5)
    if best_kr and best_kr.canonical not in seen:
        results.append((f"🇰🇷 {best_kr.canonical}  · {best_kr.source}", best_kr.canonical))
        seen.add(best_kr.canonical)
    for c in cand_kr:
        if c.canonical in seen:
            continue
        results.append((f"🇰🇷 {c.canonical}  · {c.source}", c.canonical))
        seen.add(c.canonical)
        if len(results) >= 5:
            break

    # 2) 해외
    best_intl, cand_intl = company_resolver.resolve_or_search_international(query, max_candidates=5)
    if best_intl and best_intl.canonical not in seen:
        results.append((f"🌍 {best_intl.canonical}  · {best_intl.source}", best_intl.canonical))
        seen.add(best_intl.canonical)
    for c in cand_intl:
        if c.canonical in seen:
            continue
        label_text = c.label if c.source == 'yahoo_search' else c.canonical
        results.append((f"🌍 {label_text}", c.canonical))
        seen.add(c.canonical)
        if len(results) >= 10:
            break

    return results


def _search_keyword(query: str) -> list[tuple[str, str]]:
    """키워드(섹터) 검색."""
    if not query or not query.strip():
        return []
    hits = keyword_index.search(query, max_results=8)
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for h in hits:
        kw = h.get('keyword', '')
        if not kw or kw in seen:
            continue
        d = h.get('distance')
        suffix = f"  · d={d:.2f}" if d is not None else ""
        out.append((f"🔍 {kw}{suffix}", kw))
        seen.add(kw)
    return out


def _search_unified(query: str) -> list[tuple[str, str]]:
    """회사 + 키워드 통합 (회사 후보 위, 키워드 후보 아래)."""
    if not query or not query.strip():
        return []

    company_results = _search_company(query)[:6]
    keyword_results = _search_keyword(query)[:4]

    # value 기준 중복 제거 (label 만 다른 경우 첫 번째 채택)
    merged: list[tuple[str, str]] = []
    seen: set[str] = set()
    for label, value in (company_results + keyword_results):
        if value in seen:
            continue
        merged.append((label, value))
        seen.add(value)
    return merged


def _search_company_kr(query: str) -> list[tuple[str, str]]:
    """한국 종목 전용 (FS 의 국내 모드 라디오 선택 시)."""
    if not query or not query.strip():
        return []
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    best, candidates = company_resolver.resolve_or_search_korean(query, max_candidates=8)
    if best and best.canonical not in seen:
        results.append((f"🇰🇷 {best.canonical}  · {best.source}", best.canonical))
        seen.add(best.canonical)
    for c in candidates:
        if c.canonical in seen:
            continue
        results.append((f"🇰🇷 {c.canonical}  · {c.source}", c.canonical))
        seen.add(c.canonical)
        if len(results) >= 10:
            break
    return results


def _search_company_intl(query: str) -> list[tuple[str, str]]:
    """해외 종목 전용 (FS 의 해외 모드 라디오 선택 시)."""
    if not query or not query.strip():
        return []
    results: list[tuple[str, str]] = []
    seen: set[str] = set()
    best, candidates = company_resolver.resolve_or_search_international(query, max_candidates=8)
    if best and best.canonical not in seen:
        results.append((f"🌍 {best.canonical}  · {best.source}", best.canonical))
        seen.add(best.canonical)
    for c in candidates:
        if c.canonical in seen:
            continue
        label_text = c.label if c.source == 'yahoo_search' else c.canonical
        results.append((f"🌍 {label_text}", c.canonical))
        seen.add(c.canonical)
        if len(results) >= 10:
            break
    return results


_SEARCH_FNS = {
    'company':         _search_company,        # KR + INTL 통합
    'company_kr':      _search_company_kr,     # KR 전용
    'company_intl':    _search_company_intl,   # INTL 전용
    'keyword':         _search_keyword,
    'unified':         _search_unified,
}


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────
def render_search(
    label: str,
    mode: str = 'unified',
    key: str = 'search',
    placeholder: str | None = None,
    default: str | None = None,
) -> str | None:
    """
    Type-ahead 자동완성 검색 입력.

    :param label:       위젯 라벨
    :param mode:        'company' | 'keyword' | 'unified'
    :param key:         Streamlit 위젯 고유 key (충돌 방지)
    :param placeholder: hint 텍스트
    :param default:     초기 표시 값
    :return:            사용자가 선택한 값 (canonical id 또는 키워드). 미선택 시 None
    """
    if mode not in _SEARCH_FNS:
        raise ValueError(
            f"mode 는 {list(_SEARCH_FNS)} 중 하나여야 합니다 (got {mode!r})"
        )

    if placeholder is None:
        placeholder = {
            'company':      "회사명 / 티커 / 종목코드 (예: 삼성전자, AAPL, 005930)",
            'company_kr':   "국내 회사명 / KRX 종목코드 (예: 삼성전자, 005930, 현대차)",
            'company_intl': "해외 회사명 / 티커 (예: Apple, AAPL, 인텔, 7203.T)",
            'keyword':      "키워드 입력 (예: 반도체, 바이오, 2차전지)",
            'unified':      "회사명 또는 키워드 (예: 삼성전자, 반도체, AAPL)",
        }[mode]

    return st_searchbox(
        search_function=_SEARCH_FNS[mode],
        label=label,
        placeholder=placeholder,
        default=default,
        key=key,
        clear_on_submit=False,
    )
