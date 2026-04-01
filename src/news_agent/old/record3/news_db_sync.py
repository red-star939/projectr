import os
import json
import chromadb
import hashlib
import re
from chromadb.utils import embedding_functions

# [Step 1] 상대 경로 기반 설정 (배트 컴퓨터 표준 규격)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))

DB_PATH = os.path.join(PROJECT_ROOT, "data", "News_DB")
SOURCE_DIR = os.path.join(BASE_DIR, "crawled_news")

def sanitize_collection_name(name):
    """한글 키워드를 ChromaDB 안전 규격으로 변환"""
    encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
    return f"kwd_{encoded}"[:63]

class BatNewsSync:
    def __init__(self):
        # 1. DB 클라이언트 및 임베딩 모델 설정
        self.client = chromadb.PersistentClient(path=DB_PATH)
        # 한국어 뉴스 분석에 최적화된 공개 모델 사용
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )
        print(f"[*] DB 동기화 엔진 가동: {DB_PATH}")

    def sync_all(self):
        """crawled_news 폴더의 모든 데이터를 DB와 동기화"""
        if not os.path.exists(SOURCE_DIR):
            print(f"[!] 소스 폴더가 없습니다: {SOURCE_DIR}")
            return

        # 키워드 폴더 탐색
        for keyword in os.listdir(SOURCE_DIR):
            kwd_path = os.path.join(SOURCE_DIR, keyword)
            if not os.path.isdir(kwd_path): continue

            print(f"\n[*] 키워드 [{keyword}] 데이터 스캔 중...")
            collection = self.client.get_or_create_collection(
                name=sanitize_collection_name(keyword),
                embedding_function=self.embedding_fn
            )

            # 연도_월 폴더 탐색
            for date_folder in os.listdir(kwd_path):
                date_path = os.path.join(kwd_path, date_folder)
                if not os.path.isdir(date_path): continue

                self._index_folder(collection, date_path, keyword, date_folder)

    def _index_folder(self, collection, folder_path, keyword, date_str):
        indexed_count = 0
        for file in os.listdir(folder_path):
            if file.endswith(".json"):
                try:
                    with open(os.path.join(folder_path, file), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # URL 기반 고유 ID 생성 (중복 저장 방지 핵심)
                        doc_id = hashlib.md5(data['url'].encode()).hexdigest()
                        
                        # 데이터가 있을 경우 업데이트, 없을 경우 추가 (upsert)
                        collection.upsert(
                            ids=[doc_id],
                            documents=[data['content']],
                            metadatas=[{
                                "title": data['title'],
                                "url": data['url'],
                                "keyword": keyword,
                                "date": date_str
                            }]
                        )
                        indexed_count += 1
                except Exception as e:
                    print(f"    [!] 파일 처리 오류 ({file}): {e}")
        
        if indexed_count > 0:
            print(f"    -> {date_str} 데이터 {indexed_count}건 동기화 완료.")

if __name__ == "__main__":
    syncer = BatNewsSync()
    syncer.sync_all()