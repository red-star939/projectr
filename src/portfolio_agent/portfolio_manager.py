import chromadb
from chromadb.utils import embedding_functions
import os
import sys
import re
import streamlit as st # [추가] 세션 상태 확인용
from datetime import datetime
from pathlib import Path

class BatPortfolioAgent:
    def __init__(self):
        # [1] 상대 경로 설정 (프로젝트 루트 확보)
        self.root_dir = Path(__file__).resolve().parent.parent.parent
        
        # [2] 공유 임베딩 모델 확인 및 지연 로딩 [핵심 수정 사항]
        if 'embedding_fn' in st.session_state:
            self.embedding_fn = st.session_state.embedding_fn
            print("[*] Unified Dashboard의 임베딩 엔진을 공유합니다.")
        else:
            # 예열된 모델이 없을 경우 직접 로드하여 세션에 공유
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="jhgan/ko-sroberta-multitask"
            )
            st.session_state.embedding_fn = self.embedding_fn
        
        # [3] 지능형 데이터베이스 경로 설정
        ns_db_path = str(self.root_dir / "data" / "NS_DB")
        fs_db_path = str(self.root_dir / "data" / "FS_DB")
        
        self.ns_client = chromadb.PersistentClient(path=ns_db_path)
        self.fs_client = chromadb.PersistentClient(path=fs_db_path)

    def get_company_context(self, target_corp):
        """가공된 두 가지 리포트(NS/FS)를 인출하고 상태를 보고합니다."""
        status = {"ns": False, "fs": False}
        
        # 1. NS_DB(뉴스 지능) 인출
        try:
            ns_col = self.ns_client.get_collection(name="final_reports", embedding_function=self.embedding_fn)
            ns_res = ns_col.get(ids=[f"SUMMARY_{target_corp}"])
            ns_doc = ns_res['documents'][0] if ns_res['documents'] else "뉴스 요약 데이터 부재"
            status["ns"] = True if ns_res['documents'] else False
        except:
            ns_doc = "NS_DB 접근 오류"

        # 2. FS_DB(재무 지능) 인출
        try:
            fs_col = self.fs_client.get_collection(name="financial_reports", embedding_function=self.embedding_fn)
            fs_res = fs_col.get(ids=[f"REPORT_{target_corp}"])
            fs_doc = fs_res['documents'][0] if fs_res['documents'] else "재무 리포트 부재"
            status["fs"] = True if fs_res['documents'] else False
        except:
            fs_doc = "FS_DB 접근 오류"

        return {"ns_report": ns_doc, "fs_report": fs_doc, "status": status}

    def generate_strategy(self, target_corp, context, reporter_instance):
        """교차 분석 전략 생성 로직"""
        prompt = f"""
        당신은 수석 투자 전략가입니다. 아래의 분석된 데이터를 바탕으로 {target_corp}의 포트폴리오를 제안하세요.
        
        [뉴스 요약 지능]: {context['ns_report']}
        [재무 분석 지능]: {context['fs_report']}
        
        시장 흐름과 내재 가치 사이의 괴리를 분석하고 최종 비중을 제안하십시오.
        """
        return reporter_instance._generate("수석 분석가 모드", prompt, stream=True)

    def save_portfolio_report(self, corp_name, content):
        """결과 저장"""
        save_path = self.root_dir / "data" / "Portfolio"
        os.makedirs(save_path, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = save_path / f"Portfolio_{corp_name}_{timestamp}.md"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return str(file_path)