import os
import sys
import json
import chromadb
import re
import time
import gc
from datetime import datetime
from llama_cpp import Llama
from chromadb.utils import embedding_functions # [추가] DB 저장을 위한 임베딩 모듈

# [Step 1] 상대 경로 설정 (프로젝트 루트: projectr)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))

MODEL_PATH = os.path.join(BASE_DIR, "model", "EXAONE-3.0-7.8B-Instruct-Q4_K_M.gguf")
PROMPT_JSON = os.path.join(BASE_DIR, "model", "prompt", "news_prompts.json")

# [수정] 원문 DB와 요약 리포트 DB 경로 분리
DB_PATH = os.path.join(PROJECT_ROOT, "data", "News_DB")
NS_DB_PATH = os.path.join(PROJECT_ROOT, "data", "NS_DB") # [신규] 요약 리포트 전용 DB
REPORT_DIR = os.path.join(BASE_DIR, "reports")

def sanitize_collection_name(name):
    """news_fast_stream.py와 동일한 명칭 인코딩 규칙"""
    encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
    return f"kwd_{encoded}"[:63]

class BatExaoneReporter:
    def __init__(self):
        # 1. 프롬프트 및 DB 클라이언트 초기화
        if not os.path.exists(PROMPT_JSON):
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {PROMPT_JSON}")
        with open(PROMPT_JSON, 'r', encoding='utf-8') as f:
            self.prompt_cfg = json.load(f)
            
        # [수정] 두 개의 DB 클라이언트 운용 (원문용, 요약보고서용)
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.ns_client = chromadb.PersistentClient(path=NS_DB_PATH) # 없을 시 자동 생성됨
        
        # 임베딩 함수 설정 (NS_DB 저장 및 조회용)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )
        
        # 2. EXAONE 엔진 최적화 (4K 컨텍스트 유지)
        print(f"[*] EXAONE 분석기 기동: {os.path.basename(MODEL_PATH)}")
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=4096,
            n_gpu_layers=-1,
            type_k=2,
            type_v=2,
            flash_attn=True,
            verbose=False
        )

    def _generate(self, system, user, stream=False):
        """EXAONE-3.0 전용 [| |] 템플릿 적용"""
        prompt = f"[|system|]\n{system}[|sep|]\n[|user|]\n{user}[|sep|]\n[|assistant|]\n"
        return self.llm(prompt, stream=stream, **self.prompt_cfg['params'])

    def _save_to_db(self, keyword, content):
        """[수정] 최종 리포트를 새로운 NS_DB에 마크다운 형식으로 저장"""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # NS_DB 내 'final_reports' 컬렉션에 저장 (없으면 자동 생성)
        ns_collection = self.ns_client.get_or_create_collection(
            name="final_reports",
            embedding_function=self.embedding_fn
        )
        
        # 키워드별 고유 ID 생성 (중복 방지 및 최신화)
        doc_id = f"SUMMARY_{keyword}"
        ns_collection.upsert(
            ids=[doc_id],
            documents=[f"# {keyword} 통합 뉴스 분석 리포트\n\n{content}"],
            metadatas=[{
                "type": "summary_report",
                "created_at": now_str,
                "keyword": keyword
            }]
        )
        return True

    def summarize(self, keyword):
        """ 로직 유지"""
        today_str = datetime.now().strftime("%Y-%m-%d")
        col_name = sanitize_collection_name(keyword)
        
        try:
            collection = self.client.get_collection(name=col_name)
            results = collection.get()
            docs = results['documents']
            if not docs: return print(f"[!] '{keyword}'에 대한 데이터가 없습니다.")
            
            # Map Phase: 개별 요약
            summaries = []
            map_cfg = self.prompt_cfg['prompts']['map_phase']
            for i, doc in enumerate(docs, 1):
                sys_msg = map_cfg['system'].format(today=today_str)
                user_msg = map_cfg['user_template'].format(document=doc[:2500], today=today_str)
                res = self._generate(sys_msg, user_msg)
                summaries.append(f"기사 {i} 분석 요약: {res['choices'][0]['text'].strip()}")
            
            # Reduce Phase: 통합 리포트
            red_cfg = self.prompt_cfg['prompts']['reduce_phase']
            combined_summaries = "\n\n".join(summaries)
            sys_msg_final = red_cfg['system'].format(today=today_str)
            user_msg_final = red_cfg['user_template'].format(
                keyword=keyword, summaries=combined_summaries, today=today_str
            )
            
            full_report = ""
            for chunk in self._generate(sys_msg_final, user_msg_final, stream=True):
                token = chunk['choices'][0]['text']
                full_report += token
            
            # 저장 루틴 호출 (NS_DB 및 파일)
            self._save_to_db(keyword, full_report)
            self._save_to_md(keyword, full_report, today_str)
            gc.collect()

        except Exception as e:
            print(f"\n[!] 연산 오류 발생: {e}")

    def _save_to_md(self, keyword, content, today_str):
        if not os.path.exists(REPORT_DIR): os.makedirs(REPORT_DIR)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(REPORT_DIR, f"Report_{keyword}_{timestamp}.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path