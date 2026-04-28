import os

def create_paragraph(*args, **kwargs):
    """
    개별 문단(섹션)의 텍스트를 생성하는 함수입니다.
    어떤 데이터가 들어올지 모르므로 입력값은 *args, **kwargs로 열어두었습니다.
    """
    # TODO: 사용자님이 직접 메시지 파싱 및 문단 구성 로직을 작성하실 부분
    paragraph_content = ""
    
    return paragraph_content


def create_markdown_template(*args, **kwargs):
    """
    전체 마크다운 프롬프트 템플릿을 조합하는 메인 함수입니다.
    """
    # 1. 앞쪽 템플릿 (고정된 시스템 프롬프트나 역할 부여 등)
    front_template = """# 기업 가치 분석 프롬프트
[여기에 고정된 역할 부여 및 기본 지시사항을 작성합니다.]

---
"""

    # 2. 문단 생성 함수를 여러 번 호출하여 세부 내용 구성
    # (예: 기업 개요 문단, 수익성 지표 문단, 가치평가 지표 문단 등)
    section_1 = create_paragraph() 
    section_2 = create_paragraph()
    section_3 = create_paragraph()

    # 3. 전체 마크다운 텍스트 병합
    final_markdown = f"{front_template}\n{section_1}\n{section_2}\n{section_3}"

    # TODO: 최종 완성된 final_markdown을 파일로 적거나(Write), 
    # LLM API로 전송하기 위해 파싱하는 로직을 작성하실 부분
    pass

    return final_markdown