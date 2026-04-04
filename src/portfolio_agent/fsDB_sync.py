import os
import json
import chromadb
import hashlib
import re
from chromadb.utils import embedding_functions

# [설정] 마스터 홍이 지정한 경로 및 키워드
FS_DB_PATH = r"C:\Users\USER\projectr\data\FS_DB"
JSON_SOURCE_DIR = r"C:\Users\USER\projectr\data\jsonDB"
TARGET_KEYWORD = "SK하이닉스"

def sanitize_collection_name(name):
    """키워드를 ChromaDB 안전 규격으로 변환"""
    encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
    return f"fs_{encoded}"[:63] # 재무 데이터임을 식별하기 위해 fs_ 접두사 사용

class BatFinancialSync:
    def __init__(self):
        # FS_DB 경로로 클라이언트 접속
        self.client = chromadb.PersistentClient(path=FS_DB_PATH)
        # 한국어 분석에 최적화된 임베딩 모델 로드
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )
        print(f"[*] 재무 DB 동기화 엔진 가동: {FS_DB_PATH}")

    def sync_json_files(self):
        """jsonDB 폴더의 파일들을 특정 키워드로 DB에 저장"""
        if not os.path.exists(JSON_SOURCE_DIR):
            print(f"[!] 소스 폴더를 찾을 수 없습니다: {JSON_SOURCE_DIR}")
            return

        col_name = sanitize_collection_name(TARGET_KEYWORD)
        
        # 최신성 유지를 위해 기존 컬렉션 초기화 후 재생성
        try:
            self.client.delete_collection(name=col_name)
            print(f"[*] 기존 '{TARGET_KEYWORD}' 재무 데이터 파기 완료.")
        except:
            pass

        collection = self.client.create_collection(
            name=col_name,
            embedding_function=self.embedding_fn
        )

        indexed_count = 0
        print(f"[*] '{TARGET_KEYWORD}' 재무 제표 데이터 인덱싱 시작...")

        for file in os.listdir(JSON_SOURCE_DIR):
            if file.endswith(".json"):
                file_path = os.path.join(JSON_SOURCE_DIR, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        
                        # 데이터 내용을 문자열로 병합 (전체 본문 저장)
                        content = json.dumps(data, ensure_ascii=False)
                        
                        # 파일명을 기반으로 고유 ID 생성
                        doc_id = hashlib.md5(file.encode()).hexdigest()
                        
                        collection.add(
                            ids=[doc_id],
                            documents=[content],
                            metadatas=[{
                                "source_file": file,
                                "keyword": TARGET_KEYWORD,
                                "type": "financial_statement"
                            }]
                        )
                        indexed_count += 1
                        print(f"    -> [{indexed_count}] {file} 처리 완료")
                except Exception as e:
                    print(f"    [!] {file} 처리 중 오류 발생: {e}")

        print(f"\n[*] 완료: 총 {indexed_count}건의 재무 데이터가 FS_DB에 저장되었습니다.")

if __name__ == "__main__":
    syncer = BatFinancialSync()
    syncer.sync_json_files()