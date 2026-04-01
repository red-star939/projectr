import os
import json
import chromadb
from chromadb.utils import embedding_functions
import re
import hashlib

# [설정] 홍 님의 실제 데이터 경로
NEWS_BASE_DIR = r"C:\Users\USER\projectr\src\news_agent\crawled_news"
CHROMA_PATH = r"C:\Users\USER\projectr\src\news_agent\data\chroma_db"

def sanitize_collection_name(name):
    """한글 키워드를 ChromaDB 규격(영문/숫자/_-)에 맞게 변환"""
    encoded_name = ""
    for char in name:
        if re.match(r'[a-zA-Z0-9]', char):
            encoded_name += char
        else:
            encoded_name += f"_{ord(char):x}"
    clean_name = re.sub(r'_+', '_', encoded_name).strip('_')
    return f"kwd_{clean_name}"[:63]

class NewsDBManager:
    def __init__(self):
        # 1. 영구 저장소 활성화
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)
        
        # 2. 한국어 지원 임베딩 설정 (기존 all-MiniLM보다 한국어에 적합한 모델 추천)
        # 만약 속도가 중요하다면 기존 cpu 설정을 유지하십시오.
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="snunlp/KR-SBERT-V4C", # 한국어 뉴스 분석 최적화
            device="cpu" 
        )

    def _generate_unique_id(self, url):
        """URL 기반 고유 해시 생성 (중복 방지 핵심)"""
        return hashlib.md5(url.encode()).hexdigest()

    def index_all_folders(self):
        """crawled_news 하위의 모든 키워드 폴더를 순회하며 색인"""
        if not os.path.exists(NEWS_BASE_DIR):
            print(f"❌ [오류] 경로를 찾을 수 없습니다: {NEWS_BASE_DIR}")
            return

        keywords = [d for d in os.listdir(NEWS_BASE_DIR) if os.path.isdir(os.path.join(NEWS_BASE_DIR, d))]
        
        for kwd in keywords:
            print(f"[*] 키워드 '{kwd}' 색인 시작...")
            count = self.index_keyword_folder(kwd)
            print(f"    -> {kwd} 완료 (현재 총 {count}개 저장됨)")

    def index_keyword_folder(self, keyword):
        """특정 키워드 폴더 내의 01.json, 02.json 등을 읽어 DB 저장"""
        collection_name = sanitize_collection_name(keyword)
        collection = self.client.get_or_create_collection(
            name=collection_name, 
            embedding_function=self.embedding_fn
        )
        
        keyword_dir = os.path.join(NEWS_BASE_DIR, keyword)
        total_indexed = 0
        
        for file in os.listdir(keyword_dir):
            if not file.endswith(".json"): continue
            
            file_path = os.path.join(keyword_dir, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # [핵심] URL 기반 고유 ID 생성하여 중복 방지
                    doc_id = self._generate_unique_id(data['url'])
                    
                    collection.upsert(
                        documents=[data['content']],
                        metadatas=[{
                            "title": data['title'], 
                            "url": data['url'],
                            "collected_at": data.get('collected_at', 'unknown')
                        }],
                        ids=[doc_id]
                    )
                    total_indexed += 1
            except Exception as e:
                print(f"⚠️ {file} 색인 오류: {e}")

        return collection.count()

    def get_stats(self):
        """전체 DB 상태 보고"""
        print("\n" + "="*30)
        print("   ChromaDB 현황 보고서")
        print("="*30)
        for col in self.client.list_collections():
            print(f"- 컬렉션: {col.name} | 데이터 수: {col.count()}")

# --- 실행부 ---
if __name__ == "__main__":
    db_manager = NewsDBManager()
    
    # 1. 모든 폴더 자동 스캔 및 색인
    db_manager.index_all_folders()
    
    # 2. 결과 리포트 출력
    db_manager.get_stats()