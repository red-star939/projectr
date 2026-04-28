import time
import json
import re
import hashlib
import threading
import concurrent.futures
from datetime import datetime
from pathlib import Path
import sys

import chromadb
from chromadb.utils import embedding_functions
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from readability import Document
from bs4 import BeautifulSoup
import feedparser
import urllib.parse
from llama_cpp import Llama

# [단계 1] 상대 경로 기반 환경 설정
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
DB_PATH = str(PROJECT_ROOT / "data" / "News_DB")
MODEL_PATH = str(BASE_DIR / "model" / "EXAONE-3.0-7.8B-Instruct-Q4_K_M.gguf")
PROMPT_JSON = str(BASE_DIR / "model" / "prompt" / "news_prompts.json")

class BatIntegratedEngine:
    def __init__(self, limit=10):
        self.limit = limit
        self.embedding_fn = None
        self.llm = None
        self.prompt_cfg = None
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.lock = threading.Lock()
        
        # [핵심] 배경 연산: 임베딩 및 EXAONE 모델 병렬 로딩 시작
        self.model_loader_thread = threading.Thread(target=self._load_all_models)
        self.model_loader_thread.start()

    def _load_all_models(self):
        """뉴스 수집 중에 배경에서 모든 AI 엔진을 예열합니다."""
        print("[*] 배경 연산: AI 통합 엔진(Embedding + EXAONE) 로드 시작...")
        
        # 1. 임베딩 모델 로드
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )
        
        # 2. 프롬프트 로드 (상대 경로 적용)
        with open(PROMPT_JSON, 'r', encoding='utf-8') as f:
            self.prompt_cfg = json.load(f)
            
        # 3. EXAONE 엔진 로드 (VRAM 6GB 최적화 설정)
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=16384,           # 8080 토큰 에러 방지를 위한 확장
            n_gpu_layers=-1,      # RTX 4050 전량 할당
            type_k=2,             # 4-bit KV Cache (필수)
            type_v=2,
            flash_attn=True,
            verbose=False
        )
        print("[*] 배경 연산: 모든 AI 모델이 VRAM에 장착되었습니다.")

    def _get_driver(self):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def _crawl_and_sync(self, url, collection):
        """수집 데이터를 마크다운으로 변환하여 실시간 DB 저장"""
        driver = self._get_driver()
        try:
            driver.get(url)
            time.sleep(2)
            doc = Document(driver.page_source)
            soup = BeautifulSoup(doc.summary(), 'html.parser')
            lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if len(line.strip()) > 10]
            raw_content = "\n\n".join(lines)
            
            if len(raw_content) > 100:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                md_content = f"# {doc.title()}\n\n- 수집: {now_str}\n- URL: {url}\n\n---\n\n{raw_content}"
                doc_id = hashlib.md5(url.encode()).hexdigest()
                
                with self.lock:
                    collection.upsert(
                        ids=[doc_id],
                        documents=[md_content],
                        metadatas=[{"title": doc.title(), "url": url}]
                    )
                return f"✅ 수집완료: {doc.title()[:15]}..."
        except: return "❌ 수집실패"
        finally: driver.quit()

    def generate_report(self, keyword, docs):
        """ 원샷 분석 방식으로 리포트 생성"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        print(f"[*] 분석 엔진 가동: {len(docs)}개 데이터를 기반으로 리포트 생성 중...")
        
        # 데이터 압축 및 결합
        compressed_context = ""
        for i, doc in enumerate(docs, 1):
            compressed_context += f"### [기사 {i}]\n{doc[:1200]}\n\n"

        sys_msg = self.prompt_cfg['prompts']['reduce_phase']['system'].format(today=today_str)
        user_msg = f"주제: {keyword}\n\n[뉴스셋]\n{compressed_context}\n\n요청: 위 기사들을 바탕으로 투자 전략 리포트를 작성하세요."
        
        prompt = f"[|system|]\n{sys_msg}[|sep|]\n[|user|]\n{user_msg}[|sep|]\n[|assistant|]\n"
        
        full_report = ""
        # 스트리밍 출력
        for chunk in self.llm(prompt, stream=True, **self.prompt_cfg['params']):
            token = chunk['choices'][0]['text']
            sys.stdout.write(token)
            sys.stdout.flush()
            full_report += token
        return full_report

    def run_pipeline(self, keyword):
        # 1. 뉴스 링크 확보 (가장 먼저 수행)
        full_query = f"{keyword} when:1h"
        encoded = urllib.parse.quote(full_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        links = [e.link for e in feed.entries[:self.limit]]

        if not links:
            print("[!] 최근 1시간 이내 뉴스가 없습니다.")
            return

        # 2. 멀티스레드 크롤링 시작 (모델 로딩과 병렬 진행)
        print(f"[*] 실시간 수집 시작 ({len(links)}개 타겟)...")
        
        # 임베딩 모델 로딩 대기 (DB 컬렉션 생성을 위해 필요)
        while self.embedding_fn is None:
            time.sleep(0.5)

        col_name = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in keyword])[:63]
        try: self.client.delete_collection(col_name)
        except: pass
        collection = self.client.create_collection(name=col_name, embedding_function=self.embedding_fn)

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            list(executor.map(lambda url: self._crawl_and_sync(url, collection), links))

        # 3. 모델 로딩 완료 확인 및 리포트 생성 직결
        print("\n[*] 수집 완료. AI 분석 엔진 최종 상태 점검...")
        self.model_loader_thread.join() # 모델 로딩이 덜 끝났다면 여기서 잠시 대기

        docs = collection.get()['documents']
        if docs:
            report = self.generate_report(keyword, docs)
            print("\n\n[*] 파이프라인 공정 완료.")

if __name__ == "__main__":
    engine = BatIntegratedEngine(limit=10)
    kwd = input("\n분석 키워드 입력: ").strip()
    if kwd:
        start = time.time()
        engine.run_pipeline(kwd)
        print(f"\n[*] 총 소요 시간 (수집+로드+분석): {time.time() - start:.2f}초")