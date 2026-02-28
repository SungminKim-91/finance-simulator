# Design: BTC Liquidity Prediction Model v1.0.0

> Feature: btc-liquidity-model
> Created: 2026-03-01
> Status: Final (v1.0.0)
> PDCA Phase: Completed
> Updated: 2026-03-01 (Gap Analysis 반영)
> Based on: [Plan](../../01-plan/features/btc-liquidity-model.plan.md)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        main.py (CLI)                             │
│  Commands: fetch / calculate / optimize / run / visualize        │
└──────────┬───────────────────────────────────────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────┐
│                   pipeline/runner.py                              │
│  Orchestrates: Fetch → Calculate → Score → Store → Visualize     │
└──────┬──────────┬──────────┬──────────┬──────────┬───────────────┘
       │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼
  ┌─────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌─────────────┐
  │Fetchers │ │Calcs   │ │Optim.  │ │Storage │ │Visualization│
  │ Layer   │ │ Layer  │ │ Layer  │ │ Layer  │ │   Layer     │
  └─────────┘ └────────┘ └────────┘ └────────┘ └─────────────┘
       │
       ▼
  ┌─────────────────────────┐
  │  data/raw/    (캐시)     │
  │  data/processed/ (시계열)│
  │  data/scores/  (결과)    │
  └─────────────────────────┘
```

---

## 2. Module Design — Fetchers

### 2.1 `config/settings.py` — 환경 설정

```python
"""환경변수 로드 및 글로벌 설정"""
from dotenv import load_dotenv
import os

load_dotenv()

# API Keys
FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")

# Data Range
DATA_START: str = "2016-01-01"
DATA_END: str = "2025-12-31"       # 백테스트 종료
WARMUP_MONTHS: int = 12            # 12m MA warm-up
EFFECTIVE_START: str = "2017-01-01" # 유효 기간 시작

# Paths
DATA_DIR: str = "data"
RAW_DIR: str = f"{DATA_DIR}/raw"
PROCESSED_DIR: str = f"{DATA_DIR}/processed"
SCORES_DIR: str = f"{DATA_DIR}/scores"
```

### 2.2 `config/constants.py` — 모델 상수

```python
"""v4.0 모델 상수 — 최적화 후 업데이트"""

# FRED 시리즈 매핑
FRED_SERIES = {
    "WALCL": "WALCL",           # Fed Balance Sheet (주간)
    "RRP": "RRPONTSYD",         # Reverse Repo (일간)
    "SOFR": "SOFR",             # SOFR rate (일간)
    "IORB": "IORB",             # Interest on Reserve Balances (일간)
    "US_M2": "M2SL",            # US M2 Money Supply (월간)
    "EU_M2": "MABMM301EZM189S",  # Euro Area M3 Broad Money (M2 단종으로 대체, ~2023-11)
    "CN_M2": "MYAGM2CNM189N",   # China M2 (월간, ~2019-08, carry-forward)
    "JP_M2": "MABMM301JPM189S", # Japan M3 Broad Money (M2 단종으로 대체, ~2023-11)
    "HY_SPREAD": "BAMLH0A0HYM2", # HY OAS (월간)
}

# Treasury API
TREASURY_TGA_ENDPOINT = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    "/v1/accounting/dts/operating_cash_balance"
)
TREASURY_TGA_FIELDS = "record_date,open_today_bal,account_type"
TREASURY_TGA_FILTER_OLD = "account_type:eq:Federal Reserve Account"           # ~2021-09
TREASURY_TGA_FILTER_NEW = "account_type:eq:Treasury General Account (TGA) Closing Balance"  # 2021-10~
TREASURY_PAGE_SIZE = 10000

# Market Tickers (yfinance)
TICKERS = {
    "DXY": "DX-Y.NYB",
    "BTC_SPOT": "BTC-USD",
    "CME_BTC_FUTURES": "BTC=F",
}

# CoinGecko (fallback)
COINGECKO_BTC_URL = (
    "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
)

# SOFR Binary Threshold
SOFR_THRESHOLD_BPS = 20  # basis points

# Detrend Window
MA_WINDOW_MONTHS = 12

# Grid Search Ranges
GRID_SEARCH = {
    "NL_level":    {"min": 0.5, "max": 5.5, "step": 0.5},
    "GM2_resid":   {"min": 0.0, "max": 4.0, "step": 0.5},
    "SOFR_binary": {"min": -4.0, "max": 0.0, "step": 0.5},
    "HY_level":    {"min": -4.0, "max": 0.0, "step": 0.5},
    "CME_basis":   {"min": -2.0, "max": 3.0, "step": 0.5},
    "lag_months":  {"min": 0, "max": 9, "step": 1},
}

# Walk-Forward Parameters
WALK_FORWARD = {
    "initial_train": 60,   # 초기 훈련 윈도우 (월)
    "test_window": 6,      # 테스트 윈도우 (월)
    "expanding": True,     # expanding window
}

# Previous Best (v3.0 — 3변수 기준, 비교용)
V3_WEIGHTS = {
    "NL_level": 1.5,
    "GM2_resid": 2.0,
    "SOFR_binary": -2.5,
}
V3_OPTIMAL_LAG = 5
V3_CORRELATION = 0.407

# Orthogonalization Threshold
ORTHO_CORR_THRESHOLD = 0.5

# Z-Score params (v3.0 기준 — Phase 4 Grid Search 후 업데이트)
ZSCORE_PARAMS_V3 = {
    "NL_level":  {"mean": 2.3800, "std": 9.6004},
    "NL_accel":  {"mean": 0.0119, "std": 3.6226},
    "GM2_level": {"mean": 2.5455, "std": 2.8769},
    "DXY_level": {"mean": 0.0023, "std": 3.6039},
    "SOFR_bin":  {"mean": 0.1204, "std": 0.3269},
}
# HY_level, CME_basis z-score params → 데이터 수집 후 계산
```

### 2.3 `src/fetchers/fred_fetcher.py`

```python
"""FRED API를 통한 경제 데이터 수집"""

class FredFetcher:
    """
    FRED API wrapper.
    캐싱: data/raw/fred_{series}_{date}.csv
    Rate limit: 120 req/min (자동 throttle)
    """

    def __init__(self, api_key: str):
        """fredapi.Fred 초기화"""

    def fetch_series(
        self,
        series_id: str,
        start: str,
        end: str,
        frequency: str | None = None,  # 'd', 'w', 'm' 등
    ) -> pd.DataFrame:
        """
        단일 시리즈 수집.
        Returns: DataFrame[date, value]
        캐시 히트 시 로컬 파일 반환.
        """

    def fetch_all_fred_series(
        self,
        start: str,
        end: str,
    ) -> dict[str, pd.DataFrame]:
        """
        FRED_SERIES 전체 배치 수집.
        Returns: {"WALCL": df, "RRP": df, ...}
        """

    def _save_cache(self, series_id: str, df: pd.DataFrame) -> None:
        """data/raw/fred_{series_id}.csv 저장"""

    def _load_cache(self, series_id: str) -> pd.DataFrame | None:
        """캐시 파일 존재 + 유효기간 내 → 반환, 아니면 None"""
```

### 2.4 `src/fetchers/treasury_fetcher.py`

```python
"""Treasury Fiscal Data API — TGA(재무부 일반계정) 수집"""

class TreasuryFetcher:
    """
    API Key 불필요. REST 직접 호출.
    캐싱: data/raw/treasury_tga.csv
    """

    def fetch_tga(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """
        TGA 일간 잔액 수집.
        Endpoint: /v1/accounting/dts/operating_cash_balance
        2021-10-01 이후 account_type 명칭 변경 대응:
          - 이전: "Federal Reserve Account" (FILTER_OLD)
          - 이후: "Treasury General Account (TGA) Closing Balance" (FILTER_NEW)
        두 기간을 각각 fetch하여 합산.
        Pagination: 자동 처리 (page[size]=10000)
        Returns: DataFrame[date, tga_balance] (단위: $M → $T 변환)
        """

    def _fetch_with_filter(self, account_filter, start, end) -> list[dict]:
        """특정 account_type 필터로 API 호출 (페이지네이션 포함)"""

    def _parse_records(self, records: list[dict]) -> pd.DataFrame:
        """API 응답 레코드 → DataFrame 변환"""
```

### 2.5 `src/fetchers/market_fetcher.py`

```python
"""Yahoo Finance — DXY, BTC, CME BTC Futures 수집"""

class MarketFetcher:
    """
    yfinance 패키지 사용. 무료, 키 불필요.
    캐싱: data/raw/market_{ticker}.csv
    """

    def fetch_ticker(
        self,
        ticker: str,
        start: str,
        end: str,
        interval: str = "1d",
    ) -> pd.DataFrame:
        """
        단일 티커 수집.
        Returns: DataFrame[date, open, high, low, close, volume]
        """

    def fetch_dxy(self, start: str, end: str) -> pd.DataFrame:
        """DXY 월말 종가 → DataFrame[date, dxy]"""

    def fetch_btc_spot(self, start: str, end: str) -> pd.DataFrame:
        """BTC-USD 일간/월말 종가 → DataFrame[date, btc_spot]"""

    def fetch_cme_futures(self, start: str, end: str) -> pd.DataFrame:
        """
        CME BTC 근월물(BTC=F) 일간/월말 종가.
        주의: 2017-12 이전 데이터 없음 → NaN.
        Returns: DataFrame[date, cme_futures]
        """

    def _resample_monthly(self, df: pd.DataFrame, col: str) -> pd.DataFrame:
        """일간 → 월말 리샘플링 (last business day)"""
```

### 2.6 `src/fetchers/fallback_fetcher.py`

```python
"""CoinGecko / Binance — BTC 현물 보조 데이터"""

class FallbackFetcher:
    """
    yfinance 실패 시 fallback.
    CoinGecko: 무료 (50 req/min), Binance: 무료 (1200 req/min)
    """

    def fetch_coingecko_btc(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """
        CoinGecko /market_chart/range API.
        Returns: DataFrame[date, btc_spot]
        주의: 무료 tier 365일 제한 → 분할 요청 필요
        """

    def fetch_binance_btc(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """
        Binance /api/v3/klines API.
        Returns: DataFrame[date, btc_spot]
        """

    def fetch_btc_spot_with_fallback(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """Yahoo → CoinGecko → Binance 순차 시도"""
```

---

## 3. Module Design — Calculators

### 3.1 `src/calculators/detrend.py` — 핵심 공통 모듈

```python
"""12m MA Detrend + Z-Score 표준화 — 모든 수준 변수에 공통 적용"""

def detrend_12m_ma(
    series: pd.Series,
    window: int = 12,
) -> pd.Series:
    """
    X_detrended(t) = (X(t) - MA12(X, t)) / MA12(X, t) × 100

    Args:
        series: 원본 월간 시계열
        window: MA 윈도우 (default 12)
    Returns:
        detrended series (처음 window-1개월은 NaN)

    경제적 의미: "최근 1년 추세 대비 현재 수준이 얼마나 높은가/낮은가 (%)"
    """

def zscore(
    series: pd.Series,
    mean: float | None = None,
    std: float | None = None,
) -> pd.Series:
    """
    z = (x - μ) / σ

    Args:
        series: detrended 시계열
        mean, std: 고정 파라미터 (None이면 series에서 계산)
    Returns:
        z-score 표준화 시계열

    주의: 백테스트 기간의 μ, σ를 고정해야 미래 데이터 누출 방지
    """

def compute_zscore_params(
    series: pd.Series,
) -> dict:
    """
    시계열에서 mean, std 계산.
    Returns: {"mean": float, "std": float}
    """
```

### 3.2 `src/calculators/net_liquidity.py`

```python
"""Net Liquidity (NL) = WALCL - TGA - RRP"""

class NetLiquidityCalculator:

    def calculate(
        self,
        walcl: pd.DataFrame,  # [date, value] 주간
        tga: pd.DataFrame,    # [date, tga_balance] 일간
        rrp: pd.DataFrame,    # [date, value] 일간
    ) -> pd.DataFrame:
        """
        1. 모든 시계열을 월말 기준으로 리샘플링
        2. NL = WALCL - TGA - RRP (단위: $T)
        3. NL_level = detrend_12m_ma(NL)
        4. NL_accel = NL_level.diff()  # 가속도

        Returns: DataFrame[date, nl_raw, nl_level, nl_accel]

        Edge cases:
        - WALCL은 주간 → 월말 가장 가까운 값 사용
        - TGA는 일간 → 월말 값 사용
        - RRP는 일간 → 월말 값 사용
        - 단위 통일: 모두 $T (trillion)
        """

    def _align_to_monthly(
        self,
        walcl: pd.DataFrame,
        tga: pd.DataFrame,
        rrp: pd.DataFrame,
    ) -> pd.DataFrame:
        """주간/일간 → 월말 정렬, 결측 forward-fill"""
```

### 3.3 `src/calculators/global_m2.py`

```python
"""Global M2 합산 + 직교화"""

class GlobalM2Calculator:

    def calculate(
        self,
        us_m2: pd.DataFrame,
        eu_m2: pd.DataFrame,
        cn_m2: pd.DataFrame,
        jp_m2: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        1. 각국 M2를 USD 기준으로 통일 (이미 FRED에서 USD)
        2. GM2 = US + EU + CN + JP (단위: $T)
        3. 래그 처리: 최신 2-3개월 → 직전값 캐리포워드
        4. GM2_level = detrend_12m_ma(GM2)

        Returns: DataFrame[date, gm2_raw, gm2_level]
        """

    def orthogonalize(
        self,
        gm2_level: pd.Series,
        nl_level: pd.Series,
    ) -> tuple[pd.Series, dict]:
        """
        GM2에서 NL과 겹치는 부분 제거.

        Method: OLS regression
          GM2_level = β × NL_level + α + ε
          GM2_resid = ε (잔차)

        Returns:
          - gm2_resid: 직교화된 시리즈
          - params: {"beta": float, "alpha": float, "corr_before": float, "corr_after": float}

        검증: corr(gm2_resid, nl_level) ≈ 0.000
        """

    def _carry_forward_lag(
        self,
        series: pd.Series,
        max_lag_months: int = 3,
    ) -> pd.Series:
        """최신 래그 기간 → 직전값으로 채우기"""
```

### 3.4 `src/calculators/sofr_binary.py`

```python
"""SOFR Binary — 위기 감지"""

class SofrBinaryCalculator:

    def calculate(
        self,
        sofr: pd.DataFrame,  # [date, value] 일간
        iorb: pd.DataFrame,  # [date, value] 일간
        threshold_bps: int = 20,
    ) -> pd.DataFrame:
        """
        1. spread = SOFR - IORB (bps)
        2. 월말 기준 spread 계산
        3. binary = 1 if spread > threshold else 0

        Returns: DataFrame[date, sofr_spread_bps, sofr_binary]

        참고: 2018-04 이전 SOFR 없음 → 0 처리
              IORB 2021-07 이전 → IOER 사용 가능 (같은 역할)
        """
```

### 3.5 `src/calculators/hy_spread.py`

```python
"""HY Spread Level — 신용 스프레드 (위험선호)"""

class HySpreadCalculator:

    def calculate(
        self,
        hy_oas: pd.DataFrame,  # [date, value] 월간
    ) -> pd.DataFrame:
        """
        1. HY_level = detrend_12m_ma(HY_OAS)
        2. 역상관 예상: HY 상승(위험회피) → BTC 하락

        Returns: DataFrame[date, hy_raw, hy_level]

        데이터 특성:
        - ICE BofA US High Yield OAS (Option-Adjusted Spread)
        - 단위: percentage points (예: 3.5 = 350bps)
        - 2016-01 ~ 현재: 전 기간 커버
        """
```

### 3.6 `src/calculators/cme_basis.py`

```python
"""CME Basis — 기관 포지셔닝"""

class CmeBasisCalculator:

    def calculate(
        self,
        cme_futures: pd.DataFrame,  # [date, cme_futures] 일간
        btc_spot: pd.DataFrame,     # [date, btc_spot] 일간
    ) -> pd.DataFrame:
        """
        1. 월말 기준 정렬
        2. raw_basis = (futures - spot) / spot × 100  (%)
        3. annualized_basis = raw_basis × (365 / days_to_expiry)
           - days_to_expiry: CME BTC 월물 만기까지 잔존일
           - CME BTC: 매월 마지막 금요일 만기
        4. Basis_level = detrend_12m_ma(annualized_basis)
           - 주의: |Basis_12mMA|로 나눔 (음수 방지)

        Returns: DataFrame[date, basis_raw_pct, basis_annualized, basis_level]

        Edge cases:
        - 2017-12 이전: NaN (CME BTC 선물 미존재)
        - 만기 당일: 다음 월물로 전환 (롤오버)
        - basis < 0 (백워데이션): 그대로 사용
        """

    def _estimate_days_to_expiry(self, date: pd.Timestamp) -> int:
        """
        해당 월의 CME BTC 만기일(마지막 금요일) 계산.
        date가 만기 이후면 다음 월 만기까지 잔존일.
        """

    def _handle_rollover(
        self,
        futures: pd.Series,
        dates: pd.DatetimeIndex,
    ) -> pd.Series:
        """만기일 전후 가격 점프 스무딩"""
```

---

## 4. Module Design — Optimizers

### 4.1 `src/optimizers/orthogonalize.py`

```python
"""변수 간 직교화 모듈"""

def check_and_orthogonalize(
    variables: dict[str, pd.Series],
    threshold: float = 0.5,
) -> tuple[dict[str, pd.Series], list[dict]]:
    """
    모든 변수 쌍의 상관 확인.
    |corr| > threshold인 쌍 → OLS residual로 직교화.

    Args:
        variables: {"NL_level": series, "GM2_level": series, ...}
        threshold: 직교화 기준 상관 계수
    Returns:
        - orthogonalized variables dict
        - log: [{"pair": ("GM2", "NL"), "corr_before": 0.53, "corr_after": 0.00, ...}]

    직교화 우선순위:
    1. NL은 메인 변수 → 절대 직교화하지 않음
    2. 다른 변수가 NL과 상관 높으면 → 해당 변수에서 NL 제거
    3. NL 외 변수끼리 상관 높으면 → 경제적 의미 기준 판단
    """

def ols_residual(
    y: pd.Series,
    x: pd.Series,
) -> tuple[pd.Series, float, float]:
    """
    y = β*x + α + ε → return ε
    Returns: (residual, beta, alpha)
    """
```

### 4.2 `src/optimizers/grid_search.py`

```python
"""5변수 파형 매칭 Grid Search"""

class GridSearchOptimizer:

    def __init__(self, search_config: dict = GRID_SEARCH):
        """탐색 범위 설정"""

    def optimize(
        self,
        z_matrix: pd.DataFrame,  # [date, NL_z, GM2r_z, SOFR_z, HY_z, CME_z]
        log_btc: pd.Series,      # log₁₀(BTC) 월간
    ) -> dict:
        """
        Grid Search 수행.

        Algorithm:
          for each weight_combination in grid:
              score = Z @ weights
              for k in range(0, max_lag+1):
                  if k > 0:
                      r = corr(score[:-k], log_btc[k:])
                  else:
                      r = corr(score, log_btc)
              best_r_for_this_combo = max(r over k)
          → return combination with highest best_r

        Returns: {
            "weights": {"NL_level": 1.5, ...},
            "optimal_lag": 5,
            "correlation": 0.45,
            "top_50": [...],  # 상위 50개 결과 (안정성 분석)
        }

        최적화 팁:
        - NaN이 있는 변수(CME_basis): 유효 기간만 사용
        - 변수 0개인 조합 제외
        - 진행률 표시 (tqdm)
        """

    def _generate_grid(self) -> list[dict]:
        """탐색 범위에서 모든 가중치 조합 생성"""

    def _compute_score(
        self,
        z_matrix: np.ndarray,
        weights: np.ndarray,
    ) -> np.ndarray:
        """score = Z @ w"""

    def _evaluate(
        self,
        score: np.ndarray,
        target: np.ndarray,
        max_lag: int,
    ) -> tuple[float, int]:
        """
        모든 lag에서 corr 계산 → (best_corr, best_lag) 반환.
        corr = pearsonr(score[:-k], target[k:])
        """
```

### 4.3 `src/optimizers/walk_forward.py`

```python
"""Walk-Forward 검증"""

class WalkForwardValidator:

    def __init__(
        self,
        initial_train: int = 60,
        test_window: int = 6,
        expanding: bool = True,
    ):
        """윈도우 파라미터 설정"""

    def validate(
        self,
        z_matrix: pd.DataFrame,
        log_btc: pd.Series,
        weights: dict,
        lag: int,
    ) -> dict:
        """
        Walk-Forward OOS 검증.

        Algorithm:
          total = len(z_matrix)  # ~108
          for i in range(n_windows):
              if expanding:
                  train = z_matrix[:initial_train + i*test_window]
              else:
                  train = z_matrix[i*test_window : initial_train + i*test_window]
              test = z_matrix[initial_train + i*test_window :
                              initial_train + (i+1)*test_window]
              # train에서 z-score params 재계산
              # test에서 OOS corr 계산

        Returns: {
            "n_windows": 8,
            "oos_correlations": [0.35, 0.42, ...],
            "mean_oos_corr": 0.38,
            "std_oos_corr": 0.05,
            "all_positive": True,
            "windows": [{"train_range": ..., "test_range": ..., "corr": ...}, ...]
        }
        """

    def _split_windows(
        self,
        total_months: int,
    ) -> list[tuple[range, range]]:
        """(train_indices, test_indices) 리스트 생성"""
```

---

## 5. Module Design — Pipeline & Storage

### 5.1 `src/pipeline/runner.py`

```python
"""주간 파이프라인 오케스트레이터"""

class PipelineRunner:

    def __init__(self, mode: str = "full"):
        """
        mode:
          - "full": 전체 백테스트 (fetch + calc + optimize)
          - "update": 최신 데이터만 추가 (주간 실행용)
          - "score_only": 저장된 가중치로 현재 Score만 계산
        """

    def run(self) -> dict:
        """
        Full pipeline:
        1. Fetch all data sources
        2. Calculate derived variables (NL, GM2, SOFR, HY, CME)
        3. Orthogonalization check (직교화를 z-score 전에 수행)
        4. Z-score standardization
        5. If mode=="full": Grid Search + Walk-Forward
        6. Compute current score
        7. Store results
        8. Generate visualization (optional)

        Returns: {
            "score": float,
            "signal": "BULLISH" | "BEARISH" | "NEUTRAL",
            "lag": int,
            "weights": dict,
            "correlation": float,
            "timestamp": str,
        }
        """

    def _signal_from_score(self, score: float) -> str:
        """
        score > +0.5  → "BULLISH"
        score < -0.5  → "BEARISH"
        else           → "NEUTRAL"
        (임계값은 히스토리 기반 조정)
        """
```

### 5.2 `src/pipeline/storage.py`

```python
"""결과 저장 (JSON + SQLite)"""

class StorageManager:

    def __init__(self, base_dir: str = "data"):
        """data/ 하위 디렉토리 초기화"""

    # --- JSON 저장 ---

    def save_score(self, result: dict) -> str:
        """
        data/scores/score_{YYYY-MM-DD}.json 저장
        Returns: 파일 경로
        """

    def save_optimization_result(self, result: dict) -> str:
        """
        data/scores/optimization_{YYYY-MM-DD}.json 저장
        Grid Search + Walk-Forward 결과 전체
        """

    def load_latest_weights(self) -> dict | None:
        """가장 최근 optimization 결과에서 weights 로드"""

    # --- SQLite 저장 ---

    def init_db(self) -> None:
        """
        Tables:
        - scores: (id, date, score, signal, lag, weights_json, corr, created_at)
        - variables: (id, date, nl_level, gm2_resid, sofr_bin, hy_level, cme_basis, created_at)
        - optimizations: (id, date, weights_json, lag, corr, oos_corr, walk_forward_json, created_at)
        """

    def insert_score(self, result: dict) -> None:
    def insert_variables(self, date: str, variables: dict) -> None:
    def get_score_history(self, n: int = 12) -> list[dict]:
```

---

## 6. Module Design — Visualization

### 6.1 `src/visualization/overlay_chart.py`

```python
"""Score vs log₁₀(BTC) 오버레이 차트"""

def plot_score_vs_btc(
    score: pd.Series,       # 월간 score
    log_btc: pd.Series,     # log₁₀(BTC)
    lag: int = 5,           # 최적 lag
    save_path: str | None = None,
) -> None:
    """
    2-axis chart:
    - 좌축: Liquidity Score (blue)
    - 우축: log₁₀(BTC) (orange, lag만큼 좌로 시프트)
    - 상관계수 텍스트 표시
    - Phase 구간 음영 (하락기=red, 상승기=green)

    Optional: save_path 지정 시 PNG 저장
    """
```

### 6.2 `src/visualization/correlation_heatmap.py`

```python
"""교차상관 히트맵"""

def plot_cross_correlation(
    score: pd.Series,
    log_btc: pd.Series,
    max_lag: int = 12,
    save_path: str | None = None,
) -> None:
    """
    X축: lag (0-12개월)
    Y축: correlation
    Bar chart + 최적 lag 하이라이트
    """

def plot_variable_correlation_matrix(
    variables: pd.DataFrame,
    save_path: str | None = None,
) -> None:
    """
    변수 간 상관 행렬 히트맵.
    직교화 전/후 비교 가능.
    """
```

### 6.3 `src/visualization/walkforward_plot.py`

```python
"""Walk-Forward 결과 시각화"""

def plot_walk_forward(
    result: dict,  # WalkForwardValidator.validate() 결과
    save_path: str | None = None,
) -> None:
    """
    Subplot 1: 각 윈도우별 OOS corr (bar chart)
    Subplot 2: 누적 OOS score vs log₁₀(BTC) 오버레이
    Mean ± Std 표시
    """
```

---

## 7. CLI Interface — `main.py`

```python
"""
Finance Simulator CLI — BTC Liquidity Prediction Model v1.0.0

Usage:
    python main.py fetch         # 데이터 수집만
    python main.py calculate     # 수집 + 계산
    python main.py optimize      # 수집 + 계산 + Grid Search + Walk-Forward
    python main.py run           # 전체 파이프라인 (주간 실행용)
    python main.py score         # 저장된 가중치로 현재 Score만
    python main.py visualize     # 차트 생성
    python main.py status        # 최신 Score + 모델 상태 출력
"""

import argparse

def main():
    parser = argparse.ArgumentParser(description="BTC Liquidity Model v1.0.0")
    subparsers = parser.add_subparsers(dest="command")

    # fetch
    fetch_parser = subparsers.add_parser("fetch", help="Fetch all data sources")
    fetch_parser.add_argument("--no-cache", action="store_true")

    # calculate
    calc_parser = subparsers.add_parser("calculate", help="Fetch + Calculate variables")

    # optimize
    opt_parser = subparsers.add_parser("optimize", help="Full optimization (Grid Search + WF)")

    # run
    run_parser = subparsers.add_parser("run", help="Full pipeline (weekly)")

    # score
    score_parser = subparsers.add_parser("score", help="Current score with saved weights")

    # visualize
    viz_parser = subparsers.add_parser("visualize", help="Generate charts")
    viz_parser.add_argument("--type", choices=["overlay", "correlation", "walkforward", "all"],
                            default="all")

    # status
    status_parser = subparsers.add_parser("status", help="Show latest model status")

    args = parser.parse_args()
    # ... dispatch to PipelineRunner
```

---

## 8. Data Flow (상세)

```
                    FETCH PHASE
    ┌─────────────────────────────────────────┐
    │                                         │
    │  FRED API ──→ WALCL, RRP, SOFR, IORB   │
    │               M2(US,EU,CN,JP), HY_OAS   │
    │                                         │
    │  Treasury ──→ TGA (일간)                 │
    │                                         │
    │  yfinance ──→ DXY, BTC-USD, BTC=F       │
    │                                         │
    │  Fallback ──→ CoinGecko/Binance BTC     │
    │                                         │
    └──────────────────┬──────────────────────┘
                       │  raw DataFrames
                       ▼
                 CALCULATE PHASE
    ┌─────────────────────────────────────────┐
    │                                         │
    │  NL = WALCL - TGA - RRP   ──→ detrend  │──→ NL_level
    │                                         │
    │  GM2 = US+EU+CN+JP        ──→ detrend  │──→ GM2_level
    │    └→ orthogonalize(NL)   ──→          │──→ GM2_resid
    │                                         │
    │  SOFR - IORB > 20bps     ──→ binary    │──→ SOFR_bin
    │                                         │
    │  HY OAS                   ──→ detrend  │──→ HY_level
    │                                         │
    │  (futures-spot)/spot×ann  ──→ detrend   │──→ CME_basis
    │                                         │
    └──────────────────┬──────────────────────┘
                       │  5 detrended + z-scored variables
                       ▼
                 OPTIMIZE PHASE
    ┌─────────────────────────────────────────┐
    │                                         │
    │  Z-Matrix = [NL_z, GM2r_z, SOFR_z,     │
    │              HY_z, CME_z]               │
    │                                         │
    │  Grid Search:                           │
    │    score = Z @ weights                  │
    │    maximize corr(score(t), logBTC(t+k)) │
    │                                         │
    │  Walk-Forward:                          │
    │    8 windows × expanding train          │
    │    OOS corr validation                  │
    │                                         │
    └──────────────────┬──────────────────────┘
                       │  optimal weights + lag
                       ▼
                 SCORE PHASE
    ┌─────────────────────────────────────────┐
    │                                         │
    │  Final Score = w1×NL_z + w2×GM2r_z      │
    │              + w3×SOFR_z + w4×HY_z      │
    │              + w5×CME_z                  │
    │                                         │
    │  Signal: bullish / neutral / bearish    │
    │                                         │
    │  Store → JSON + SQLite                  │
    │  Visualize → PNG charts                 │
    │                                         │
    └─────────────────────────────────────────┘
```

---

## 9. Error Handling Strategy

| 상황 | 처리 |
|------|------|
| FRED API 키 없음 | 시작 시 체크, 명확한 에러 메시지 + 발급 가이드 URL |
| FRED Rate Limit (120/min) | `time.sleep(0.5)` 자동 throttle |
| FRED 시리즈 응답 없음 | 해당 변수 NaN 처리, 경고 로그 |
| Treasury API 다운 | 캐시된 TGA 사용, 경고 로그 |
| yfinance 실패 | CoinGecko → Binance fallback 체인 |
| CME 선물 NaN (2017.12 이전) | Grid Search에서 유효 기간만 사용 |
| GM2 래그 (최신 2-3개월) | 직전값 캐리포워드 |
| 직교화 후 corr != 0 | 소수점 오차 허용 (|corr| < 0.01) |
| Grid Search 0 결과 | 최소 1개 변수 활성 조건 강제 |
| Walk-Forward 윈도우 부족 | 최소 3개 윈도우 보장, 아니면 경고 |

### Logging Strategy

```python
# src/utils/logger.py
import logging

def setup_logger(name: str, level: str = "INFO") -> logging.Logger:
    """
    Format: [2026-03-01 10:30:00] [INFO] [fred_fetcher] Fetched WALCL: 120 rows
    File: data/logs/pipeline_{date}.log
    Console: 동시 출력
    """
```

---

## 10. EU M2 — FRED 대체 시리즈 조사

ECB SDW 대신 FRED에서 사용 가능한 유로존 M2 시리즈:

| FRED 시리즈 | 설명 | 주기 | 기간 |
|-------------|------|------|------|
| `MYAGM2EZM196N` | Euro Area M2 (Broad Money, NSA) | 월간 | 1980~ |
| `MANMM2EZM196N` | Euro Area M2 (NSA, Mil. EUR) | 월간 | 1980~ |

**최종 선택: `MABMM301EZM189S`** (Euro Area M3 Broad Money)

> **변경 사유**: `MYAGM2EZM196N` (M2)은 2017-03에 단종되어 15행만 사용 가능.
> `MABMM301EZM189S` (M3)는 ~2023-11까지 95행 제공. M3는 M2를 포함하는 상위 집계이므로
> 글로벌 유동성 추적 목적에는 유효. JP_M2도 동일 사유로 `MABMM301JPM189S` (M3)로 대체.
> CN_M2는 `MYAGM2CNM189N` 유지 (~2019-08 이후 carry-forward).

---

## 11. CME Basis 상세 계산 로직

### 만기일 결정
```
CME BTC Futures: 매월 마지막 금요일 만기
예: 2026-03 → 2026-03-27 (금)

last_friday = date의 월말에서 역순으로 첫 금요일
```

### 연율화 공식
```python
raw_basis_pct = (futures - spot) / spot * 100
days_to_expiry = (expiry_date - current_date).days
annualized_basis = raw_basis_pct * (365 / max(days_to_expiry, 1))
```

### 롤오버 처리
```
만기 7일 전부터: 다음 월물 가격 사용 (근월물 → 차월물 전환)
yfinance BTC=F: 자동 롤오버 (continuous contract)
→ 별도 롤오버 로직 불필요할 수 있으나, 가격 점프 모니터링 필요
```

### NaN 처리
```
2017-12 이전: CME BTC 선물 미존재 → NaN
Grid Search: CME_basis가 NaN인 기간은 해당 변수 가중치 0으로 처리
즉, 2017-12 이전은 4변수(NL, GM2r, SOFR, HY)로 평가
```

---

## 12. 구현 우선순위 (파일별)

### Priority 1 — 기초 인프라
| 순서 | 파일 | 설명 |
|------|------|------|
| 1 | `requirements.txt` | 의존성 정의 |
| 2 | `config/settings.py` | 환경 설정 |
| 3 | `config/constants.py` | 모델 상수 |
| 4 | `src/utils/logger.py` | 로깅 |
| 5 | `src/utils/date_utils.py` | 날짜 유틸 |

### Priority 2 — 데이터 수집
| 순서 | 파일 | 설명 |
|------|------|------|
| 6 | `src/fetchers/fred_fetcher.py` | FRED 전체 |
| 7 | `src/fetchers/treasury_fetcher.py` | TGA |
| 8 | `src/fetchers/market_fetcher.py` | yfinance |
| 9 | `src/fetchers/fallback_fetcher.py` | Fallback |

### Priority 3 — 계산 엔진
| 순서 | 파일 | 설명 |
|------|------|------|
| 10 | `src/calculators/detrend.py` | 공통 detrend + z-score |
| 11 | `src/calculators/net_liquidity.py` | NL |
| 12 | `src/calculators/global_m2.py` | GM2 + 직교화 |
| 13 | `src/calculators/sofr_binary.py` | SOFR |
| 14 | `src/calculators/hy_spread.py` | HY Spread |
| 15 | `src/calculators/cme_basis.py` | CME Basis |

### Priority 4 — 최적화
| 순서 | 파일 | 설명 |
|------|------|------|
| 16 | `src/optimizers/orthogonalize.py` | 직교화 |
| 17 | `src/optimizers/grid_search.py` | Grid Search |
| 18 | `src/optimizers/walk_forward.py` | Walk-Forward |

### Priority 5 — 파이프라인 + 출력
| 순서 | 파일 | 설명 |
|------|------|------|
| 19 | `src/pipeline/storage.py` | 저장 |
| 20 | `src/pipeline/runner.py` | 오케스트레이터 |
| 21 | `src/visualization/*.py` | 차트 3종 |
| 22 | `main.py` | CLI 진입점 |

---

## 13. 테스트 전략

### Unit Tests
```python
# tests/test_calculators.py
class TestDetrend:
    def test_12m_ma_basic(self):
        """알려진 입력 → 기대 출력 확인"""
    def test_warmup_nans(self):
        """처음 11개월은 NaN"""

class TestNetLiquidity:
    def test_nl_formula(self):
        """NL = WALCL - TGA - RRP 검증"""

class TestOrthogonalize:
    def test_zero_correlation(self):
        """직교화 후 상관 ≈ 0"""
```

### Integration Tests
```python
# tests/test_pipeline.py
class TestPipeline:
    def test_full_run_with_mock(self):
        """Mock API → 전체 파이프라인 → Score 출력 확인"""
    def test_score_only_mode(self):
        """저장된 가중치로 Score 계산"""
```

---

## References
- Plan: `docs/01-plan/features/btc-liquidity-model.plan.md`
- Original Context: `CLAUDE_PROJECT_CONTEXT.md`
- Data Pipeline: `v3_data_pipeline_plan.md`
