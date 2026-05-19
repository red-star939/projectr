import sys
import datetime

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

def get_5y_history(company):
    """
    5년치 OHLCV DataFrame 반환 (Open/High/Low/Close/Volume 컬럼 포함).

    호출자가 close 만 필요한 경우는 get_5y_close_history 를 사용한다.
    이 함수는 거래량/고저가까지 필요한 기술적 지표 계산용.

    - KOSPI ("^KS11") 및 한국 종목 (.KS → .KQ fallback) 지원
    - 국내 코드북에 없으면 해외 티커로 직접 시도 (예: "AAPL", "^GSPC")
    - 실패 시 빈 DataFrame 반환
    """
    try:
        if company == "KOSPI":
            try:
                hist = yf.Ticker("^KS11").history(period="5y")
                if hist is not None and not hist.empty:
                    hist.index = hist.index.normalize()
                    return hist
            except Exception as e:
                print(f"⚠️ [KOSPI] 주가 데이터 호출 중 에러 발생: {e}")
            return pd.DataFrame()

        stock_code = utils_.call_stock_code(company)
        if stock_code is None:
            # 국내 코드북에 없는 경우 — 해외 티커로 직접 시도
            try:
                hist = yf.Ticker(company).history(period="5y")
                if hist is not None and not hist.empty:
                    hist.index = hist.index.normalize()
                    return hist
            except Exception as e:
                print(f"⚠️ [{company}] yfinance 직접 조회 실패: {e}")
            return pd.DataFrame()

        raw_code = str(stock_code).zfill(6)
        hist = None

        # KS → KQ fallback
        for suffix in ('.KS', '.KQ'):
            try:
                hist = yf.Ticker(f"{raw_code}{suffix}").history(period="5y")
                if hist is not None and not hist.empty:
                    break
            except Exception:
                hist = None

        if hist is None or hist.empty:
            return pd.DataFrame()

        hist.index = hist.index.normalize()
        return hist

    except Exception as e:
        print(f"🚨 [{company}] 주가 히스토리 수집 중 치명적 에러: {e}")
        return pd.DataFrame()


def get_5y_close_history(company):
    """5년치 일일 종가 Series. get_5y_history 의 Close 컬럼만 반환 (기존 호환용)."""
    hist = get_5y_history(company)
    if hist.empty or 'Close' not in hist.columns:
        return pd.Series()
    return hist['Close'].dropna()

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


def correlation_with_KOSPI(corp, kospi_value=None, mode="pearson",
                           corp_close=None, kospi_close=None):
    """
    특정 회사의 5년 주가 수익률과 KOSPI 지수의 상관관계를 계산합니다.

    :param corp: 계산할 회사명 (예: "SK하이닉스")
    :param kospi_value: (legacy) 현 시점 KOSPI 값 — 사용되지 않으나 호환 위해 유지
    :param mode: 상관계수 계산 방식 ("pearson", "spearman", "kendall", "distance")
    :param corp_close: 사전 수집한 종목 5년 종가 Series (None 이면 직접 수집)
    :param kospi_close: 사전 수집한 KOSPI 5년 종가 Series (None 이면 직접 수집)
    :return: 계산된 상관관계 값 (실패 시 None)

    Note: app_1FS.py 등 호출자가 미리 시계열을 한 번만 가져와서
          기술적 지표 계산기와 공유할 수 있도록 corp_close/kospi_close 인자를 받는다.
    """
    # 1. 사전 fetch 된 시계열이 없으면 직접 수집
    correlation_result = None

    print(f"🔄 [{corp}] vs KOSPI 5년 주가 수익률 상관계수 계산 중...")
    try:
        if kospi_close is None:
            kospi_close = get_5y_close_history("KOSPI")
        if corp_close is None:
            corp_close = get_5y_close_history(corp)

        if corp_close is None or corp_close.empty or kospi_close is None or kospi_close.empty:
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


# ============================================================
# 해외 종목 벤치마크 상관계수 (correlation_with_KOSPI 의 일반화)
# ============================================================

def correlation_with_benchmark(
    corp_or_ticker: str,
    benchmark_ticker: str,
    mode: str = "pearson",
    corp_close=None,
    benchmark_close=None,
) -> float | None:
    """
    특정 종목과 지정된 벤치마크 지수 간 5년 일일 수익률 상관계수를 계산한다.

    correlation_with_KOSPI 의 일반화 버전으로,
    국내·해외 종목 모두에 사용할 수 있다.

    Parameters
    ----------
    corp_or_ticker : str
        한국 기업명("삼성전자") 또는 해외 티커("AAPL", "7203.T")
    benchmark_ticker : str
        yfinance 지수 티커 (예: "^GSPC", "^N225").
        market_index_map.get_benchmark_index() 로 구하거나 직접 지정.
    corp_close, benchmark_close : pd.Series | None
        사전 수집한 종가 Series. None 이면 직접 수집.
    mode : str
        상관계수 방식 ("pearson" | "spearman" | "kendall" | "distance")

    Notes
    -----
    - yfinance_api.fetch_and_save_yfinance_info 는 호출하지 않는다.
      호출자(app_1FS.py)가 이미 저장했다고 가정한다.
    - 주가 히스토리는 DB 에 저장하지 않고 계산에만 사용한다.
    """
    print(f"🔄 [{corp_or_ticker}] vs [{benchmark_ticker}] 5년 수익률 상관계수 계산 중...")

    try:
        if corp_close is None:
            corp_close = get_5y_close_history(corp_or_ticker)
        if benchmark_close is None:
            benchmark_close = get_5y_close_history(benchmark_ticker)

        if corp_close is None or corp_close.empty or benchmark_close is None or benchmark_close.empty:
            print(f"🚨 [{corp_or_ticker}] 또는 [{benchmark_ticker}] 주가 데이터를 찾을 수 없습니다.")
            return None

        df_merged = pd.DataFrame(
            {"corp": corp_close, "bench": benchmark_close}
        ).dropna()

        if df_merged.empty:
            print("🚨 데이터 병합 후 유효한 기간이 없습니다.")
            return None

        df_merged["corp_return"]  = df_merged["corp"].pct_change()  * 100
        df_merged["bench_return"] = df_merged["bench"].pct_change() * 100
        df_merged = df_merged.dropna()

        corr = calculate_correlation(df_merged["corp_return"], df_merged["bench_return"], mode)
        print(f"✅ [{corp_or_ticker}] - [{benchmark_ticker}] 상관계수({mode}): {corr:.4f}")
        return corr

    except Exception as e:
        print(f"🚨 [{corp_or_ticker}] 벤치마크 상관계수 계산 중 에러: {e}")
        return None


# ============================================================
# 투자 지표 계산 및 DB 저장
# ============================================================

# 포트폴리오 "기본" 모드에서 사용할 핵심 지표 셋 (실전 활용 팁 기준)
#   · 향후 portfolio_manager / app_3Port 에서 모드 분기 시 import 하여 사용
#   · compute_financial_indicators 는 항상 전체 지표를 저장하며,
#     "기본" 필터는 보고서/포트폴리오 조회 단계에서 적용된다
PORTFOLIO_DEFAULT_INDICATORS: frozenset[str] = frozenset({
    # 가치투자 (6)
    'PER', 'PBR', 'ROE', '부채비율', 'FCF수익률', 'Piotroski_F',
    # 성장투자 (4)
    '매출CAGR_3Y', 'EPS성장률', 'Rule_of_40', 'ROIC',
    # 배당투자 (3) — 배당성장률은 Phase 3 구현 후 자동 포함
    '배당수익률', '배당성장률', '배당커버리지',
})


# ============================================================
# 지표 합리적 범위 — 보고서 표시 시 이탈값에 ⚠️ 마커
#   None = 해당 방향 제한 없음 (예: 베타는 음수 가능 → 하한 None)
#   yfinance 데이터 이상 / 회계적 극단 케이스 (Apple ROE 141% 등) 식별용
#   저장 데이터는 그대로, 표시 단계에서만 적용
# ============================================================
SUSPICIOUS_RANGE: dict[str, tuple[float | None, float | None]] = {
    # ── 밸류에이션 ──
    'PER':              (0,    100),
    'PBR':              (0,    20),
    'PSR':              (0,    50),
    'PEG':              (-5,   10),
    'EV/EBITDA':        (-20,  100),
    'EV/Sales':         (0,    50),
    'EV/FCF':           (-100, 200),
    'P/FCF':            (0,    200),
    'GP/A':             (0,    1.5),
    'NCAV/시총':        (-2,   5),
    'FCF수익률':         (-20,  30),
    # ── 수익성 ──
    'ROE':              (-50,  60),
    'ROA':              (-30,  30),
    '영업이익률':         (-50,  60),
    '매출총이익률':       (0,    95),
    'EBITDA마진':        (-50,  70),
    'ROIC':             (-50,  60),
    'ROCE':             (-50,  60),
    'CROIC':            (-50,  60),
    '자산회전율':         (0,    5),
    '재고회전율':         (0,    50),
    'DSO':              (0,    365),
    'CCC':              (-180, 365),
    # ── 안정성 ──
    '부채비율':          (0,    400),
    '유동비율':          (50,   600),
    '당좌비율':          (30,   600),
    '순부채/EBITDA':     (-10,  10),
    'Piotroski_F':       (0,    9),
    'Piotroski_가용항목수': (0, 9),
    'Altman_Z':          (-5,   20),
    # ── 현금흐름 ──
    '영업CF품질비율':     (-3,   5),
    'CapEx/매출':       (0,    50),
    'Owner_Earnings수익률': (-10, 30),
    # ── 배당 ──
    '배당수익률':         (0,    15),
    '배당성향':          (0,    200),
    '배당커버리지':       (0,    50),
    '배당성장률':         (-50,  100),
    '자사주수익률':       (0,    20),
    '총주주환원율':       (0,    30),
    # ── 성장성 ──
    '매출성장률':         (-80,  300),
    'EPS성장률':         (-200, 1000),
    '분기EPS성장률':     (-200, 1000),
    'Rule_of_40':       (-100, 300),
    '재투자율':          (-100, 200),
    'SGR':              (-50,  50),
    '매출CAGR_3Y':       (-30,  100),
    '매출CAGR_5Y':       (-30,  100),
    # ── 시장·기술적 ──
    '베타':              (-2,   3),
    '공매도잔고율':       (0,    50),
    'RSI_14':           (0,    100),
    'MA20_괴리율':       (-50,  100),
    'MA60_괴리율':       (-50,  150),
    'MA200_괴리율':      (-70,  200),
    'MACD_히스토그램':    (-0.1, 0.1),
    'Bollinger_%B':     (-0.5, 1.5),
    '거래량추세_20/60':   (0.1,  5),
}


def is_suspicious_value(account_nm: str, amount) -> bool:
    """지표 값이 SUSPICIOUS_RANGE 의 합리적 범위를 벗어났는지 판정."""
    if account_nm not in SUSPICIOUS_RANGE:
        return False
    try:
        v = float(amount)
    except (TypeError, ValueError):
        return False
    lo, hi = SUSPICIOUS_RANGE[account_nm]
    if lo is not None and v < lo:
        return True
    if hi is not None and v > hi:
        return True
    return False

def _get_yf_value(df: pd.DataFrame, account_nm: str):
    """DB DataFrame에서 YFINANCE 항목 최신값을 float으로 반환. 없으면 None."""
    mask = (df['source'] == 'YFINANCE') & (df['account_nm'] == account_nm)
    sub = df[mask]
    if sub.empty:
        return None
    try:
        return float(sub.sort_values('target_year', ascending=False).iloc[0]['amount'])
    except (ValueError, TypeError):
        return None


def _get_dart_value(df: pd.DataFrame, *account_names: str):
    """
    DB DataFrame에서 DART 또는 YF_FS 항목 최신값을 반환.
    account_names 순서대로 시도하여 첫 번째로 발견된 값을 쓴다.
    DART CFS → DART OFS → DART 무관 → YF_FS 순으로 우선순위 적용.
    Returns: (float value, int year) 또는 (None, None)
    """
    for acct in account_names:
        # DART (한국) 우선 검색
        dart_sub = df[(df['source'] == 'DART') & (df['account_nm'] == acct)]
        if not dart_sub.empty:
            for fs_type in ['CFS', 'OFS']:
                t = dart_sub[dart_sub['fs_div'] == fs_type]
                if not t.empty:
                    row = t.sort_values('target_year', ascending=False).iloc[0]
                    try:
                        return float(row['amount']), int(row['target_year'])
                    except (ValueError, TypeError):
                        pass
            # fs_div 무관 최신값 fallback
            row = dart_sub.sort_values('target_year', ascending=False).iloc[0]
            try:
                return float(row['amount']), int(row['target_year'])
            except (ValueError, TypeError):
                pass

        # YF_FS (해외 종목) fallback — YF_FS_ACCOUNT_MAP으로 정규화된 한국어 계정명 검색
        yf_fs_sub = df[(df['source'] == 'YF_FS') & (df['account_nm'] == acct)]
        if not yf_fs_sub.empty:
            row = yf_fs_sub.sort_values('target_year', ascending=False).iloc[0]
            try:
                return float(row['amount']), int(row['target_year'])
            except (ValueError, TypeError):
                pass

    return None, None


def compute_financial_indicators(corp: str) -> list:
    """
    DB에 저장된 DART/YF_FS/YFINANCE 데이터만으로 주요 투자 지표 40+개를 계산하고
    FS.db에 source='INDICATOR'로 저장합니다. 추가 외부 API 호출 없음.

    사전 조건:
        FS_to_SQL.ensure_company_data(corp) [국내] 또는
        intl_yf.ensure_intl_data(corp) [해외]
        + yfinance_api.fetch_and_save_yfinance_info([corp]) 또는
          intl_yf.fetch_and_save_intl_yf_info(corp)
        가 먼저 실행되어 DB에 데이터가 적재되어 있어야 합니다.

    저장 구조:
        source      = 'INDICATOR'
        fs_div      = 분류 (VAL/PROF/STAB/CF/DIV/GROWTH/MKT)
        sj_div      = 단위 (x=배수, %=퍼센트, 점수, 일=일수)
        report_type = 계산 출처 (DART/YFINANCE/MIXED/MIXED-APPROX)
        account_nm  = 지표명 (PER, PBR, ROE, ROIC, Piotroski_F 등)

    구현 카테고리:
      VAL    — PER, PBR, PSR, PEG, EV/EBITDA, EV/Sales, EV/FCF, P/FCF,
               GP/A, NCAV/시총, FCF수익률
      PROF   — ROE, ROA, 영업이익률, ROIC, ROCE, CROIC, 매출총이익률,
               EBITDA마진, 자산회전율
      STAB   — 부채비율, 유동비율, 순부채/EBITDA, 당좌비율,
               Piotroski_F (+가용항목수), Altman_Z
      CF     — 영업CF품질비율, CapEx/매출, Owner_Earnings수익률
      DIV    — 배당수익률, 배당성향, 배당커버리지
      GROWTH — 매출성장률, EPS성장률, 분기EPS성장률, Rule_of_40,
               재투자율, SGR, 매출CAGR_3Y (5Y는 데이터 있을 때만)
      MKT    — 베타, 공매도잔고율

    참고:
      한국 종목은 DART fnlttSinglAcnt 가 매출총이익/매출원가/재고자산/매출채권/
      매입채무/감가상각비를 반환하지 않아 일부 지표는 yfinance fallback 사용 또는
      N/A 처리됩니다. 해외 종목은 YF_FS_ACCOUNT_MAP 으로 정규화되어 전체 가용.

    Returns:
        저장된 레코드 딕셔너리 리스트
    """
    db = conSQL.FS()
    df = db.search_sql(corp)
    db.close()

    if df is None or df.empty:
        print(f"🚨 [{corp}] DB에 데이터가 없습니다. Financial Agent를 먼저 실행해주세요.")
        return []

    # 해외 종목은 DART 코드북에 없으므로 corp 티커 자체를 코드로 사용
    c_code = str(utils_.call_corp_code(corp) or corp)
    s_code = str(utils_.call_stock_code(corp) or corp)
    curr_year = datetime.datetime.now().year
    records = []

    def _add(account_nm, amount, report_type, fs_div, sj_div, year=None):
        """유효한 값만 records에 추가하는 내부 헬퍼."""
        if amount is None:
            return
        try:
            v = float(amount)
        except (ValueError, TypeError):
            return
        records.append({
            'source':      'INDICATOR',
            'report_type': report_type,
            'corp_code':   c_code,
            'stock_code':  s_code,
            'fs_div':      fs_div,
            'sj_div':      sj_div,
            'account_nm':  account_nm,
            'target_year': year if year is not None else curr_year,
            'amount':      round(v, 6),
        })

    # ── 공통으로 쓰이는 DART/YF_FS 값을 미리 추출 ───────────────────
    net_income, ni_year   = _get_dart_value(df, '당기순이익', '당기순이익(손실)')
    equity_val, eq_year   = _get_dart_value(df, '자본총계', '자본합계')
    assets_val, as_year   = _get_dart_value(df, '자산총계')
    liab_val,   lb_year   = _get_dart_value(df, '부채총계')
    cur_assets, ca_year   = _get_dart_value(df, '유동자산')
    cur_liab,   cl_year   = _get_dart_value(df, '유동부채')
    op_income,  op_year   = _get_dart_value(df, '영업이익')
    revenue,    rev_year  = _get_dart_value(df, '매출액')
    gross_profit, gp_year = _get_dart_value(df, '매출총이익')
    cost_of_rev, cor_year = _get_dart_value(df, '매출원가')
    inventory,  inv_year  = _get_dart_value(df, '재고자산')
    receivables, ar_year  = _get_dart_value(df, '매출채권')
    payables,   ap_year   = _get_dart_value(df, '매입채무')
    da_dart,    da_year   = _get_dart_value(df, '감가상각비')
    capex_dart, capex_year_dart = _get_dart_value(df, '자본적지출')

    # ── 공통 yfinance 시장 데이터 ────────────────────────────────────
    price    = _get_yf_value(df, 'regularMarketPrice')
    shares   = _get_yf_value(df, 'sharesOutstanding')
    m_cap    = _get_yf_value(df, 'marketCap')
    fcf      = _get_yf_value(df, 'freeCashflow')
    op_cf    = _get_yf_value(df, 'operatingCashflow')
    ebitda_v = _get_yf_value(df, 'ebitda')
    tot_debt = _get_yf_value(df, 'totalDebt')
    tot_cash = _get_yf_value(df, 'totalCash')
    capex_yf = _get_yf_value(df, 'capitalExpenditures')

    # 감가상각: DART → yfinance 순서
    da_val = da_dart if da_dart is not None else _get_yf_value(df, 'reconciledDepreciation')
    if da_val is None:
        da_val = _get_yf_value(df, 'depreciationAndAmortization')

    # CapEx: yfinance(절댓값) → DART(절댓값)
    capex_abs = None
    if capex_yf is not None:
        capex_abs = abs(capex_yf)
    elif capex_dart is not None:
        capex_abs = abs(capex_dart)

    # 특정 연도의 DART/YF_FS 값 조회 (Piotroski/CAGR 등 다년 비교용)
    def _year_value(acct_list, year):
        if year is None:
            return None
        for acct in acct_list:
            sub = df[(df['account_nm'] == acct)
                     & df['source'].isin(['DART', 'YF_FS'])
                     & (df['target_year'] == year)]
            if sub.empty:
                continue
            # DART: CFS 우선
            for fs_type in ['CFS', 'OFS']:
                t = sub[sub['fs_div'] == fs_type]
                if not t.empty:
                    try:
                        return float(t.iloc[0]['amount'])
                    except (ValueError, TypeError):
                        pass
            # fs_div 무관 fallback
            try:
                return float(sub.iloc[0]['amount'])
            except (ValueError, TypeError):
                pass
        return None

    # ── 1. 밸류에이션 (Valuation) ────────────────────────────────────

    # PER: yfinance forwardPE
    _add('PER', _get_yf_value(df, 'forwardPE'), 'YFINANCE', 'VAL', 'x')

    # PBR: 주가 / BPS — DART/YF_FS 자본총계 우선, fallback: priceToBook
    if price and shares and equity_val and shares > 0 and equity_val > 0:
        bps = equity_val / shares
        _add('PBR', price / bps, 'MIXED', 'VAL', 'x', eq_year)
    else:
        ptb = _get_yf_value(df, 'priceToBook')
        if ptb is not None:
            _add('PBR', ptb, 'YFINANCE', 'VAL', 'x')

    # PSR / PEG / EV/EBITDA — yfinance 직접
    _add('PSR', _get_yf_value(df, 'priceToSalesTrailing12Months'), 'YFINANCE', 'VAL', 'x')
    _add('PEG', _get_yf_value(df, 'pegRatio'), 'YFINANCE', 'VAL', 'x')
    _add('EV/EBITDA', _get_yf_value(df, 'enterpriseToEbitda'), 'YFINANCE', 'VAL', 'x')

    # EV/Sales — 적자/성장 기업 평가용
    _add('EV/Sales', _get_yf_value(df, 'enterpriseToRevenue'), 'YFINANCE', 'VAL', 'x')

    # EV/FCF — PER보다 조작 어려운 valuation 지표
    ev = _get_yf_value(df, 'enterpriseValue')
    if ev is not None and fcf and fcf > 0:
        _add('EV/FCF', ev / fcf, 'YFINANCE', 'VAL', 'x')

    # P/FCF — 주가 ÷ 주당 FCF
    if price and shares and fcf and shares > 0:
        fcf_ps = fcf / shares
        if fcf_ps > 0:
            _add('P/FCF', price / fcf_ps, 'YFINANCE', 'VAL', 'x')

    # GP/A — Novy-Marx의 수익성·valuation 결합 지표
    if gross_profit is not None and assets_val and assets_val != 0:
        _add('GP/A', gross_profit / assets_val, 'DART', 'VAL', 'x', gp_year)
    else:
        # 한국 종목 fallback: yfinance grossMargins × revenue ÷ 자산
        gm_v = _get_yf_value(df, 'grossMargins')
        if gm_v is not None and revenue and assets_val and assets_val != 0:
            _add('GP/A', (gm_v * revenue) / assets_val, 'MIXED', 'VAL', 'x', rev_year)

    # NCAV/시총 비율 — Graham 안전마진
    #   2/3(≈0.67) 이상이면 극도의 저평가 신호
    if cur_assets is not None and liab_val is not None and m_cap and m_cap > 0:
        ncav = cur_assets - liab_val
        _add('NCAV/시총', ncav / m_cap, 'MIXED', 'VAL', 'x', ca_year)

    # FCF 수익률 — 채권금리와 직접 비교 가능
    if fcf is not None and m_cap and m_cap > 0:
        _add('FCF수익률', (fcf / m_cap) * 100, 'YFINANCE', 'VAL', '%')

    # ── 2. 수익성·효율성 (Profitability & Efficiency) ─────────────────

    # ROE
    if net_income is not None and equity_val and equity_val != 0:
        _add('ROE', (net_income / equity_val) * 100, 'DART', 'PROF', '%', ni_year)
    else:
        v = _get_yf_value(df, 'returnOnEquity')
        if v is not None:
            _add('ROE', v * 100, 'YFINANCE', 'PROF', '%')

    # ROA
    if net_income is not None and assets_val and assets_val != 0:
        _add('ROA', (net_income / assets_val) * 100, 'DART', 'PROF', '%', ni_year)
    else:
        v = _get_yf_value(df, 'returnOnAssets')
        if v is not None:
            _add('ROA', v * 100, 'YFINANCE', 'PROF', '%')

    # 영업이익률
    if op_income is not None and revenue and revenue != 0:
        _add('영업이익률', (op_income / revenue) * 100, 'DART', 'PROF', '%', op_year)
    else:
        v = _get_yf_value(df, 'operatingMargins')
        if v is not None:
            _add('영업이익률', v * 100, 'YFINANCE', 'PROF', '%')

    # 매출총이익률 — 가격 결정력·경쟁우위(해자) 판단
    if gross_profit is not None and revenue and revenue != 0:
        _add('매출총이익률', (gross_profit / revenue) * 100, 'DART', 'PROF', '%', gp_year)
    else:
        gm_v = _get_yf_value(df, 'grossMargins')
        if gm_v is not None:
            _add('매출총이익률', gm_v * 100, 'YFINANCE', 'PROF', '%')

    # EBITDA 마진 — 업종 간 비교 용이
    em_v = _get_yf_value(df, 'ebitdaMargins')
    if em_v is not None:
        _add('EBITDA마진', em_v * 100, 'YFINANCE', 'PROF', '%')

    # 투하자본 (Invested Capital = 자산총계 - 유동부채)
    invested_cap = None
    if assets_val is not None and cur_liab is not None:
        invested_cap = assets_val - cur_liab

    # 실효세율 (없으면 한국 기준 25% 기본값)
    tax_rate = _get_yf_value(df, 'effectiveTaxRate')
    if tax_rate is None or tax_rate < 0 or tax_rate > 0.5:
        tax_rate = 0.25

    # ROIC — NOPAT / 투하자본 (WACC 비교 기준)
    if op_income is not None and invested_cap and invested_cap > 0:
        nopat = op_income * (1 - tax_rate)
        _add('ROIC', (nopat / invested_cap) * 100, 'MIXED', 'PROF', '%', op_year)

    # ROCE — 영업이익 / 사용자본 (유럽 표준)
    if op_income is not None and invested_cap and invested_cap > 0:
        _add('ROCE', (op_income / invested_cap) * 100, 'DART', 'PROF', '%', op_year)

    # CROIC — 현금 기반 ROIC
    if fcf is not None and invested_cap and invested_cap > 0:
        _add('CROIC', (fcf / invested_cap) * 100, 'MIXED', 'PROF', '%')

    # 자산회전율
    if revenue is not None and assets_val and assets_val != 0:
        _add('자산회전율', revenue / assets_val, 'DART', 'PROF', 'x', rev_year)

    # 재고회전율 (해외 종목 — 한국은 DART에 재고자산 없음)
    if cost_of_rev is not None and inventory and inventory > 0:
        _add('재고회전율', cost_of_rev / inventory, 'DART', 'PROF', 'x', cor_year)

    # DSO (매출채권회전일수) — 해외 종목
    if receivables is not None and revenue and revenue > 0:
        _add('DSO', (receivables / revenue) * 365, 'DART', 'PROF', '일', ar_year)

    # CCC (현금전환주기) = DIO + DSO - DPO
    if (inventory is not None and cost_of_rev and cost_of_rev > 0
        and receivables is not None and revenue and revenue > 0
        and payables is not None):
        dio = (inventory / cost_of_rev) * 365
        dso = (receivables / revenue) * 365
        dpo = (payables / cost_of_rev) * 365
        _add('CCC', dio + dso - dpo, 'DART', 'PROF', '일', cor_year)

    # ── 3. 재무 안정성 (Stability) ───────────────────────────────────

    # 부채비율
    if liab_val is not None and equity_val and equity_val != 0:
        _add('부채비율', (liab_val / equity_val) * 100, 'DART', 'STAB', '%', lb_year)
    else:
        dte = _get_yf_value(df, 'debtToEquity')
        if dte is not None:
            _add('부채비율', dte, 'YFINANCE', 'STAB', '%')

    # 유동비율
    if cur_assets is not None and cur_liab and cur_liab != 0:
        _add('유동비율', (cur_assets / cur_liab) * 100, 'DART', 'STAB', '%', ca_year)
    else:
        v = _get_yf_value(df, 'currentRatio')
        if v is not None:
            _add('유동비율', v * 100, 'YFINANCE', 'STAB', '%')

    # 당좌비율 — 재고 제외한 즉시 현금화 가능 자산 / 유동부채
    qr_v = _get_yf_value(df, 'quickRatio')
    if qr_v is not None:
        _add('당좌비율', qr_v * 100, 'YFINANCE', 'STAB', '%')

    # 순부채/EBITDA — 3배 이하 안정, 5배 초과 위험
    if tot_debt is not None and tot_cash is not None and ebitda_v and ebitda_v > 0:
        net_debt = tot_debt - tot_cash
        _add('순부채/EBITDA', net_debt / ebitda_v, 'YFINANCE', 'STAB', 'x')

    # ── 4. 현금흐름 (Cash Flow) ──────────────────────────────────────

    # 영업CF품질비율 — 1에 가까울수록 이익의 질 우수
    net_inc_yf = _get_yf_value(df, 'netIncomeToCommon')
    if op_cf is not None and net_inc_yf and net_inc_yf != 0:
        _add('영업CF품질비율', op_cf / net_inc_yf, 'YFINANCE', 'CF', 'x')

    # CapEx/매출 — 자본집약도 (낮을수록 자본 효율적)
    if capex_abs is not None and revenue and revenue > 0:
        _add('CapEx/매출', (capex_abs / revenue) * 100, 'MIXED', 'CF', '%')

    # Owner Earnings — 버핏 제안: 순이익 + 감가상각 - 유지보수 CapEx (근사)
    # 결과는 수익률 형태(시총 대비)로 저장
    if net_income is not None and da_val is not None and capex_abs is not None and m_cap and m_cap > 0:
        owner_earn = net_income + da_val - capex_abs
        _add('Owner_Earnings수익률', (owner_earn / m_cap) * 100, 'MIXED-APPROX', 'CF', '%')

    # ── 5. 배당 (Dividend) ───────────────────────────────────────────

    # 배당수익률
    #   yfinance API 변경 (~2024) — dividendYield 가 이미 % 단위로 반환됨
    #   (예: 삼성전자 0.53 = 0.53%). 과거의 소수형 가정으로 ×100 적용 시 100배 부풀려짐.
    div_yield = _get_yf_value(df, 'dividendYield')
    if div_yield is not None:
        _add('배당수익률', div_yield, 'YFINANCE', 'DIV', '%')

    # 배당성향
    payout = _get_yf_value(df, 'payoutRatio')
    if payout is not None:
        _add('배당성향', payout * 100, 'YFINANCE', 'DIV', '%')

    # 배당커버리지 — FCF ÷ 총배당금. 1.5배 이상이면 안정적
    div_rate = _get_yf_value(df, 'dividendRate')
    if fcf is not None and div_rate and shares and div_rate > 0 and shares > 0:
        total_div = div_rate * shares
        if total_div > 0:
            _add('배당커버리지', fcf / total_div, 'YFINANCE', 'DIV', 'x')

    # 배당성장률 (DGR) — '연간배당' 시계열에서 CAGR 산출
    #   진행중 연도(올해)는 분기 단위 데이터만 있을 수 있어 끝점 왜곡 → 제외
    div_hist = df[(df['source'] == 'YFINANCE')
                  & (df['account_nm'] == '연간배당')].copy()
    if not div_hist.empty and len(div_hist) >= 2:
        div_hist = div_hist.sort_values('target_year')
        # 진행중 연도 제외
        div_hist = div_hist[div_hist['target_year'] < curr_year]
        # 최근 5개 완결 연도
        div_hist = div_hist.tail(5)
        if len(div_hist) >= 2:
            try:
                first = float(div_hist.iloc[0]['amount'])
                last = float(div_hist.iloc[-1]['amount'])
                span = int(div_hist.iloc[-1]['target_year']) - int(div_hist.iloc[0]['target_year'])
                if first > 0 and last > 0 and span > 0:
                    dgr = ((last / first) ** (1 / span) - 1) * 100
                    _add('배당성장률', dgr, 'YFINANCE', 'DIV', '%')
            except (TypeError, ValueError):
                pass

    # 자사주매입 수익률 — YF_FS(해외) 또는 YFINANCE(국내) 의 '자사주매입' 최신값 ÷ 시총
    bb_sub = df[df['account_nm'] == '자사주매입'].copy()
    if not bb_sub.empty and m_cap and m_cap > 0:
        bb_sub = bb_sub.sort_values('target_year', ascending=False)
        try:
            bb_latest = abs(float(bb_sub.iloc[0]['amount']))
            buyback_yield = (bb_latest / m_cap) * 100
            _add('자사주수익률', buyback_yield, 'MIXED', 'DIV', '%',
                 int(bb_sub.iloc[0]['target_year']))

            # 총주주환원율 = 배당수익률 + 자사주수익률 (가용한 경우)
            div_yield_rec = next((r for r in records if r['account_nm'] == '배당수익률'), None)
            if div_yield_rec is not None:
                total_yield = div_yield_rec['amount'] + buyback_yield
                _add('총주주환원율', total_yield, 'MIXED', 'DIV', '%')
        except (TypeError, ValueError):
            pass

    # ── 6. 성장성 (Growth) ───────────────────────────────────────────

    rev_growth = _get_yf_value(df, 'revenueGrowth')
    if rev_growth is not None:
        _add('매출성장률', rev_growth * 100, 'YFINANCE', 'GROWTH', '%')

    eps_growth = _get_yf_value(df, 'earningsGrowth')
    if eps_growth is not None:
        _add('EPS성장률', eps_growth * 100, 'YFINANCE', 'GROWTH', '%')

    q_growth = _get_yf_value(df, 'earningsQuarterlyGrowth')
    if q_growth is not None:
        _add('분기EPS성장률', q_growth * 100, 'YFINANCE', 'GROWTH', '%')

    # Rule of 40 — SaaS 평가용. 매출성장률 + 영업이익률 ≥ 40 이면 우수
    op_margin_v = _get_yf_value(df, 'operatingMargins')
    if rev_growth is not None and op_margin_v is not None:
        _add('Rule_of_40', rev_growth * 100 + op_margin_v * 100,
             'YFINANCE', 'GROWTH', '점수')

    # 재투자율 — (당기순이익 - 배당총액) / 당기순이익
    if net_income is not None and div_rate and shares and div_rate > 0 and shares > 0 and net_income > 0:
        total_div_paid = div_rate * shares
        _add('재투자율', ((net_income - total_div_paid) / net_income) * 100,
             'MIXED', 'GROWTH', '%', ni_year)
    elif payout is not None:
        _add('재투자율', (1 - payout) * 100, 'YFINANCE', 'GROWTH', '%')

    # SGR (지속가능성장률) — ROE × (1 - 배당성향)
    roe_rec = next((r for r in records if r['account_nm'] == 'ROE'), None)
    if roe_rec is not None and payout is not None:
        sgr_v = (roe_rec['amount'] / 100) * (1 - payout) * 100
        _add('SGR', sgr_v, 'MIXED', 'GROWTH', '%')

    # 매출 CAGR 3Y (5Y는 데이터 있을 때만)
    #   연도별로 fs_div 알파벳 우선순위 적용 (CFS < IS < OFS) →
    #     한국: CFS 우선, 해외(YF_FS): IS 우선 으로 자동 선택
    #   pandas 버전 무관 (groupby.apply 미사용)
    rev_mask = (df['account_nm'] == '매출액') & df['source'].isin(['DART', 'YF_FS'])
    rev_df = df[rev_mask]
    if not rev_df.empty:
        rev_sorted = rev_df.sort_values(['target_year', 'fs_div'], ascending=[False, True])
        rev_unique = rev_sorted.drop_duplicates(subset='target_year', keep='first')
        try:
            rev_yearly = (
                rev_unique
                .set_index('target_year')['amount']
                .astype(float)
                .sort_index(ascending=False)
            )
        except (ValueError, TypeError):
            rev_yearly = None

        if rev_yearly is not None and len(rev_yearly) >= 4:
            r_curr = float(rev_yearly.iloc[0])
            r_3y = float(rev_yearly.iloc[3])
            if r_3y > 0 and r_curr > 0:
                cagr3 = ((r_curr / r_3y) ** (1/3) - 1) * 100
                _add('매출CAGR_3Y', cagr3, 'DART', 'GROWTH', '%')

        if rev_yearly is not None and len(rev_yearly) >= 6:
            r_5y = float(rev_yearly.iloc[5])
            r_curr = float(rev_yearly.iloc[0])
            if r_5y > 0 and r_curr > 0:
                cagr5 = ((r_curr / r_5y) ** (1/5) - 1) * 100
                _add('매출CAGR_5Y', cagr5, 'DART', 'GROWTH', '%')

    # ── 7. 시장 (Market) ─────────────────────────────────────────────

    beta_v = _get_yf_value(df, 'beta')
    if beta_v is not None:
        _add('베타', beta_v, 'YFINANCE', 'MKT', 'x')

    short_v = _get_yf_value(df, 'shortPercentOfFloat')
    if short_v is not None:
        _add('공매도잔고율', short_v * 100, 'YFINANCE', 'MKT', '%')

    # ── 8. Piotroski F-Score (9개 항목 중 가용한 만큼 채점) ──────────

    base_year_p = rev_year or ni_year or (curr_year - 1)
    prev_year_p = base_year_p - 1

    ni_prev = _year_value(['당기순이익', '당기순이익(손실)'], prev_year_p)
    assets_prev = _year_value(['자산총계'], prev_year_p)
    liab_prev = _year_value(['부채총계'], prev_year_p)
    ca_prev = _year_value(['유동자산'], prev_year_p)
    cl_prev = _year_value(['유동부채'], prev_year_p)
    gp_prev = _year_value(['매출총이익'], prev_year_p)
    rev_prev = _year_value(['매출액'], prev_year_p)

    f_score = 0
    f_avail = 0

    # F1: 순이익 > 0
    if net_income is not None:
        f_avail += 1
        if net_income > 0:
            f_score += 1

    # F2: 영업현금흐름 > 0
    if op_cf is not None:
        f_avail += 1
        if op_cf > 0:
            f_score += 1

    # F3: ROA 개선 (YoY)
    if (net_income is not None and assets_val and assets_val > 0
        and ni_prev is not None and assets_prev and assets_prev > 0):
        f_avail += 1
        if (net_income / assets_val) > (ni_prev / assets_prev):
            f_score += 1

    # F4: 영업CF > 순이익 (Accruals 검증)
    if op_cf is not None and net_income is not None:
        f_avail += 1
        if op_cf > net_income:
            f_score += 1

    # F5: 부채비율(부채/자산) 감소
    if (liab_val is not None and assets_val and assets_val > 0
        and liab_prev is not None and assets_prev and assets_prev > 0):
        f_avail += 1
        if (liab_val / assets_val) < (liab_prev / assets_prev):
            f_score += 1

    # F6: 유동비율 개선
    if (cur_assets is not None and cur_liab and cur_liab > 0
        and ca_prev is not None and cl_prev and cl_prev > 0):
        f_avail += 1
        if (cur_assets / cur_liab) > (ca_prev / cl_prev):
            f_score += 1

    # F7: 주식 희석 없음 — 전년도 sharesOutstanding 미보유로 채점 불가 (스킵)

    # F8: 매출총이익률 개선
    if (gross_profit is not None and revenue and revenue > 0
        and gp_prev is not None and rev_prev and rev_prev > 0):
        f_avail += 1
        if (gross_profit / revenue) > (gp_prev / rev_prev):
            f_score += 1

    # F9: 자산회전율 개선
    if (revenue and assets_val and assets_val > 0
        and rev_prev and assets_prev and assets_prev > 0):
        f_avail += 1
        if (revenue / assets_val) > (rev_prev / assets_prev):
            f_score += 1

    if f_avail > 0:
        _add('Piotroski_F', f_score, 'MIXED', 'STAB', '점수')
        _add('Piotroski_가용항목수', f_avail, 'MIXED', 'STAB', '점수')

    # ── 9. Altman Z-Score (근사: retained earnings 자리에 자본총계 사용) ──
    # Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
    #  X1=(유동자산-유동부채)/총자산  X2=자본총계/총자산 (approx)
    #  X3=영업이익/총자산  X4=시총/부채총계  X5=매출/총자산
    if (cur_assets is not None and cur_liab is not None and assets_val and assets_val > 0
        and op_income is not None and liab_val and liab_val > 0
        and m_cap and m_cap > 0 and revenue and equity_val is not None):
        X1 = (cur_assets - cur_liab) / assets_val
        X2 = equity_val / assets_val
        X3 = op_income / assets_val
        X4 = m_cap / liab_val
        X5 = revenue / assets_val
        z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
        _add('Altman_Z', z, 'MIXED-APPROX', 'STAB', '점수')

    # ── DB 저장 ──────────────────────────────────────────────────────
    if not records:
        print(f"⚠️ [{corp}] 계산된 지표가 없습니다. DART/YFINANCE 데이터가 DB에 있는지 확인해주세요.")
        return []

    ind_df = pd.DataFrame(records)
    db = conSQL.FS()
    # (source, corp_code, fs_div, account_nm, target_year) 조합이 동일하면 최신값으로 갱신
    subset = ['source', 'corp_code', 'fs_div', 'account_nm', 'target_year']
    db.to_sql(corp, ind_df, subset=subset)
    db.close()

    print(f"✅ [{corp}] {len(records)}개 투자 지표 계산 및 DB 저장 완료")
    for r in records:
        unit = r['sj_div']
        val  = r['amount']
        if unit == '%':
            disp = f"{val:.2f}%"
        elif unit == '일':
            disp = f"{val:.1f}일"
        elif unit == '점수':
            disp = f"{val:.2f}점"
        else:
            disp = f"{val:.4f}x"
        src = r['report_type']
        print(f"   [{r['fs_div']:6s}] {r['account_nm']:18s} = {disp:>12s}  ({src})")

    return records


# ============================================================
# 기술적 지표 계산 및 DB 저장 (Phase 4)
# ============================================================

def compute_technical_indicators(corp: str, hist: pd.DataFrame | None = None) -> list:
    """
    5년 주가 OHLCV 시계열로부터 기술적 지표를 계산하여 INDICATOR/MKT 로 저장.

    저장 항목 (account_nm, sj_div):
        RSI_14            (점수, 0~100)
        MA20_괴리율        (%, (가격-MA20)/MA20×100)
        MA60_괴리율        (%)
        MA200_괴리율       (%)
        MACD_히스토그램     (x, 가격으로 정규화된 비율)
        Bollinger_%B      (x, 0=하단·1=상단)
        거래량추세_20/60   (x, 단기/장기 거래량 평균 비율)

    Parameters
    ----------
    corp : str
        한국 기업명 또는 해외 티커
    hist : pd.DataFrame | None
        사전에 수집한 5년 OHLCV. None 이면 직접 get_5y_history 호출.

    Returns
    -------
    저장된 레코드 리스트
    """
    if hist is None:
        hist = get_5y_history(corp)

    if hist is None or hist.empty or 'Close' not in hist.columns:
        print(f"⚠️ [{corp}] 주가 시계열이 없어 기술적 지표 계산을 건너뜁니다.")
        return []

    close = hist['Close'].dropna()
    if len(close) < 30:
        print(f"⚠️ [{corp}] 거래일 부족 ({len(close)}일) — 기술적 지표 계산 불가")
        return []

    volume = hist['Volume'].dropna() if 'Volume' in hist.columns else pd.Series()

    c_code = str(utils_.call_corp_code(corp) or corp)
    s_code = str(utils_.call_stock_code(corp) or corp)
    curr_year = datetime.datetime.now().year
    records = []

    def _add(account_nm, amount, sj_div):
        if amount is None:
            return
        try:
            v = float(amount)
        except (TypeError, ValueError):
            return
        if np.isnan(v) or np.isinf(v):
            return
        records.append({
            'source':      'INDICATOR',
            'report_type': 'TECHNICAL',
            'corp_code':   c_code,
            'stock_code':  s_code,
            'fs_div':      'MKT',
            'sj_div':      sj_div,
            'account_nm':  account_nm,
            'target_year': curr_year,
            'amount':      round(v, 6),
        })

    price_now = float(close.iloc[-1])

    # ── RSI(14) — Wilder's smoothing 약식 (SMA 기반)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi_latest = rsi.dropna().iloc[-1] if not rsi.dropna().empty else None
    _add('RSI_14', rsi_latest, '점수')

    # ── 이동평균 괴리율
    for period in (20, 60, 200):
        if len(close) >= period:
            ma = close.rolling(period).mean().iloc[-1]
            if ma and ma > 0:
                divergence_pct = (price_now / ma - 1) * 100
                _add(f'MA{period}_괴리율', divergence_pct, '%')

    # ── MACD (12, 26, 9) — 히스토그램을 현재가 대비 비율로 정규화
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist_last = (macd_line - signal).iloc[-1]
    if price_now > 0 and pd.notna(macd_hist_last):
        _add('MACD_히스토그램', macd_hist_last / price_now, 'x')

    # ── Bollinger %B (20, 2σ)
    if len(close) >= 20:
        bb_mid = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        upper = bb_mid + 2 * bb_std
        lower = bb_mid - 2 * bb_std
        width = upper.iloc[-1] - lower.iloc[-1]
        if width and width > 0:
            bp = (price_now - lower.iloc[-1]) / width
            _add('Bollinger_%B', bp, 'x')

    # ── 거래량 추세 (20일 평균 ÷ 60일 평균)
    if not volume.empty and len(volume) >= 60:
        v_short = volume.tail(20).mean()
        v_long = volume.tail(60).mean()
        if v_long and v_long > 0:
            _add('거래량추세_20/60', v_short / v_long, 'x')

    if not records:
        return []

    ind_df = pd.DataFrame(records)
    db = conSQL.FS()
    subset = ['source', 'corp_code', 'fs_div', 'account_nm', 'target_year']
    db.to_sql(corp, ind_df, subset=subset)
    db.close()

    print(f"✅ [{corp}] 기술적 지표 {len(records)}개 계산 및 DB 저장 완료")
    for r in records:
        unit, val = r['sj_div'], r['amount']
        if unit == '%':
            disp = f"{val:+.2f}%"
        elif unit == '점수':
            disp = f"{val:.2f}점"
        else:
            disp = f"{val:.4f}x"
        print(f"   [MKT] {r['account_nm']:20s} = {disp:>12s}")

    return records
