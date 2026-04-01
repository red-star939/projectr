import os
import sys
import chromadb
from llama_cpp import Llama
from datetime import datetime
import re

# 1단계: 경로 및 환경 설정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
MODEL_PATH = os.path.join(PROJECT_ROOT, "model", "Phi-3.5-mini-instruct-Q4_K_M.gguf")
CHROMA_PATH = os.path.join(PROJECT_ROOT, "data", "chroma_db")
SUMMARY_PATH = os.path.join(PROJECT_ROOT, "summaries")

if not os.path.exists(SUMMARY_PATH):
    os.makedirs(SUMMARY_PATH)

class BatIndividualSummarizer:
    def __init__(self):
        print(f"🦇 LLM 개별 분석 엔진 가동... (RTX 4050 가속)")
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=8192,       # 개별 문서 처리이므로 8k면 충분합니다.
            n_gpu_layers=-1, 
            verbose=False
        )
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)

    def _stream_response(self, prompt):
        """실시간 스트리밍 출력 서브루틴"""
        stream = self.llm(prompt, max_tokens=1024, stop=["<|end|>"], stream=True)
        full_text = ""
        for output in stream:
            token = output['choices'][0]['text']
            full_text += token
            sys.stdout.write(token); sys.stdout.flush()
        return full_text

    def list_collections(self):
        """DB에 저장된 키워드 리스트 출력"""
        collections = self.client.list_collections()
        return [col.name for col in collections]

    def process_keyword(self, collection_name):
        collection = self.client.get_collection(name=collection_name)
        results = collection.get()
        
        ids = results.get("ids", [])
        documents = results.get("documents", [])
        metadatas = results.get("metadatas", [])
        
        total = len(ids)
        print(f"🤖 '{collection_name}'에서 총 {total}개의 문서를 발견했습니다.")
        
        for i in range(total):
            doc_id = ids[i]
            content = documents[i]
            meta = metadatas[i] if metadatas else {}
            title = meta.get('title', 'No Title')
            
            print(f"\n[{i+1}/{total}] 분석 중: {title}")
            print("-" * 50)
            
            # 노이즈 제거 및 본질 추출 프롬프트 설계
            prompt = (
                f"<|system|>\n당신은 배트 컴퓨터의 수석 전략가입니다. "
                f"제공된 텍스트에서 광고, 불필요한 인사말, 기자 정보, 저작권 문구 등 노이즈를 모두 제거하십시오. "
                f"오직 핵심 팩트와 정보의 본질만을 추출하여 논리적인 한국어 요약본을 작성하십시오.<|end|>\n"
                f"<|user|>\n문서 ID: {doc_id}\n제목: {title}\n내용:\n{content}<|end|>\n"
                f"<|assistant|>\n"
            )
            
            summary_content = self._stream_response(prompt)
            print("\n" + "-" * 50)
            
            # 개별 파일 저장 프로토콜
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:30]
            filename = f"SUMMARY_{collection_name}_{doc_id}_{datetime.now().strftime('%H%M%S')}.md"
            save_path = os.path.join(SUMMARY_PATH, filename)
            
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(f"# 🔍 개별 뉴스 분석 리포트\n\n")
                f.write(f"- **문서 고유 ID**: `{doc_id}`\n")
                f.write(f"- **원본 제목**: {title}\n")
                f.write(f"- **분석 일시**: {datetime.now().isoformat()}\n\n")
                f.write(f"## 📝 핵심 요약 내용\n\n{summary_content}\n")
            
            print(f"💾 개별 리포트 저장 완료: {filename}")

def main():
    summarizer = BatIndividualSummarizer()
    keywords = summarizer.list_collections()
    
    if not keywords:
        print("❌ DB에 저장된 키워드가 없습니다."); return

    print("\n" + "="*60)
    print("📋 분석 가능한 키워드 색인 목록")
    for idx, kw in enumerate(keywords):
        print(f"[{idx+1}] {kw}")
    print("="*60)
    
    choice = input("분석할 키워드 번호를 선택하십시오 (종료: q): ")
    if choice.lower() == 'q': return
    
    try:
        selected_kw = keywords[int(choice)-1]
        summarizer.process_keyword(selected_kw)
        print(f"\n✨ '{selected_kw}'에 대한 모든 개별 분석이 종료되었습니다.")
    except Exception as e:
        print(f"❌ 시스템 오류: {e}")

if __name__ == "__main__":
    main()