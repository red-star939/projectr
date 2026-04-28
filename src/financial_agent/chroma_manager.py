import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime
import os
from pathlib import Path
import streamlit as st # [추가] 세션 상태 확인을 위해 필요

class FinancialChromaDB:
    def __init__(self):
        # [1] 경로 설정 (프로젝트 루트의 data/FS_DB)
        base_dir = Path(__file__).resolve().parent.parent.parent
        db_path = str(base_dir / "data" / "FS_DB")
        os.makedirs(db_path, exist_ok=True)
        
        # [2] DB 클라이언트 연결
        self.client = chromadb.PersistentClient(path=db_path)

        # [3] 임베딩 모델 준비 상태 체크 및 로드 [핵심 수정 사항]
        # app_v01.py에서 예열된 모델이 있는지 확인합니다.
        if 'embedding_fn' in st.session_state:
            self.embedding_fn = st.session_state.embedding_fn
        else:
            # 예열된 모델이 없을 경우 여기서 직접 로드합니다.
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="jhgan/ko-sroberta-multitask"
            )
            # 다른 에이전트와 공유할 수 있도록 세션에 저장합니다.
            st.session_state.embedding_fn = self.embedding_fn

        # [4] 컬렉션 확보
        self.collection = self.client.get_or_create_collection(
            name="financial_reports",
            embedding_function=self.embedding_fn
        )

    def upsert_report(self, corp_name, content, metadata):
        """재무 보고서를 DB에 저장하거나 갱신합니다."""
        doc_id = f"REPORT_{corp_name}"
        self.collection.upsert(
            documents=[content],
            metadatas=[metadata],
            ids=[doc_id]
        )
        return True

def save_report_to_db(corp, content, sector, stock_code):
    """외부 에이전트 호출용 래퍼 함수"""
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
        # 에러 발생 시 상세 정보 출력 (NameError 등 방지)
        st.error(f"ChromaDB 인덱싱 에러: {e}")
        return False