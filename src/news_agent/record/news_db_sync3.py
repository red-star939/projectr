import os
import json
import chromadb
import hashlib
import re
from chromadb.utils import embedding_functions

# [경로 동기화] 인덱서와 동일한 소스 폴더 지정
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(BASE_DIR))
DB_PATH = os.path.join(PROJECT_ROOT, "data", "News_DB")
SOURCE_DIR = os.path.join(BASE_DIR, "crawled_news")

def sanitize_collection_name(name):
    encoded = "".join([char if re.match(r'[a-zA-Z0-9]', char) else f"_{ord(char):x}" for char in name])
    return f"kwd_{encoded}"[:63]

class BatNewsFreshSync:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=DB_PATH)
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="jhgan/ko-sroberta-multitask"
        )

    def sync_latest_only(self):
        if not os.path.exists(SOURCE_DIR): return
        for keyword in os.listdir(SOURCE_DIR):
            kwd_path = os.path.join(SOURCE_DIR, keyword)
            date_folders = sorted([f for f in os.listdir(kwd_path) if os.path.isdir(os.path.join(kwd_path, f))])
            if not date_folders: continue
            
            latest_path = os.path.join(kwd_path, date_folders[-1])
            col_name = sanitize_collection_name(keyword)
            try: self.client.delete_collection(name=col_name)
            except: pass

            collection = self.client.create_collection(name=col_name, embedding_function=self.embedding_fn)
            for file in os.listdir(latest_path):
                if file.endswith(".json"):
                    with open(os.path.join(latest_path, file), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        doc_id = hashlib.md5(data['url'].encode()).hexdigest()
                        collection.add(ids=[doc_id], documents=[data['content']], 
                                       metadatas=[{"title": data['title'], "url": data['url'], "date": date_folders[-1]}])