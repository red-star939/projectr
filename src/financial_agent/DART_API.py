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

    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        response = requests.get(url, params=params)

        if response.status_code == 200:
            data = response.json()
            
            if data['status'] == '000':
                os.makedirs(save_dir, exist_ok=True)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
                print(f"✅ [{corp}] {year}년 {report} 수집 및 파일 저장 완료")
            else:
                print(f"오류 발생: {data['message']}")
        else:
            print(f"HTTP 요청 실패: {response.status_code}")
        
        return
        
    else:
        # 캐싱 처리: 파일이 이미 존재하면 다시 API를 호출하지 않고 넘어갑니다.
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                # 파일이 손상되지 않았는지 파싱용으로만 체크
                json.load(f)
            print(f"💡 [{corp}] {year}년 {report} 데이터는 이미 안전하게 캐싱되어 있습니다. 다운로드를 스킵합니다.")
            return
        except json.JSONDecodeError:
            print(f"🚨 캐시 파일이 비어있거나 손상되었습니다. 수집을 다시 진행하려면 '{file_path}' 파일을 직접 삭제해주세요.")
            return