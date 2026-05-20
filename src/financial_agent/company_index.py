"""
회사명 의미 검색 인덱스 — ChromaDB + ko-sroberta 임베딩 (Phase 4).

DART CORPCODE 의 KRX 상장사(~2,500개) 를 ChromaDB collection 에 임베딩 적재.
정확/별칭 매칭 실패 시 폴백 검색에 사용:
    "삼선전자" (오타) → 삼성전자 (top hit)
    "전자" (부분어)   → 삼성전자, LG전자, ... (관련 종목들)

build_index() 는 scripts/build_company_index.py 가 1회 실행한다.
검색은 search(query, max_results) 사용.

기존 chroma_manager.py 의 financial_reports collection 과 별개로
company_index collection 을 사용한다 (같은 ChromaDB 인스턴스 공유).
"""
from __future__ import annotations

import os
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

from src.financial_agent import utils_


_COLLECTION_NAME = "company_index"
_EMBED_MODEL = "jhgan/ko-sroberta-multitask"

# ChromaDB 경로 (chroma_manager.py 와 동일)
_DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "FS_DB")

# 모듈 레벨 캐시 (재로딩 비용 절감)
_client = None
_embedding_fn = None
_collection = None


def _get_client():
    global _client
    if _client is None:
        os.makedirs(_DB_PATH, exist_ok=True)
        _client = chromadb.PersistentClient(path=_DB_PATH)
    return _client


def _get_embedding_fn():
    global _embedding_fn
    if _embedding_fn is None:
        # Streamlit 세션에 예열된 모델이 있으면 재사용 (chroma_manager 와 공유)
        try:
            import streamlit as st
            if 'embedding_fn' in st.session_state:
                _embedding_fn = st.session_state.embedding_fn
                return _embedding_fn
        except Exception:
            pass
        _embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=_EMBED_MODEL,
        )
    return _embedding_fn


def _get_collection():
    """기존 collection 반환. 없으면 create."""
    global _collection
    if _collection is None:
        client = _get_client()
        _collection = client.get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=_get_embedding_fn(),
        )
    return _collection


def build_index(listed_only: bool = True, batch_size: int = 200) -> int:
    """
    DART CORPCODE → ChromaDB 인덱스 1회 구축.

    :param listed_only: True 면 KRX 상장사만 (stock_code 있는 회사). 기본 True.
    :param batch_size:  upsert 배치 크기 (메모리 보호)
    :return: 적재된 회사 수
    """
    client = _get_client()

    # 기존 collection 삭제 후 재생성 (구버전 데이터 잔존 방지)
    try:
        client.delete_collection(_COLLECTION_NAME)
        print(f"💡 기존 '{_COLLECTION_NAME}' collection 삭제")
    except Exception:
        pass

    col = client.create_collection(
        name=_COLLECTION_NAME,
        embedding_function=_get_embedding_fn(),
    )
    # 모듈 캐시 갱신
    global _collection
    _collection = col

    # 회사 목록 수집
    docs, ids, metas = [], [], []
    for name, code in utils_.corp_code.items():
        stock = utils_.call_stock_code(name)
        stock_str = str(stock).strip() if stock is not None else ""
        if listed_only and not stock_str:
            continue
        if not name or not str(name).strip():
            continue

        docs.append(str(name))
        ids.append(str(code))
        metas.append({
            "corp_name":  str(name),
            "corp_code":  str(code),
            "stock_code": stock_str.zfill(6) if stock_str else "",
        })

    if not docs:
        print("⚠️ 인덱싱할 회사가 없습니다.")
        return 0

    total = len(docs)
    print(f"📊 적재 시작: {total}개 회사 (배치 {batch_size}개씩)")

    for i in range(0, total, batch_size):
        end = min(i + batch_size, total)
        col.upsert(
            documents=docs[i:end],
            metadatas=metas[i:end],
            ids=ids[i:end],
        )
        print(f"  ✅ {end}/{total} 적재")

    print(f"🎉 완료: {_COLLECTION_NAME} collection 에 {total}개 회사 적재됨")
    return total


def search(query: str, max_results: int = 5) -> list[dict]:
    """
    회사명 의미 검색.

    :param query:        사용자 입력 (예: "삼선전자", "전자", "Korean Display")
    :param max_results:  반환할 후보 수
    :return: [{corp_name, corp_code, stock_code, distance}, ...]
             distance 는 cosine distance (낮을수록 유사)
             collection 이 비어있으면 빈 리스트
    """
    if not query or not str(query).strip():
        return []

    col = _get_collection()
    try:
        if col.count() == 0:
            print(
                "⚠️ company_index collection 이 비어있습니다. "
                "scripts/build_company_index.py 를 먼저 실행하세요."
            )
            return []
    except Exception:
        return []

    try:
        result = col.query(
            query_texts=[str(query).strip()],
            n_results=max_results,
        )
    except Exception as e:
        print(f"🚨 회사 인덱스 검색 중 에러: {e}")
        return []

    candidates: list[dict] = []
    if not result or not result.get('ids') or not result['ids'][0]:
        return candidates

    for i in range(len(result['ids'][0])):
        meta = result['metadatas'][0][i]
        distance = (
            result['distances'][0][i]
            if 'distances' in result and result['distances']
            else None
        )
        candidates.append({
            'corp_name':  meta.get('corp_name', ''),
            'corp_code':  meta.get('corp_code', ''),
            'stock_code': meta.get('stock_code', ''),
            'distance':   distance,
        })
    return candidates


def is_built() -> bool:
    """인덱스가 구축되어 있는지 확인."""
    try:
        return _get_collection().count() > 0
    except Exception:
        return False
