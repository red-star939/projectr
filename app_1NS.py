import streamlit as st
import os
import sys
from datetime import datetime
from pathlib import Path

# [단계 1] 경로 및 모듈 로드 설정
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR / "src" / "news_agent") not in sys.path:
    sys.path.append(str(ROOT_DIR / "src" / "news_agent"))

from news_fast_stream import BatFastStreamer
from news_sum4_3 import BatExaoneReporter, sanitize_collection_name

# 통합 실행 시 중복 설정을 방지합니다.
if "app_main" not in sys.modules:
    st.set_page_config(page_title="News Intelligence", layout="wide")

def main():
    st.title("📊 Real-time Fast News Intelligence")
    st.markdown("---")

    with st.form("news_form"):
        keyword = st.text_input("분석 키워드 입력", placeholder="예: 엔비디아")
        submit = st.form_submit_button("초고속 분석 가동", use_container_width=True)

    if submit and keyword:
        try:
            with st.status(f"[{keyword}] 파이프라인 가동 중...", expanded=True) as status:
                # [단계 1] 뉴스 수집 및 목록 표시 [요청 사항 반영]
                st.write("뉴스 수집 중...")
                streamer = BatFastStreamer(limit=10)
                acquired_news = streamer.run(keyword)
                
                if not acquired_news:
                    status.update(label="❌ 수집된 뉴스가 없습니다.", state="error")
                    st.stop()
                
                # 확보한 뉴스 목록 출력
                st.write(f"✅ **{len(acquired_news)}개의 뉴스를 확보했습니다:**")
                for i, meta in enumerate(acquired_news, 1):
                    # 제목과 링크를 마크다운으로 표시
                    st.markdown(f"{i}. [{meta.get('title', '제목 없음')}]({meta.get('url', '#')})")

                # [단계 2] 분석 엔진 로드 (세션 예열 확인)
                st.write("🤖 분석 엔진(EXAONE) 상태 점검 중...")
                reporter = BatExaoneReporter()

                # [단계 3] 개별 요약 진행률 표시 [요청 사항 반영]
                st.write("🔄 기사별 핵심 팩트 추출 시작 (Map Phase)...")
                col_name = sanitize_collection_name(keyword)
                docs = reporter.client.get_collection(name=col_name).get()['documents']
                
                # 진행률 표시를 위한 위젯 생성
                progress_bar = st.progress(0)
                progress_text = st.empty()
                summaries = []
                today_str = datetime.now().strftime("%Y-%m-%d")

                for i, doc in enumerate(docs, 1):
                    # 진행률 업데이트
                    percent = i / len(docs)
                    progress_bar.progress(percent)
                    progress_text.info(f"기사 요약 중: {i} / {len(docs)} ({(percent*100):.1f}%)")
                    
                    # 개별 요약 연산 수행
                    sys_msg = reporter.prompt_cfg['prompts']['map_phase']['system'].format(today=today_str)
                    user_msg = reporter.prompt_cfg['prompts']['map_phase']['user_template'].format(document=doc[:2500], today=today_str)
                    res = reporter._generate(sys_msg, user_msg)
                    summaries.append(f"기사 {i} 요약: {res['choices'][0]['text'].strip()}")
                
                progress_text.success(f"✅ {len(docs)}개 기사 개별 요약 완료")
                status.update(label="최종 전략 리포트 생성 단계", state="complete", expanded=False)

            # [단계 4] 최종 통합 리포트 출력 및 저장
            st.divider()
            st.subheader(f"📊 {keyword} 실시간 통합 전략 리포트")
            report_placeholder = st.empty()
            
            combined = "\n\n".join(summaries)
            red_cfg = reporter.prompt_cfg['prompts']['reduce_phase']
            sys_msg_f = red_cfg['system'].format(today=today_str)
            user_msg_f = red_cfg['user_template'].format(keyword=keyword, summaries=combined, today=today_str)
            
            full_report = ""
            for chunk in reporter._generate(sys_msg_f, user_msg_f, stream=True):
                token = chunk['choices'][0]['text']
                full_report += token
                report_placeholder.markdown(full_report + "▌")
            report_placeholder.markdown(full_report)

            # 지식 베이스(NS_DB) 저장
            reporter._save_to_db(keyword, full_report)
            st.toast(f"✅ {keyword} 리포트 저장 완료", icon="⚡")

        except Exception as e:
            st.error(f"연산 오류 발생: {str(e)}")

# 단독 실행 대응
if __name__ == "__main__":
    main()