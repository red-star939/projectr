import os
import chromadb
from chromadb.utils import embedding_functions

# [설정] 재무제표 DB 경로
FS_DB_PATH = r"C:\Users\USER\projectr\data\FS_DB"

# 디렉토리 유무 확인 및 생성
if not os.path.exists(FS_DB_PATH):
    os.makedirs(FS_DB_PATH)
    print(f"[*] FS_DB 저장소를 신규 생성했습니다: {FS_DB_PATH}")

# PersistentClient를 통한 영구 저장소 인스턴스 생성
client = chromadb.PersistentClient(path=FS_DB_PATH)

# 한국어 및 경제 지표 분석에 적합한 임베딩 함수 정의
embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="jhgan/ko-sroberta-multitask"
)

# 재무제표 전용 컬렉션 생성
collection = client.get_or_create_collection(
    name="financial_statements",
    embedding_function=embedding_fn
)
print("[*] 'financial_statements' 컬렉션이 활성화되었습니다.")