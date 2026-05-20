키워드를 입력받으면 API 기반으로 재무제표 문서를 얻어내는 agent

사용 방법
DBPattern.py의 패턴을 따라 호출
-세부 설정 구현 시, Extract_corr.py의 함수 사용.
 ㄴ세부 설정에 넣을 수치적 계산 항목은 여기서 발생

 4/28 상관계수 추가
 - 함수: correlation_with_KOSPI(), compare_with_sector()
 해당 함수들은 입력받은 회사를 바탕으로 상관 계수 리턴
 mode: 피어슨, 스피어만, 켄달, distance
 4가지를 인자로 받음(자세한 입력은 코드 참조)
 return type: correlation_with_KOSPI는 상관계수(float), compare_with_sector는 상관계수 리스트(float)