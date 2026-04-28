import streamlit as st
import os
import sys
import json
import chromadb
import re
import time
import gc
from datetime import datetime
from llama_cpp import Llama
from chromadb.utils import embedding_functions

# [Step 1] 상대 경로 및 상수 설정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))

MODEL_PATH = os.path.join(BASE_DIR, "model", "EXAONE-3.0-7.8B-Instruct-Q4_K_M.gguf")
PROMPT_JSON = os.path.join(BASE_DIR, "model", "prompt", "news_prompts.json")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "News_DB")
NS_DB_PATH = os.path.join(PROJECT_ROOT, "data", "NS_DB")
REPORT_DIR = os.path.join(BASE_DIR, "reports")

# [ImportError 해결] 최상위 레벨에 함수 배치
def sanitize_collection_name(name):
    """news_fast_stream.py와 동일한 명칭 인코딩 규칙을 적용합니다."""
    encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
    return f"kwd_{encoded}"[:63]

class BatExaoneReporter:
    def __init__(self):
        # 1. 프롬프트 설정 로드
        if not os.path.exists(PROMPT_JSON):
            raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {PROMPT_JSON}")
        with open(PROMPT_JSON, 'r', encoding='utf-8') as f:
            self.prompt_cfg = json.load(f)
            
        # 2. DB 클라이언트 초기화
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.ns_client = chromadb.PersistentClient(path=NS_DB_PATH)
        
        # 3. 공유 임베딩 엔진 활용 (없을 시 지연 로딩)
        if 'embedding_fn' in st.session_state:
            self.embedding_fn = st.session_state.embedding_fn
        else:
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="jhgan/ko-sroberta-multitask"
            )
            st.session_state.embedding_fn = self.embedding_fn

        # 4. 공유 LLM 엔진 활용 (없을 시 VRAM 로딩)
        if 'llm_engine' in st.session_state:
            self.llm = st.session_state.llm_engine
        else:
            self.llm = Llama(
                model_path=MODEL_PATH,
                n_ctx=4096,
                n_gpu_layers=-1,
                type_k=2, type_v=2, # 4-bit KV Cache 최적화
                flash_attn=True,
                verbose=False
            )
            st.session_state.llm_engine = self.llm

    def _generate(self, system, user, stream=False):
        """EXAONE-3.0 템플릿 기반 추론 실행"""
        prompt = f"[|system|]\n{system}[|sep|]\n[|user|]\n{user}[|sep|]\n[|assistant|]\n"
        return self.llm(prompt, stream=stream, **self.prompt_cfg['params'])

    def _save_to_db(self, keyword, content):
        """최종 리포트를 NS_DB에 SUMMARY_ID로 영구 저장합니다."""
        ns_collection = self.ns_client.get_or_create_collection(
            name="final_reports",
            embedding_function=self.embedding_fn
        )
        doc_id = f"SUMMARY_{keyword}"
        ns_collection.upsert(
            ids=[doc_id],
            documents=[f"# {keyword} 통합 분석 리포트\n\n{content}"],
            metadatas=[{"type": "summary_report", "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}]
        )

    def _save_to_md(self, keyword, content, today_str):
        """물리 파일로 리포트 추출"""
        if not os.path.exists(REPORT_DIR): os.makedirs(REPORT_DIR)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        file_path = os.path.join(REPORT_DIR, f"Report_{keyword}_{timestamp}.md")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path