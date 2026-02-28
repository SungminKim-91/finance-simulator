# Design: BTC Liquidity Prediction Model v2.0.0

> Feature: btc-liquidity-v2
> Created: 2026-03-01
> Status: Draft
> PDCA Phase: Design
> Based on: [v2.0 Plan](../../01-plan/features/btc-liquidity-v2.plan.md) + [v1.0 Design](./btc-liquidity-model.design.md)

---

## 1. Architecture Overview

### 1.1 v1.0 → v2.0 아키텍처 변화

```
v1.0.0 Architecture (Grid Search 기반)
──────────────────────────────────────
  Fetchers → Calculators → Z-score → Grid Search → Walk-Forward → Score
                                       ↑ BTC 참조 (과적합)

v2.0.0 Architecture (3-Stage 파이프라인)
──────────────────────────────────────
  Fetchers → Calculators → [Stage 1: BTC-blind Index] → [Stage 2: Direction Validation] → [Stage 3: Robustness]
                            ↑ BTC 절대 불참조              ↑ 여기서만 BTC 참조           ↑ 과적합 방지
```

### 1.2 전체 아키텍처 다이어그램

```
┌───────────────────────────────────────────────────────────────────────────┐
│                          main.py (CLI v2.0)                               │
│  Commands: fetch / build-index / validate / analyze / run / visualize     │
│  Options: --freq daily|weekly|monthly  --method pca|ica|dfm|sparse       │
└──────────┬────────────────────────────────────────────────────────────────┘
           │
           ▼
┌───────────────────────────────────────────────────────────────────────────┐
│                     pipeline/runner_v2.py                                  │
│  Orchestrates: Fetch → Calculate → Stage1 → Stage2 → Stage3 → Store      │
└──────┬──────────┬──────────┬──────────┬──────────┬──────────┬─────────────┘
       │          │          │          │          │          │
       ▼          ▼          ▼          ▼          ▼          ▼
  ┌─────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐
  │Fetchers │ │Calcs   │ │ Index    │ │Validators│ │Robustness│ │Storage  │
  │ (기존)  │ │(수정)  │ │ Builders │ │ (검증)   │ │ (방지)   │ │Viz(수정)│
  └─────────┘ └────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────┘
       │
       ▼
  ┌──────────────────────────┐
  │  data/raw/     (캐시)     │
  │  data/processed/ (일별)   │
  │  data/indices/   (인덱스) │  ★ NEW
  │  data/validation/(검증)   │  ★ NEW
  │  data/scores/   (결과)    │
  └──────────────────────────┘
```

### 1.3 모듈 변경 요약

| 모듈 | v1.0 파일 수 | v2.0 파일 수 | 변경 |
|------|:----------:|:----------:|------|
| config/ | 2 | 2 | 수정 (DATA_END 동적, v2 파라미터) |
| src/fetchers/ | 4 | 4 | 유지 (변경 없음) |
| src/calculators/ | 6 | 7 | +1 (sofr_smooth.py), sofr_binary.py deprecated |
| **src/index_builders/** | 0 | **5** | **신규** (PCA, ICA, DFM, SparsePCA) |
| **src/validators/** | 0 | **5** | **신규** (MDA, SBD, Wavelet, Granger, CWS) |
| **src/robustness/** | 0 | **4** | **신규** (Bootstrap, CPCV, Deflated) |
| src/optimizers/ | 3 | 3 | grid_search.py deprecated, 나머지 유지 |
| src/pipeline/ | 2 | 3 | +1 (runner_v2.py) |
| src/visualization/ | 3 | 5 | +2 (wavelet, bootstrap plots) |
| src/utils/ | 2 | 2 | 유지 |
| **합계** | **22** | **36** | **+14 신규** |

---

## 2. Module Design — Config 수정

### 2.1 `config/settings.py` — 변경사항

```python
"""v2.0 환경 설정 — DATA_END 동적화 + freq 옵션"""
from dotenv import load_dotenv
from datetime import datetime
import os

load_dotenv()

# API Keys
FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")

# Data Range
DATA_START: str = "2016-01-01"
DATA_END: str = datetime.now().strftime("%Y-%m-%d")  # ★ 동적화 (v1.0: "2025-12-31" 고정)
WARMUP_MONTHS: int = 12
EFFECTIVE_START: str = "2017-01-01"

# Frequency (v2.0 추가)
DEFAULT_FREQ: str = "monthly"  # "daily" | "weekly" | "monthly"

# Paths (v2.0 추가)
DATA_DIR: str = "data"
RAW_DIR: str = f"{DATA_DIR}/raw"
PROCESSED_DIR: str = f"{DATA_DIR}/processed"
INDICES_DIR: str = f"{DATA_DIR}/indices"        # ★ NEW
VALIDATION_DIR: str = f"{DATA_DIR}/validation"  # ★ NEW
SCORES_DIR: str = f"{DATA_DIR}/scores"
LOG_DIR: str = f"{DATA_DIR}/logs"
CHARTS_DIR: str = f"{DATA_DIR}/charts"

# Cache
CACHE_EXPIRY_HOURS: int = 24
```

### 2.2 `config/constants.py` — v2.0 파라미터 추가

```python
"""v2.0 모델 상수 — 기존 유지 + v2.0 추가"""

# ===== v1.0 기존 상수 유지 (FRED_SERIES, TICKERS 등) =====
# ... (변경 없음)

# ===== v2.0 추가 =====

# SOFR Smooth Transition (Phase 1: Logistic)
SOFR_LOGISTIC = {
    "gamma": 0.2,           # 전환 기울기 (0.1=완만, 0.5=급격)
    "threshold_bps": 20,    # 중심점 (v1.0 binary threshold과 동일)
}

# SOFR Markov Regime (Phase 2: 고급)
SOFR_MARKOV = {
    "k_regimes": 2,         # 정상/위기
    "order": 1,             # AR(1) within regime
}

# PCA/ICA 설정
INDEX_BUILDER = {
    "n_components": 1,       # 1차 팩터만 추출 (기본)
    "max_components": 3,     # ICA 비교 시 최대 3개
    "random_state": 42,
    "sparse_alpha": 1.0,     # Sparse PCA L1 페널티
}

# DFM (Dynamic Factor Model) 설정
DFM_CONFIG = {
    "k_factors": 1,          # 공통 팩터 수
    "factor_order": 2,       # VAR(2) 팩터 동학
    "max_iter": 500,         # EM 최대 반복
    "tolerance": 1e-6,
}

# 방향성 검증 메트릭
WAVEFORM_WEIGHTS = {
    "MDA": 0.4,              # Sign Concordance Rate
    "SBD": 0.3,              # Shape-Based Distance (1-SBD)
    "CosSim": 0.2,           # Cosine Similarity on derivatives
    "Tau": 0.1,              # Kendall Tau
}

# Cross-Correlation 설정
XCORR_CONFIG = {
    "max_lag": 15,           # 최대 lag (개월)
    "min_lag": 0,
}

# Bootstrap 설정
BOOTSTRAP_CONFIG = {
    "n_bootstraps": 1000,
    "block_length": 12,      # 12개월 블록 (연간 계절성 보존)
    "confidence_level": 0.95,
}

# CPCV 설정
CPCV_CONFIG = {
    "n_folds": 10,
    "n_test_folds": 2,       # C(10,2) = 45 paths
    "purge_threshold": 9,    # 9개월 (lag 길이)
    "embargo": 2,
}

# Granger Causality
GRANGER_CONFIG = {
    "max_lag": 12,
    "alpha": 0.05,           # 유의수준
}

# 성공 기준
SUCCESS_CRITERIA = {
    "min_mda": 0.60,                  # 방향 일치율 60%+
    "all_lag_positive": True,          # 모든 lag에서 r > 0
    "bootstrap_ci_excludes_zero": True, # 95% CI가 0 포함 안함
    "granger_p_value": 0.05,          # Index→BTC p < 0.05
    "min_cpcv_mean": 0.15,            # CPCV 평균 OOS > 0.15
}
```

---

## 3. Module Design — Calculators 수정

### 3.1 `src/calculators/sofr_smooth.py` — ★ NEW

```python
"""SOFR Smooth Transition — Binary(v1.0) → 연속 확률(v2.0)"""
import numpy as np
import pandas as pd
from config.constants import SOFR_LOGISTIC, SOFR_MARKOV

class SofrSmoothCalculator:
    """
    v1.0의 binary(0/1)를 연속 확률(0~1)로 대체.
    Phase 1: Logistic smoothing (즉시 구현)
    Phase 2: Markov Regime-Switching (고급)
    """

    def calculate_logistic(
        self,
        sofr: pd.DataFrame,   # [date, value] 일별
        iorb: pd.DataFrame,   # [date, value] 일별
        gamma: float = SOFR_LOGISTIC["gamma"],
        threshold: float = SOFR_LOGISTIC["threshold_bps"],
    ) -> pd.DataFrame:
        """
        Logistic smoothing:
          spread = (SOFR - IORB) × 10000  (bps 변환)
          P(crisis) = 1 / (1 + exp(-gamma × (spread - threshold)))

        gamma 해석:
          - 0.1: 매우 완만 (spread 0~40bps 전체가 0.3~0.7)
          - 0.2: 기본값 (spread 10~30bps 전환구간)
          - 0.5: 급격 (거의 binary에 가까움)

        Returns: DataFrame[date, sofr_spread_bps, sofr_smooth]
          - sofr_smooth: 0~1 연속값 (1에 가까울수록 위기)

        Edge cases:
          - 2018-04 이전 SOFR 없음 → 0.0 (정상 상태)
          - IORB 2021-07 이전 → IOER 시리즈 사용
        """

    def calculate_markov(
        self,
        sofr: pd.DataFrame,
        iorb: pd.DataFrame,
        k_regimes: int = SOFR_MARKOV["k_regimes"],
    ) -> pd.DataFrame:
        """
        Markov Regime-Switching:
          P(crisis_t | data) via statsmodels.tsa.regime_switching.markov_regression

        Returns: DataFrame[date, sofr_spread_bps, regime_prob, regime_label]
          - regime_prob: P(crisis) 0~1
          - regime_label: "normal" | "crisis"

        주의:
          - 수렴 실패 시 Logistic fallback
          - EM 알고리즘 초기값 민감 → 3번 시도 (다른 random seed)
        """

    def resample_to_freq(
        self,
        smooth_daily: pd.DataFrame,
        freq: str = "monthly",
    ) -> pd.DataFrame:
        """
        일별 smooth 값 → 원하는 빈도로 집계.
        monthly: 월평균, weekly: 주평균, daily: 그대로
        """
```

### 3.2 기존 Calculator 변경 없음

- `detrend.py`: 그대로 유지 (12m MA detrend + z-score)
- `net_liquidity.py`: 그대로 유지
- `global_m2.py`: 그대로 유지
- `hy_spread.py`: 그대로 유지
- `cme_basis.py`: 그대로 유지
- `sofr_binary.py`: **deprecated** (v1.0 호환용 유지, 실제 사용 안함)

---

## 4. Module Design — Index Builders (★ NEW)

### 4.1 `src/index_builders/__init__.py`

```python
"""
독립 인덱스 구성 모듈 — BTC-blind
Stage 1 of v2.0 3-Stage Pipeline

핵심 원칙:
  - 이 모듈의 어떤 함수도 BTC 데이터를 입력받지 않음
  - 5개 유동성 변수의 공분산 구조에서만 인덱스 도출
  - 가중치는 데이터가 결정, 인간이 결정하지 않음
"""

from .pca_builder import PCAIndexBuilder
from .ica_builder import ICAIndexBuilder
from .dfm_builder import DFMIndexBuilder
from .sparse_pca_builder import SparsePCAIndexBuilder
```

### 4.2 `src/index_builders/pca_builder.py` — Primary

```python
"""PCA 기반 독립 인덱스 구성 — Phase 1c 검증됨"""
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from config.constants import INDEX_BUILDER

class PCAIndexBuilder:
    """
    Phase 1c에서 검증: BTC-blind PC1이 lag=7에서 r=0.318, 모든 lag 양의 상관.
    v2.0의 기본(primary) 인덱스 구성 방법.
    """

    def __init__(
        self,
        n_components: int = INDEX_BUILDER["n_components"],
        random_state: int = INDEX_BUILDER["random_state"],
    ):
        """
        Args:
            n_components: 추출할 주성분 수 (기본 1)
            random_state: 재현성 보장
        """
        self.pca = PCA(n_components=n_components, random_state=random_state)
        self.is_fitted = False

    def build(
        self,
        z_matrix: pd.DataFrame,
    ) -> dict:
        """
        z_matrix에서 PC1 인덱스 구성.

        Args:
            z_matrix: DataFrame[date, NL_z, GM2r_z, SOFR_z, HY_z, CME_z]
                      - 모든 변수는 detrend + z-score 완료 상태
                      - NaN 행은 사전 제거 필요

        Returns: {
            "index": pd.Series,           # PC1 시계열 (T,)
            "loadings": dict[str, float],  # {"NL_z": 0.55, "GM2r_z": 0.12, ...}
            "explained_variance": float,   # 설명된 분산 비율
            "n_observations": int,
            "method": "PCA",
        }

        검증 체크:
          - loadings 합이 대략 1에 가까운지
          - NL_z의 loading이 최대인지 (이론 기대)
          - explained_variance > 0.3 (5변수 중 1개가 30%+ 설명)
        """

    def transform(
        self,
        z_matrix: pd.DataFrame,
    ) -> pd.Series:
        """
        이미 fit된 PCA로 새 데이터 변환 (주간 업데이트용).

        Args:
            z_matrix: fit 시와 동일한 변수 순서

        Returns: PC1 시계열

        주의: is_fitted=False이면 ValueError
        """

    def get_loadings_dict(self) -> dict[str, float]:
        """
        현재 fitted PCA의 loading을 변수명 dict로 반환.
        Returns: {"NL_z": 0.55, "GM2r_z": 0.12, ...}
        """

    def sign_correction(
        self,
        index: pd.Series,
        nl_series: pd.Series,
    ) -> pd.Series:
        """
        PC1 부호 보정: NL과 양의 상관이 되도록 부호 결정.
        PCA는 부호가 임의 → NL과 같은 방향 보장.

        Args:
            index: PC1 시계열
            nl_series: NL_z 시계열 (부호 기준)

        Returns: 부호 보정된 PC1

        로직: corr(index, nl_series) < 0 이면 index × (-1)
        """
```

### 4.3 `src/index_builders/ica_builder.py` — Comparison

```python
"""ICA 기반 독립 인덱스 구성 — PCA 비교용"""
import numpy as np
import pandas as pd
from sklearn.decomposition import FastICA
from config.constants import INDEX_BUILDER

class ICAIndexBuilder:
    """
    ICA: 통계적 독립 성분 분리.
    금융 데이터는 fat-tailed → ICA가 이론적으로 적합할 수 있음.
    PCA 결과와 비교하여 더 나은 방향 일치를 보이면 채택.
    """

    def __init__(
        self,
        n_components: int = INDEX_BUILDER["max_components"],
        random_state: int = INDEX_BUILDER["random_state"],
    ):
        """
        Args:
            n_components: 추출할 IC 수 (기본 3, 경제적 해석 후 1개 선택)
        """
        self.ica = FastICA(
            n_components=n_components,
            random_state=random_state,
            max_iter=500,
            tol=1e-4,
        )

    def build(
        self,
        z_matrix: pd.DataFrame,
    ) -> dict:
        """
        z_matrix에서 IC 추출.

        Returns: {
            "components": pd.DataFrame,    # (T, n_components) 모든 IC
            "index": pd.Series,            # 선택된 "유동성 IC" 1개
            "selected_ic": int,            # 선택된 IC 번호
            "mixing_matrix": np.ndarray,   # 혼합 행렬 (해석용)
            "method": "ICA",
        }

        IC 선택 기준 (BTC 참조 없이):
          1. NL_z와 가장 높은 |상관|을 보이는 IC 선택
          2. 이유: NL은 유동성의 핵심 → 유동성 IC는 NL과 가장 연결됨
          3. 부호 보정: NL과 양의 상관으로 맞춤
        """

    def select_liquidity_ic(
        self,
        components: pd.DataFrame,
        nl_series: pd.Series,
    ) -> tuple[pd.Series, int]:
        """
        NL과 가장 높은 |corr|을 가진 IC를 "유동성 IC"로 선택.

        Args:
            components: 모든 IC (T, n_components)
            nl_series: NL_z 시계열

        Returns: (selected_ic_series, ic_index)

        주의: BTC를 절대 참조하지 않음. NL은 이론적 기준.
        """
```

### 4.4 `src/index_builders/dfm_builder.py` — Mixed-Frequency

```python
"""DFM(Dynamic Factor Model) — 혼합 주기 인덱스 구성"""
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.dynamic_factor import DynamicFactor
from config.constants import DFM_CONFIG

class DFMIndexBuilder:
    """
    일/주/월 혼합 주기 데이터를 통합하는 Dynamic Factor Model.
    칼만 필터로 결측치(NaN) 최적 보간.
    """

    def __init__(
        self,
        k_factors: int = DFM_CONFIG["k_factors"],
        factor_order: int = DFM_CONFIG["factor_order"],
    ):
        """
        Args:
            k_factors: 공통 팩터 수 (기본 1)
            factor_order: 팩터 VAR 차수 (기본 2)
        """
        self.k_factors = k_factors
        self.factor_order = factor_order
        self.model = None
        self.result = None

    def build(
        self,
        daily_matrix: pd.DataFrame,
    ) -> dict:
        """
        일별 격자(NaN 포함) 데이터에서 공통 팩터 추출.

        Args:
            daily_matrix: DataFrame[date(daily), NL, GM2r, SOFR, HY, CME]
                          - 일별 격자에 배치된 모든 변수
                          - 관측 없는 날 = NaN (칼만 필터가 보간)
                          - 월별 M2: 발표일만 값, 나머지 NaN

        Returns: {
            "daily_factor": pd.Series,        # 매일 업데이트되는 팩터 (T_daily,)
            "filtered_factor": pd.Series,     # 칼만 필터 기반 (실시간)
            "smoothed_factor": pd.Series,     # RTS 스무더 기반 (사후 분석)
            "factor_loadings": dict[str, float],
            "log_likelihood": float,
            "aic": float,
            "bic": float,
            "method": "DFM",
        }

        주의:
          - 수렴 실패 시 max_iter 증가 → 여전히 실패 시 PCA fallback
          - 초기값 민감 → EM 알고리즘 기본 사용
          - 일별 데이터가 매우 클 수 있음 (3000+ 행) → 메모리 주의
        """

    def resample_to_freq(
        self,
        daily_factor: pd.Series,
        freq: str = "monthly",
    ) -> pd.Series:
        """
        일별 팩터를 원하는 빈도로 리샘플링.

        Args:
            freq: "daily" (그대로), "weekly" (주말 값), "monthly" (월말 값)

        Returns: 리샘플링된 팩터 시계열
        """

    def prepare_daily_matrix(
        self,
        variables: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        """
        혼합 빈도 변수들을 일별 격자에 배치.

        Args:
            variables: {
                "NL": daily_df,          # 일별 (WALCL 보간)
                "GM2r": monthly_df,      # 발표일만 값
                "SOFR_smooth": daily_df, # 일별
                "HY": monthly_df,        # 발표일만 값
                "CME": daily_df,         # 일별
            }

        Returns: DataFrame[date(daily_index), NL, GM2r, SOFR, HY, CME]
                 - 관측 없는 셀 = NaN

        로직:
          1. 전체 기간의 business day 인덱스 생성
          2. 각 변수를 해당 인덱스에 reindex (없는 날 NaN)
          3. 월별 변수: 발표일(보통 월말)에만 값 배치
        """
```

### 4.5 `src/index_builders/sparse_pca_builder.py` — Variable Selection

```python
"""Sparse PCA — 자동 변수 선택"""
import numpy as np
import pandas as pd
from sklearn.decomposition import SparsePCA
from config.constants import INDEX_BUILDER

class SparsePCAIndexBuilder:
    """
    L1 정규화로 중요하지 않은 변수의 loading = 0.
    v1.0.0에서 GM2=0, CME=0이 나온 결과를 비지도로 검증.
    """

    def __init__(
        self,
        n_components: int = INDEX_BUILDER["n_components"],
        alpha: float = INDEX_BUILDER["sparse_alpha"],
        random_state: int = INDEX_BUILDER["random_state"],
    ):
        self.spca = SparsePCA(
            n_components=n_components,
            alpha=alpha,
            random_state=random_state,
            max_iter=500,
        )

    def build(
        self,
        z_matrix: pd.DataFrame,
    ) -> dict:
        """
        Returns: {
            "index": pd.Series,
            "loadings": dict[str, float],
            "nonzero_variables": list[str],  # loading != 0인 변수 목록
            "sparsity": float,               # 0인 loading 비율
            "method": "SparsePCA",
        }

        분석:
          - nonzero_variables에 NL이 반드시 포함되어야 함
          - GM2, CME가 0이면 v1.0.0 결과와 일치 (비지도 검증)
          - alpha 값에 따라 sparsity 조절 가능
        """

    def alpha_sensitivity(
        self,
        z_matrix: pd.DataFrame,
        alphas: list[float] = [0.1, 0.5, 1.0, 2.0, 5.0],
    ) -> pd.DataFrame:
        """
        다양한 alpha에서 loading 변화 분석.

        Returns: DataFrame[alpha, NL_z, GM2r_z, SOFR_z, HY_z, CME_z]
                 각 셀은 loading 값 (0이면 해당 변수 제외됨)
        """
```

---

## 5. Module Design — Validators (★ NEW)

### 5.1 `src/validators/__init__.py`

```python
"""
방향성 검증 모듈 — Stage 2
여기서만 BTC 데이터를 참조하여 인덱스 품질을 평가.
"""

from .waveform_metrics import WaveformMetrics
from .wavelet_coherence import WaveletCoherenceAnalyzer
from .granger_test import GrangerCausalityTest
from .composite_score import CompositeWaveformScore
```

### 5.2 `src/validators/waveform_metrics.py`

```python
"""방향성 메트릭: MDA, SBD, Cosine Similarity, Kendall Tau"""
import numpy as np
import pandas as pd
from scipy.stats import kendalltau
from tslearn.metrics import dtw as tslearn_dtw

class WaveformMetrics:
    """
    인덱스와 log₁₀(BTC)의 방향 일치도를 다각도로 측정.
    """

    @staticmethod
    def mda(
        index: pd.Series,
        target: pd.Series,
        lag: int = 0,
    ) -> float:
        """
        Mean Directional Accuracy (Sign Concordance Rate).

        MDA = (1/T) × Σ 𝟙[sign(Δindex_t) == sign(Δtarget_{t+lag})]

        Args:
            index: 유동성 인덱스 (Stage 1 출력)
            target: log₁₀(BTC)
            lag: 시프트 (0=동시, 7=7개월 선행)

        Returns: 0.0~1.0 (0.5=랜덤, 1.0=완벽 방향 일치)

        주의:
          - diff() 후 부호 비교 → T-1개 비교점
          - lag > 0: index가 target을 선행
          - 동일 부호(둘 다 0 포함) 시 일치로 간주
        """

    @staticmethod
    def sbd(
        index: pd.Series,
        target: pd.Series,
        lag: int = 0,
    ) -> float:
        """
        Shape-Based Distance.
        교차상관 기반 형태 유사도 — 진폭 무시, 형태만 비교.

        SBD = 1 - max_s(NCC(index, shift(target, s)))

        Args:
            index, target: 시계열
            lag: 사전 시프트 적용

        Returns: 0.0~2.0 (0=동일 형태, 2=완전 반대)
        """

    @staticmethod
    def cosine_similarity_derivatives(
        index: pd.Series,
        target: pd.Series,
        lag: int = 0,
    ) -> float:
        """
        변화율 벡터의 코사인 유사도.

        cos_sim = (Δindex · Δtarget) / (|Δindex| × |Δtarget|)

        Args:
            index, target: 원본 시계열 (diff는 내부 수행)
            lag: 시프트

        Returns: -1.0~1.0 (1=같은 방향, -1=반대 방향)
        """

    @staticmethod
    def kendall_tau(
        index: pd.Series,
        target: pd.Series,
        lag: int = 0,
    ) -> tuple[float, float]:
        """
        Kendall Tau 순위 상관.
        이상치에 강건, 비선형 단조 관계 포착.

        Returns: (tau, p_value)
          - tau: -1~1
          - p_value: 유의수준 검정
        """

    def cross_correlation_profile(
        self,
        index: pd.Series,
        target: pd.Series,
        max_lag: int = 15,
    ) -> pd.DataFrame:
        """
        lag=0~max_lag에서 모든 메트릭 동시 계산.

        Returns: DataFrame[lag, pearson_r, mda, sbd, cosine_sim, kendall_tau, kendall_p]

        성공 기준 확인:
          - 모든 lag에서 pearson_r > 0 → all_positive
          - 형태: smooth hill (0에서 시작, 피크 후 감소)
        """
```

### 5.3 `src/validators/wavelet_coherence.py`

```python
"""Wavelet Coherence — 시간-주파수 방향 분석"""
import numpy as np
import pandas as pd
import pycwt

class WaveletCoherenceAnalyzer:
    """
    시간-주파수 영역에서 인덱스와 BTC의 관계를 분석.
    "어떤 주기(frequency)에서 선행(lead)하는가?"
    """

    def analyze(
        self,
        index: pd.Series,
        target: pd.Series,
        dt: float = 1.0,
    ) -> dict:
        """
        Wavelet coherence 계산.

        Args:
            index: 유동성 인덱스
            target: log₁₀(BTC)
            dt: 시간 간격 (1.0 = 1개월)

        Returns: {
            "coherence": np.ndarray,       # (freq, time) WCT
            "phase": np.ndarray,           # (freq, time) 위상
            "coi": np.ndarray,             # Cone of Influence
            "freqs": np.ndarray,           # 주파수 축
            "significance": np.ndarray,    # 95% 유의수준
            "dominant_period": float,      # 최대 coherence 주기 (개월)
            "mean_phase_lag": float,       # 평균 위상 지연 (개월)
        }

        해석:
          - coherence > 0.5 & significance 통과 → 유의미한 관계
          - phase arrows → 0°=동시, 90°=index 선행 1/4주기
          - dominant_period=24m이면 "2년 주기에서 관계가 강함"
        """

    def plot_coherence(
        self,
        result: dict,
        save_path: str | None = None,
    ) -> None:
        """
        Wavelet coherence contour plot + phase arrows.
        COI 외부는 음영 처리.
        """
```

### 5.4 `src/validators/granger_test.py`

```python
"""Granger Causality — 단방향 인과 검정"""
import pandas as pd
from statsmodels.tsa.stattools import grangercausalitytests
from config.constants import GRANGER_CONFIG

class GrangerCausalityTest:
    """
    인덱스가 BTC를 Granger-cause 하는지 검정.
    역방향(BTC→Index)은 기각되어야 함.
    """

    def test_bidirectional(
        self,
        index: pd.Series,
        target: pd.Series,
        max_lag: int = GRANGER_CONFIG["max_lag"],
    ) -> dict:
        """
        양방향 Granger 인과 검정.

        Returns: {
            "forward": {                    # Index → BTC
                "lag_results": {1: p_val, 2: p_val, ...},
                "best_lag": int,
                "best_p_value": float,
                "significant": bool,        # p < alpha
            },
            "reverse": {                    # BTC → Index (기각 기대)
                "lag_results": {1: p_val, 2: p_val, ...},
                "best_lag": int,
                "best_p_value": float,
                "significant": bool,
            },
            "unidirectional": bool,         # forward ✓ AND reverse ✗
        }

        성공 기준:
          - forward.significant = True (Index가 BTC를 예측)
          - reverse.significant = False (BTC가 Index를 예측 안함)
          - unidirectional = True
        """

    def stationarity_check(
        self,
        series: pd.Series,
    ) -> dict:
        """
        ADF test로 정상성 확인 (Granger 전제조건).

        Returns: {"adf_stat": float, "p_value": float, "stationary": bool}

        주의: 비정상이면 차분 후 재검정 권고
        """
```

### 5.5 `src/validators/composite_score.py`

```python
"""Composite Waveform Score (CWS) — 복합 방향 점수"""
import pandas as pd
from config.constants import WAVEFORM_WEIGHTS
from .waveform_metrics import WaveformMetrics

class CompositeWaveformScore:
    """
    CWS = 0.4×MDA + 0.3×(1-SBD) + 0.2×CosSim + 0.1×Tau

    4개 메트릭을 가중 합산하여 단일 점수로 평가.
    """

    def __init__(
        self,
        weights: dict = WAVEFORM_WEIGHTS,
    ):
        self.weights = weights
        self.metrics = WaveformMetrics()

    def calculate(
        self,
        index: pd.Series,
        target: pd.Series,
        lag: int,
    ) -> dict:
        """
        특정 lag에서 CWS 계산.

        Returns: {
            "cws": float,            # 0~1 (높을수록 좋음)
            "mda": float,
            "sbd": float,
            "cosine_sim": float,
            "kendall_tau": float,
            "kendall_p": float,
            "lag": int,
        }
        """

    def optimal_lag(
        self,
        index: pd.Series,
        target: pd.Series,
        max_lag: int = 15,
    ) -> dict:
        """
        모든 lag에서 CWS를 계산하여 최적 lag 탐색.

        Returns: {
            "optimal_lag": int,
            "best_cws": float,
            "profile": pd.DataFrame,  # [lag, cws, mda, sbd, cos, tau]
        }
        """

    def compare_methods(
        self,
        indices: dict[str, pd.Series],
        target: pd.Series,
    ) -> pd.DataFrame:
        """
        PCA, ICA, DFM, SparsePCA 인덱스를 CWS로 비교.

        Args:
            indices: {"PCA": series, "ICA": series, "DFM": series, "SparsePCA": series}
            target: log₁₀(BTC)

        Returns: DataFrame[method, optimal_lag, best_cws, mda, sbd, cos, tau]
                 CWS 기준 정렬
        """
```

---

## 6. Module Design — Robustness (★ NEW)

### 6.1 `src/robustness/__init__.py`

```python
"""
과적합 방지 모듈 — Stage 3
통계적 검정으로 결과의 신뢰성 확인.
"""

from .bootstrap_analysis import BootstrapAnalyzer
from .cpcv import CPCVValidator
from .deflated_test import DeflatedTest
```

### 6.2 `src/robustness/bootstrap_analysis.py`

```python
"""Block Bootstrap 안정성 분석"""
import numpy as np
import pandas as pd
from tsbootstrap import MovingBlockBootstrap
from config.constants import BOOTSTRAP_CONFIG

class BootstrapAnalyzer:
    """
    PC1 loadings, 최적 lag, MDA의 통계적 안정성을 Bootstrap으로 검증.
    """

    def __init__(
        self,
        n_bootstraps: int = BOOTSTRAP_CONFIG["n_bootstraps"],
        block_length: int = BOOTSTRAP_CONFIG["block_length"],
        confidence_level: float = BOOTSTRAP_CONFIG["confidence_level"],
    ):
        self.n_bootstraps = n_bootstraps
        self.block_length = block_length
        self.confidence_level = confidence_level

    def loading_stability(
        self,
        z_matrix: pd.DataFrame,
        builder_class: type,
    ) -> dict:
        """
        Bootstrap으로 PC1 loadings의 95% CI 계산.

        Algorithm:
          for b in range(n_bootstraps):
              z_boot = block_bootstrap(z_matrix)
              builder = builder_class()
              result = builder.build(z_boot)
              loading_samples[b] = result["loadings"]

        Returns: {
            "mean_loadings": dict[str, float],
            "ci_lower": dict[str, float],     # 2.5 percentile
            "ci_upper": dict[str, float],     # 97.5 percentile
            "nl_always_max": bool,             # NL이 항상 최대 loading
            "ci_excludes_zero": dict[str, bool], # 각 변수 CI가 0 포함 여부
            "samples": np.ndarray,             # (n_bootstraps, n_vars)
        }

        성공 기준:
          - nl_always_max = True
          - NL의 ci_excludes_zero = True
        """

    def lag_distribution(
        self,
        z_matrix: pd.DataFrame,
        target: pd.Series,
        builder_class: type,
        scorer: "CompositeWaveformScore",
    ) -> dict:
        """
        Bootstrap으로 최적 lag의 분포 분석.

        Returns: {
            "mean_lag": float,
            "median_lag": float,
            "mode_lag": int,
            "ci_lower": float,
            "ci_upper": float,
            "distribution": np.ndarray,  # (n_bootstraps,)
        }
        """

    def mda_significance(
        self,
        mda_value: float,
        n_observations: int,
    ) -> dict:
        """
        MDA의 통계적 유의성 — Binomial test.

        H0: MDA = 0.5 (방향 일치는 랜덤)
        H1: MDA > 0.5 (방향 일치가 유의미)

        Returns: {
            "mda": float,
            "p_value": float,           # binomial test p
            "significant": bool,        # p < 0.05
            "n_observations": int,
        }
        """
```

### 6.3 `src/robustness/cpcv.py`

```python
"""Combinatorial Purged Cross-Validation (CPCV)"""
import numpy as np
import pandas as pd
from config.constants import CPCV_CONFIG

class CPCVValidator:
    """
    de Prado (2018) CPCV — 45-path validation.
    v1.0.0 Walk-Forward (9경로) 대비 5배 강건.
    """

    def __init__(
        self,
        n_folds: int = CPCV_CONFIG["n_folds"],
        n_test_folds: int = CPCV_CONFIG["n_test_folds"],
        purge_threshold: int = CPCV_CONFIG["purge_threshold"],
        embargo: int = CPCV_CONFIG["embargo"],
    ):
        """
        C(10,2) = 45 train-test splits.
        purge: 테스트 전후 9개월 제거 (lag 길이).
        embargo: 추가 2개월 안전 마진.
        """

    def validate(
        self,
        z_matrix: pd.DataFrame,
        target: pd.Series,
        builder_class: type,
        scorer: "CompositeWaveformScore",
    ) -> dict:
        """
        45-path CPCV 수행.

        Algorithm:
          for each (train_folds, test_folds) in C(10,2):
              # Purge: 테스트 시작 전 purge_threshold개월 제거
              # Embargo: 테스트 종료 후 embargo개월 제거
              builder.build(z_matrix[train_idx])
              index_oos = builder.transform(z_matrix[test_idx])
              cws = scorer.calculate(index_oos, target[test_idx])
              results.append(cws)

        Returns: {
            "n_paths": 45,
            "cws_mean": float,
            "cws_std": float,
            "cws_all": list[float],       # 45개 CWS
            "mda_mean": float,
            "all_positive_rate": float,    # r>0인 경로 비율
            "worst_path": dict,
            "best_path": dict,
        }

        주의:
          - skfolio 사용 시: CombinatorialPurgedCV 직접 호출
          - skfolio 미설치 시: 자체 구현 fallback
        """

    def _generate_splits(
        self,
        n_samples: int,
    ) -> list[tuple[np.ndarray, np.ndarray]]:
        """
        C(n_folds, n_test_folds) 조합에서 purge+embargo 적용한 인덱스 생성.

        Returns: [(train_idx, test_idx), ...] × 45개
        """
```

### 6.4 `src/robustness/deflated_test.py`

```python
"""다중 비교 보정 — Deflated Sharpe Ratio 아이디어 적용"""
import numpy as np
from scipy.stats import norm

class DeflatedTest:
    """
    여러 방법(PCA, ICA, DFM, SparsePCA)을 시도할 때
    최고 결과가 우연인지 검정.
    """

    def deflated_cws(
        self,
        cws_values: list[float],
        n_methods: int,
        n_observations: int,
    ) -> dict:
        """
        Multiple testing correction for CWS.

        Bailey & de Prado (2014) Deflated Sharpe Ratio 원리 적용:
          - n_methods개 방법을 시도한 후 최고 CWS 선택
          - 이 최고 CWS가 우연이 아닌지 보정

        Returns: {
            "best_cws": float,
            "deflated_cws": float,      # 보정된 CWS
            "p_value": float,
            "significant": bool,
            "n_methods_tried": int,
        }
        """
```

---

## 7. Module Design — Pipeline 수정

### 7.1 `src/pipeline/runner_v2.py` — ★ NEW

```python
"""v2.0 파이프라인 오케스트레이터 — 3-Stage Pipeline"""
import logging
from config.constants import SUCCESS_CRITERIA

class PipelineRunnerV2:
    """
    v2.0 3-Stage 파이프라인:
      Stage 1: 독립 인덱스 구성 (BTC-blind)
      Stage 2: 방향성 검증 (BTC 참조)
      Stage 3: 과적합 방지 (통계 검정)
    """

    def __init__(
        self,
        method: str = "pca",
        freq: str = "monthly",
    ):
        """
        Args:
            method: "pca" | "ica" | "dfm" | "sparse" | "all" (비교)
            freq: "daily" | "weekly" | "monthly"
        """
        self.method = method
        self.freq = freq
        self.logger = logging.getLogger(__name__)

    def run_full(self) -> dict:
        """
        전체 v2.0 파이프라인 실행.

        Flow:
          1. FETCH: 기존 fetcher 레이어 사용
          2. CALCULATE: 기존 calculator + sofr_smooth
          3. PREPROCESS:
             a. freq=monthly → 12m MA detrend → z-score → z_matrix (기존 방식)
             b. freq=daily → daily_matrix 구성 (DFM용)
          4. STAGE 1 (BTC-blind):
             a. method에 따라 인덱스 구성
             b. PCA 부호 보정 (NL과 양의 상관)
             c. 결과 저장: data/indices/
          5. STAGE 2 (Direction Validation):
             a. Cross-correlation profile (lag=0~15)
             b. CWS 계산 + 최적 lag 탐색
             c. Granger 양방향 검정
             d. Wavelet Coherence
             e. 결과 저장: data/validation/
          6. STAGE 3 (Robustness):
             a. Bootstrap loading 안정성
             b. CPCV 45-path validation
             c. Deflated test (다중 비교 보정)
             d. 결과 저장: data/validation/
          7. REPORT: 종합 결과 출력

        Returns: {
            "stage1": {...},  # 인덱스 구성 결과
            "stage2": {...},  # 방향성 검증 결과
            "stage3": {...},  # 과적합 방지 결과
            "success": bool,  # SUCCESS_CRITERIA 충족 여부
            "summary": str,   # 결과 요약 텍스트
        }
        """

    def run_stage1(
        self,
        z_matrix: pd.DataFrame = None,
        daily_matrix: pd.DataFrame = None,
    ) -> dict:
        """
        Stage 1만 실행 (독립 인덱스 구성).
        개발/디버그 용도.
        """

    def run_stage2(
        self,
        index: pd.Series,
        target: pd.Series,
    ) -> dict:
        """
        Stage 2만 실행 (방향성 검증).
        """

    def run_stage3(
        self,
        z_matrix: pd.DataFrame,
        target: pd.Series,
    ) -> dict:
        """
        Stage 3만 실행 (과적합 방지).
        """

    def compare_all_methods(
        self,
        z_matrix: pd.DataFrame,
        target: pd.Series,
    ) -> pd.DataFrame:
        """
        PCA, ICA, DFM, SparsePCA 4개 방법을 모두 실행하고 CWS로 비교.

        Returns: DataFrame[method, optimal_lag, cws, mda, pearson_r, ...]
                 CWS 기준 내림차순 정렬
        """

    def _check_success_criteria(
        self,
        stage2_result: dict,
        stage3_result: dict,
    ) -> dict:
        """
        SUCCESS_CRITERIA 충족 여부 체크.

        Returns: {
            "min_mda": {"target": 0.6, "actual": 0.65, "pass": True},
            "all_lag_positive": {"target": True, "actual": True, "pass": True},
            "bootstrap_ci": {"target": True, "actual": True, "pass": True},
            "granger": {"target": 0.05, "actual": 0.02, "pass": True},
            "overall": True,
        }
        """
```

### 7.2 기존 파이프라인 유지

- `pipeline/runner.py`: v1.0 호환용 유지 (deprecated)
- `pipeline/storage.py`: 그대로 유지 + `save_index()`, `save_validation()` 메서드 추가

```python
# storage.py 추가 메서드

def save_index(self, method: str, result: dict) -> str:
    """data/indices/{method}_{date}.json 저장"""

def save_validation(self, result: dict) -> str:
    """data/validation/validation_{date}.json 저장"""

def save_bootstrap(self, result: dict) -> str:
    """data/validation/bootstrap_{date}.json 저장"""
```

---

## 8. Module Design — Visualization 추가

### 8.1 기존 수정: `overlay_chart.py`

v2.0 인덱스 오버레이 지원 + 방향 일치 구간 표시

```python
def plot_index_vs_btc(
    index: pd.Series,
    log_btc: pd.Series,
    lag: int,
    method: str = "PCA",
    mda: float | None = None,
    save_path: str | None = None,
) -> None:
    """
    v2.0 인덱스 vs log₁₀(BTC) 오버레이.
    - 좌축: Liquidity Index (blue)
    - 우축: log₁₀(BTC) (orange, lag 시프트)
    - 방향 일치 구간: green 배경
    - 방향 불일치 구간: red 배경
    - MDA 값 텍스트 표시
    - 제목: "{method} Index vs BTC (lag={lag}, MDA={mda})"
    """
```

### 8.2 ★ NEW: `src/visualization/bootstrap_plot.py`

```python
"""Bootstrap 결과 시각화"""

def plot_loading_ci(
    bootstrap_result: dict,
    save_path: str | None = None,
) -> None:
    """
    PC1 loadings의 95% CI 에러바 차트.
    X축: 변수명, Y축: loading 값
    에러바: 95% CI, 점: mean
    NL loading이 항상 최대인지 시각적 확인.
    """

def plot_lag_distribution(
    lag_result: dict,
    save_path: str | None = None,
) -> None:
    """
    최적 lag의 Bootstrap 분포 히스토그램.
    X축: lag (0~15), Y축: 빈도
    95% CI 범위 음영
    """
```

### 8.3 ★ NEW: `src/visualization/method_comparison_plot.py`

```python
"""인덱스 방법 비교 시각화"""

def plot_method_comparison(
    comparison: pd.DataFrame,
    save_path: str | None = None,
) -> None:
    """
    PCA vs ICA vs DFM vs SparsePCA 비교 차트.
    Subplot 1: CWS 비교 (bar chart)
    Subplot 2: 각 방법의 XCORR profile (line chart)
    Subplot 3: Loading 비교 (grouped bar)
    """
```

---

## 9. CLI Interface — `main.py` v2.0

```python
"""
Finance Simulator CLI — BTC Liquidity Prediction Model v2.0.0

Usage:
    # === v1.0 호환 명령 (deprecated) ===
    python main.py fetch              # 데이터 수집
    python main.py optimize           # v1.0 Grid Search (deprecated)

    # === v2.0 신규 명령 ===
    python main.py build-index        # Stage 1: 인덱스 구성
    python main.py validate           # Stage 2: 방향성 검증
    python main.py analyze            # Stage 3: 과적합 분석
    python main.py run                # 전체 3-Stage 파이프라인
    python main.py compare            # 4개 방법 비교
    python main.py visualize          # 시각화

    # === 공통 옵션 ===
    --freq daily|weekly|monthly       # 타임스케일 (기본: monthly)
    --method pca|ica|dfm|sparse|all   # 인덱스 방법 (기본: pca)
"""

import argparse

def main():
    parser = argparse.ArgumentParser(description="BTC Liquidity Model v2.0.0")
    parser.add_argument("--freq", choices=["daily", "weekly", "monthly"],
                        default="monthly", help="Time frequency")
    parser.add_argument("--method", choices=["pca", "ica", "dfm", "sparse", "all"],
                        default="pca", help="Index building method")

    subparsers = parser.add_subparsers(dest="command")

    # v1.0 호환
    subparsers.add_parser("fetch", help="Fetch all data sources")
    subparsers.add_parser("optimize", help="[deprecated] v1.0 Grid Search")

    # v2.0 신규
    subparsers.add_parser("build-index", help="Stage 1: Build liquidity index (BTC-blind)")
    subparsers.add_parser("validate", help="Stage 2: Direction validation against BTC")
    subparsers.add_parser("analyze", help="Stage 3: Robustness analysis")
    subparsers.add_parser("run", help="Full 3-Stage pipeline")
    subparsers.add_parser("compare", help="Compare all index methods (PCA/ICA/DFM/Sparse)")

    viz_parser = subparsers.add_parser("visualize", help="Generate charts")
    viz_parser.add_argument("--type",
        choices=["overlay", "xcorr", "wavelet", "bootstrap", "comparison", "all"],
        default="all")

    subparsers.add_parser("status", help="Show model status")

    args = parser.parse_args()
    # ... dispatch to PipelineRunnerV2
```

---

## 10. Data Flow (v2.0 상세)

```
                      FETCH PHASE (v1.0 동일)
    ┌──────────────────────────────────────────────────┐
    │  FRED → WALCL, RRP, SOFR, IORB, M2s, HY_OAS     │
    │  Treasury → TGA                                   │
    │  yfinance → DXY, BTC-USD, BTC=F                   │
    │  Fallback → CoinGecko/Binance BTC                 │
    └────────────────────┬─────────────────────────────┘
                         │
                         ▼
                   CALCULATE PHASE (수정)
    ┌──────────────────────────────────────────────────┐
    │  NL = WALCL - TGA - RRP      → detrend → z-score │
    │  GM2 = US+EU+CN+JP → ortho   → detrend → z-score │
    │  SOFR - IORB → ★Logistic smooth (0~1)   → z-score│ ← v2.0 변경
    │  HY OAS                      → detrend → z-score │
    │  CME Basis                   → detrend → z-score │
    └────────────────────┬─────────────────────────────┘
                         │  z_matrix (T×5)
                         │  ※ BTC 데이터는 여기서 분리
                         ▼
              ╔═══════════════════════════════════════╗
              ║     STAGE 1: 독립 인덱스 구성           ║
              ║     (BTC 데이터 절대 불참조)             ║
              ╠═══════════════════════════════════════╣
              ║                                       ║
              ║  freq=monthly:                        ║
              ║    z_matrix → PCA → PC1 (index)       ║
              ║    z_matrix → ICA → IC_liq (index)    ║
              ║    z_matrix → SparsePCA → SPC1         ║
              ║                                       ║
              ║  freq=daily:                          ║
              ║    daily_matrix(NaN) → DFM+Kalman     ║
              ║    → daily_factor (index)              ║
              ║                                       ║
              ║  Output: Liquidity Index (T,)          ║
              ║  저장: data/indices/                    ║
              ╚═══════════════════╤═══════════════════╝
                                  │  index + log₁₀(BTC)
                                  ▼
              ╔═══════════════════════════════════════╗
              ║     STAGE 2: 방향성 검증                ║
              ║     (여기서만 BTC 참조)                  ║
              ╠═══════════════════════════════════════╣
              ║                                       ║
              ║  Cross-Correlation Profile:            ║
              ║    lag=0~15: Pearson r, MDA, SBD,     ║
              ║              Cosine Sim, Kendall Tau   ║
              ║                                       ║
              ║  CWS = 0.4×MDA + 0.3×(1-SBD)         ║
              ║      + 0.2×CosSim + 0.1×Tau           ║
              ║                                       ║
              ║  Granger: Index→BTC (✓), BTC→Index(✗) ║
              ║  Wavelet: 시간-주파수 coherence         ║
              ║                                       ║
              ║  Output: CWS, optimal_lag, metrics     ║
              ║  저장: data/validation/                 ║
              ╚═══════════════════╤═══════════════════╝
                                  │
                                  ▼
              ╔═══════════════════════════════════════╗
              ║     STAGE 3: 과적합 방지                ║
              ╠═══════════════════════════════════════╣
              ║                                       ║
              ║  Bootstrap (1000 iter):                ║
              ║    - Loading 안정성 (95% CI)            ║
              ║    - Lag 분포                           ║
              ║    - MDA p-value (binomial)             ║
              ║                                       ║
              ║  CPCV (45 paths):                      ║
              ║    - Purge=9m, Embargo=2m              ║
              ║    - OOS CWS mean/std                   ║
              ║                                       ║
              ║  Deflated Test:                        ║
              ║    - 4 methods → 최고 CWS 우연 검정     ║
              ║                                       ║
              ║  Output: pass/fail + confidence        ║
              ╚═══════════════════╤═══════════════════╝
                                  │
                                  ▼
                         SUCCESS CHECK
              ┌──────────────────────────────┐
              │  MDA > 0.60?           ✓/✗    │
              │  All lag r > 0?        ✓/✗    │
              │  Bootstrap CI ∌ 0?     ✓/✗    │
              │  Granger p < 0.05?     ✓/✗    │
              │  CPCV mean > 0.15?     ✓/✗    │
              └──────────────┬───────────────┘
                             │
                             ▼
                   STORE + VISUALIZE
              ┌──────────────────────────────┐
              │  JSON + SQLite 저장            │
              │  Charts: overlay, xcorr,      │
              │    wavelet, bootstrap,         │
              │    method comparison           │
              └──────────────────────────────┘
```

---

## 11. Error Handling Strategy (v2.0 추가)

### 11.1 새로운 에러 시나리오

| 상황 | 처리 |
|------|------|
| DFM 수렴 실패 | max_iter×2로 재시도 → 여전히 실패 시 월별 PCA fallback |
| DFM 칼만 초기값 불안정 | EM 알고리즘 (기본) → 3개 random seed 시도 |
| ICA 수렴 실패 | max_iter=1000으로 재시도 → 실패 시 PCA 사용 |
| Sparse PCA 모든 loading=0 | alpha 감소 (÷2) → 재시도 (최대 3회) |
| pycwt 설치 실패 | Wavelet 분석 skip, 경고 로그 |
| skfolio 미설치 | CPCV 자체 구현 fallback |
| tsbootstrap 미설치 | numpy 기반 block bootstrap 자체 구현 |
| Bootstrap 결과 불안정 | n_bootstraps 증가 (→2000) 또는 block_length 조정 |
| Granger 비정상 시계열 | ADF test → 실패 시 1차 차분 후 재검정 |
| 일별 데이터 크기 (3000+ 행) | DFM에 chunking 또는 downsampling 적용 |
| tslearn SBD NaN | NaN 행 제거 후 재계산, 유효 데이터 < 30이면 skip |
| 메모리 초과 (DFM+Bootstrap) | gc.collect() + 순차 실행 (병렬 X) |

### 11.2 Fallback 체인

```
DFM 실패 → PCA (monthly)
ICA 실패 → PCA
SparsePCA 모든 0 → 일반 PCA
skfolio 미설치 → 자체 CPCV
tsbootstrap 미설치 → numpy block bootstrap
pycwt 미설치 → Wavelet skip (CWS에서 제외)
```

---

## 12. 구현 우선순위 (파일별)

### Phase 1: 기반 변경 (Quick Wins)

| 순서 | 파일 | 작업 | 설명 |
|:----:|------|:----:|------|
| 1 | `config/settings.py` | 수정 | DATA_END 동적화, freq 옵션 |
| 2 | `config/constants.py` | 수정 | v2.0 파라미터 추가 |
| 3 | `requirements.txt` | 수정 | v2.0 의존성 추가 |
| 4 | `src/calculators/sofr_smooth.py` | 생성 | Logistic smoothing |
| 5 | `src/index_builders/pca_builder.py` | 생성 | PCA 인덱스 (primary) |
| 6 | `src/validators/waveform_metrics.py` | 생성 | MDA, SBD, CosSim, Tau |
| 7 | `src/validators/composite_score.py` | 생성 | CWS 복합 점수 |

### Phase 2: 인덱스 비교 + 검증

| 순서 | 파일 | 작업 | 설명 |
|:----:|------|:----:|------|
| 8 | `src/index_builders/ica_builder.py` | 생성 | ICA 인덱스 |
| 9 | `src/index_builders/sparse_pca_builder.py` | 생성 | Sparse PCA |
| 10 | `src/robustness/bootstrap_analysis.py` | 생성 | Bootstrap 안정성 |
| 11 | `src/validators/granger_test.py` | 생성 | Granger 인과 |

### Phase 3: 혼합 주기 + 고급

| 순서 | 파일 | 작업 | 설명 |
|:----:|------|:----:|------|
| 12 | `src/index_builders/dfm_builder.py` | 생성 | DFM + 칼만 필터 |
| 13 | `src/validators/wavelet_coherence.py` | 생성 | Wavelet 분석 |
| 14 | `src/robustness/cpcv.py` | 생성 | CPCV 45-path |
| 15 | `src/robustness/deflated_test.py` | 생성 | 다중 비교 보정 |

### Phase 4: 파이프라인 통합

| 순서 | 파일 | 작업 | 설명 |
|:----:|------|:----:|------|
| 16 | `src/pipeline/runner_v2.py` | 생성 | 3-Stage 오케스트레이터 |
| 17 | `src/pipeline/storage.py` | 수정 | save_index/validation 추가 |
| 18 | `main.py` | 수정 | v2.0 CLI 명령 |

### Phase 5: 시각화

| 순서 | 파일 | 작업 | 설명 |
|:----:|------|:----:|------|
| 19 | `src/visualization/overlay_chart.py` | 수정 | 방향 일치 구간 표시 |
| 20 | `src/visualization/bootstrap_plot.py` | 생성 | Loading CI + lag 분포 |
| 21 | `src/visualization/method_comparison_plot.py` | 생성 | 4-method 비교 |

### Phase 6: 검증 + 문서화

| 순서 | 파일 | 작업 | 설명 |
|:----:|------|:----:|------|
| 22 | (통합 테스트) | - | 전체 파이프라인 실행 |
| 23 | (v1.0 vs v2.0 비교) | - | 결과 비교 보고서 |
| 24 | CLAUDE.md, README | 수정 | 문서 업데이트 |

---

## 13. 파일 구조 (v2.0 최종)

```
finance-simulator/
├── config/
│   ├── __init__.py
│   ├── constants.py           # 수정: v2.0 파라미터 추가
│   └── settings.py            # 수정: DATA_END 동적, freq 옵션
│
├── src/
│   ├── fetchers/              # 변경 없음 (v1.0 유지)
│   │   ├── __init__.py
│   │   ├── fred_fetcher.py
│   │   ├── treasury_fetcher.py
│   │   ├── market_fetcher.py
│   │   └── fallback_fetcher.py
│   │
│   ├── calculators/
│   │   ├── __init__.py
│   │   ├── detrend.py         # 유지
│   │   ├── net_liquidity.py   # 유지
│   │   ├── global_m2.py       # 유지
│   │   ├── sofr_binary.py     # deprecated (v1.0 호환)
│   │   ├── sofr_smooth.py     # ★ NEW (Logistic + Markov)
│   │   ├── hy_spread.py       # 유지
│   │   └── cme_basis.py       # 유지
│   │
│   ├── index_builders/        # ★ NEW 모듈
│   │   ├── __init__.py
│   │   ├── pca_builder.py     # PCA 기반 인덱스 (primary)
│   │   ├── ica_builder.py     # ICA 기반 인덱스
│   │   ├── dfm_builder.py     # DFM + 칼만 필터
│   │   └── sparse_pca_builder.py  # Sparse PCA 변수 선택
│   │
│   ├── validators/            # ★ NEW 모듈
│   │   ├── __init__.py
│   │   ├── waveform_metrics.py    # MDA, SBD, CosSim, Tau
│   │   ├── wavelet_coherence.py   # 시간-주파수 분석
│   │   ├── granger_test.py        # Granger 인과 검정
│   │   └── composite_score.py     # CWS 복합 점수
│   │
│   ├── robustness/            # ★ NEW 모듈
│   │   ├── __init__.py
│   │   ├── bootstrap_analysis.py  # Block Bootstrap 안정성
│   │   ├── cpcv.py                # Combinatorial Purged CV
│   │   └── deflated_test.py       # 다중 비교 보정
│   │
│   ├── optimizers/            # v1.0 유지 (deprecated)
│   │   ├── __init__.py
│   │   ├── grid_search.py     # deprecated
│   │   ├── walk_forward.py    # 유지 (v2.0 비교용)
│   │   └── orthogonalize.py   # 유지
│   │
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── runner.py          # v1.0 유지 (deprecated)
│   │   ├── runner_v2.py       # ★ NEW (3-Stage)
│   │   └── storage.py         # 수정: index/validation 저장 추가
│   │
│   ├── visualization/
│   │   ├── __init__.py
│   │   ├── overlay_chart.py       # 수정: 방향 일치 구간 표시
│   │   ├── correlation_heatmap.py # 유지
│   │   ├── walkforward_plot.py    # 유지
│   │   ├── bootstrap_plot.py      # ★ NEW
│   │   └── method_comparison_plot.py  # ★ NEW
│   │
│   └── utils/                 # 유지
│       ├── __init__.py
│       ├── date_utils.py
│       └── logger.py
│
├── data/
│   ├── raw/                   # API 캐시
│   ├── processed/             # z-matrix, 일별 데이터
│   ├── indices/               # ★ NEW (인덱스 결과)
│   ├── validation/            # ★ NEW (검증 결과)
│   ├── scores/                # JSON + SQLite
│   ├── logs/
│   └── charts/
│
├── web/                       # React 대시보드 (v2.0 업데이트 예정)
├── main.py                    # 수정: v2.0 CLI
└── requirements.txt           # 수정: v2.0 의존성
```

---

## 14. Dependencies (requirements.txt 추가분)

```
# === v1.0 기존 ===
pandas>=2.0
numpy>=2.0
scipy>=1.11
fredapi>=0.5.2
yfinance>=0.2.31
matplotlib>=3.8
seaborn>=0.13
python-dotenv>=1.0
tqdm>=4.66

# === v2.0 추가 ===
scikit-learn>=1.4          # PCA, FastICA, SparsePCA
statsmodels>=0.14          # DFM, MarkovRegression, Granger, ADF
tslearn>=0.6               # SBD, DTW
pycwt>=0.4                 # Wavelet Coherence
tsbootstrap>=0.1           # Moving Block Bootstrap (optional)
# skfolio>=0.3             # CPCV (optional, 자체 구현 fallback)
```

---

## 15. 테스트 전략 (v2.0)

### Unit Tests

```python
# tests/test_index_builders.py
class TestPCABuilder:
    def test_build_returns_index(self):
        """z_matrix 입력 → index 시계열 반환"""
    def test_sign_correction(self):
        """NL과 양의 상관으로 부호 보정"""
    def test_loadings_sum(self):
        """loadings 제곱합 = 1"""
    def test_no_btc_input(self):
        """build() 인자에 BTC 관련 데이터 없음"""

class TestICABuilder:
    def test_select_liquidity_ic(self):
        """NL과 가장 높은 |corr| IC 선택"""
    def test_convergence_failure(self):
        """수렴 실패 시 ValueError"""

class TestDFMBuilder:
    def test_nan_handling(self):
        """NaN 셀이 칼만 필터로 보간"""
    def test_daily_to_monthly(self):
        """resample_to_freq 정확성"""

# tests/test_validators.py
class TestWaveformMetrics:
    def test_mda_perfect(self):
        """완전 일치 → MDA=1.0"""
    def test_mda_random(self):
        """랜덤 → MDA≈0.5"""
    def test_sbd_identical(self):
        """동일 시계열 → SBD=0"""

class TestCompositeScore:
    def test_cws_weights_sum(self):
        """가중치 합 = 1.0"""
    def test_optimal_lag(self):
        """최적 lag 범위 0~15"""

# tests/test_robustness.py
class TestBootstrap:
    def test_loading_ci(self):
        """CI가 합리적 범위"""
    def test_mda_significance(self):
        """MDA > 0.5일 때 p < 0.05"""

class TestCPCV:
    def test_45_paths(self):
        """C(10,2) = 45 경로 생성"""
    def test_purge_embargo(self):
        """purge+embargo 제거 확인"""
```

### Integration Tests

```python
# tests/test_pipeline_v2.py
class TestPipelineV2:
    def test_full_monthly_pca(self):
        """월별 PCA 전체 파이프라인 실행"""
    def test_stage1_btc_blind(self):
        """Stage 1에서 BTC 미참조 확인"""
    def test_compare_all_methods(self):
        """4개 방법 비교 결과 DataFrame 형태"""
    def test_success_criteria_check(self):
        """성공 기준 체크 로직"""
```

---

## References

- v2.0 Plan: `docs/01-plan/features/btc-liquidity-v2.plan.md`
- v1.0 Design: `docs/02-design/features/btc-liquidity-model.design.md`
- v1.0 Report: `docs/04-report/btc-liquidity-model.report.md`
- Phase 1c: BTC-blind PCA baseline (r=0.318, all lags positive)
- de Prado (2018): CPCV — Advances in Financial Machine Learning
- Hamilton (1989): Markov Regime-Switching Models
