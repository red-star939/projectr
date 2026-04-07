import os
import sys
import json
import chromadb
import re
import gc
import time  # [해결] 타임스탬프 생성을 위한 모듈 추가
from datetime import datetime
from llama_cpp import Llama
from chromadb.utils import embedding_functions

# [Step 1] 절대 경로 및 환경 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # src/portfolio_agent
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR)) # C:\Users\USER\projectr

NEWS_DB_PATH = os.path.join(PROJECT_ROOT, "data", "News_DB")
FS_DB_PATH = os.path.join(PROJECT_ROOT, "data", "FS_DB")
# [해결] 리포트 저장 폴더 경로 정의 및 고정
PORTFOLIO_DIR = r"projectr\data\Portfolio"
MODEL_PATH = os.path.join(PROJECT_ROOT, "src", "news_agent", "model", "EXAONE-3.0-7.8B-Instruct-Q4_K_M.gguf")

def sanitize_name(name, prefix="kwd"):
    """ChromaDB 컬렉션 네이밍 규격화"""
    encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
    return f"{prefix}_{encoded}"[:63]

class PortfolioAgent:
    def __init__(self):
        # [해결] 저장 폴더가 없을 경우 자동 생성 로직
        if not os.path.exists(PORTFOLIO_DIR):
            os.makedirs(PORTFOLIO_DIR)

        # 1. 듀얼 DB 클라이언트 로드
        self.news_client = chromadb.PersistentClient(path=NEWS_DB_PATH)
        self.fs_client = chromadb.PersistentClient(path=FS_DB_PATH)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )
        
        # 2. EXAONE 엔진 최적화 (VRAM 6GB 보호 모드 적용)
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=4096,
            n_gpu_layers=-1,      # RTX 4050 가속
            type_k=2, type_v=2,   # 4-bit KV Cache 활성화
            flash_attn=True, 
            verbose=False
        )

    def _get_data(self, client, col_name):
        """DB로부터 문서 리스트 추출"""
        try:
            col = client.get_collection(name=col_name, embedding_function=self.embedding_fn)
            return col.get()['documents']
        except:
            return []

    def _save_report(self, keyword, content, today_str):
        """분석 결과를 Markdown 파일로 물리적 저장"""
        # [해결] 이제 time 모듈을 정상적으로 참조합니다
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"Portfolio_{keyword}_{timestamp}.md"
        file_path = os.path.join(PORTFOLIO_DIR, filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

    def create_portfolio_report(self, keyword):
        """뉴스 및 재무 데이터를 결합한 전문 투자 리포트 생성"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        # 정성적(News) 및 정량적(Financial) 데이터 확보
        news_docs = self._get_data(self.news_client, sanitize_name(keyword, "kwd"))
        fs_docs = self._get_data(self.fs_client, sanitize_name(keyword, "fs"))

        if not news_docs and not fs_docs:
            return print(f"[!] No data found for '{keyword}' in any database.")

        # [전문 페르소나 및 영어 지시문 체계 유지]
        system_instr = (
            f"You are a senior investment strategist. Today is {today_str}. "
            "Your task is to synthesize qualitative market sentiment and quantitative financial metrics "
            "to generate a high-level investment intelligence report. "
            "Maintain an objective, evidence-based tone. Write the final report in Korean."
        )
        
        user_instr = f"""
Target Keyword: {keyword}
Reference Date: {today_str}

[Input Data 1: Financial Metrics (Quantitative)]
{fs_docs[0] if fs_docs else "No financial data available."}

[Input Data 2: Market News Summaries (Qualitative)]
{chr(10).join(news_docs[:5]) if news_docs else "No recent news data available."}

[Report Requirements]
Generate a professional Markdown report in Korean including:
1. Fundamental Health Check: Based on financial metrics.
2. Market Sentiment Analysis: Based on recent news trends.
3. Holistic Investment Opinion: Integration of numbers and sentiment, including risk assessment.
"""
        # EXAONE 전용 프롬프트 템플릿 적용
        prompt = f"[|system|]\n{system_instr}[|sep|]\n[|user|]\n{user_instr}[|sep|]\n[|assistant|]\n"
        
        # [해결] 전체 보고서 저장을 위한 변수 초기화
        full_report = ""
        print(f"[*] Analyzing '{keyword}' Portfolio Strategy...\n" + "="*50)
        
        # 스트리밍 연산 및 텍스트 데이터 수집
        for chunk in self.llm(prompt, stream=True, temperature=0.1, max_tokens=2048, repeat_penalty=1.2):
            token = chunk['choices'][0]['text']
            sys.stdout.write(token)
            sys.stdout.flush()
            # [해결] 생성된 토큰을 full_report 변수에 누적하여 데이터 소실 방지
            full_report += token
        
        # [해결] 누적된 리포트 내용을 기반으로 파일 저장 수행
        save_path = self._save_report(keyword, full_report, today_str)
        print(f"\n\n[*] Report successfully exported to: {save_path}")

        # 메모리 자원 관리
        gc.collect()

if __name__ == "__main__":
    agent = PortfolioAgent()
    target = input("\nEnter Target Company/Keyword: ").strip()
    if target:
        agent.create_portfolio_report(target)