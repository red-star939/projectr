import os
from datetime import datetime
from llama_cpp import Llama
from data_DBsave import NewsDBManager, sanitize_collection_name

# 배트 컴퓨터 핵심 경로
BASE_DIR = r"C:\Users\USER\Desktop\projectr"
MODEL_PATH = os.path.join(BASE_DIR, r"model\Phi-3.5-mini-instruct-Q4_K_M.gguf")
BRIEF_RESULT_DIR = os.path.join(BASE_DIR, "brief_result")

class StrategyAI:
    def __init__(self):
        # n_ctx=4096 유지하여 VRAM 4.5GB 사수
        self.llm = Llama(model_path=MODEL_PATH, n_gpu_layers=-1, n_ctx=4096, verbose=False)
        self.db_manager = NewsDBManager()
        os.makedirs(BRIEF_RESULT_DIR, exist_ok=True)

    def compress_docs(self, docs):
        """각 문서를 1문장으로 요약하여 컨텍스트 밀도를 높입니다."""
        compressed_list = []
        for idx, doc in enumerate(docs):
            # 홍님의 16코어 CPU를 활용한 고속 요약
            prompt = f"<|user|>\n다음 뉴스를 1문장으로 핵심만 요약하라:\n{doc[:1000]}\n<|end|>\n<|assistant|>\n"
            response = self.llm(prompt, max_tokens=150, stop=["<|end|>"])
            summary = response['choices'][0]['text'].strip()
            compressed_list.append(f"{idx+1}. {summary}")
        return "\n".join(compressed_list)

    def get_context(self, keyword, query):
        """10개의 뉴스를 가져와 농축된 컨텍스트를 생성합니다."""
        try:
            col_name = keyword if keyword.startswith("kwd_") else sanitize_collection_name(keyword)
            collection = self.db_manager.client.get_collection(
                name=col_name, 
                embedding_function=self.db_manager.embedding_fn
            )
            
            # 홍님의 요청대로 10개의 첩보를 입수
            results = collection.query(query_texts=[query], n_results=10)
            raw_docs = results['documents'][0]
            
            if not raw_docs:
                return "분석할 데이터가 존재하지 않습니다."
                
            # [핵심] 1차 농축 단계 실행
            return self.compress_docs(raw_docs)
        except Exception as e:
            return f"❌ 첩보 추출 실패: {str(e)}"

    def generate_briefing_stream(self, keyword, query):
        """농축된 정보를 바탕으로 최종 전략 보고서 생성 (Streaming)"""
        # 1단계에서 농축된 10개의 핵심 문장들을 가져옴
        compressed_context = self.get_context(keyword, query)
        
        # 2단계: 최종 합성 프롬프트 구성
        prompt = f"""<|user|>
[입수된 10대 핵심 첩보 요약]:
{compressed_context}

[질문]: {query}
위 10가지 핵심 정보를 융합하여 홍(Hong)을 위한 최종 전략 보고서를 작성하라.
형식: [요약] [본론] [결론] 순으로 작성할 것.
<|end|>
<|assistant|>
"""
        return self.llm(prompt, max_tokens=1500, stream=True, stop=["<|end|>"])

    def save_briefing(self, keyword, content):
        """분석 결과 영구 보관 로직"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"FINAL_STRATEGY_{keyword}_{timestamp}.txt"
        path = os.path.join(BRIEF_RESULT_DIR, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"--- PROJECT R: STRATEGIC REPORT ---\nDATE: {datetime.now()}\n\n{content}")
        return path