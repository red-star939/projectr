import os
import chromadb
from chromadb.utils import embedding_functions
import re

# 1단계: 상대 경로 기반 프로젝트 루트 및 DB 경로 설정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
CHROMA_PATH = os.path.join(PROJECT_ROOT, "data", "chroma_db")

def sanitize_collection_name(name):
    """2단계: 한글 키워드를 ChromaDB 규격에 맞는 안전한 이름으로 인코딩"""
    encoded_name = ""
    for char in name:
        if re.match(r'[a-zA-Z0-9]', char):
            encoded_name += char
        else:
            encoded_name += f"_{ord(char):x}"
            
    clean_name = re.sub(r'_+', '_', encoded_name).strip('_')
    final_name = f"kwd_{clean_name}"
    return final_name[:63]

def run_viewer():
    print("🦇 Bat Computer DB Terminal Activated.")
    print(f"Target DB Path: {CHROMA_PATH}")
    
    if not os.path.exists(CHROMA_PATH):
        print("❌ [오류] 데이터베이스 경로를 찾을 수 없습니다. 데이터가 먼저 저장되었는지 확인하십시오.")
        return

    # 클라이언트 및 임베딩 설정 (저장 환경과 동일하게 구성)
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2",
        device="cpu" 
    )

    while True:
        print("\n" + "="*60)
        keyword = input("검색을 원하는 키워드를 입력하십시오 (종료하려면 'q' 입력): ")
        
        if keyword.lower() == 'q':
            print("세션을 종료합니다.")
            break
            
        collection_name = sanitize_collection_name(keyword)
        
        try:
            # 3단계: 컬렉션 로드 및 데이터 추출
            collection = client.get_collection(
                name=collection_name,
                embedding_function=embedding_fn
            )
            
            # 컬렉션 내 모든 데이터 가져오기
            results = collection.get()
            
            ids = results.get("ids", [])
            documents = results.get("documents", [])
            metadatas = results.get("metadatas", [])
            
            total_count = len(ids)
            print(f"\n✅ [조회 성공] '{keyword}' 데이터 총 {total_count}건 발견")
            print("-" * 60)
            
            for i in range(total_count):
                meta = metadatas[i] if metadatas else {}
                print(f"[{i+1}] 문서 ID : {ids[i]}")
                print(f"  - 출처   : {meta.get('source', 'N/A')}")
                print(f"  - 제목   : {meta.get('title', 'N/A')}")
                print(f"  - 날짜   : {meta.get('date', 'N/A')}")
                print(f"  - 본문   : {documents[i][:150]}... (이하 생략)")
                print("-" * 60)
                
        except ValueError:
            print(f"⚠️ '{keyword}'에 해당하는 컬렉션(데이터)이 존재하지 않습니다.")
        except Exception as e:
            print(f"❌ 시스템 에러 발생: {e}")

if __name__ == "__main__":
    run_viewer()