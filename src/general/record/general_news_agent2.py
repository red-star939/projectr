import re
from datetime import datetime
import numpy as np  # 고속 행렬 연산을 위한 NumPy 의존성 추가

class GeneralFastNewsAgent:
    def __init__(self, limit=15, similarity_threshold=0.6, token_budget_chars=3000):
        self.limit = limit
        self.similarity_threshold = similarity_threshold
        self.token_budget_chars = token_budget_chars  # 대략적인 토큰 한계 관리를 위한 바운더리 문자열 크기

    def _calculate_jaccard(self, str1: str, str2: str) -> float:
        """자카드 유사도 기반 텍스트 유사도 고속 연산 (어텐션 실패 시 폴백용 보존)"""
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
        cleaned = re.sub(r'\[.*?\]|\(.*?Collapsed\)', '', cleaned) # 정규식 구조 최적화 유지
        cleaned = re.sub(r'\[.*?\]|\(.*?\)', '', cleaned)
        return cleaned.strip()

    def _parse_date(self, raw_date: str) -> str:
        """RSS 날짜 파싱 폴백 가드"""
        try:
            # 기본 포맷 파싱 시도
            dt = datetime.strptime(raw_date, "%a, %d %b %Y %H:%M:%S %Z")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            # 포맷 미스매치 시 최소한의 자르기 가드 수행
            return raw_date[:10] if raw_date else datetime.now().strftime("%Y-%m-%d")

    def fetch_news_snippets_optimized(self, keyword: str, reporter=None) -> list:
        """
        메모리 내 자가 어텐션 풀링(Self-Attention Pooling)이 내장된 고속 뉴스 파싱 엔진.
        상위 패널에서 주입된 reporter 객체의 embedding_fn을 사용하여 중복을 완전 소거하고 정보 가치 순으로 정렬합니다.
        """
        import feedparser
        import urllib.parse

        encoded_kwd = urllib.parse.quote(f"{keyword} when:24h")
        rss_url = f"https://news.google.com/rss/search?q={encoded_kwd}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        
        raw_snippets = []
        titles = []
        
        # 1. 원천 XML 스트림 수집 및 1차 텍스트 정제
        for entry in feed.entries[:self.limit]:
            raw_title = entry.title
            clean_title = self._clean_title(raw_title)
            compact_date = self._parse_date(entry.get("published", ""))
            actual_link = entry.get("link", "")
            
            if clean_title not in titles:
                titles.append(clean_title)
                raw_snippets.append({
                    "title": clean_title,
                    "date": compact_date,
                    "link": actual_link,
                    "attention_weight": 0.0  # 기본 가중치 초기화
                })
        
        if not raw_snippets:
            return []

        # 2. [Self-Attention Core Engine Layer]
        # 메인 세션의 임베딩 레이어 엔진 가용 여부 검증
        if reporter is not None and hasattr(reporter, "embedding_fn"):
            try:
                # 문장 군집 벡터화 변환 처리 -> 형상(Shape): (기사 개수, 768) 등
                embeddings = np.array(reporter.embedding_fn(titles))
                
                # Scaled Dot-Product 수치 모방 및 코사인 유사도 행렬 계산
                dot_products = np.dot(embeddings, embeddings.T)
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                sim_matrix = dot_products / (np.dot(norms, norms.T) + 1e-9)
                
                # 각 문장이 전체 문장 집합과 가지는 상호 연관 가중치의 평균값 산출 (Attention Centrality)
                attention_weights = np.mean(sim_matrix, axis=1)
                
                for idx, snip in enumerate(raw_snippets):
                    snip["attention_weight"] = float(attention_weights[idx])
                
                # 어텐션 기반 동적 마스킹을 통한 고밀도 중복 소거 구현
                filtered_snippets = []
                skip_indices = set()
                
                for i in range(len(raw_snippets)):
                    if i in skip_indices:
                        continue
                    for j in range(i + 1, len(raw_snippets)):
                        # 상호 벡터 유사도가 임계치(0.75)를 초과하는 실질적 복사 기사 발견 시
                        if sim_matrix[i, j] > 0.75:
                            # 어텐션 중앙 연관도가 더 떨어지는 요소를 중복 노이즈로 간주하여 인덱스 락 제외
                            if raw_snippets[i]["attention_weight"] >= raw_snippets[j]["attention_weight"]:
                                skip_indices.add(j)
                            else:
                                skip_indices.add(i)
                                break
                    if i not in skip_indices:
                        filtered_snippets.append(raw_snippets[i])
                
                # 시장 핵심 시그널 밀도가 높은(어텐션 스코어가 극대화된) 순서대로 정렬 재배치
                filtered_snippets.sort(key=lambda x: x["attention_weight"], reverse=True)
                unique_snippets = filtered_snippets

            except Exception:
                # 임베딩 하드웨어 예외 발생 시 안전한 자카드 폴백 파이프라인 작동
                unique_snippets = self._fallback_jaccard_filter(raw_snippets)
        else:
            # 임베딩 엔진 주입 누락 시 기존 레거시 자카드 필터 작동
            unique_snippets = self._fallback_jaccard_filter(raw_snippets)
        
        # 3. 슬라이딩 윈도우 기반 토큰 버젯 통제 알고리즘 작동
        final_snippets = []
        accumulated_chars = 0
        
        for snip in unique_snippets:
            # UI 가독성을 위해 상위 단에서 날짜 출력을 제거하더라도 
            # 컨텍스트 정합성을 위한 빌더 문자열 규격은 안정적으로 계측 및 압축 유지
            entry_str = f"제목:{snip['title']}({snip['date']})\n"
            if accumulated_chars + len(entry_str) > self.token_budget_chars:
                break
            final_snippets.append(snip)
            accumulated_chars += len(entry_str)
            
        return final_snippets

    def _fallback_jaccard_filter(self, raw_snippets: list) -> list:
        """백엔드 임베딩 결손 상황을 대비한 내결함성 레거시 자카드 필터 레이어"""
        f_snippets = []
        for snip in raw_snippets:
            is_duplicate = False
            for existing in f_snippets:
                if self._calculate_jaccard(snip["title"], existing["title"]) > self.similarity_threshold:
                    is_duplicate = True
                    break
            if not is_duplicate:
                f_snippets.append(snip)
        return f_snippets