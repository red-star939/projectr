import os
import chromadb
from chromadb.utils import embedding_functions
import re
from datetime import datetime

# 1단계: 경로 설정 및 환경 구축
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
CHROMA_PATH = os.path.join(PROJECT_ROOT, "data", "chroma_db")
EXPORT_PATH = os.path.join(PROJECT_ROOT, "exports")

if not os.path.exists(EXPORT_PATH):
    os.makedirs(EXPORT_PATH)

def sanitize_collection_name(name):
    """한글 키워드 인코딩 (기존 유지)"""
    encoded_name = ""
    for char in name:
        if re.match(r'[a-zA-Z0-9]', char):
            encoded_name += char
        else:
            encoded_name += f"_{ord(char):x}"
    clean_name = re.sub(r'_+', '_', encoded_name).strip('_')
    final_name = f"kwd_{clean_name}"
    return final_name[:63]

def export_data(keyword, ids, documents, metadatas, mode='txt'):
    """데이터 추출 통합 서브루틴 (txt 및 md 지원)"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    extension = 'txt' if mode == 'txt' else 'md'
    filename = f"export_{keyword}_{timestamp}.{extension}"
    full_path = os.path.join(EXPORT_PATH, filename)
    
    try:
        with open(full_path, "w", encoding="utf-8") as f:
            if mode == 'md':
                # Markdown 전용 레이아웃
                f.write(f"# 🦇 Bat Computer Data Export: {keyword}\n\n")
                f.write(f"- **Export Date**: `{datetime.now().isoformat()}`\n")
                f.write(f"- **Total Records**: {len(ids)}\n\n")
                f.write("---\n\n")
                
                for i in range(len(ids)):
                    meta = metadatas[i] if metadatas else {}
                    f.write(f"## [{i+1}] {meta.get('title', 'No Title')}\n\n")
                    f.write(f"| Category | Information |\n")
                    f.write(f"| :--- | :--- |\n")
                    f.write(f"| **ID** | {ids[i]} |\n")
                    f.write(f"| **Source** | {meta.get('source', 'N/A')} |\n")
                    f.write(f"| **Date** | {meta.get('date', 'N/A')} |\n")
                    f.write(f"| **URL** | [Link]({meta.get('url', '#')}) |\n\n")
                    f.write(f"### Content\n\n{documents[i]}\n\n")
                    f.write("---\n\n")
            else:
                # 기본 TXT 레이아웃 (기존 유지)
                f.write(f"=== Bat Computer Data Export: {keyword} ===\n")
                f.write(f"Export Date: {datetime.now().isoformat()}\n")
                f.write(f"Total Records: {len(ids)}\n")
                f.write("-" * 60 + "\n\n")
                for i in range(len(ids)):
                    meta = metadatas[i] if metadatas else {}
                    f.write(f"[{i+1}] Document ID: {ids[i]}\n")
                    f.write(f"Source: {meta.get('source', 'N/A')}\n")
                    f.write(f"Title: {meta.get('title', 'N/A')}\n")
                    f.write(f"Date: {meta.get('date', 'N/A')}\n")
                    f.write(f"Content:\n{documents[i]}\n")
                    f.write("\n" + "="*60 + "\n\n")
                    
        return full_path
    except Exception as e:
        return f"Error: {str(e)}"

def run_viewer():
    print("🦇 Bat Computer DB Terminal & Multi-Exporter Activated.")
    
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2", device="cpu" 
    )

    while True:
        print("\n" + "="*60)
        keyword = input("추출할 키워드 입력 ('q' 종료): ")
        if keyword.lower() == 'q': break
            
        collection_name = sanitize_collection_name(keyword)
        
        try:
            collection = client.get_collection(name=collection_name, embedding_function=embedding_fn)
            results = collection.get()
            ids, documents, metadatas = results.get("ids", []), results.get("documents", []), results.get("metadatas", [])
            
            if not ids:
                print(f"⚠️ '{keyword}'에 데이터가 없습니다."); continue

            print(f"✅ '{keyword}' 데이터 {len(ids)}건 확보.")
            print("1: TXT 파일로 추출")
            print("2: Markdown(.md) 파일로 추출")
            print("3: 두 형식 모두 추출")
            choice = input("추출 형식을 선택하십시오: ")

            if choice == '1':
                path = export_data(keyword, ids, documents, metadatas, mode='txt')
                print(f"💾 TXT 저장 완료: {path}")
            elif choice == '2':
                path = export_data(keyword, ids, documents, metadatas, mode='md')
                print(f"💾 MD 저장 완료: {path}")
            elif choice == '3':
                p1 = export_data(keyword, ids, documents, metadatas, mode='txt')
                p2 = export_data(keyword, ids, documents, metadatas, mode='md')
                print(f"💾 추출 완료:\n - {p1}\n - {p2}")
                
        except ValueError:
            print(f"⚠️ '{keyword}' 컬렉션이 존재하지 않습니다.")
        except Exception as e:
            print(f"❌ 에러: {e}")

if __name__ == "__main__":
    run_viewer()