import yfinance as yf
import pandas as pd
import datetime
from . import utils_
from . import conSQL

def fetch_and_save_yfinance_info(corp_names):
    """
    여러 회사의 yfinance info (현재 제공 가능한 최대한의 기본 지표)를 
    모두 긁어와서 SQL에 저장합니다.
    
    :param corp_names: 회사명 리스트 (예: ["SK하이닉스", "삼성전자"])
    """
    db = conSQL.FS()
    
    for corp in corp_names:
        print(f"⏳ [{corp}] yfinance 데이터 가져오기 시도 중...")
        try:
            # 1. 고유번호 및 종목코드 조회 (CORPCODE.xml 활용)
            corp_code = str(utils_.call_corp_code(corp))
            # 종목코드가 숫자인 경우 6자리 문자열로 패딩
            raw_stock_code = str(utils_.call_stock_code(corp)).zfill(6)
            
            # 2. yfinance Ticker 조회 (한국 주식: 코스피 .KS 시도, 안 되면 코스닥 .KQ 시도)
            ticker = yf.Ticker(f"{raw_stock_code}.KS")
            info = ticker.info
            
            # KS(코스피)로 찾지 못했거나 기본 가격 데이터조차 없는 경우 KQ(코스닥)로 재시도
            if not info or ('regularMarketPrice' not in info and 'previousClose' not in info):
                ticker = yf.Ticker(f"{raw_stock_code}.KQ")
                info = ticker.info
                if not info or ('regularMarketPrice' not in info and 'previousClose' not in info):
                    print(f"❌ [{corp}] yfinance 데이터를 찾을 수 없습니다 (KS/KQ 모두 실패).")
                    continue
            
            # 3. 데이터 파싱 (최대한 긁어오기)
            parsed_data = []
            current_year = datetime.datetime.now().year # 현재 기준 보조지표이므로 당해 연도를 사용
            
            for key, value in info.items():
                # 리스트나 복잡한 딕셔너리가 아닌 단순 값(숫자형, 문자형, 불리언)만 허용합니다.
                if isinstance(value, (int, float, str, bool)):
                    parsed_data.append({
                        "source": "YFINANCE",
                        "report_type": "기본지표",
                        "corp_code": corp_code,
                        "stock_code": raw_stock_code,
                        "fs_div": "YF", # yfinance 출처임을 쉽게 알수있는 임의 구분자
                        "sj_div": "INFO", # Info 정보
                        "account_nm": key, # 예: forwardPE, marketCap 등
                        "target_year": current_year,
                        "amount": value # 실수, 정수, 텍스트 등이 들어갈 수 있음
                    })
            
            if parsed_data:
                dfr = pd.DataFrame(parsed_data)
                
                # 방금 정리했던 덮어쓰기 논리구조(계층)와 일치시킵니다.
                subset_keys = ['source', 'report_type', 'corp_code', 'fs_div', 'sj_div', 'account_nm', 'target_year']
                
                # DB에 저장
                db.to_sql(corp, dfr, subset=subset_keys)
                print(f"✅ [{corp}] yfinance {len(dfr)}개의 지표 수집 및 SQL 누적 완료.")
            else:
                print(f"⚠️ [{corp}] 추출할 수 있는 유효한 지표 값이 없습니다.")
                
        except Exception as e:
            print(f"🚨 [{corp}] yfinance 처리 중 에러 발생: {e}")

    db.close()

if __name__ == "__main__":
    # 간단한 테스트
    sample_corps = ["SK하이닉스", "삼성전자"]
    fetch_and_save_yfinance_info(sample_corps)
    
    # DB에 잘 저장되었는지 조회 테스트
    print("\n[DB 적재 결과 엿보기]")
    db = conSQL.FS()
    df = db.search_sql("SK하이닉스")
    db.close()
    
    if df is not None:
        # yfinance 출처인 것만 필터링해서 보여주기
        yf_df = df[df['source'] == 'YFINANCE']
        print(f"SK하이닉스 DB 내 YFINANCE 지표 총 {len(yf_df)}건 존재")
        print(yf_df.head())
