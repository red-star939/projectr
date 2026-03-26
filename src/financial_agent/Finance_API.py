import requests
import json
import utils_
import os

url = f"https://opendart.fss.or.kr/api/fnlttSinglAcnt.json"

reptcodes={
    '사업보고서': '11011',
    '반기보고서': '11012',
    '1분기보고서': '11013',
    '3분기보고서': '11014'
}

API_KEY = 'e20391fbb2db170d0b6160a94dfa0b9e40e92b26'


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

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        
        if data['status'] == '000':
            save_dir = f"data/Financial_Statement/{corp}"
            os.makedirs(save_dir, exist_ok=True)
            file_path = os.path.join(save_dir, f"{corp}.json")
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        else:
            print(f"오류 발생: {data['message']}")
    else:
        print(f"HTTP 요청 실패: {response.status_code}")

CallFinDescription('SK하이닉스', '사업보고서', 2025)