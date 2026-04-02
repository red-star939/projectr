import pandas as pd
import json
import sqlite3

def FSpreproc(FSPath, source="DART", report_type="사업보고서"):
    with open(FSPath, "r", encoding="utf-8") as f:
        data = json.load(f)

    parsed_data = []

    # 2. 필요한 데이터만 추출하여 세로(Row) 단위로 쪼개기
    for item in data['list']:
        corp_code = item['corp_code']
        fs_div = item['fs_div']
        sj_div = item['sj_div']
        account_nm = item['account_nm']
        stock_code = item['stock_code']
        
        # 기준 연도 (API 호출 시 사용한 bsns_year)
        base_year = int(item['bsns_year'])
        
        # 당기, 전기, 전전기 데이터를 각각 별도의 행(Row)으로 분리
        # 콤마(,) 제거 및 정수형 변환 필수
        periods = [
            (base_year, item.get('thstrm_amount')),
            (base_year - 1, item.get('frmtrm_amount')),
            (base_year - 2, item.get('bfefrmtrm_amount'))
        ]
        
        for year, amount in periods:
            if amount: # 값이 존재하는 경우만 추가
                clean_amount = int(amount.replace(',', ''))
                parsed_data.append({
                    "source": source,
                    "report_type": report_type,
                    "corp_code": corp_code,
                    "stock_code": stock_code,
                    "fs_div": fs_div,
                    "sj_div": sj_div,
                    "account_nm": account_nm,
                    "target_year": year,
                    "amount": clean_amount
                })

    # 3. 깔끔한 DataFrame으로 변환 완료 (이를 to_sql 로 DB에 넣으면 됩니다)
    dfr=pd.DataFrame(parsed_data)
    dfr.drop_duplicates(subset=['source', 'report_type', 'corp_code', 'fs_div', 'sj_div', 'account_nm', 'target_year'], keep='last', inplace=True)
    return dfr

if __name__ == "__main__":
    a=FSpreproc("data/Financial_Statement/SK하이닉스/SK하이닉스.json", source="DART", report_type="사업보고서")
    
    # 텍스트 편집기에서 보기 좋게 들여쓰기(indent)를 포함하여 저장
    a.to_json("check_finance.json", orient='records', force_ascii=False, indent=4)
    print("✅ 'check_finance.json' 파일이 생성되었습니다.")