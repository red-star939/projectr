import os
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

class BatSummarizer:
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
        """DB에서 키워드별 문서들을 가져와 하나로 병합"""
        col_name = sanitize_collection_name(keyword)
        try:
            collection = self.client.get_collection(name=col_name)
            results = collection.get()
            
            if not results['documents']:
                return None
                
            # 문서들을 구조화된 텍스트로 변환
            context = ""
            for i, doc in enumerate(results['documents'], 1):
                title = results['metadatas'][i-1].get('title', 'Untitled')
                context += f"\n[Document {i}]\nTitle: {title}\nContent: {doc}\n---\n"
            return context
        except:
            return None

    def summarize(self, keyword):
        """통합 요약 실행"""
        context = self.get_news_content(keyword)
        if not context:
            return f"'{keyword}'에 대한 데이터를 찾을 수 없습니다."

        # Phi-3.5용 인스트럭트 프롬프트 구성
        prompt = f"<|system|>\nYou are a professional news analyst. Summarize the following news articles concisely. <|end|>\n<|user|>\nKeyword: {keyword}\n\n{context}\n\nPlease provide a summary in Korean including: 1. Main issues, 2. Key entities, 3. Overall conclusion. <|end|>\n<|assistant|>\n"
        
        print(f"[*] '{keyword}' 관련 기사 요약 분석 중...")
        response = self.llm(
            prompt,
            max_tokens=1024,
            temperature=0.3, # 일관된 요약을 위해 낮은 온도 설정
            stop=["<|end|>"]
        )
        return response['choices'][0]['text']

if __name__ == "__main__":
    summarizer = BatSummarizer()
    target = input("\n요약할 뉴스 키워드를 입력하세요: ").strip()
    
    report = summarizer.summarize(target)
    print("\n" + "="*50)
    print(f"   [{target}] 뉴스 분석 리포트")
    print("="*50)
    print(report)