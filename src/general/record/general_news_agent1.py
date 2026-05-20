import re
from datetime import datetime

class GeneralFastNewsAgent:
    def __init__(self, limit=15, similarity_threshold=0.6, token_budget_chars=3000):
        self.limit = limit
        self.similarity_threshold = similarity_threshold
        self.token_budget_chars = token_budget_chars  # 대략적인 토큰 한계 관리를 위한 바운더리 문자열 크기

    def _calculate_jaccard(self, str1: str, str2: str) -> float:
        """자카드 유사도 기반 텍스트 유사도 고속 연산"""
        words1 = set(str1.split())
        words2 = set(str2.split())
        if not words1 or not words2:
            return 0.0
        return len(words1 & words2) / len(words1 | words2)

    def _clean_title(self, title: str) -> str:
        """불필요한 미디어 접미사 및 특수문자 제거로 토큰 절감"""
        # 1. ' - 언론사명' 제거
        cleaned = title.split(" - ")[0] if " - " in title else title
        # 2. 괄호 안의 불필요한 보충 정보 찌꺼기 제거 (예: [속보], (종합) 등)
        cleaned = re.sub(r'\[.*?\]|\(.*?\)', '', cleaned)
        return cleaned.strip()

    def _parse_date(self, raw_date: str) -> str:
        """길고 복잡한 표준 날짜 형식을 컴팩트한 10자 포맷으로 최적화"""
        try:
            # RSS 날짜 형태: "Wed, 20 May 2026 09:25:18 GMT" 파싱 시도
            dt = datetime.strptime(raw_date, "%a, %d %b %Y %H:%M:%S %Z")
            return dt.strftime("%Y-%m-%d")
        except Exception:
            return raw_date[:10]  # 파싱 실패 시 상위 10자만 인출

    def fetch_news_snippets_optimized(self, keyword: str) -> list:
        """토큰 절감 알고리즘이 적용된 고속 뉴스 인출 파이프라인"""
        import feedparser
        import urllib.parse

        encoded_kwd = urllib.parse.quote(f"{keyword} when:24h")
        rss_url = f"https://news.google.com/rss/search?q={encoded_kwd}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        
        unique_snippets = []
        
        for entry in feed.entries[:self.limit]:
            raw_title = entry.title
            clean_title = self._clean_title(raw_title)
            compact_date = self._parse_date(entry.published)
            
            # 자카드 유사도 필터링 수행: 기존 수집 데이터와 비교
            is_duplicate = False
            for existing in unique_snippets:
                if self._calculate_jaccard(clean_title, existing["title"]) > self.similarity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_snippets.append({
                    "title": clean_title,
                    "date": compact_date
                })
        
        # 토큰 버젯 가드: 설정된 바이트 한계 내로 컨텍스트 버퍼 압축 제어
        final_snippets = []
        accumulated_chars = 0
        
        for snip in unique_snippets:
            entry_str = f"제목:{snip['title']}({snip['date']})\n"
            if accumulated_chars + len(entry_str) > self.token_budget_chars:
                break  # 예산 초과 시 슬라이딩 윈도우 조기 컷오프
            final_snippets.append(snip)
            accumulated_chars += len(entry_str)
            
        return final_snippets