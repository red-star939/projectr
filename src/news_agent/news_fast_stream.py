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

# ──────────────────────────────────────────────────────────────
# 공유 유틸 — news_sum4_3.sanitize_collection_name 이 본 함수를 re-export
# ──────────────────────────────────────────────────────────────
def sanitize_collection_name(name: str) -> str:
    """
    ChromaDB collection 이름 규칙 준수: 알파벳/숫자로 시작, 길이 ≤ 63.
    한글·특수문자는 ord 16진수로 인코딩. 'news_' 접두사로 시작 규칙 강제.
    """
    encoded = "".join(
        char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}"
        for char in name
    )
    return f"news_{encoded}"[:63]


# ──────────────────────────────────────────────────────────────
# ChromeDriver 1회 캐싱 (#4)
#   이전: _get_driver 호출마다 ChromeDriverManager().install() 실행 →
#         병렬 워커 N × URL M 회 install 호출 → 네트워크 부담
#   개선: process-life 캐시로 1회만 실행
# ──────────────────────────────────────────────────────────────
_DRIVER_PATH_LOCK = threading.Lock()
_DRIVER_PATH: str | None = None


def _ensure_driver_path() -> str:
    """ChromeDriver 경로를 1회만 다운로드·확보 후 캐시."""
    global _DRIVER_PATH
    if _DRIVER_PATH is None:
        with _DRIVER_PATH_LOCK:
            if _DRIVER_PATH is None:  # double-checked locking
                _DRIVER_PATH = ChromeDriverManager().install()
    return _DRIVER_PATH


def _build_chrome_options() -> Options:
    """크롤링 전용 경량 Chrome 옵션 (#5 — VRAM 6GB 환경 메모리 절감)."""
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    # 메모리 절감
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-plugins")
    options.add_argument("--blink-settings=imagesEnabled=false")  # 이미지 차단
    options.add_argument("--window-size=1280,720")
    # 로깅 노이즈 억제
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    return options


class BatFastStreamer:
    def __init__(self, limit=7):
        self.limit = limit
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.lock = threading.Lock()  # VRAM 6GB 보호 (LLM 추론 serialize)

    def _get_driver(self):
        """캐싱된 ChromeDriver + 경량 옵션 + 페이지 로드 타임아웃 적용."""
        driver = webdriver.Chrome(
            service=Service(_ensure_driver_path()),
            options=_build_chrome_options(),
        )
        # 느린 페이지에서 무한 대기 방지 (#5)
        driver.set_page_load_timeout(15)
        return driver

    def _sanitize_name(self, name):
        """backward-compat: 기존 인스턴스 메서드 호출 경로 유지."""
        return sanitize_collection_name(name)

    def _crawl_and_map(self, url, collection, reporter):
        """[Map Phase] 수집과 동시에 EXAONE 요약 수행."""
        driver = self._get_driver()
        try:
            try:
                driver.get(url)
            except Exception as e:
                # 페이지 로드 타임아웃 초과 시에도 partial DOM 활용 가능하나
                # page_source 가 비어있으면 조기 종료
                if not driver.page_source:
                    return f"❌ 페이지 로드 실패: {str(e)[:60]}"

            doc = Document(driver.page_source)
            soup = BeautifulSoup(doc.summary(), 'html.parser')
            lines = [l.strip() for l in soup.get_text("\n", strip=True).splitlines() if len(l.strip()) > 20]
            raw_content = "\n\n".join(lines)

            if len(raw_content) > 100:
                # 6GB VRAM 환경이므로 LLM 추론은 lock 으로 직렬화
                with self.lock:
                    summary_res = reporter._generate(
                        system="기사의 핵심 내용을 2문장으로 요약하십시오.",
                        user=raw_content[:2500],
                    )

                summary_text = summary_res['choices'][0]['text'].strip()
                doc_id = hashlib.md5(url.encode()).hexdigest()

                with self.lock:
                    collection.upsert(
                        ids=[doc_id],
                        documents=[summary_text],
                        metadatas=[{"title": doc.title(), "url": url}],
                    )
                return f"✅ 요약 완료: {doc.title()[:15]}..."
            return f"⚠️ 본문 부족: {doc.title()[:15] if doc.title() else url[:30]}..."
        except Exception as e:
            return f"❌ 실패: {str(e)[:80]}"
        finally:
            try:
                driver.quit()
            except Exception:
                pass

    def run(self, keyword, reporter):
        # 1. 쿼리 확장 (실시간 1h + 과거 1년)
        one_year_ago = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
        queries = [f"{keyword} when:1h", f"{keyword} after:{one_year_ago}"]

        links = []
        for q in queries:
            encoded = urllib.parse.quote(q)
            feed = feedparser.parse(
                f"https://news.google.com/rss/search?q={encoded}&hl=ko&gl=KR&ceid=KR:ko"
            )
            links.extend([e.link for e in feed.entries[:self.limit]])

        links = list(set(links))
        if not links:
            return None

        col_name = sanitize_collection_name(keyword)
        try:
            self.client.delete_collection(col_name)
        except Exception:
            pass
        collection = self.client.create_collection(
            name=col_name,
            embedding_function=reporter.embedding_fn,
        )

        # 2. 병렬 파이프라인 (I/O 병렬, LLM lock 으로 순차)
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(self._crawl_and_map, url, collection, reporter)
                for url in links
            ]
            for future in concurrent.futures.as_completed(futures):
                st.write(future.result())

        return collection.get(include=['metadatas', 'documents'])
