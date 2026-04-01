import os
import sys
import json
import chromadb
import re
from llama_cpp import Llama

# [Step 1] 상대 경로 설정 최적화
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))

MODEL_PATH = os.path.join(BASE_DIR, "model", "Phi-3.5-mini-instruct-Q4_K_M.gguf")
PROMPT_JSON = os.path.join(BASE_DIR, "model", "prompt", "news_prompts.json")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "News_DB")

def sanitize_collection_name(name):
    """한글 키워드를 ChromaDB 규격에 맞게 변환"""
    encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
    return f"kwd_{encoded}"[:63]

class PromptManager:
    """외부 JSON 프롬프트를 관리 (Key 불일치 수정)"""
    def __init__(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)
    
    def get_map(self, doc):
        cfg = self.data['prompts']['map_phase']
        # 기존 'user'에서 'user_template'으로 키 수정
        return cfg['system'], cfg['user_template'].format(document=doc)

    def get_reduce(self, keyword, summaries):
        cfg = self.data['prompts']['reduce_phase']
        # 기존 'user'에서 'user_template'으로 키 수정
        return cfg['system'], cfg['user_template'].format(keyword=keyword, summaries=summaries)

    @property
    def params(self):
        return self.data['params']

class BatHierarchicalSummarizer:
    def __init__(self):
        self.prompts = PromptManager(PROMPT_JSON)
        self.client = chromadb.PersistentClient(path=DB_PATH)
        
        # 2. Phi-3.5-mini 모델 최적화 가동 (VRAM 6GB 보호 모드)
        print(f"[*] 배트 컴퓨터 엔진 가동: {os.path.basename(MODEL_PATH)}")
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=8192,
            n_gpu_layers=-1,      # RTX 4050 전량 할당
            type_k=2,             # Key 캐시 4비트 양자화
            type_v=2,             # Value 캐시 4비트 양자화
            flash_attn=True,
            verbose=False
        )

    def _generate(self, system, user, stream=False):
        """Phi-3.5 전용 인스트럭트 템플릿 적용"""
        prompt = f"<|system|>\n{system}<|end|>\n<|user|>\n{user}<|end|>\n<|assistant|>\n"
        return self.llm(prompt, stream=stream, **self.prompts.params)

    def summarize(self, keyword):
        col_name = sanitize_collection_name(keyword)
        try:
            collection = self.client.get_collection(name=col_name)
            results = collection.get()
            docs = results['documents']
            if not docs:
                print(f"[!] '{keyword}' 데이터를 찾을 수 없습니다."); return
            
            # 1. Map Phase: 개별 압축
            print(f"[*] {len(docs)}개 기사 데이터 분석 및 정보 압축 시작...")
            summaries = []
            for i, doc in enumerate(docs, 1):
                sys.stdout.write(f"    -> [{i}/{len(docs)}] 기사 분석 중...\r")
                sys.stdout.flush()
                sys_msg, user_msg = self.prompts.get_map(doc)
                res = self._generate(sys_msg, user_msg)
                summaries.append(f"기사 {i} 요약:\n{res['choices'][0]['text'].strip()}")
            
            # 2. Reduce Phase: 최종 통합 (실시간 스트리밍)
            print(f"\n\n[*] 최종 통합 리포트 생성 중 (Reduce Phase)...")
            print("="*50)
            
            combined_summary = "\n\n".join(summaries)
            sys_msg, user_msg = self.prompts.get_reduce(keyword, combined_summary)
            
            stream_res = self._generate(sys_msg, user_msg, stream=True)
            for chunk in stream_res:
                token = chunk['choices'][0]['text']
                sys.stdout.write(token)
                sys.stdout.flush()
            print("\n" + "="*50)

        except Exception as e:
            print(f"\n[!] 연산 오류 발생: {e}")

if __name__ == "__main__":
    summarizer = BatHierarchicalSummarizer()
    target = input("\n분석 키워드 입력: ").strip()
    if target:
        summarizer.summarize(target)