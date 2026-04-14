import pandas as pd
import yfinance as yf
from src.financial_agent import yfinance_api
from src.financial_agent import conSQL
from src.financial_agent import Sector

def get_current_kospi():
    """
    yfinance를 이용하여 현재 기준 KOSPI 지수(^KS11)를 실시간으로 받아옵니다.
    """
    try:
        kospi_ticker = yf.Ticker("^KS11")
        # history로 가장 최근 확정(종가 혹은 현재가) KOSPI 값을 가져옵니다.
        hist = kospi_ticker.history(period="1d")
        if not hist.empty:
            kospi_val = hist['Close'].iloc[-1]
            return float(kospi_val)
        return None
    except Exception as e:
        print(f"🚨 KOSPI 지수를 받아오는 과정에서 에러 발생: {e}")
        return None


def correlation_with_KOSPI(corp, kospi_value=None):
    """
    특정 회사의 현재 주식 지표와 KOSPI 지수를 바탕으로 상관관계(correlation)를 계산합니다.
    코스피 값은 DB에 저장되지 않으며 임시로 계산에만 활용됩니다.
    
    :param corp: 계산할 회사명 (예: "SK하이닉스")
    :param kospi_value: 현 시점의 코스피 값 (None일 경우 yfinance에서 자동으로 받아옵니다)
    :return: 계산된 상관관계 값 (또는 결과)
    """
    # 0. 코스피 값이 누락되었으면 현 시점 KOSPI 수치를 직접 가져옵니다.
    if kospi_value is None:
        kospi_value = get_current_kospi()
        if kospi_value is not None:
            print(f"📈 현재가 기준 KOSPI 지수를 받아왔습니다: {kospi_value:.2f}")
        else:
            print("🚨 KOSPI 지수 확인 불가로 계산을 종료합니다.")
            return None
    # 1. yfinance_api의 함수를 호출하여 현 시점의 주식지표값을 최신화합니다.
    # (이 함수는 내부적으로 데이터를 수집하고 SQL DB에 저장합니다.)
    yfinance_api.fetch_and_save_yfinance_info([corp])
    
    # 2. DB에서 최근 수집된 YFINANCE 기반 지표 데이터를 다시 불러옵니다.
    db = conSQL.FS()
    df = db.search_sql(corp)
    db.close()
    
    yf_df = None
    if df is not None and not df.empty:
        # DB에서 yfinance를 통해 수집된 'YFINANCE' 지표만 필터링합니다.
        yf_df = df[df['source'] == 'YFINANCE']
    
    if yf_df is None or yf_df.empty:
        print(f"🚨 [{corp}] 지표값을 불러오지 못해 상관관계를 계산할 수 없습니다.")
        return None

    # 3. KOSPI 지수와 yfinance 지표들을 기반으로 Correlation 수식 적용 (TODO)
    correlation_result = None
    
    # ---------------------------------------------------------
    # [수식 작성 부분]
    # 어떤 correlation을 구할지 정해지지 않았으므로 이곳은 비워둡니다.
    # yf_df (기업의 최신 지표 DataFrame)와 kospi_value (현재 KOSPI 지수)를 활용해
    # 아래에 로직을 작성해주시면 됩니다.
    # ---------------------------------------------------------
    
    # TODO: Correlation 계산 공식 작성
    
    
    
    # ---------------------------------------------------------

    return correlation_result


def compare_with_sector(corp):
    """
    입력 받은 회사의 섹터를 추출하고, 해당 섹터 내 경쟁 회사들의 목록을 가져와 
    지표를 비교(Correlation)하는 기능의 뼈대 함수입니다.
    
    :param corp: 비교 기준이 될 회사명
    :return: 비교 결과값 (사용자 구현 예정)
    """
    # 1. 입력된 회사의 섹터를 추출합니다.
    sector_name = Sector.get_sector(corp)
    print(f"🏢 [{corp}]의 섹터를 분석합니다. -> '{sector_name}'")
    
    # 2. 해당 섹터에 포함된 동일 업종의 회사 리스트를 가져옵니다.
    corps_in_sector = Sector.get_corps_in_sector(sector_name)
    print(f"📊 '{sector_name}' 섹터에는 총 {len(corps_in_sector)}개의 회사가 존재합니다.")
    
    # TODO: 이 이후의 세부 지표 비교 계산 및 반환값 설정은 사용자가 직접 구현합니다.
    
    pass


if __name__ == "__main__":
    # 간단한 테스트 동작 (KOSPI 값이 2650.12 라고 가정)
    corp_name = "SK하이닉스"
    current_kospi = 2650.12
    
    result = correlation_with_KOSPI(corp_name, current_kospi)
    print(f"\n최종 리턴된 KOSPI 상관관계 값: {result}")
    
    print("\n[섹터 비교 기반 테스트 시작]")
    compare_with_sector(corp_name)
