import streamlit as st
import hashlib
import threading
import concurrent.futures
from datetime import datetime, timedelta
from pathlib import Path
import chromadb
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from readability import Document
from bs4 import BeautifulSoup
import feedparser
import urllib.parse
import re

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
DB_PATH = str(PROJECT_ROOT / "data" / "News_DB")

class BatFastStreamer:
    def __init__(self, limit=7): 
        self.limit = limit
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.lock = threading.Lock() # VRAM 6GB 보호용

    def _get_driver(self):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    def _sanitize_name(self, name):
        """ChromaDB 규칙 준수: 알파벳/숫자로 시작 필수"""
        encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
        return f"news_{encoded}"[:63] # 'news_' 접두사로 시작 규칙 강제 적용

    def _crawl_and_map(self, url, collection, reporter):
        """[Map Phase] 수집과 동시에 EXAONE 요약 수행"""
        driver = self._get_driver()
        try:
            driver.get(url)
            doc = Document(driver.page_source)
            soup = BeautifulSoup(doc.summary(), 'html.parser')
            lines = [l.strip() for l in soup.get_text("\n", strip=True).splitlines() if len(l.strip()) > 20]
            raw_content = "\n\n".join(lines)
            
            if len(raw_content) > 100:
                # 6GB VRAM 환경이므로 추론 시에만 Lock 획득
                with self.lock:
                    summary_res = reporter._generate(
                        system="기사의 핵심 내용을 2문장으로 요약하십시오.",
                        user=raw_content[:2500]
                    )
                
                summary_text = summary_res['choices'][0]['text'].strip()
                doc_id = hashlib.md5(url.encode()).hexdigest()

                with self.lock:
                    collection.upsert(
                        ids=[doc_id],
                        documents=[summary_text],
                        metadatas=[{"title": doc.title(), "url": url}]
                    )
                return f"✅ 요약 완료: {doc.title()[:15]}..."
        except Exception as e:
            return f"❌ 실패: {str(e)}"
        finally:
            driver.quit()

    def run(self, keyword, reporter):
        # 1. 쿼리 확장 (실시간 1h + 과거 1년)
        one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        queries = [f"{keyword} when:1h", f"{keyword} after:{one_year_ago}"]
        
        links = []
        for q in queries:
            encoded = urllib.parse.quote(q)
            feed = feedparser.parse(f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko")
            links.extend([e.link for e in feed.entries[:self.limit]])

        links = list(set(links))
        if not links: return None

        col_name = self._sanitize_name(keyword)
        try: self.client.delete_collection(col_name)
        except: pass
        collection = self.client.create_collection(name=col_name, embedding_function=reporter.embedding_fn)

        # 2. 병렬 파이프라인 (I/O 병렬, LLM 순차)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(self._crawl_and_map, url, collection, reporter) for url in links]
            for future in concurrent.futures.as_completed(futures):
                st.write(future.result())

        return collection.get(include=['metadatas', 'documents'])