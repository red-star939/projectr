import os
import sys
import json
import chromadb
import re
import time
from datetime import datetime # [추가] 실시간 날짜 처리를 위한 모듈
from llama_cpp import Llama

# [Step 1] 상대 경로 설정 (홍 님의 환경 최적화)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))

MODEL_PATH = os.path.join(BASE_DIR, "model", "EXAONE-3.0-7.8B-Instruct-Q4_K_M.gguf")
PROMPT_JSON = os.path.join(BASE_DIR, "model", "prompt", "news_prompts.json")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "News_DB")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

def sanitize_collection_name(name):
    encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
    return f"kwd_{encoded}"[:63]

class BatExaoneReporter:
    def __init__(self):
        # 1. 프롬프트 및 DB 로드
        if not os.path.exists(PROMPT_JSON):
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {PROMPT_JSON}")
        with open(PROMPT_JSON, 'r', encoding='utf-8') as f:
            self.prompt_cfg = json.load(f)
        self.client = chromadb.PersistentClient(path=DB_PATH)
        
        # 2. EXAONE 엔진 최적화 (VRAM 6GB 보호 모드)
        print(f"[*] EXAONE 분석기 기동: {os.path.basename(MODEL_PATH)}")
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=4096,           # 7.8B 모델 부하를 고려한 4K 컨텍스트
            n_gpu_layers=-1,      # RTX 4050 전량 활용
            type_k=2,             # 4-bit KV Cache (필수)
            type_v=2,
            flash_attn=True,
            verbose=False
        )

    def _generate(self, system, user, stream=False):
        """EXAONE-3.0 전용 [| |] 템플릿 적용"""
        prompt = f"[|system|]\n{system}[|sep|]\n[|user|]\n{user}[|sep|]\n[|assistant|]\n"
        return self.llm(prompt, stream=stream, **self.prompt_cfg['params'])

    def _save_to_md(self, keyword, content, today_str):
        """생성된 리포트를 Markdown 파일로 저장"""
        if not os.path.exists(REPORT_DIR):
            os.makedirs(REPORT_DIR)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"Report_{keyword}_{timestamp}.md"
        file_path = os.path.join(REPORT_DIR, filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"# 뉴스 분석 리포트: {keyword} ({today_str})\n\n")
            f.write(f"- **분석 시각**: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"- **분석 모델**: EXAONE-3.0-7.8B-Instruct\n\n")
            f.write("---\n\n")
            f.write(content)
        
        return file_path

    def summarize(self, keyword):
        # 실시간 날짜 획득 (예: 2026-04-01)
        today_str = datetime.now().strftime("%Y-%m-%d")
        col_name = sanitize_collection_name(keyword)
        
        try:
            collection = self.client.get_collection(name=col_name)
            results = collection.get()
            docs = results['documents']
            if not docs: return print(f"[!] '{keyword}'에 대한 데이터가 없습니다.")
            
            # 1. Map Phase: 개별 압축 (날짜 주입)
            print(f"[*] {len(docs)}개 기사 분석 시작 (기준일: {today_str})...")
            summaries = []
            map_cfg = self.prompt_cfg['prompts']['map_phase']
            
            for i, doc in enumerate(docs, 1):
                sys.stdout.write(f"    -> [{i}/{len(docs)}] 처리 중...\r")
                sys.stdout.flush()
                
                # 시스템 및 사용자 프롬프트에 날짜 주입
                sys_msg = map_cfg['system'].format(today=today_str)
                user_msg = map_cfg['user_template'].format(document=doc, today=today_str)
                
                res = self._generate(sys_msg, user_msg)
                summaries.append(f"기사 {i} 요약: {res['choices'][0]['text'].strip()}")
            
            # 2. Reduce Phase: 통합 리포트 (날짜 주입 및 스트리밍)
            print(f"\n\n[*] 최종 리포트 생성 중 (Reduce Phase)...")
            print("="*50)
            
            red_cfg = self.prompt_cfg['prompts']['reduce_phase']
            combined = "\n\n".join(summaries)
            
            # 최종 리포트 프롬프트에 날짜 주입
            sys_msg_final = red_cfg['system'].format(today=today_str)
            user_msg_final = red_cfg['user_template'].format(
                keyword=keyword, 
                summaries=combined, 
                today=today_str
            )
            
            full_report = ""
            stream_res = self._generate(sys_msg_final, user_msg_final, stream=True)
            
            for chunk in stream_res:
                token = chunk['choices'][0]['text']
                sys.stdout.write(token)
                sys.stdout.flush()
                full_report += token
            
            # 파일 저장
            report_path = self._save_to_md(keyword, full_report, today_str)
            print("\n" + "="*50)
            print(f"[*] 리포트 추출 완료: {report_path}")

        except Exception as e:
            print(f"\n[!] 연산 오류: {e}")

if __name__ == "__main__":
    summarizer = BatExaoneReporter()
    target = input("\n분석 키워드 입력: ").strip()
    if target:
        summarizer.summarize(target)