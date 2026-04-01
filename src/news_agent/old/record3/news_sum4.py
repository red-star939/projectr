import os
import sys
import json
import chromadb
import re
import time
from llama_cpp import Llama

# [Step 1] 상대 경로 설정 (홍 님의 환경 최적화)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))

MODEL_PATH = os.path.join(BASE_DIR, "model", "EXAONE-3.0-7.8B-Instruct-Q4_K_M.gguf")
PROMPT_JSON = os.path.join(BASE_DIR, "model", "prompt", "news_prompts.json")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "News_DB")
REPORT_DIR = os.path.join(BASE_DIR, "reports") # 리포트 저장 폴더

def sanitize_collection_name(name):
    encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
    return f"kwd_{encoded}"[:63]

class BatExaoneReporter:
    def __init__(self):
        # 1. 프롬프트 및 DB 로드
        with open(PROMPT_JSON, 'r', encoding='utf-8') as f:
            self.prompt_cfg = json.load(f)
        self.client = chromadb.PersistentClient(path=DB_PATH)
        
        # 2. EXAONE 엔진 최적화 (VRAM 6GB 보호 모드)
        print(f"[*] EXAONE 분석기 기동: {os.path.basename(MODEL_PATH)}")
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=4096,           # 7.8B 모델 부하를 고려한 4K 컨텍스트
            n_gpu_layers=-1,      # RTX 4050 전량 활용
            type_k=2,             # 4-bit KV Cache
            type_v=2,
            flash_attn=True,
            verbose=False
        )

    def _generate(self, system, user, stream=False):
        prompt = f"[|system|]\n{system}[|sep|]\n[|user|]\n{user}[|sep|]\n[|assistant|]\n"
        return self.llm(prompt, stream=stream, **self.prompt_cfg['params'])

    def _save_to_md(self, keyword, content):
        """생성된 리포트를 Markdown 파일로 저장"""
        if not os.path.exists(REPORT_DIR):
            os.makedirs(REPORT_DIR)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"Report_{keyword}_{timestamp}.md"
        file_path = os.path.join(REPORT_DIR, filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# 뉴스 분석 리포트: {keyword}\n\n")
            f.write(f"- **분석 시각**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **분석 모델**: EXAONE-3.0-7.8B-Instruct\n\n")
            f.write("---\n\n")
            f.write(content)
        
        return file_path

    def summarize(self, keyword):
        col_name = sanitize_collection_name(keyword)
        try:
            collection = self.client.get_collection(name=col_name)
            results = collection.get()
            docs = results['documents']
            if not docs: return print(f"[!] 데이터 없음")
            
            # Map Phase: 개별 압축
            print(f"[*] {len(docs)}개 기사 분석 및 정보 압축 중...")
            summaries = []
            for i, doc in enumerate(docs, 1):
                sys.stdout.write(f"    -> [{i}/{len(docs)}] 처리 중...\r")
                sys_msg = self.prompt_cfg['prompts']['map_phase']['system']
                user_msg = self.prompt_cfg['prompts']['map_phase']['user_template'].format(document=doc)
                res = self._generate(sys_msg, user_msg)
                summaries.append(f"기사 {i} 요약: {res['choices'][0]['text'].strip()}")
            
            # Reduce Phase: 통합 리포트 및 실시간 파일 캡처
            print(f"\n\n[*] 최종 통합 리포트 생성 및 저장 중...")
            print("="*50)
            
            combined = "\n\n".join(summaries)
            sys_msg = self.prompt_cfg['prompts']['reduce_phase']['system']
            user_msg = self.prompt_cfg['prompts']['reduce_phase']['user_template'].format(keyword=keyword, summaries=combined)
            
            full_report = ""
            stream_res = self._generate(sys_msg, user_msg, stream=True)
            
            for chunk in stream_res:
                token = chunk['choices'][0]['text']
                sys.stdout.write(token)
                sys.stdout.flush()
                full_report += token # 실시간 텍스트 캡처
            
            # 파일 저장 실행
            report_path = self._save_to_md(keyword, full_report)
            print("\n" + "="*50)
            print(f"[*] 리포트 추출 완료: {report_path}")

        except Exception as e:
            print(f"\n[!] 연산 오류: {e}")

if __name__ == "__main__":
    summarizer = BatExaoneReporter()
    summarizer.summarize(input("\n분석 키워드 입력: ").strip())