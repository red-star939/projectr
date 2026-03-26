# 포켓에셋

### 핵심

1. 뉴스, 기업 공시, 리포트 등 산재한 자료를 찾는데 쌓이는 피로를 줄이기 위해 'Search Cost'를 줄이는 것이 투자하는 전 세대를 위한 수용성의 핵심
2. 고가의 포트폴리오 구독 서비스 대신, 주변의 공개된 자료(Public Domain)만으로도 투자 기업에 대한 요약과 근사포트폴리오를 생성하여 투자 결정권에 대한 방향성 확립

### 구조도
```
C:\\Users\\USER\\projectr
│  .gitignore
│  app.py
│  README.md
│  requirements.txt
│
├─data
│  ├─chroma_db
│  │
│  ├─Financial_Statements
│  │
│  └─News_Reports
│
├─model
│
├─src
│  ├─financial_agent
│  │
│  ├─news_agent
│  │
│  └─portfolio_agent
│
└─venv
```

### Requirements 설명
```
# python 3.11 기준
# --- Core UI & Data Handling ---
streamlit
pandas

# --- AI & LLM (RTX 4050 Optimized) ---
# [주의] GPU 가속을 위해 로컬 환경에 맞는 CUDA 버전에 따라 별도 빌드가 필요할 수 있습니다.
llama-cpp-python

# --- Web Scraping & API ---
requests
beautifulsoup4
feedparser
selenium
webdriver-manager

# --- Vector Database & RAG ---
chromadb
sentence-transformers
```

"2026-03-19 Invited"
