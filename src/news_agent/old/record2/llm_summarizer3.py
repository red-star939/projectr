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
        print(f"🦇 LLM 개별 분석 엔진 가동... (RTX 4050 가속 최적화)")
        # n_threads: CPU 물리 코어 수에 맞춤 (성능 향상)
        # n_batch: 프롬프트 처리 속도 향상
        # flash_attn: 메모리 효율 및 속도 향상
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=8192,
            n_gpu_layers=-1, 
            n_threads=8,      
            n_batch=512,      
            flash_attn=True,   
            verbose=False
        )
        self.client = chromadb.PersistentClient(path=CHROMA_PATH)

    def _stream_response(self, prompt):
        """실시간 스트리밍 출력 및 중단 방지 설정"""
        # max_tokens를 2048로 상향하여 긴 요약 시 끊김 방지
        # repeat_penalty로 반복 문구 억제
        stream = self.llm(
            prompt, 
            max_tokens=2048, 
            stop=["<|end|>", "<|endoftext|>", "###"], 
            stream=True,
            repeat_penalty=1.1
        )
        
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
        
        ids, documents, metadatas = results.get("ids", []), results.get("documents", []), results.get("metadatas", [])
        total = len(ids)
        
        for i in range(total):
            doc_id, content = ids[i], documents[i]
            meta = metadatas[i] if metadatas else {}
            title = meta.get('title', 'No Title')
            
            print(f"\n[{i+1}/{total}] 분석 중: {title}")
            print("-" * 50)
            
            # 구조화된 프롬프트로 노이즈 차단 및 효율 증대
            prompt = (
                f"<|system|>\n당신은 뉴스 요약 전문가입니다. 광고, 기자 정보, 저작권 문구 등을 철저히 배제하십시오. "
                f"핵심 정보만 번호 리스트 형식으로 간결하게 답변하십시오.<|end|>\n"
                f"<|user|>\n내용: {content}<|end|>\n"
                f"<|assistant|>\n"
            )
            
            summary_content = self._stream_response(prompt)
            print("\n" + "-" * 50)
            
            # 파일 저장 (기존 유지)
            filename = f"SUMMARY_{collection_name}_{doc_id}.md"
            with open(os.path.join(SUMMARY_PATH, filename), "w", encoding="utf-8") as f:
                f.write(f"# 🔍 분석 리포트: {title}\n\n{summary_content}\n")

def main():
    summarizer = BatIndividualSummarizer()
    keywords = summarizer.list_collections()
    
    if not keywords: return

    print("\n" + "📋 분석 가능한 키워드 목록 ".center(50, "="))
    for idx, kw in enumerate(keywords):
        print(f"[{idx+1}] {kw}")
    
    choice = input("\n분석할 번호를 선택하십시오 (종료: q): ")
    if choice.lower() != 'q':
        summarizer.process_keyword(keywords[int(choice)-1])

if __name__ == "__main__":
    main()