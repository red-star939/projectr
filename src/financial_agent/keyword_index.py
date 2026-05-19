"""
키워드 자동완성 인덱스 — KRX SECTORS 기반 ChromaDB 의미 검색.

용도:
    - News Agent 의 검색 키워드 자동완성 (반도체, 바이오, ...)
    - Portfolio Agent 의 통합 검색 후보 (테마/섹터 차원)

데이터 소스:
    - SECTORS 테이블 (KRX 섹터/산업 분류 ~30개)
      → 회사명(corp_name) 은 company_index 가 별도 보유하므로 중복 회피

회사명·티커 검색은 company_resolver / company_index 가 담당하며,
unified 검색은 두 인덱스를 호출자가 머지한다.

build_index(): scripts/build_keyword_index.py 가 1회 실행
search(query, max_results): 의미 검색
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

_COLLECTION_NAME = "keyword_index"
_EMBED_MODEL = "jhgan/ko-sroberta-multitask"

_DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "FS_DB")
_FS_DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "FS.db")

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
    global _collection
    if _collection is None:
        _collection = _get_client().get_or_create_collection(
            name=_COLLECTION_NAME,
            embedding_function=_get_embedding_fn(),
        )
    return _collection


def _collect_seeds() -> list[dict]:
    """SECTORS 테이블에서 키워드 시드 수집."""
    seeds: list[dict] = []
    if not os.path.exists(_FS_DB_PATH):
        print(f"⚠️ FS.db 없음: {_FS_DB_PATH}")
        return seeds

    try:
        con = sqlite3.connect(_FS_DB_PATH)
        # SECTORS 가 존재하는지 사전 확인
        chk = con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='SECTORS'"
        ).fetchone()
        if chk is None:
            print("⚠️ SECTORS 테이블이 FS.db 에 없습니다")
            con.close()
            return seeds
        rows = con.execute("SELECT DISTINCT sector FROM SECTORS WHERE sector IS NOT NULL").fetchall()
        con.close()
        for (sector,) in rows:
            sector = (sector or "").strip()
            if not sector or sector in ("기타(DB없음)", "오류", "해외기업/미분류"):
                continue
            seeds.append({'keyword': sector, 'type': 'sector'})
    except Exception as e:
        print(f"🚨 SECTORS 조회 실패: {e}")
        return seeds

    # 중복 제거
    seen = set()
    unique: list[dict] = []
    for s in seeds:
        if s['keyword'] not in seen:
            seen.add(s['keyword'])
            unique.append(s)
    return unique


def build_index(batch_size: int = 200) -> int:
    """SECTORS 시드로 키워드 인덱스 구축. 기존 collection 은 삭제 후 재생성."""
    client = _get_client()
    try:
        client.delete_collection(_COLLECTION_NAME)
        print(f"💡 기존 '{_COLLECTION_NAME}' 삭제")
    except Exception:
        pass

    col = client.create_collection(
        name=_COLLECTION_NAME,
        embedding_function=_get_embedding_fn(),
    )
    global _collection
    _collection = col

    seeds = _collect_seeds()
    if not seeds:
        print("⚠️ 시드 키워드 없음")
        return 0

    docs = [s['keyword'] for s in seeds]
    ids = [f"{s['type']}_{i}" for i, s in enumerate(seeds)]
    metas = [{'keyword': s['keyword'], 'type': s['type']} for s in seeds]

    total = len(seeds)
    print(f"📊 적재 시작: {total}개 키워드")
    for i in range(0, total, batch_size):
        end = min(i + batch_size, total)
        col.upsert(documents=docs[i:end], metadatas=metas[i:end], ids=ids[i:end])
        print(f"  ✅ {end}/{total}")

    print(f"🎉 완료: {_COLLECTION_NAME} collection 에 {total}개 키워드 적재")
    return total


def search(query: str, max_results: int = 8) -> list[dict]:
    """
    키워드 의미 검색.

    :return: [{keyword, type, distance}, ...] (distance 오름차순)
             인덱스 미구축 시 빈 리스트
    """
    if not query or not str(query).strip():
        return []

    col = _get_collection()
    try:
        if col.count() == 0:
            return []
    except Exception:
        return []

    try:
        result = col.query(query_texts=[str(query).strip()], n_results=max_results)
    except Exception as e:
        print(f"🚨 키워드 검색 에러: {e}")
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
            'keyword':  meta.get('keyword', ''),
            'type':     meta.get('type', ''),
            'distance': distance,
        })
    return candidates


def is_built() -> bool:
    try:
        return _get_collection().count() > 0
    except Exception:
        return False
