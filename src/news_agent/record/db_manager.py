import os
import chromadb
import re
from chromadb.utils import embedding_functions

# [설정] 기존 DB 경로 유지 (상대 경로)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
DB_DIR = os.path.join(PROJECT_ROOT, "data", "News_DB")

def sanitize_collection_name(name):
    encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
    return f"kwd_{encoded}"[:63]

class BatDBManager:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=DB_DIR)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )

    def list_all_keywords(self):
        """현재 DB에 저장된 모든 키워드(컬렉션) 목록 표시"""
        collections = self.client.list_collections()
        if not collections:
            print("\n[!] 저장된 데이터가 없습니다.")
            return []
        
        print("\n" + "="*30)
        print("   현재 저장된 키워드 목록")
        print("="*30)
        for i, col in enumerate(collections, 1):
            # 역인코딩은 복잡하므로 컬렉션 이름 자체를 출력하거나 별도 매핑 테이블 권장
            print(f"{i}. {col.name} (문서 수: {col.count()})")
        return collections

    def view_documents(self, keyword):
        """특정 키워드의 문서 내용 조회"""
        col_name = sanitize_collection_name(keyword)
        try:
            collection = self.client.get_collection(name=col_name, embedding_function=self.embedding_fn)
            results = collection.get()
            
            if not results['ids']:
                print(f"\n[!] '{keyword}' 컬렉션에 문서가 없습니다.")
                return

            print(f"\n" + "-"*50)
            print(f"   [{keyword}] 컬렉션 문서 리스트")
            print("-"*50)
            for i in range(len(results['ids'])):
                title = results['metadatas'][i].get('title', '제목 없음')
                doc_id = results['ids'][i]
                print(f"[{i+1}] ID: {doc_id} | 제목: {title}")
            
            return results['ids']
        except Exception as e:
            print(f"❌ 해당 키워드를 찾을 수 없습니다: {e}")

    def delete_data(self, keyword, doc_id=None):
        """데이터 삭제 (doc_id가 없으면 컬렉션 전체 삭제)"""
        col_name = sanitize_collection_name(keyword)
        try:
            if doc_id:
                # 개별 문서 삭제
                collection = self.client.get_collection(name=col_name)
                collection.delete(ids=[doc_id])
                print(f"✅ [삭제 완료] 문서 ID: {doc_id}")
            else:
                # 컬렉션 전체 삭제
                self.client.delete_collection(name=col_name)
                print(f"✅ [삭제 완료] 키워드 '{keyword}' 전체 데이터 소거")
        except Exception as e:
            print(f"❌ 삭제 중 오류 발생: {e}")

if __name__ == "__main__":
    manager = BatDBManager()
    
    while True:
        print("\n" + "### News_DB 관리 시스템 ###")
        print("1. 전체 키워드 목록 보기")
        print("2. 특정 키워드 문서 조회")
        print("3. 문서/키워드 삭제")
        print("Q. 종료")
        
        choice = input("\n명령을 선택하세요: ").strip().upper()
        
        if choice == '1':
            manager.list_all_keywords()
            
        elif choice == '2':
            kwd = input("조회할 키워드를 입력하세요: ").strip()
            manager.view_documents(kwd)
            
        elif choice == '3':
            kwd = input("삭제 대상 키워드를 입력하세요: ").strip()
            ids = manager.view_documents(kwd)
            if ids:
                target = input("\n삭제할 문서의 번호를 입력하세요 (전체 삭제는 'ALL'): ").strip()
                if target.upper() == 'ALL':
                    manager.delete_data(kwd)
                elif target.isdigit() and 0 < int(target) <= len(ids):
                    manager.delete_data(kwd, ids[int(target)-1])
        
        elif choice == 'Q':
            break