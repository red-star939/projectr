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

# KRX 종목코드 → DART 회사명 역방향 매핑 (상장사만)
#   "005930" → "삼성전자" 식 조회를 위한 캐시
#   6자리 zfill 정규화 + 상장사(stock_code 비어있지 않음) 필터
stock_code_to_corp: dict[str, str] = {}
for _name, _code in zip(dartCodes['corp_name'], dartCodes['stock_code']):
    _c = str(_code).strip()
    if not _c:
        continue
    _c6 = _c.zfill(6)
    # 동일 종목코드가 여러 회사명에 매핑된 경우 (희박), 마지막 값 유지
    stock_code_to_corp[_c6] = _name


def call_corp_code(corp):
    """회사명 → DART corp_code. 없으면 None (이전엔 KeyError)."""
    return corp_code.get(corp)


def call_stock_code(corp):
    """회사명 → KRX 종목코드. 없으면 None (이전엔 KeyError)."""
    return stock_code.get(corp)


def call_corp_name_by_stock_code(code):
    """
    KRX 6자리 종목코드 → DART 회사명. 없으면 None.

    "005930" / "5930" / 5930 모두 6자리 zfill 후 매칭.
    """
    if code is None:
        return None
    c = str(code).strip()
    if not c.isdigit():
        return None
    return stock_code_to_corp.get(c.zfill(6))