import pandas as pd
import json

import datetime

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

def ensure_company_data(corp):
    """
    한 번도 불린 적 없는 회사(DB에 테이블이 없음)인 경우,
    근래 10년 내의 사업보고서(연간보고서)를 자동으로 가져와 DB에 저장합니다.
    (yfinance 데이터 제외, 연간보고서 한정)
    """
    from src.financial_agent import conSQL
    from src.financial_agent import DART_API

    db = conSQL.FS()
    if not db.has_table(corp):
        current_year = datetime.datetime.now().year
        start_year = current_year - 9
        
        print(f"[{corp}] DB에 기존 데이터가 없습니다. 최근 10년({start_year}~{current_year}년) 사업보고서 수집을 일괄 시작합니다.")
        for year in range(start_year, current_year + 1):
            print(f"  👉 [{corp}] {year}년 사업보고서 요청 중...")
            file_path = DART_API.CallFinDescription(corp=corp, report="사업보고서", year=year)
            
            if file_path:
                df = FSpreproc(file_path, source="DART", report_type="사업보고서")
                if not df.empty:
                    # 중복 데이터는 conSQL에서 자동으로 처리됨
                    db.to_sql(table_name=corp, df=df, if_exists="append")
        print(f"🎉 [{corp}] 최근 10년({start_year}~{current_year}년) 사업보고서 수집 및 DB 저장이 모두 완료되었습니다!")
    else:
        print(f"💡 [{corp}] 회사는 이미 DB에 존재합니다. (초기 연속 수집 스킵)")
    db.close()

if __name__ == "__main__":
    a=FSpreproc("data/Financial_Statement/SK하이닉스/SK하이닉스.json", source="DART", report_type="사업보고서")
    
    # 텍스트 편집기에서 보기 좋게 들여쓰기(indent)를 포함하여 저장
    a.to_json("check_finance.json", orient='records', force_ascii=False, indent=4)
    print("✅ 'check_finance.json' 파일이 생성되었습니다.")