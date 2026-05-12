import os
import sys

# 이 파일은 프로젝트 루트에 있으므로, 자기 자신의 디렉터리를 sys.path에 추가하면 된다.
# (이전 코드는 _test_pipeline.py에서 복사하면서 dirname을 3번 호출, 프로젝트 루트보다
#  2단계 위 디렉터리를 sys.path에 넣어 패키지 import가 깨질 수 있었다.)
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.financial_agent import DART_API
from src.financial_agent import FS_to_SQL
from src.financial_agent import conSQL
from src.financial_agent import yfinance_api
from src.financial_agent import sql_to_json

corp = "SK하이닉스"
report = "반기보고서"
year = "2025"

DART_API.CallFinDescription(corp, report, year)#여기서는 DART API(재무재표)를 받아옴
yfinance_api.fetch_and_save_yfinance_info([corp])#여기서는 주식 지표

db = conSQL.FS()
df = FS_to_SQL.FSpreproc("data/Financial_Statement/SK하이닉스/SK하이닉스.json")

# 들어오는 데이터가 회사별, 보고서 종류별, 계정별, 연도별 하나만 존재하도록 subset 설정
subset_keys = ['source', 'report_type', 'corp_code', 'fs_div', 'sj_div', 'account_nm', 'target_year']
#얘는 sql로 올릴 목록임
db.to_sql(corp, df, subset=subset_keys) # 여기서 db로 올라감 
db.search_sql(corp)#그리고 이거에서 db로 올라간 정보 획득 가능
db.close()

sql_to_json.save_company_data_to_jsonDB(corp)
print("\n🎉 모든 파이프라인 시뮬레이션 종료: 'data/jsonDB/' 폴더를 확인해 주세요!")

