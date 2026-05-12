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


# ============================================================
# 투자 지표 계산 및 DB 저장
# ============================================================

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
    DB DataFrame에서 DART 항목 최신값을 반환.
    account_names 순서대로 시도하여 첫 번째로 발견된 값을 쓴다.
    연결재무제표(CFS) 우선, 없으면 개별(OFS), 그것도 없으면 fs_div 무관 최신값.
    Returns: (float value, int year) 또는 (None, None)
    """
    for acct in account_names:
        mask = (df['source'] == 'DART') & (df['account_nm'] == acct)
        sub = df[mask]
        if sub.empty:
            continue
        for fs_type in ['CFS', 'OFS']:
            t = sub[sub['fs_div'] == fs_type]
            if not t.empty:
                row = t.sort_values('target_year', ascending=False).iloc[0]
                try:
                    return float(row['amount']), int(row['target_year'])
                except (ValueError, TypeError):
                    pass
        # fs_div 무관 최신값 fallback
        row = sub.sort_values('target_year', ascending=False).iloc[0]
        try:
            return float(row['amount']), int(row['target_year'])
        except (ValueError, TypeError):
            pass
    return None, None


def compute_financial_indicators(corp: str) -> list:
    """
    DB에 저장된 DART 및 YFINANCE 데이터만으로 주요 투자 지표 13개를 계산하고
    FS.db에 source='INDICATOR'로 저장합니다. 추가 외부 API 호출 없음.

    사전 조건:
        FS_to_SQL.ensure_company_data(corp)와
        yfinance_api.fetch_and_save_yfinance_info([corp])가
        먼저 실행되어 DB에 데이터가 적재되어 있어야 합니다.

    저장 구조:
        source      = 'INDICATOR'
        fs_div      = 분류 (VAL/PROF/STAB/CF/DIV)
        sj_div      = 단위 (x=배수, %=퍼센트)
        report_type = 계산 출처 (DART/YFINANCE/MIXED)
        account_nm  = 지표명 (PER, PBR, ROE 등)

    Returns:
        저장된 레코드 딕셔너리 리스트
    """
    db = conSQL.FS()
    df = db.search_sql(corp)
    db.close()

    if df is None or df.empty:
        print(f"🚨 [{corp}] DB에 데이터가 없습니다. Financial Agent를 먼저 실행해주세요.")
        return []

    c_code = str(utils_.call_corp_code(corp))
    s_code = str(utils_.call_stock_code(corp))
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

    # ── 공통으로 쓰이는 DART 값을 미리 추출 ─────────────────────────
    net_income, ni_year   = _get_dart_value(df, '당기순이익', '당기순이익(손실)')
    equity_val, eq_year   = _get_dart_value(df, '자본총계', '자본합계')
    assets_val, as_year   = _get_dart_value(df, '자산총계')
    liab_val,   lb_year   = _get_dart_value(df, '부채총계')
    cur_assets, ca_year   = _get_dart_value(df, '유동자산')
    cur_liab,   cl_year   = _get_dart_value(df, '유동부채')
    op_income,  op_year   = _get_dart_value(df, '영업이익')
    revenue,    rev_year  = _get_dart_value(df, '매출액')

    # ── 1. 밸류에이션 (Valuation) ────────────────────────────────────

    # PER: yfinance forwardPE (이미 DB에 있는 값 그대로 사용)
    _add('PER', _get_yf_value(df, 'forwardPE'),
         'YFINANCE', 'VAL', 'x')

    # PBR: 주가(yfinance) / BPS(DART 자본총계 ÷ yfinance 발행주식수)
    #      yfinance는 한국 종목에 priceToBook을 제공하지 않으므로 직접 계산
    price  = _get_yf_value(df, 'regularMarketPrice')
    shares = _get_yf_value(df, 'sharesOutstanding')
    if price and shares and equity_val and shares > 0 and equity_val > 0:
        bps = equity_val / shares
        _add('PBR', price / bps, 'MIXED', 'VAL', 'x', eq_year)

    # PSR: yfinance priceToSalesTrailing12Months
    _add('PSR', _get_yf_value(df, 'priceToSalesTrailing12Months'),
         'YFINANCE', 'VAL', 'x')

    # PEG: yfinance pegRatio
    _add('PEG', _get_yf_value(df, 'pegRatio'),
         'YFINANCE', 'VAL', 'x')

    # EV/EBITDA: yfinance enterpriseToEbitda
    _add('EV/EBITDA', _get_yf_value(df, 'enterpriseToEbitda'),
         'YFINANCE', 'VAL', 'x')

    # ── 2. 수익성 (Profitability) ────────────────────────────────────

    # ROE: DART 당기순이익 / 자본총계 × 100  (fallback: yfinance returnOnEquity)
    if net_income is not None and equity_val and equity_val != 0:
        _add('ROE', (net_income / equity_val) * 100,
             'DART', 'PROF', '%', ni_year)
    else:
        v = _get_yf_value(df, 'returnOnEquity')
        if v is not None:
            _add('ROE', v * 100, 'YFINANCE', 'PROF', '%')

    # ROA: DART 당기순이익 / 자산총계 × 100  (fallback: yfinance returnOnAssets)
    if net_income is not None and assets_val and assets_val != 0:
        _add('ROA', (net_income / assets_val) * 100,
             'DART', 'PROF', '%', ni_year)
    else:
        v = _get_yf_value(df, 'returnOnAssets')
        if v is not None:
            _add('ROA', v * 100, 'YFINANCE', 'PROF', '%')

    # 영업이익률: DART 영업이익 / 매출액 × 100  (fallback: yfinance operatingMargins)
    if op_income is not None and revenue and revenue != 0:
        _add('영업이익률', (op_income / revenue) * 100,
             'DART', 'PROF', '%', op_year)
    else:
        v = _get_yf_value(df, 'operatingMargins')
        if v is not None:
            _add('영업이익률', v * 100, 'YFINANCE', 'PROF', '%')

    # ── 3. 재무 안정성 (Stability) ───────────────────────────────────

    # 부채비율 (한국 회계 기준): DART 부채총계 / 자본총계 × 100
    if liab_val is not None and equity_val and equity_val != 0:
        _add('부채비율', (liab_val / equity_val) * 100,
             'DART', 'STAB', '%', lb_year)

    # 유동비율: DART 유동자산 / 유동부채 × 100  (fallback: yfinance currentRatio × 100)
    if cur_assets is not None and cur_liab and cur_liab != 0:
        _add('유동비율', (cur_assets / cur_liab) * 100,
             'DART', 'STAB', '%', ca_year)
    else:
        v = _get_yf_value(df, 'currentRatio')
        if v is not None:
            _add('유동비율', v * 100, 'YFINANCE', 'STAB', '%')

    # ── 4. 현금흐름 (Cash Flow) ──────────────────────────────────────

    # 영업CF품질비율: 영업현금흐름 / 순이익
    #   1에 가까울수록 이익의 질이 좋음 (영업CF ≈ 순이익)
    op_cf      = _get_yf_value(df, 'operatingCashflow')
    net_inc_yf = _get_yf_value(df, 'netIncomeToCommon')
    if op_cf is not None and net_inc_yf and net_inc_yf != 0:
        _add('영업CF품질비율', op_cf / net_inc_yf,
             'YFINANCE', 'CF', 'x')

    # ── 5. 배당 (Dividend) ───────────────────────────────────────────

    # 배당수익률: yfinance dividendYield (소수점 → % 변환)
    div_yield = _get_yf_value(df, 'dividendYield')
    if div_yield is not None:
        _add('배당수익률', div_yield * 100, 'YFINANCE', 'DIV', '%')

    # 배당성향: yfinance payoutRatio (소수점 → % 변환)
    payout = _get_yf_value(df, 'payoutRatio')
    if payout is not None:
        _add('배당성향', payout * 100, 'YFINANCE', 'DIV', '%')

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
        disp = f"{val:.2f}{unit}" if unit == '%' else f"{val:.4f}x"
        src  = r['report_type']
        print(f"   [{r['fs_div']}] {r['account_nm']:12s} = {disp:>12s}  ({src})")

    return records
