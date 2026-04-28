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
│  ├─FS_DB
│  │
│  ├─NS_DB
│  │
│  └─Portfolio
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
streamlit               # UI 구성
pandas<2.2.0            # 재무제표 및 지표 데이터 핸들링 (호환성을 위해 2.2.0 미만 유지)
numpy<2.0.0             # 수치 연산 및 상관계수 계산 (np.matrix 제거된 2.0 미만 필수)
tabulate                # 분석 데이터를 마크다운 표 형식으로 변환

# --- AI & LLM (RTX 4050 Optimized) ---
# [주의] RTX 4050 GPU 가속(CUDA)을 위해 로컬 환경에 맞는 빌드가 필요합니다.
# pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
llama-cpp-python        # EXAONE-3.0 모델 구동 및 4-bit KV Cache 연산 엔진

# --- Web Scraping & Content Extraction ---
requests                # 외부 API 및 웹 데이터 요청 기본 라이브러리
beautifulsoup4          # 수집된 HTML 데이터에서 핵심 텍스트 파싱
feedparser              # 구글 뉴스 RSS 피드 분석 및 링크 추출
selenium                # 동적 웹페이지 크롤링을 위한 브라우저 자동화
webdriver-manager       # 크롬 드라이버 자동 관리 및 버전 동기화
lxml                    # 고속 XML/HTML 파싱 엔진
readability-lxml        # 뉴스 본문만 정교하게 추출하는 지능형 파서

# --- Vector Database & RAG ---
chromadb>=0.4.0         # 뉴스(News_DB), 요약(NS_DB), 재무(FS_DB) 지식 저장소
sentence-transformers   # jhgan/ko-sroberta-multitask 임베딩 모델 구동

# --- Financial Data & API ---
yfinance                # 글로벌 시장 지표 및 실시간 주가 데이터 수집
finance-datareader      # 국내 시장 지수(KOSPI) 및 종목 코드 동기화
python-dotenv           # API 키 및 시스템 환경 변수 보안 관리
```

"2026-03-19 Invited"
