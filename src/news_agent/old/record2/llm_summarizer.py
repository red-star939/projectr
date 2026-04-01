import os
import sys
from llama_cpp import Llama
from datetime import datetime

# 1단계: 경로 및 모델 설정
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(CURRENT_DIR))
MODEL_PATH = os.path.join(PROJECT_ROOT, "model", "Phi-3.5-mini-instruct-Q4_K_M.gguf")
EXPORT_PATH = os.path.join(PROJECT_ROOT, "exports")
SUMMARY_PATH = os.path.join(PROJECT_ROOT, "summaries")

if not os.path.exists(SUMMARY_PATH):
    os.makedirs(SUMMARY_PATH)

class BatSummarizer:
    def __init__(self):
        print(f"🦇 LLM 엔진 가동... (RTX 4050 GPU 스트리밍 모드 활성화)")
        self.llm = Llama(
            model_path=MODEL_PATH,
            n_ctx=40000,
            n_gpu_layers=-1, 
            verbose=False
        )

    def _stream_response(self, prompt):
        """실시간으로 토큰을 출력하고 전체 텍스트를 반환하는 스트리밍 서브루틴"""
        stream = self.llm(
            prompt,
            max_tokens=1024,
            stop=["<|end|>"],
            stream=True # 실시간 스트리밍 활성화
        )
        
        full_text = ""
        for output in stream:
            token = output['choices'][0]['text']
            full_text += token
            # 터미널에 즉시 출력 (줄바꿈 없이 버퍼 비우기)
            sys.stdout.write(token)
            sys.stdout.flush()
        
        print("\n") # 섹션 종료 후 줄바꿈
        return full_text

    def generate_summary(self, file_name):
        file_path = os.path.join(EXPORT_PATH, file_name)
        with open(file_path, "r", encoding="utf-8") as f:
            full_content = f.read()

        # 뉴스별 구분선(---)으로 데이터 분할
        raw_sections = full_content.split("---")
        chunks = [s.strip() for s in raw_sections if len(s.strip()) > 200]
        
        print(f"🤖 총 {len(chunks)}개의 분석 섹션을 감지했습니다.")
        
        partial_results = []
        for i, chunk in enumerate(chunks):
            print(f"  ▶️ [{i+1}/{len(chunks)}] 섹션 분석 결과:")
            print("-" * 30)
            prompt = f"<|system|>\n당신은 뉴스 분석가 알프레드입니다. 다음 뉴스 내용을 핵심만 한국어로 요약하세요.<|end|>\n<|user|>\n{chunk}<|end|>\n<|assistant|>\n"
            
            # 실시간 출력 함수 호출
            summary = self._stream_response(prompt)
            partial_results.append(summary)
            print("-" * 30)

        # 2단계: 최종 종합 분석 스트리밍
        combined_summaries = "\n".join([f"- {res}" for res in partial_results])
        print("🎯 [최종 종합 인사이트 도출 중...]")
        print("=" * 60)
        
        final_prompt = f"<|system|>\n당신은 수석 전략가 알프레드입니다. 나열된 요약들을 종합하여 핵심 인사이트를 한국어로 도출하세요.<|end|>\n<|user|>\n다음 요약들을 종합해줘:\n{combined_summaries}<|end|>\n<|assistant|>\n"
        final_strategy = self._stream_response(final_prompt)
        print("=" * 60)

        # 3단계: 파일 저장 (내부 로직 동일)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = f"summary_{file_name.replace('.md', '')}_{timestamp}.md"
        output_path = os.path.join(SUMMARY_PATH, output_file)
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# 📋 Bat Computer Strategic Summary\n\n")
            f.write(f"## 💡 Total Insight\n{final_strategy}\n\n")
            f.write(f"---\n## 🔍 Detailed Points\n{combined_summaries}")
            
        return output_path

def run_summarizer():
    files = [f for f in os.listdir(EXPORT_PATH) if f.endswith('.md')]
    if not files:
        print("⚠️ 분석할 리포트가 없습니다."); return

    print("\n" + "="*60)
    for idx, f in enumerate(files):
        print(f"[{idx+1}] {f}")
    
    choice = input("\n번호 선택 (종료: q): ")
    if choice.lower() == 'q': return

    try:
        summarizer = BatSummarizer()
        result_path = summarizer.generate_summary(files[int(choice)-1])
        print(f"✅ 분석 완료: {result_path}")
    except Exception as e:
        print(f"❌ 분석 실패: {e}")

if __name__ == "__main__":
    run_summarizer()