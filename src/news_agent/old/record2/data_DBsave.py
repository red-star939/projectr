import os
import json
import chromadb
from chromadb.utils import embedding_functions
from datetime import datetime
import re

# [Step 1] 상대 경로 기반 프로젝트 루트 및 DB 경로 설정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))

CHROMA_PATH = os.path.join(PROJECT_ROOT, "data", "chroma_db")
NEWS_BASE_DIR = os.path.join(PROJECT_ROOT, "data", "News_Reports")

def sanitize_collection_name(name):
    """한글 키워드를 ChromaDB 규격에 맞는 안전한 이름으로 인코딩"""
    encoded_name = ""
    for char in name:
        if re.match(r'[a-zA-Z0-9]', char):
            encoded_name += char
        else:
            encoded_name += f"_{ord(char):x}"
            
    clean_name = re.sub(r'_+', '_', encoded_name).strip('_')
    final_name = f"kwd_{clean_name}"
    return final_name[:63]

class NewsDBManager:
    def __init__(self):
        # 1. 영구 저장소 활성화
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)
        
        # 2. CPU 기반 임베딩 설정 (VRAM 보호)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2",
            device="cpu" 
        )

    def index_keyword_folder(self, keyword):
        """JSON 데이터를 읽어 DB에 색인 (중복 시 업데이트)"""
        collection_name = sanitize_collection_name(keyword)
        collection = self.client.get_or_create_collection(
            name=collection_name, 
            embedding_function=self.embedding_fn
        )
        
        keyword_dir = os.path.join(NEWS_BASE_DIR, keyword)
        if not os.path.exists(keyword_dir):
            print(f"❌ [오류] {keyword} 폴더가 존재하지 않습니다.")
            return

        total_indexed = 0
        for source in os.listdir(keyword_dir):
            source_path = os.path.join(keyword_dir, source)
            if not os.path.isdir(source_path): continue
            
            for file in os.listdir(source_path):
                if not file.endswith(".json"): continue
                
                file_path = os.path.join(source_path, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        doc_id = f"{data['source']}_{data['index']}"
                        
                        collection.upsert( # add 대신 upsert 사용하여 중복 방지
                            documents=[data['content']],
                            metadatas=[{
                                "source": data['source'], 
                                "title": data['title'], 
                                "url": data['url'],
                                "date": data['date']
                            }],
                            ids=[doc_id]
                        )
                        total_indexed += 1
                except Exception as e:
                    print(f"⚠️ {file} 색인 오류: {e}")

        return collection.count()

    # --- [추가] 데이터 삭제 프로토콜 ---

    def delete_keyword_collection(self, keyword):
        """특정 키워드 컬렉션 전체 삭제"""
        try:
            collection_name = sanitize_collection_name(keyword)
            self.client.delete_collection(name=collection_name)
            print(f"✅ [삭제 완료] 키워드 컬렉션: {keyword}")
            return True
        except Exception as e:
            print(f"❌ 삭제 실패: {e}")
            return False

    def delete_document_by_id(self, keyword, doc_id):
        """특정 문서 ID로 개별 삭제 (예: Google_G0001)"""
        try:
            collection_name = sanitize_collection_name(keyword)
            collection = self.client.get_collection(name=collection_name)
            collection.delete(ids=[doc_id])
            print(f"✅ [삭제 완료] 문서 ID: {doc_id} (키워드: {keyword})")
            return True
        except Exception as e:
            print(f"❌ 문서 삭제 실패: {e}")
            return False

    def get_all_collection_stats(self):
        """저장된 모든 키워드 현황 보고"""
        collections = self.client.list_collections()
        return [{"Keyword": col.name, "Count": col.count()} for col in collections]

    def reset_all_data(self):
        """데이터베이스 전체 초기화"""
        try:
            for col in self.client.list_collections():
                self.client.delete_collection(name=col.name)
            return True
        except Exception as e:
            print(f"❌ 초기화 실패: {e}")
            return False