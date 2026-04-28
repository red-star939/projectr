import sys

# Windows 콘솔 환경에서 이모지 출력 시 발생하는 cp949 인코딩 에러 방지
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
import yfinance as yf
import concurrent.futures
from src.financial_agent import yfinance_api
from src.financial_agent import conSQL
from src.financial_agent import Sector
from src.financial_agent import utils_

def calculate_correlation(series1, series2, mode="pearson"):
    """
    지정된 방식(mode)에 따라 두 시리즈 간의 상관계수를 계산합니다.
    지원 모드: pearson, spearman, kendall, distance
    """
    if mode in ["pearson", "spearman", "kendall"]:
        return series1.corr(series2, method=mode)
    elif mode == "distance":
        X = np.atleast_1d(series1)
        Y = np.atleast_1d(series2)
        if len(X) < 2:
            return 0.0
            
        a = np.abs(X[:, None] - X[None, :])
        b = np.abs(Y[:, None] - Y[None, :])
        
        A = a - a.mean(axis=0)[None, :] - a.mean(axis=1)[:, None] + a.mean()
        B = b - b.mean(axis=0)[None, :] - b.mean(axis=1)[:, None] + b.mean()
        
        n = a.shape[0]
        dcov2_xy = (A * B).sum() / (n ** 2)
        dcov2_xx = (A * A).sum() / (n ** 2)
        dcov2_yy = (B * B).sum() / (n ** 2)
        
        if dcov2_xx * dcov2_yy == 0:
            return 0.0
        return np.sqrt(dcov2_xy) / np.sqrt(np.sqrt(dcov2_xx) * np.sqrt(dcov2_yy))
    else:
        raise ValueError(f"지원하지 않는 상관계수 방식입니다: {mode}")

def get_5y_close_history(company):
    """
    특정 기업의 5년치 일일 종가 데이터를 안전하게 가져옵니다. (멀티스레딩 지원용)
    - 코스피(^KS11) 및 개별 기업(.KS -> .KQ fallback) 지원
    - 네트워크 에러 등 각종 예외 상황에 대한 안전망 포함
    """
    try:
        if company == "KOSPI":
            try:
                ticker = yf.Ticker("^KS11")
                hist = ticker.history(period="5y")
                if hist is None or hist.empty or 'Close' not in hist.columns:
                    return pd.Series()
                close = hist['Close'].dropna()
                close.index = close.index.normalize()
                return close
            except Exception as e:
                print(f"⚠️ [KOSPI] 주가 데이터 호출 중 에러 발생: {e}")
                return pd.Series()
            
        stock_code = utils_.call_stock_code(company)
        if stock_code is None:
            print(f"⚠️ [{company}] 종목 코드가 존재하지 않습니다.")
            return pd.Series()
            
        raw_code = str(stock_code).zfill(6)
        hist = None
        
        # 1. 코스피 시도
        try:
            ticker = yf.Ticker(f"{raw_code}.KS")
            hist = ticker.history(period="5y")
        except Exception:
            pass
            
        # 2. 코스닥 재시도
        if hist is None or hist.empty or 'Close' not in hist.columns:
            try:
                ticker = yf.Ticker(f"{raw_code}.KQ")
                hist = ticker.history(period="5y")
            except Exception:
                pass
                
        # 최종 확인
        if hist is None or hist.empty or 'Close' not in hist.columns:
            return pd.Series()
            
        close = hist['Close'].dropna()
        close.index = close.index.normalize()
        return close
        
    except Exception as e:
        print(f"🚨 [{company}] 주가 데이터 수집 중 치명적 에러 발생: {e}")
        return pd.Series()

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


def correlation_with_KOSPI(corp, kospi_value=None, mode="pearson"):
    """
    특정 회사의 현재 주식 지표와 KOSPI 지수를 바탕으로 상관관계(correlation)를 계산합니다.
    코스피 값은 DB에 저장되지 않으며 임시로 계산에만 활용됩니다.
    
    :param corp: 계산할 회사명 (예: "SK하이닉스")
    :param kospi_value: 현 시점의 코스피 값 (None일 경우 yfinance에서 자동으로 받아옵니다)
    :param mode: 상관계수 계산 방식 ("pearson", "spearman", "kendall", "distance")
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

    # 3. KOSPI 5년 주가와 기업의 5년 주가를 가져와 스케일링 후 상관계수 계산
    correlation_result = None
    
    # ---------------------------------------------------------
    print(f"🔄 [{corp}] 및 KOSPI의 5년 주가 데이터를 가져와 상관관계를 계산합니다...")
    try:
        # 1. KOSPI 5년 일일 종가 가져오기
        kospi_close = get_5y_close_history("KOSPI")
        
        # 2. 기업 5년 일일 종가 가져오기
        corp_close = get_5y_close_history(corp)
        
        if corp_close.empty or kospi_close.empty:
            print(f"🚨 [{corp}] 또는 KOSPI의 주가 데이터를 찾을 수 없습니다.")
        else:
            # 상장 시점이 짧으면 그만큼만 가져오고, 코스피도 동일한 기간으로 자름 (dropna로 교집합 날짜만 유지)
            df_merged = pd.DataFrame({'corp': corp_close, 'kospi': kospi_close}).dropna()
            
            if df_merged.empty:
                print("🚨 데이터 병합 후 유효한 기간이 없습니다.")
            else:
                # 전일 대비 일일 수익률(%)로 변환
                df_merged['corp_return'] = df_merged['corp'].pct_change() * 100
                df_merged['kospi_return'] = df_merged['kospi'].pct_change() * 100
                
                # 첫 번째 행은 pct_change로 인해 NaN이 되므로 제거
                df_merged = df_merged.dropna()
                
                # 수익률 기반 상관계수 구하기
                correlation_result = calculate_correlation(df_merged['corp_return'], df_merged['kospi_return'], mode)
                print(f"✅ [{corp}] - KOSPI 5년 주가 수익률(%) 상관계수({mode}): {correlation_result:.4f}")
                
    except Exception as e:
        print(f"🚨 상관관계 계산 중 에러 발생: {e}")
    # ---------------------------------------------------------

    return correlation_result


def compare_with_sector(corp, n=5, mode="pearson"):
    """
    입력 받은 회사의 섹터를 추출하고, 해당 섹터 내 경쟁 회사들의 목록을 가져와 
    지표를 비교(Correlation)하는 기능입니다.
    
    :param corp: 비교 기준이 될 회사명
    :param n: 비교할 상위 회사의 개수 (기본값 5)
    :param mode: 상관계수 계산 방식 ("pearson", "spearman", "kendall", "distance")
    :return: (비교 회사명, 상관계수) 튜플의 리스트
    """
    # 1. 입력된 회사의 섹터를 추출합니다.
    sector_name = Sector.get_sector(corp)
    print(f"🏢 [{corp}]의 섹터를 분석합니다. -> '{sector_name}'")
    
    # 해당 섹터에 포함된 동일 업종의 회사 리스트를 가져옵니다. (conSQL에서 기업가치 순으로 정렬됨)
    all_corps_in_sector = Sector.get_corps_in_sector(sector_name)
    print(f"📊 '{sector_name}' 섹터에는 총 {len(all_corps_in_sector)}개의 회사가 존재합니다.")
    
    # 3. 섹터 내부의 회사 개수가 n+1보다 작다면, n을 (섹터 내부 회사 개수 - 1)로 변경합니다.
    if len(all_corps_in_sector) < n + 1:
        n = len(all_corps_in_sector) - 1
        
    if n <= 0:
        print("🚨 비교할 수 있는 다른 경쟁 회사가 섹터 내에 충분하지 않습니다.")
        return []
        
    # 1. 입력 받은 회사가 상위권에 속하면 이를 제외하고 다음 순위의 회사를 포함해 n개를 가져옵니다.
    target_corps = [c for c in all_corps_in_sector if c != corp][:n]
    
    # 2. 5년 일일 종가 추출 (멀티스레딩 병렬 처리 적용)
    all_targets = [corp] + target_corps
    print(f"🔄 총 {len(all_targets)}개 회사의 주가 데이터를 멀티스레딩으로 수집합니다...")
    
    prices_dict = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(10, len(all_targets))) as executor:
        future_to_corp = {executor.submit(get_5y_close_history, c): c for c in all_targets}
        
        for future in concurrent.futures.as_completed(future_to_corp):
            c = future_to_corp[future]
            try:
                data = future.result()
                if data is not None and not data.empty:
                    prices_dict[c] = data
                else:
                    print(f"⚠️ [{c}] 유효한 주가 데이터가 반환되지 않았습니다.")
            except Exception as exc:
                print(f"🚨 [{c}] 스레드 실행 중 예외 발생: {exc}")

    corp_close = prices_dict.get(corp, pd.Series())
    if corp_close.empty:
        print(f"🚨 입력 회사 [{corp}]의 주가 데이터를 확보하지 못해 비교를 종료합니다.")
        return []

    # 4 & 5. 가져온 차트를 바탕으로 각각의 상관계수를 구하고 리스트로 저장
    results = []
    print(f"🔄 상위 {n}개 회사와의 상관계수({mode}) 계산을 시작합니다...")
    for target in target_corps:
        target_close = prices_dict.get(target, pd.Series())
        if target_close.empty:
            print(f"⚠️ [{target}]의 주가 데이터를 찾을 수 없어 계산을 건너뜁니다.")
            results.append((target, None))
            continue
            
        # 병합을 통한 기간 맞춤
        df_merged = pd.DataFrame({'corp': corp_close, 'target': target_close}).dropna()
        if df_merged.empty:
            print(f"⚠️ [{target}]와 겹치는 주가 기간이 없어 계산을 건너뜁니다.")
            results.append((target, None))
            continue
            
        # 전일 대비 일일 수익률(%)로 변환
        df_merged['corp_return'] = df_merged['corp'].pct_change() * 100
        df_merged['target_return'] = df_merged['target'].pct_change() * 100
        df_merged = df_merged.dropna()
        
        # 수익률 기반 상관계수 산출
        corr = calculate_correlation(df_merged['corp_return'], df_merged['target_return'], mode)
        results.append((target, corr))
        print(f"✅ [{corp}] - [{target}] 5년 수익률(%) 상관계수({mode}): {corr:.4f}")
        
    # 최종 리턴은 각각의 상관계수의 리스트입니다. (회사명, 상관계수) 형태
    return results


