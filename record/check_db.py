import chromadb
from pathlib import Path
import pprint

def verify_chroma_db():
    base_dir = Path(__file__).resolve().parent
    db_path = str(base_dir / "data" / "FS_DB")
    
    print(f"🔍 [시스템 점검] ChromaDB 경로 확인: {db_path}")
    
    if not Path(db_path).exists():
        print("❌ 오류: DB 폴더가 존재하지 않습니다.")
        return

    # [수정] 별도의 임베딩 함수를 정의하지 않고 기본 설정을 사용합니다.
    client = chromadb.PersistentClient(path=db_path)
    
    try:
        # 기존에 'default'로 생성된 컬렉션을 그대로 불러옵니다.
        collection = client.get_collection(name="financial_reports")
        
        doc_count = collection.count()
        print(f"✅ 연결 성공! 현재 저장된 총 리포트 수: {doc_count}개")

        if doc_count > 0:
            results = collection.get(limit=5)
            print("\n📌 최근 저장된 데이터 ID 목록:")
            for doc_id in results['ids']:
                print(f" - {doc_id}")

            sample_id = results['ids'][0]
            sample_data = collection.get(ids=[sample_id])
            
            print(f"\n📄 데이터 샘플 확인 ({sample_id}):")
            print("-" * 50)
            print(f"🔹 메타데이터: {sample_data['metadatas'][0]}")
            # 본문 가독성을 위해 개행 문자 처리 후 일부 출력
            content_peek = sample_data['documents'][0][:200].replace('\n', ' ')
            print(f"🔹 본문 미리보기: {content_peek}...")
            print("-" * 50)
        else:
            print("⚠️ 저장된 문서가 없습니다. 분석 앱에서 데이터를 먼저 생성해 주세요.")

    except Exception as e:
        print(f"❌ DB 조회 중 에러 발생: {e}")

if __name__ == "__main__":
    verify_chroma_db()