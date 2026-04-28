import time
import json
import re
import hashlib
import threading
import concurrent.futures
from datetime import datetime
from pathlib import Path

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

# [상대 경로 설정] 현재 파일 위치 기준 프로젝트 루트의 data/News_DB 지정
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
DB_PATH = str(PROJECT_ROOT / "data" / "News_DB")

class BatFastStreamer:
    def __init__(self, limit=10):
        self.limit = limit
        self.embedding_fn = None
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.lock = threading.Lock() # DB 쓰기 동기화를 위한 락
        
        # [단계 1] 임베딩 모델 병렬 로딩 시작 (병목 제거)
        self.model_thread = threading.Thread(target=self._load_embedding_model)
        self.model_thread.start()

    def _load_embedding_model(self):
        """배경에서 임베딩 모델을 로드합니다."""
        print("[*] 배경 연산: jhgan/ko-sroberta-multitask 임베딩 엔진 예열 중...")
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )
        print("[*] 배경 연산: 임베딩 엔진 준비 완료.")

    def _get_driver(self):
        """스레드별 개별 셀레니움 드라이버 생성"""
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def _sanitize_name(self, name):
        """ChromaDB 규격에 맞는 컬렉션 명칭 생성"""
        encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
        return f"kwd_{encoded}"[:63]

    def _crawl_and_sync(self, url, collection):
        """크롤링 후 마크다운 형식으로 DB에 즉시 저장 (무복사 스트림)"""
        driver = self._get_driver()
        try:
            driver.get(url)
            time.sleep(2)
            doc = Document(driver.page_source)
            soup = BeautifulSoup(doc.summary(), 'html.parser')
            lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if len(line.strip()) > 10]
            raw_content = "\n\n".join(lines)
            
            if len(raw_content) > 100:
                # [수정] 수집된 데이터를 마크다운 형식으로 조립
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                md_content = f"""# {doc.title()}

- **수집 시각**: {now_str}
- **원문 URL**: [{url}]({url})

---

{raw_content}
"""
                doc_id = hashlib.md5(url.encode()).hexdigest()
                
                # [핵심] 메모리 상의 마크다운 데이터를 즉시 DB로 Upsert
                with self.lock:
                    collection.upsert(
                        ids=[doc_id],
                        documents=[md_content],
                        metadatas=[{
                            "title": doc.title(), 
                            "url": url, 
                            "sync_at": now_str
                        }]
                    )
                return f"✅ 성공 (MD): {doc.title()[:20]}..."
        except Exception as e:
            return f"❌ 실패: {str(e)[:30]}"
        finally:
            driver.quit()

    def run(self, keyword):
        """메인 실행 루틴"""
        # 1. RSS 검색
        full_query = f"{keyword} when:1h"
        encoded = urllib.parse.quote(full_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        links = [e.link for e in feed.entries[:self.limit]]

        if not links:
            print("[!] 최근 1시간 이내 뉴스가 없습니다.")
            return

        # 2. 임베딩 모델 로딩 완료 대기
        self.model_thread.join()

        # 3. 컬렉션 초기화 (Fresh Sync 원칙 계승)
        col_name = self._sanitize_name(keyword)
        try: self.client.delete_collection(col_name)
        except: pass
        collection = self.client.create_collection(name=col_name, embedding_function=self.embedding_fn)

        # 4. 멀티스레드 병렬 크롤링 및 실시간 DB 인덱싱
        print(f"[*] 병렬 수집 엔진 가동: {len(links)}개 타겟 분석 시작...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(self._crawl_and_sync, url, collection) for url in links]
            for future in concurrent.futures.as_completed(futures):
                print(future.result())

        print(f"[*] '{keyword}' 데이터가 마크다운 형식으로 ChromaDB에 무복사 저장되었습니다.")

if __name__ == "__main__":
    streamer = BatFastStreamer(limit=10)
    kwd = input("실시간 분석 키워드 입력: ").strip()
    if kwd:
        start = time.time()
        streamer.run(kwd)
        print(f"[*] 총 소요 시간: {time.time() - start:.2f}초")