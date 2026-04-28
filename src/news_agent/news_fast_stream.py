import streamlit as st
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

# [상대 경로 설정] 프로젝트 루트의 data/News_DB 지정
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
DB_PATH = str(PROJECT_ROOT / "data" / "News_DB")

class BatFastStreamer:
    def __init__(self, limit=10):
        self.limit = limit
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.lock = threading.Lock()
        
        # [핵심] 공유 임베딩 모델 확인 및 지연 로딩
        if 'embedding_fn' in st.session_state:
            self.embedding_fn = st.session_state.embedding_fn
            self.model_ready = True
        else:
            # 예열된 모델이 없을 경우 여기서 로드
            self.model_ready = False
            self.model_thread = threading.Thread(target=self._load_embedding_model)
            self.model_thread.start()

    def _load_embedding_model(self):
        """세션에 모델이 없을 경우 비상 로딩을 수행합니다."""
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )
        st.session_state.embedding_fn = self.embedding_fn
        self.model_ready = True

    def _get_driver(self):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def _sanitize_name(self, name):
        encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
        return f"kwd_{encoded}"[:63]

    def _crawl_and_sync(self, url, collection):
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
        except: return "❌ 실패"
        finally: driver.quit()

    def run(self, keyword):
        # RSS 검색
        encoded = urllib.parse.quote(f"{keyword} when:1h")
        rss_url = f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
        feed = feedparser.parse(rss_url)
        links = [e.link for e in feed.entries[:self.limit]]

        if not links: return print("[!] 최근 1시간 이내 뉴스가 없습니다.")

        # 모델 준비 대기
        if not self.model_ready:
            self.model_thread.join()

        # 컬렉션 초기화 (Fresh Sync)
        col_name = self._sanitize_name(keyword)
        try: self.client.delete_collection(col_name)
        except: pass
        collection = self.client.create_collection(name=col_name, embedding_function=self.embedding_fn)

        print(f"[*] 병렬 수집 가동: {len(links)}개 타겟 분석...")
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            list(executor.map(lambda u: self._crawl_and_sync(u, collection), links))

        final_data = collection.get(include=['metadatas'])
        return final_data['metadatas']