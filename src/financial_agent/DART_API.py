import requests
import json
from . import utils_
import os
from config import DART_API_KEY

url = f"https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"

reptcodes={
    '사업보고서': '11011',
    '반기보고서': '11012',
    '1분기보고서': '11013',
    '3분기보고서': '11014'
}

API_KEY = DART_API_KEY


def CallFinDescription(
        corp,
        report,
        year=2025,
):
    CORP_CODE = f"{utils_.corp_code[corp]:0>8}"
    BSNS_YEAR = year
    REPRT_CODE = reptcodes[report]

    params = {
        'crtfc_key': API_KEY,
        'corp_code': CORP_CODE,
        'bsns_year': BSNS_YEAR,
        'reprt_code': REPRT_CODE
    }
    save_dir = f"data/Financial_Statement/{corp}"
    file_path = os.path.join(save_dir, f"{corp}_{year}_{report}.json")

    if not os.path.exists(file_path):
        response = requests.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            
            if data['status'] == '000':
                os.makedirs(save_dir, exist_ok=True)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
            else:
                print(f"오류 발생: {data['message']}")
        else:
            print(f"HTTP 요청 실패: {response.status_code}")
        
        return 0
    else:
        '''
        캐싱 코드
        '''
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data