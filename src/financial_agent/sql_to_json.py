import conSQL
import json
import os

def get_company_data_as_json(company_name, output_filepath=None):
    """
    SQL(FS.db)에 저장된 특정 회사(테이블)의 데이터를 조회하여 JSON 형태로 반환하거나 저장합니다.
    
    :param company_name: 조회할 회사 이름 (테이블 이름) - 예: "SK하이닉스"
    :param output_filepath: JSON 파일로 저장할 경로 (선택 사항)
    :return: JSON 형태의 문자열 데이터
    """
    db = conSQL.FS()
    df = db.search_sql(company_name)
    db.close()
    
    if df is not None and not df.empty:
        # DataFrame을 JSON 문자열로 변환 (한글 깨짐 방지를 위해 force_ascii=False)
        json_data = df.to_json(orient='records', force_ascii=False, indent=4)
        
        # 파일 저장 경로가 주어졌다면 파일로 저장
        if output_filepath:
            # 저장할 디렉토리가 없다면 생성
            os.makedirs(os.path.dirname(output_filepath) or '.', exist_ok=True)
            with open(output_filepath, "w", encoding="utf-8") as f:
                f.write(json_data)
            print(f"✅ '{output_filepath}' 파일이 생성되었습니다.")
            
        return json_data
    else:
        print(f"해당 회사('{company_name}')의 데이터가 존재하지 않거나 조회 시 에러가 발생했습니다.")
        return None

if __name__ == "__main__":
    # 예시: SK하이닉스 데이터를 JSON으로 가져와서 저장하기
    company = "SK하이닉스"
    # 가져온 데이터를 확인할 수 있도록 현재 폴더에 JSON 파일로 저장
    result_json = get_company_data_as_json(company, output_filepath=f"{company}_sql_data.json")
    
    if result_json:
        print(f"{company} 데이터 변환 완료 (미리보기):")
        # 데이터가 너무 길 수 있으므로 앞 500자만 미리보기 방식으로 출력합니다.
        print(result_json[:500] + "\n... (생략) ...\n")
