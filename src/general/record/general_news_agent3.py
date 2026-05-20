import re
from datetime import datetime
from pathlib import Path
import sys
import numpy as np  # 고속 행렬 연산을 위한 NumPy 의존성 추가
import time

# [1] 에이전트 자체 상대 경로 연산 세팅 (상위 패키지 참조 보존 장치)
AGENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AGENT_DIR.parent.parent  # C:\Users\USER\projectr 진입

# 자매 분석 소스 경로 상대 배열 바인딩
REL_PATHS = [
    PROJECT_ROOT,
    PROJECT_ROOT / "src" / "news_agent",
    PROJECT_ROOT / "src" / "financial_agent"
]

for p_dir in REL_PATHS:
    if str(p_dir) not in sys.path:
        sys.path.insert(0, str(p_dir))

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
        cleaned = title.split(" - ")[0] if " - " in title else title
        cleaned = re.sub(r'\[.*?\]|\(.*?\)', '', cleaned)
        return cleaned.strip()

    def _parse_date(self, raw_date: str) -> str:
        """RSS 날짜 파싱 폴백 가드"""
        try:
            dt = datetime.strptime(raw_date, "%a, %d %b %Y %H:%M:%S %Z")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return raw_date[:10] if raw_date else datetime.now().strftime("%Y-%m-%d")

    def fetch_news_snippets_optimized(self, keyword: str, reporter=None, status_callback=None) -> list:
        """
        메모리 내 자가 어텐션 풀링(Self-Attention Pooling) 및 동적 로깅 인디케이터가 내장된 고속 뉴스 파싱 엔진.
        """
        import feedparser
        import urllib.parse

        def log(msg: str):
            if status_callback:
                status_callback(msg)
                time.sleep(0.4)  # 시각적 인지를 위한 정밀 지연 처리

        log("📡 구글 뉴스 RSS 원천 데이터 스트림 수집을 개시합니다...")
        encoded_kwd = urllib.parse.quote(f"{keyword} when:24h")
        rss_url = f"https://news.google.com/rss/search?q={encoded_kwd}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        
        raw_snippets = []
        titles = []
        
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
                    "attention_weight": 0.0
                })
        
        if not raw_snippets:
            log("❌ 조건에 부합하는 원천 뉴스 기사가 발견되지 않았습니다.")
            return []

        log(f"✅ 1차 고유 텍스트 뉴스 스니펫 {len(raw_snippets)}건 확보 완료.")

        # [Self-Attention Core Engine Layer with Live Logger]
        if reporter is not None and hasattr(reporter, "embedding_fn"):
            try:
                log("🧠 **[Attention Layer]** 상위 엔진 세션으로부터 Ko-sROBERTA 문장 임베딩 가중치를 인출하는 중...")
                embeddings = np.array(reporter.embedding_fn(titles))
                
                log(f"📐 **[Attention Layer]** 밀집 임베딩 행렬(Dense Matrix) 생성 완료 -> Shape: `{embeddings.shape}`")
                
                # QK^T 연산 및 코사인 유사도 변환
                dot_products = np.dot(embeddings, embeddings.T)
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                sim_matrix = dot_products / (np.dot(norms, norms.T) + 1e-9)
                
                log("🔗 **[Attention Layer]** 수치 점곱 연산 수행 및 자가 어텐션 유사도 행렬($Scaled Dot-Product Matrix$) 맵 빌드 완료.")
                
                # 각 문장의 상호 연관 가중치 평균값 계산 (Attention Centrality)
                attention_weights = np.mean(sim_matrix, axis=1)
                
                for idx, snip in enumerate(raw_snippets):
                    snip["attention_weight"] = float(attention_weights[idx])
                
                log("✂️ **[Attention Layer]** 어텐션 결합도 유사도 기준 한계값(`> 0.75`) 초과 기사 대상 동적 마스킹(Masking) 연산 집행 중...")
                filtered_snippets = []
                skip_indices = set()
                masked_count = 0
                
                for i in range(len(raw_snippets)):
                    if i in skip_indices:
                        continue
                    for j in range(i + 1, len(raw_snippets)):
                        if sim_matrix[i, j] > 0.75:
                            if raw_snippets[i]["attention_weight"] >= raw_snippets[j]["attention_weight"]:
                                skip_indices.add(j)
                            else:
                                skip_indices.add(i)
                                masked_count += 1
                                break
                    if i not in skip_indices:
                        filtered_snippets.append(raw_snippets[i])
                
                if masked_count > 0:
                    log(f"🗑️ 어텐션 마스킹 필터 레이어에 의해 정보 중복도가 높은 기사 `{masked_count}`건이 컨텍스트에서 안전하게 제외되었습니다.")
                
                log("⚖️ 정보 핵심도밀도(Attention Centrality Weight) 스코어 기준 내림차순 정렬을 완료했습니다.")
                filtered_snippets.sort(key=lambda x: x["attention_weight"], reverse=True)
                unique_snippets = filtered_snippets

            except Exception as e:
                log(f"⚠️ 백엔드 행렬 연산 중 임베딩 하드웨어 예외 발생. 내결함성 자카드 필터 레이어로 폴백합니다: {e}")
                unique_snippets = self._fallback_jaccard_filter(raw_snippets)
        else:
            log("⚠️ 공용 임베딩 포인터 바인딩 누락 확인. 레거시 자카드 필터 체인 모드로 강제 전환합니다.")
            unique_snippets = self._fallback_jaccard_filter(raw_snippets)
        
        # 3. 슬라이딩 윈도우 기반 토큰 버젯 통제
        final_snippets = []
        accumulated_chars = 0
        for snip in unique_snippets:
            entry_str = f"제목:{snip['title']}({snip['date']})\n"
            if accumulated_chars + len(entry_str) > self.token_budget_chars:
                log(f"🛑 토큰 버젯 임계점(`>{self.token_budget_chars}자`) 초과 가드가 가동되어 하위 버퍼 컨텍스트를 차단했습니다.")
                break
            final_snippets.append(snip)
            accumulated_chars += len(entry_str)
            
        return final_snippets

    def _fallback_jaccard_filter(self, raw_snippets: list) -> list:
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