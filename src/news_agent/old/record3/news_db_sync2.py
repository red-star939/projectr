import os
import json
import chromadb
import hashlib
import re
from chromadb.utils import embedding_functions

# [Step 1] 상대 경로 기반 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))

DB_PATH = os.path.join(PROJECT_ROOT, "data", "News_DB")
SOURCE_DIR = os.path.join(BASE_DIR, "crawled_news")

def sanitize_collection_name(name):
    encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
    return f"kwd_{encoded}"[:63]

class BatNewsFreshSync:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )
        print(f"[*] 실시간 DB 최신화 엔진 가동: {DB_PATH}")

    def sync_latest_only(self):
        """가장 최신 폴더의 데이터만 유지하고 나머지는 DB에서 삭제"""
        if not os.path.exists(SOURCE_DIR):
            print(f"[!] 소스 폴더가 없습니다: {SOURCE_DIR}")
            return

        for keyword in os.listdir(SOURCE_DIR):
            kwd_path = os.path.join(SOURCE_DIR, keyword)
            if not os.path.isdir(kwd_path): continue

            # 1. 날짜/시간별 폴더 리스트 확보 및 정렬
            date_folders = [f for f in os.listdir(kwd_path) if os.path.isdir(os.path.join(kwd_path, f))]
            if not date_folders: continue
            
            # 문자열 정렬을 통해 가장 최신 시간 폴더 선택 (예: 2026_04_01_19)
            latest_folder = sorted(date_folders)[-1]
            latest_path = os.path.join(kwd_path, latest_folder)

            print(f"\n[*] 키워드 [{keyword}] 최신 데이터 감지: {latest_folder}")
            
            # 2. 기존 컬렉션 삭제 (초기화)
            col_name = sanitize_collection_name(keyword)
            try:
                self.client.delete_collection(name=col_name)
                print(f"    -> 기존 과거 데이터 파기 완료.")
            except:
                # 컬렉션이 없었던 경우 무시
                pass

            # 3. 신규 컬렉션 생성 및 최신 데이터만 인덱싱
            collection = self.client.create_collection(
                name=col_name,
                embedding_function=self.embedding_fn
            )
            
            self._index_folder(collection, latest_path, keyword, latest_folder)

    def _index_folder(self, collection, folder_path, keyword, date_str):
        indexed_count = 0
        for file in os.listdir(folder_path):
            if file.endswith(".json"):
                try:
                    with open(os.path.join(folder_path, file), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # 고유 ID 생성: $H(x) = \text{MD5}(URL)$
                        doc_id = hashlib.md5(data['url'].encode()).hexdigest()
                        
                        collection.add(
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
            print(f"    -> 최신 데이터 {indexed_count}건 동기화 완료.")

if __name__ == "__main__":
    syncer = BatNewsFreshSync()
    syncer.sync_latest_only()