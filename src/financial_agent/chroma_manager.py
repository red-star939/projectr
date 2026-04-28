import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime
import os
from pathlib import Path

class FinancialChromaDB:
    def __init__(self):
        # [상대 경로 설정] 현재 파일 위치 기준 프로젝트 루트의 data/FS_DB 폴더 지정
        base_dir = Path(__file__).resolve().parent.parent.parent
        db_path = str(base_dir / "data" / "FS_DB")
        
        # 폴더 자동 생성
        os.makedirs(db_path, exist_ok=True)
        
        # 로컬 보존형 클라이언트 설정
        self.client = chromadb.PersistentClient(path=db_path)

        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )

        # 리포트 저장용 컬렉션 생성 또는 로드
        self.collection = self.client.get_or_create_collection(
            name="financial_reports",
            embedding_function=self.embedding_fn
        )


    def upsert_report(self, corp_name, content, metadata):
        """
        리포트 내용을 ChromaDB에 저장 또는 최신본으로 갱신합니다.
        """
        doc_id = f"REPORT_{corp_name}"
        self.collection.upsert(
            documents=[content],
            metadatas=[metadata],
            ids=[doc_id]
        )
        return True

def save_report_to_db(corp, content, sector, stock_code):
    """
    외부 모듈 연동용 래퍼 함수
    """
    try:
        manager = FinancialChromaDB()
        metadata = {
            "corp_name": corp,
            "sector": sector,
            "stock_code": stock_code,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        manager.upsert_report(corp, content, metadata)
        return True
    except Exception as e:
        print(f"ChromaDB 인덱싱 에러: {e}")
        return False