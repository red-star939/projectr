import pandas as pd
from pathlib import Path

def read_xml(xml_file):
    df = pd.read_xml(xml_file, xpath='.//list')
    return df

# 모듈 위치를 기준으로 CORPCODE.xml을 찾아, 어느 CWD에서 import해도 동일하게 동작하도록 한다.
_CORPCODE_PATH = Path(__file__).resolve().parent / 'CORPCODE.xml'
dartCodes=read_xml(str(_CORPCODE_PATH))

# 동명 회사 존재 시 상장사(stock_code가 있는 회사)가 딕셔너리에 최종적으로 덮어씌워지도록 정렬
dartCodes['is_listed'] = dartCodes['stock_code'].apply(lambda x: str(x).strip() != '')
dartCodes = dartCodes.sort_values('is_listed')

corp_code=dict(zip(dartCodes['corp_name'],dartCodes['corp_code']))
stock_code=dict(zip(dartCodes['corp_name'],dartCodes['stock_code']))

def call_corp_code(corp):
    return corp_code[corp]


def call_stock_code(corp):
    return stock_code[corp]