from src.financial_agent import conSQL
import json
import os
import pandas as pd

def save_company_data_to_jsonDB(company_name):
    """
    SQL(FS.db)에 저장된 특정 회사(테이블)의 전체 데이터를 가져온 후,
    데이터에 존재하는 '연도(target_year)'와 '보고서 종류(sj_div)'를 직접 추출하여
    자동으로 분류 후 여러 개의 {회사이름}_{연도}_{보고서 종류}.json 파일로 분할 저장합니다.
    
    :param company_name: 조회할 회사 이름 (테이블 이름) - 예: "SK하이닉스"
    """
    db = conSQL.FS()
    df = db.search_sql(company_name)
    db.close()
    
    if df is not None and not df.empty:
        # 'data/jsonDB' 디렉토리 경로 설정
        save_dir = os.path.join("data", "jsonDB")
        os.makedirs(save_dir, exist_ok=True)
        
        # 가져온 데이터(df) 내부의 'target_year'와 'sj_div'를 기준으로 그룹화(groupby)
        grouped = df.groupby(['target_year', 'sj_div'])
        
        for (year, report_type), group_df in grouped:
            # 예: SK하이닉스_2023_BS.json
            output_filepath = os.path.join(save_dir, f"{company_name}_{year}_{report_type}.json")
            
            # 각각 분리된 그룹 DataFrame만 JSON 문자열로 변환
            json_data = group_df.to_json(orient='records', force_ascii=False, indent=4)
            
            with open(output_filepath, "w", encoding="utf-8") as f:
                f.write(json_data)
                
        print(f"✅ '{save_dir}' 폴더에 데이터를 연도별/보고서별로 분할하여 총 {len(grouped)}개의 파일 저장을 완료했습니다.")
    else:
        print(f"해당 회사('{company_name}')의 데이터가 존재하지 않거나 조회 시 에러가 발생했습니다.")

if __name__ == "__main__":
    # 예시: SK하이닉스 전체 데이터를 검색 후 연도/보고서별로 쪼개기
    company = "SK하이닉스"
    save_company_data_to_jsonDB(company)
