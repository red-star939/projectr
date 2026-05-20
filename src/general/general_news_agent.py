import re
from datetime import datetime
from pathlib import Path
import sys
import numpy as np
import time

# 에이전트 자체 상대 경로 연산 세팅
AGENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AGENT_DIR.parent.parent

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
        self.token_budget_chars = token_budget_chars

    def _calculate_jaccard(self, str1: str, str2: str) -> float:
        words1 = set(str1.split())
        words2 = set(str2.split())
        if not words1 or not words2:
            return 0.0
        return len(words1 & words2) / len(words1 | words2)

    def _clean_title(self, title: str) -> str:
        cleaned = title.split(" - ")[0] if " - " in title else title
        cleaned = re.sub(r'\[.*?\]|\(.*?\)', '', cleaned)
        return cleaned.strip()

    def _parse_date(self, raw_date: str) -> str:
        try:
            dt = datetime.strptime(raw_date, "%a, %d %b %Y %H:%M:%S %Z")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return raw_date[:10] if raw_date else datetime.now().strftime("%Y-%m-%d")

    def fetch_news_snippets_optimized(self, keyword: str, reporter=None, status_callback=None) -> list:
        """
        메모리 내 자가 어텐션 풀링 수치 연산 과정을 실시간 로그로 변환하여 콜백함수로 전송하는 뉴스 파싱 엔진.
        """
        import feedparser
        import urllib.parse

        def log(msg: str):
            if status_callback:
                status_callback(msg)
                time.sleep(0.5)  # 실시간 계산 과정 인지를 위한 타임 슬롯 설정

        log("System: 구글 뉴스 RSS 피드 파싱을 시작합니다.")
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
            log("System: 조건에 부합하는 원천 뉴스 데이터가 없습니다.")
            return []

        log(f"System: 1차 정제 기사 집합 확보 완료 (Count: {len(raw_snippets)}).")

        # [Self-Attention Core Engine Layer with Mathematical Logger]
        if reporter is not None and hasattr(reporter, "embedding_fn"):
            try:
                log("Attention Layer: 문장 벡터 생성을 위해 임베딩 가중치를 인출합니다.")
                embeddings = np.array(reporter.embedding_fn(titles))
                
                # 수치 형태 행렬 생성 로그 명세
                n_docs, dim = embeddings.shape
                log(f"Attention Layer: 밀집 임베딩 행렬 생성 완료. Matrix Shape: {n_docs} x {dim}")
                
                # QK^T 연산 및 코사인 유사도 맵 빌드 과정 노출
                log("Attention Layer: 점곱 연산 수행 및 자가 어텐션 맵(Scaled Dot-Product Matrix) 빌드를 개시합니다.")
                dot_products = np.dot(embeddings, embeddings.T)
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                sim_matrix = dot_products / (np.dot(norms, norms.T) + 1e-9)
                
                # 맵 빌드 결과 수치적 통계값 산출
                mean_sim = np.mean(sim_matrix)
                max_sim = np.max(sim_matrix - np.eye(n_docs)) # 자기 자신을 제외한 최대 유사도
                log(f"Attention Layer: 어텐션 맵 빌드 완료. (행렬 평균 유사도: {mean_sim:.4f}, 최대 상호 유사도: {max_sim:.4f})")
                
                # 가중치 인출 (Attention Centrality Weight 계산 및 명세)
                log("Attention Layer: 각 문장 벡터별 상호 참조 어텐션 가중치(Attention Centrality Weight)를 구합니다.")
                attention_weights = np.mean(sim_matrix, axis=1)
                
                for idx, snip in enumerate(raw_snippets):
                    snip["attention_weight"] = float(attention_weights[idx])
                    # 상위 3개 기사에 대한 초기 가중치 인출 명세 예시화
                    if idx < 3:
                        log(f"   ↳ [Index {idx}] 가중치 인출 결과 -> 스코어: {snip['attention_weight']:.4f} | 문장 서두: {snip['title'][:20]}...")
                
                # 마스킹 연산 진행 과정 추적 로그
                log(f"Attention Layer: 마스킹 연산을 시작합니다. 임계치(Threshold: 0.75)를 적용하여 중복 벡터를 마스크 처리합니다.")
                filtered_snippets = []
                skip_indices = set()
                masked_records = []
                
                for i in range(len(raw_snippets)):
                    if i in skip_indices:
                        continue
                    for j in range(i + 1, len(raw_snippets)):
                        if sim_matrix[i, j] > 0.75:
                            if raw_snippets[i]["attention_weight"] >= raw_snippets[j]["attention_weight"]:
                                skip_indices.add(j)
                                masked_records.append(f"Index {j}(Score: {raw_snippets[j]['attention_weight']:.3f}) 마스킹 탈락 ➔ 유사도 {sim_matrix[i, j]:.3f}로 Index {i}에 종속")
                            else:
                                skip_indices.add(i)
                                masked_records.append(f"Index {i}(Score: {raw_snippets[i]['attention_weight']:.3f}) 마스킹 탈락 ➔ 유사도 {sim_matrix[i, j]:.3f}로 Index {j}에 종속")
                                break
                    if i not in skip_indices:
                        filtered_snippets.append(raw_snippets[i])
                
                # 마스킹 진행 내역 실시간 출력
                for record in masked_records[:4]: # 최대 4행만 가시화하여 버퍼 과부하 방지
                    log(f"   ↳ [Masking Operator] {record}")
                
                log(f"Attention Layer: 마스킹 연산 종료. 가용 기사 수: {len(raw_snippets)} ➔ {len(filtered_snippets)}")
                
                # 정렬 연산 명세
                log("Attention Layer: 가중치 스코어 기준 내림차순 정렬 연산을 집행합니다.")
                filtered_snippets.sort(key=lambda x: x["attention_weight"], reverse=True)
                
                for idx, snip in enumerate(filtered_snippets[:3]):
                    log(f"   ↳ [정렬 결과 {idx+1}순위] 스코어: {snip['attention_weight']:.4f} | {snip['title'][:25]}...")
                
                unique_snippets = filtered_snippets

            except Exception as e:
                log(f"Warning: 행렬 연산 실패로 레거시 자카드 필터 레이어로 폴백합니다. 사유: {e}")
                unique_snippets = self._fallback_jaccard_filter(raw_snippets)
        else:
            log("Warning: 공용 임베딩 엔진 바인딩 누락. 레거시 자카드 필터 모드로 전환합니다.")
            unique_snippets = self._fallback_jaccard_filter(raw_snippets)
        
        # 3. 슬라이딩 윈도우 기반 토큰 버젯 통제
        final_snippets = []
        accumulated_chars = 0
        for snip in unique_snippets:
            entry_str = f"제목:{snip['title']}({snip['date']})\n"
            if accumulated_chars + len(entry_str) > self.token_budget_chars:
                log(f"Budget Guard: 허용 바이트 수({self.token_budget_chars}자) 초과로 인출 범위를 컷오프합니다.")
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