import streamlit as st
import sys
import os
import re
import feedparser
import urllib.parse
from datetime import datetime
import time

# [1] 전역 레이아웃 세팅 및 프로젝트 최상단 경로 동기화
st.set_page_config(
    page_title="General Speed News Terminal",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# 경로 동기화 및 패키지 바인딩
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
for path_dir in [BASE_DIR, os.path.join(BASE_DIR, "src", "news_agent"), os.path.join(BASE_DIR, "src", "financial_agent")]:
    if path_dir not in sys.path:
        sys.path.append(path_dir)

# 의존성 백엔드 모듈 인출
from src.news_agent.news_sum4_3 import BatExaoneReporter
from src.financial_agent import ui_search

class GeneralFastNewsAgent:
    def __init__(self, limit=15, similarity_threshold=0.6, token_budget_chars=3000):
        self.limit = limit
        self.similarity_threshold = similarity_threshold
        self.token_budget_chars = token_budget_chars

    def _calculate_jaccard(self, str1: str, str2: str) -> float:
        """자카드 유사도 기반 문자열 중복도 연산"""
        words1 = set(str1.split())
        words2 = set(str2.split())
        if not words1 or not words2:
            return 0.0
        return len(words1 & words2) / len(words1 | words2)

    def _clean_title(self, title: str) -> str:
        """불필요한 언론사 식별자 및 괄호 데이터 소거로 토큰 고밀도화"""
        cleaned = title.split(" - ")[0] if " - " in title else title
        cleaned = re.sub(r'\[.*?\]|\(.*?\)', '', cleaned)
        return cleaned.strip()

    def _parse_date_robust(self, entry) -> str:
        """feedparser 내장 시간 구조체를 활용하여 10자 날짜로 무결 변환"""
        if hasattr(entry, "published_parsed") and entry.published_parsed is not None:
            try:
                t_struct = entry.published_parsed
                return f"{t_struct.tm_year}-{t_struct.tm_mon:02d}-{t_struct.tm_mday:02d}"
            except Exception:
                pass

        raw_date = entry.get("published", "")
        formats = [
            "%a, %d %b %Y %H:%M:%S %Z",
            "%a, %d %b %Y %H:%M:%S %z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S"
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(raw_date, fmt)
                return dt.strftime("%Y-%m-%d")
            except ValueError:
                continue

        match = re.search(r'(\d{4})[-/](\d{1,2})[-/](\d{1,2})', raw_date)
        if match:
            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
            
        return datetime.now().strftime("%Y-%m-%d")

    def fetch_news_snippets_optimized(self, keyword: str) -> list:
        """기사 고유 링크(link) 보존 로직이 포함된 고속 뉴스 파싱"""
        encoded_kwd = urllib.parse.quote(f"{keyword} when:24h")
        rss_url = f"https://news.google.com/rss/search?q={encoded_kwd}&hl=ko&gl=KR&ceid=KR:ko"
        
        feed = feedparser.parse(rss_url)
        unique_snippets = []
        
        for entry in feed.entries[:self.limit]:
            clean_title = self._clean_title(entry.title)
            compact_date = self._parse_date_robust(entry)
            actual_link = entry.link
            
            # 자카드 클러스터링 필터링
            is_duplicate = False
            for existing in unique_snippets:
                if self._calculate_jaccard(clean_title, existing["title"]) > self.similarity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_snippets.append({
                    "title": clean_title,
                    "date": compact_date,
                    "link": actual_link
                })
        
        # 슬라이딩 윈도우 기반 토큰 버젯 통제
        final_snippets = []
        accumulated_chars = 0
        
        for snip in unique_snippets:
            entry_str = f"제목:{snip['title']}({snip['date']})\n"
            if accumulated_chars + len(entry_str) > self.token_budget_chars:
                break
            final_snippets.append(snip)
            accumulated_chars += len(entry_str)
            
        return final_snippets

def main():
    st.title("👤 General Mode Terminal")
    st.markdown("일반 사용자용 패널입니다.")
    st.markdown("---")
    
    # 통합 검색창 컴포넌트 매핑
    keyword = ui_search.render_search(
        "분석 키워드 또는 회사명 입력",
        mode='unified',
        key='general_speed_ns_search',
    )
    
    submit_btn = st.button("뉴스 인텔리전스 분석", use_container_width=True, disabled=not keyword)
    
    if submit_btn and keyword:
        reporter = BatExaoneReporter()
        agent = GeneralFastNewsAgent()
        
        # 상태 표시 박스 가동
        with st.status(f"[{keyword}] 메모리 내 뉴스 인덱스 최적화 알고리즘 가동 중...", expanded=True) as status:
            snippets = agent.fetch_news_snippets_optimized(keyword)
            
            if snippets:
                st.write(f"✅ 뉴스 RSS 스트림 수집 완료: 아래의 {len(snippets)}개 핵심 뉴스를 발견했습니다:")
                for idx, snip in enumerate(snippets, 1):
                    st.markdown(f"{idx}. [{snip['title']}]({snip['link']})")
                
                status.update(label="뉴스 기사 탐색", state="complete", expanded=True)
            else:
                status.update(label="❌ 데이터 확보 실패", state="error")
                st.warning("최근 24시간 내에 수집된 유효 뉴스 팩트 데이터가 존재하지 않습니다.")
                st.stop()
            
        # 3. 데이터 컨텍스트 구조화
        context_lines = [f"[{idx}] {s['title']} ({s['date']})" for idx, s in enumerate(snippets, 1)]
        raw_context = "\n".join(context_lines)
        
        st.divider()
        st.subheader(f"📊 {keyword} 실시간 시장 트렌드 리포트")
        report_placeholder = st.empty()
        
        sys_msg = (
            f"당신은 보편적 사용자를 위한 뉴스 분석가입니다. 제시된 {keyword} 관련 정제 뉴스 목록을 기반으로 "
            "주요 시장 트렌드와 시사점을 일반 사용자가 이해하기 쉽도록 명확하게 작성하십시오. 원천 데이터에 없는 사실은 추정하지 마십시오."
        )
        
        full_report = ""
        for chunk in reporter._generate(sys_msg, raw_context, stream=True):
            full_report += chunk['choices'][0]['text']
            report_placeholder.markdown(full_report + "▌")
        report_placeholder.markdown(full_report)
        
        # 4. 백엔드 영구 지식화 처리 파이프라인
        reporter._save_to_db(f"GENERAL_{keyword}", full_report)
        today_str = datetime.now().strftime("%Y-%m-%d")
        try:
            md_path = reporter._save_to_md(f"GENERAL_{keyword}", full_report, today_str)
            st.toast(f"📄 보고서 내보내기 완료: {os.path.basename(md_path)}", icon="📄")
            st.success("💾 일반 사용자용 지식 베이스(NS_DB) 및 마크다운 문서 빌드가 완료되었습니다.")
        except Exception as e:
            st.warning(f"⚠️ 마크다운 파일 저장 실패 (NS_DB 영구 인덱싱은 안전하게 완료됨): {e}")

if __name__ == "__main__":
    main()