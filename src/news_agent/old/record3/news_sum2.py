import os
import sys
import chromadb
import re
from llama_cpp import Llama

# [Step 1] 경로 설정 (홍 님의 환경 기준)
MODEL_PATH = r"C:\Users\USER\projectr\src\news_agent\model\Phi-3.5-mini-instruct-Q4_K_M.gguf"
DB_PATH = r"C:\Users\USER\projectr\data\News_DB"

def sanitize_collection_name(name):
    """키워드를 DB 규격으로 변환"""
    encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
    return f"kwd_{encoded}"[:63]

class BatSummarizerStream:
    def __init__(self):
        # 1. ChromaDB 로드
        self.client = chromadb.PersistentClient(path=DB_PATH)
        
        # 2. Phi-3.5 GGUF 모델 로드 (RTX 4050 최적화)
        print(f"[*] 모델 로드 중: {os.path.basename(MODEL_PATH)}")
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=16384,         # 10개 기사 처리를 위해 16K 설정
            n_gpu_layers=-1,     # RTX 4050 GPU 가속 활성화
            flash_attn=True,      # 메모리 효율 극대화
            verbose=False
        )

    def get_news_content(self, keyword):
        """DB에서 데이터를 가져오는 과정을 실시간으로 표시"""
        col_name = sanitize_collection_name(keyword)
        try:
            print(f"[*] '{keyword}' 컬렉션 접근 중...", end="\r")
            collection = self.client.get_collection(name=col_name)
            results = collection.get()
            
            if not results['documents']:
                return None
            
            doc_count = len(results['documents'])
            print(f"[*] 총 {doc_count}개의 문서를 확보했습니다. 분석 준비 완료.")
                
            context = ""
            for i, doc in enumerate(results['documents'], 1):
                title = results['metadatas'][i-1].get('title', 'Untitled')
                context += f"\n[Document {i}]\nTitle: {title}\nContent: {doc}\n---\n"
            return context
        except Exception as e:
            print(f"\n[!] 데이터 로드 오류: {e}")
            return None

    def summarize_stream(self, keyword):
        """실시간 토큰 생성 과정을 보여주는 요약 함수"""
        context = self.get_news_content(keyword)
        if not context:
            return

        # Phi-3.5용 인스트럭트 프롬프트 구성
        prompt = f"<|system|>\nYou are a professional news analyst. Summarize the articles in Korean. <|end|>\n<|user|>\nKeyword: {keyword}\n\n{context}\n\nPlease provide a summary including: 1. Main issues, 2. Key entities, 3. Overall conclusion. <|end|>\n<|assistant|>\n"
        
        print(f"\n" + "="*50)
        print(f"   [{keyword}] 실시간 분석 리포트 생성")
        print("="*50 + "\n")

        # [실시간 처리 핵심] stream=True 설정
        response_generator = self.llm(
            prompt,
            max_tokens=1024,
            temperature=0.3,
            stop=["<|end|>"],
            stream=True  # 생성 과정을 하나씩 반환
        )
        
        full_text = ""
        for chunk in response_generator:
            token = chunk['choices'][0]['text']
            # 터미널에 토큰을 즉시 출력 (버퍼 비우기 포함)
            sys.stdout.write(token)
            sys.stdout.flush()
            full_text += token
            
        print("\n\n" + "="*50)
        print("[*] 분석이 완료되었습니다.")

if __name__ == "__main__":
    summarizer = BatSummarizerStream()
    while True:
        target = input("\n분석할 키워드를 입력하세요 (Q 종료): ").strip()
        if target.lower() == 'q': break
        
        summarizer.summarize_stream(target)