import requests
import zipfile
import io
import xml.etree.ElementTree as ET
import pandas as pd
import _root
from _utils import read_xml 

# 1. API 인증키 설정
API_KEY = 'e20391fbb2db170d0b6160a94dfa0b9e40e92b26'
url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={API_KEY}"

# 2. 파일 다운로드 및 압축 해제
response = requests.get(url)
with zipfile.ZipFile(io.BytesIO(response.content)) as z:
    z.extractall('dart_codes') # dart_codes 폴더에 압축 해제

dardCodes=read_xml('dart_codes/CORPCODE.xml') 

# 3. XML 파싱하여 데이터프레임으로 변환
tree = ET.parse('dart_codes/CORPCODE.xml')
root = tree.getroot()

data = []
for list_node in root.findall('list'):
    data.append({
        'corp_code': list_node.findtext('corp_code'),
        'corp_name': list_node.findtext('corp_name'),
        'stock_code': list_node.findtext('stock_code'),
        'modify_date': list_node.findtext('modify_date')
    })

df = pd.DataFrame(data)

# 4. 상장사만 필터링 (stock_code가 있는 기업) 및 확인
df_listed = df[df['stock_code'].str.strip() != '']
print(df_listed.head())

# 5. 엑셀이나 CSV로 저장하여 나중에 활용
df_listed.to_csv('dart_corp_codes.csv', index=False, encoding='utf-8-sig')