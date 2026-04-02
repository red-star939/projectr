import os
import json
import chromadb
from chromadb.utils import embedding_functions
import hashlib
import re
from pathlib import Path

# [Step 1] 상대 경로 기반 설정
# 이 파일이 src/news_agent 에 있다고 가정할 때 상위로 이동하여 data 폴더를 찾습니다.
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# projectr 루트 디렉토리 찾기 (src/news_agent -> src -> projectr)
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))

# 요청하신 C:\Users\USER\projectr\data\News_DB 경로를 상대적으로 설정
DB_DIR = os.path.join(PROJECT_ROOT, "data", "News_DB")
# 크롤링된 데이터가 있는 경로
SOURCE_DIR = os.path.join(CURRENT_DIR, "crawled_news")

def sanitize_collection_name(name):
    """한글 키워드를 ChromaDB 규격에 맞게 변환"""
    encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
    return f"kwd_{encoded}"[:63]

class BatNewsDB:
    def __init__(self):
        # 폴더가 없으면 생성
        os.makedirs(DB_DIR, exist_ok=True)
        
        # 1. 영구 저장소 활성화 (상대 경로 적용)
        self.client = chromadb.PersistentClient(path=DB_DIR)
        
        # 2. 임베딩 모델 설정 (인증 오류 없는 공개 모델 사용)
        print(f"[*] DB 위치: {DB_DIR}")
        print("[*] 엔진 가동: jhgan/ko-sroberta-multitask 모델 로드 중...")
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )

    def import_crawled_data(self):
        """crawled_news 폴더의 데이터를 DB로 이관"""
        if not os.path.exists(SOURCE_DIR):
            print(f"[!] 소스 폴더를 찾을 수 없습니다: {SOURCE_DIR}")
            return

        for keyword in os.listdir(SOURCE_DIR):
            kwd_path = os.path.join(SOURCE_DIR, keyword)
            if not os.path.isdir(kwd_path): continue

            print(f"\n[*] 키워드 [{keyword}] 데이터 색인 중...")
            collection = self.client.get_or_create_collection(
                name=sanitize_collection_name(keyword),
                embedding_function=self.embedding_fn
            )

            for file in os.listdir(kwd_path):
                if file.endswith(".json"):
                    self._process_file(collection, os.path.join(kwd_path, file))

    def _process_file(self, collection, file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # URL 기반 고유 ID 생성 (중복 방지)
                doc_id = hashlib.md5(data['url'].encode()).hexdigest()
                
                collection.upsert(
                    ids=[doc_id],
                    documents=[data['content']],
                    metadatas=[{
                        "title": data['title'],
                        "url": data['url']
                    }]
                )
        except Exception as e:
            print(f"    [!] 파일 처리 오류 ({os.path.basename(file_path)}): {e}")

if __name__ == "__main__":
    bat_db = BatNewsDB()
    bat_db.import_crawled_data()
    print("\n[성공] 새로운 News_DB가 구축되었습니다.")