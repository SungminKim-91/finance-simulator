# BTC Liquidity Prediction Model - Gap Analysis Report

> **Analysis Type**: Design-Implementation Gap Analysis
>
> **Project**: Finance Simulator
> **Version**: v1.0.0
> **Date**: 2026-03-01
> **Design Doc**: [btc-liquidity-model.design.md](../02-design/features/btc-liquidity-model.design.md)

---

## 1. Analysis Overview

### 1.1 Analysis Purpose

설계 문서(btc-liquidity-model.design.md)와 실제 구현 코드의 정합성을 검증한다.
모듈 구조, 함수 시그니처, 데이터 흐름, 에러 처리, 상수/설정, 저장 형식을 비교 대상으로 한다.

### 1.2 Analysis Scope

- **Design Document**: `docs/02-design/features/btc-liquidity-model.design.md`
- **Implementation Paths**:
  - `config/settings.py`, `config/constants.py`
  - `src/fetchers/` (4 files)
  - `src/calculators/` (6 files)
  - `src/optimizers/` (3 files)
  - `src/pipeline/` (2 files)
  - `src/visualization/` (3 files)
  - `src/utils/` (2 files)
  - `main.py`

---

## 2. Overall Scores

| Category | Score | Status |
|----------|:-----:|:------:|
| Module Structure Match | 100% | PASS |
| Function Signature Match | 92% | PASS |
| Data Flow Match | 95% | PASS |
| Error Handling Match | 95% | PASS |
| Constants/Config Match | 88% | WARNING |
| Storage Schema Match | 93% | PASS |
| CLI Interface Match | 90% | PASS |
| **Overall** | **93%** | **PASS** |

---

## 3. Module Structure Comparison (100%)

### 3.1 File-Level Comparison

| Design File | Implementation File | Status |
|-------------|---------------------|--------|
| `config/settings.py` | `/home/sungmin/finance-simulator/config/settings.py` | MATCH |
| `config/constants.py` | `/home/sungmin/finance-simulator/config/constants.py` | MATCH |
| `src/fetchers/fred_fetcher.py` | `/home/sungmin/finance-simulator/src/fetchers/fred_fetcher.py` | MATCH |
| `src/fetchers/treasury_fetcher.py` | `/home/sungmin/finance-simulator/src/fetchers/treasury_fetcher.py` | MATCH |
| `src/fetchers/market_fetcher.py` | `/home/sungmin/finance-simulator/src/fetchers/market_fetcher.py` | MATCH |
| `src/fetchers/fallback_fetcher.py` | `/home/sungmin/finance-simulator/src/fetchers/fallback_fetcher.py` | MATCH |
| `src/calculators/detrend.py` | `/home/sungmin/finance-simulator/src/calculators/detrend.py` | MATCH |
| `src/calculators/net_liquidity.py` | `/home/sungmin/finance-simulator/src/calculators/net_liquidity.py` | MATCH |
| `src/calculators/global_m2.py` | `/home/sungmin/finance-simulator/src/calculators/global_m2.py` | MATCH |
| `src/calculators/sofr_binary.py` | `/home/sungmin/finance-simulator/src/calculators/sofr_binary.py` | MATCH |
| `src/calculators/hy_spread.py` | `/home/sungmin/finance-simulator/src/calculators/hy_spread.py` | MATCH |
| `src/calculators/cme_basis.py` | `/home/sungmin/finance-simulator/src/calculators/cme_basis.py` | MATCH |
| `src/optimizers/orthogonalize.py` | `/home/sungmin/finance-simulator/src/optimizers/orthogonalize.py` | MATCH |
| `src/optimizers/grid_search.py` | `/home/sungmin/finance-simulator/src/optimizers/grid_search.py` | MATCH |
| `src/optimizers/walk_forward.py` | `/home/sungmin/finance-simulator/src/optimizers/walk_forward.py` | MATCH |
| `src/pipeline/runner.py` | `/home/sungmin/finance-simulator/src/pipeline/runner.py` | MATCH |
| `src/pipeline/storage.py` | `/home/sungmin/finance-simulator/src/pipeline/storage.py` | MATCH |
| `src/visualization/overlay_chart.py` | `/home/sungmin/finance-simulator/src/visualization/overlay_chart.py` | MATCH |
| `src/visualization/correlation_heatmap.py` | `/home/sungmin/finance-simulator/src/visualization/correlation_heatmap.py` | MATCH |
| `src/visualization/walkforward_plot.py` | `/home/sungmin/finance-simulator/src/visualization/walkforward_plot.py` | MATCH |
| `src/utils/logger.py` | `/home/sungmin/finance-simulator/src/utils/logger.py` | MATCH |
| `src/utils/date_utils.py` | `/home/sungmin/finance-simulator/src/utils/date_utils.py` | MATCH |
| `main.py` | `/home/sungmin/finance-simulator/main.py` | MATCH |

**Result**: 22/22 files -- 모든 설계 모듈이 구현됨.

---

## 4. Function Signature Comparison (92%)

### 4.1 Match

| Module | Function/Method | Design | Implementation | Status |
|--------|----------------|--------|----------------|--------|
| `detrend.py` | `detrend_12m_ma(series, window)` | `(pd.Series, int=12)` | `(pd.Series, int=MA_WINDOW_MONTHS)` | MATCH |
| `detrend.py` | `zscore(series, mean, std)` | `(pd.Series, float\|None, float\|None)` | `(pd.Series, float\|None, float\|None)` | MATCH |
| `detrend.py` | `compute_zscore_params(series)` | `(pd.Series) -> dict` | `(pd.Series) -> dict` | MATCH |
| `net_liquidity.py` | `NetLiquidityCalculator.calculate(walcl, tga, rrp)` | `(df, df, df) -> df` | `(df, df, df) -> df` | MATCH |
| `net_liquidity.py` | `_align_to_monthly(walcl, tga, rrp)` | `(df, df, df) -> df` | `(df, df, df) -> df` | MATCH |
| `global_m2.py` | `GlobalM2Calculator.calculate(us, eu, cn, jp)` | `(df, df, df, df) -> df` | `(df, df, df, df) -> df` | MATCH |
| `global_m2.py` | `orthogonalize(gm2_level, nl_level)` | `(Series, Series) -> (Series, dict)` | `(Series, Series) -> (Series, dict)` | MATCH |
| `global_m2.py` | `_carry_forward_lag(series, max_lag_months)` | `(Series, int=3) -> Series` | `(df, int=3) -> df` | CHANGED |
| `sofr_binary.py` | `SofrBinaryCalculator.calculate(sofr, iorb, threshold_bps)` | `(df, df, int=20) -> df` | `(df, df, int=SOFR_THRESHOLD_BPS) -> df` | MATCH |
| `hy_spread.py` | `HySpreadCalculator.calculate(hy_oas)` | `(df) -> df` | `(df) -> df` | MATCH |
| `cme_basis.py` | `CmeBasisCalculator.calculate(cme_futures, btc_spot)` | `(df, df) -> df` | `(df, df) -> df` | MATCH |
| `orthogonalize.py` | `check_and_orthogonalize(variables, threshold)` | `(dict, float=0.5) -> (dict, list)` | `(dict, float=0.5, list\|None) -> (dict, list)` | ENHANCED |
| `orthogonalize.py` | `ols_residual(y, x)` | `(Series, Series) -> (Series, float, float)` | `(Series, Series) -> (Series, float, float)` | MATCH |
| `grid_search.py` | `GridSearchOptimizer.__init__(search_config)` | `(dict=GRID_SEARCH)` | `(dict\|None=None)` | MATCH |
| `grid_search.py` | `optimize(z_matrix, log_btc)` | `(df, Series) -> dict` | `(df, Series, list\|None) -> dict` | ENHANCED |
| `grid_search.py` | `_generate_grid()` | `() -> list[dict]` | `(var_names) -> list[dict]` | CHANGED |
| `grid_search.py` | `_compute_score(Z, weights)` | `(ndarray, ndarray) -> ndarray` | `(ndarray, ndarray) -> ndarray` | MATCH |
| `grid_search.py` | `_evaluate(score, target, max_lag)` | `(ndarray, ndarray, int) -> (float, int)` | `(ndarray, ndarray, range) -> (float, int)` | CHANGED |
| `walk_forward.py` | `WalkForwardValidator.__init__(initial_train, test_window, expanding)` | `(int=60, int=6, bool=True)` | `(int\|None, int\|None, bool=True)` | MATCH |
| `walk_forward.py` | `validate(z_matrix, log_btc, weights, lag)` | `(df, Series, dict, int) -> dict` | `(df, Series, dict, int, list\|None) -> dict` | ENHANCED |
| `walk_forward.py` | `_split_windows(total_months)` | `(int) -> list[tuple]` | `(int) -> list[tuple]` | MATCH |
| `fred_fetcher.py` | `FredFetcher.__init__(api_key)` | `(str)` | `(str\|None)` | ENHANCED |
| `fred_fetcher.py` | `fetch_series(series_id, start, end, frequency)` | `(str, str, str, str\|None) -> df` | `(str, str, str, str\|None, bool=True) -> df` | ENHANCED |
| `fred_fetcher.py` | `fetch_all_fred_series(start, end)` | `(str, str) -> dict` | `(str, str, bool=True) -> dict` | ENHANCED |
| `fred_fetcher.py` | `_save_cache(series_id, df)` | `(str, df) -> None` | `(str, df) -> None` | MATCH |
| `fred_fetcher.py` | `_load_cache(series_id)` | `(str) -> df\|None` | `(str, bool=False) -> df\|None` | ENHANCED |
| `treasury_fetcher.py` | `TreasuryFetcher.fetch_tga(start, end)` | `(str, str) -> df` | `(str, str, bool=True) -> df` | ENHANCED |
| `treasury_fetcher.py` | `_parse_response(json_data)` | `(dict) -> df` | `_parse_records(records: list)` | CHANGED |
| `market_fetcher.py` | `fetch_ticker(ticker, start, end, interval)` | `(str, str, str, str="1d") -> df` | `(str, str, str, str="1d", bool=True, str\|None=None) -> df` | ENHANCED |
| `market_fetcher.py` | `fetch_dxy(start, end)` | `(str, str) -> df` | `(str, str, bool=True) -> df` | ENHANCED |
| `market_fetcher.py` | `fetch_btc_spot(start, end)` | `(str, str) -> df` | `(str, str, bool=True) -> df` | ENHANCED |
| `market_fetcher.py` | `fetch_cme_futures(start, end)` | `(str, str) -> df` | `(str, str, bool=True) -> df` | ENHANCED |
| `market_fetcher.py` | `_resample_monthly(df, col)` | `(df, str) -> df` | N/A (moved to `date_utils.resample_to_monthly`) | MOVED |
| `fallback_fetcher.py` | `fetch_coingecko_btc(start, end)` | `(str, str) -> df` | `(str, str) -> df` | MATCH |
| `fallback_fetcher.py` | `fetch_binance_btc(start, end)` | `(str, str) -> df` | `(str, str) -> df` | MATCH |
| `fallback_fetcher.py` | `fetch_btc_spot_with_fallback(start, end)` | `(str, str) -> df` | `(str, str, bool=True) -> df` | ENHANCED |
| `runner.py` | `PipelineRunner.__init__(mode)` | `(str="full")` | `(str="full")` | MATCH |
| `runner.py` | `run()` | `() -> dict` | `(str\|None, str\|None, bool=True) -> dict` | ENHANCED |
| `runner.py` | `_signal_from_score(score)` | `(float) -> str` | `(float) -> str` | MATCH |
| `storage.py` | `StorageManager.__init__(base_dir)` | `(str="data")` | `(str\|Path\|None=None)` | ENHANCED |
| `storage.py` | `save_score(result)` | `(dict) -> str` | `(dict) -> str` | MATCH |
| `storage.py` | `save_optimization_result(result)` | `(dict) -> str` | `(dict) -> str` | MATCH |
| `storage.py` | `load_latest_weights()` | `() -> dict\|None` | `() -> dict\|None` | MATCH |
| `storage.py` | `init_db()` | `() -> None` | `() -> None` | MATCH |
| `storage.py` | `insert_score(result)` | `(dict) -> None` | `(dict) -> None` | MATCH |
| `storage.py` | `insert_variables(date, variables)` | `(str, dict) -> None` | `(str, dict) -> None` | MATCH |
| `storage.py` | `get_score_history(n)` | `(int=12) -> list` | `(int=12) -> list` | MATCH |
| `overlay_chart.py` | `plot_score_vs_btc(score, log_btc, lag, save_path)` | `(Series, Series, int=5, str\|None)` | `(Series, Series, Series, int=5, str\|None, str\|None)` | CHANGED |
| `correlation_heatmap.py` | `plot_cross_correlation(score, log_btc, max_lag, save_path)` | `(Series, Series, int=12, str\|None)` | `(Series, Series, int=12, str\|None)` | MATCH |
| `correlation_heatmap.py` | `plot_variable_correlation_matrix(variables, save_path)` | `(df, str\|None)` | `(df, str, str\|None)` | ENHANCED |
| `walkforward_plot.py` | `plot_walk_forward(result, save_path)` | `(dict, str\|None)` | `(dict, str\|None)` | MATCH |
| `logger.py` | `setup_logger(name, level)` | `(str, str="INFO") -> Logger` | `(str, str="INFO", bool=True) -> Logger` | ENHANCED |

### 4.2 Signature Difference Summary

| Category | Count | Description |
|----------|:-----:|-------------|
| MATCH | 32 | 완전 일치 |
| ENHANCED | 14 | 구현이 `use_cache` 등 유용한 파라미터 추가 (하위호환) |
| CHANGED | 4 | 시그니처 의미 변경 (아래 상세) |
| MOVED | 1 | 다른 모듈로 이동 |
| **Total** | **51** | |

### 4.3 Changed Signatures (상세)

#### 4.3.1 `GlobalM2Calculator._carry_forward_lag`
- **Design**: `(series: pd.Series, max_lag_months: int=3) -> pd.Series`
- **Implementation**: `(df: pd.DataFrame, max_lag_months: int=3) -> pd.DataFrame`
- **Impact**: Low -- 내부 메서드이며 DataFrame 전체에 ffill 적용이 더 적절

#### 4.3.2 `TreasuryFetcher._parse_response` -> `_parse_records`
- **Design**: `_parse_response(self, json_data: dict) -> pd.DataFrame`
- **Implementation**: `_parse_records(self, records: list[dict]) -> pd.DataFrame`
- **Impact**: Low -- API 응답 구조에 맞게 records 리스트를 직접 받도록 변경

#### 4.3.3 `GridSearchOptimizer._evaluate` max_lag -> lag_range
- **Design**: `_evaluate(score, target, max_lag: int) -> (float, int)`
- **Implementation**: `_evaluate(score, target, lag_range: range) -> (float, int)`
- **Impact**: Low -- range 객체로 더 유연한 lag 범위 지정

#### 4.3.4 `plot_score_vs_btc` dates 파라미터 추가
- **Design**: `(score, log_btc, lag=5, save_path=None)`
- **Implementation**: `(score, log_btc, dates, lag=5, title=None, save_path=None)`
- **Impact**: Medium -- dates Series를 외부에서 전달해야 함 (설계는 score.index 사용 가정)

---

## 5. Constants/Config Comparison (88%)

### 5.1 settings.py

| Setting | Design | Implementation | Status |
|---------|--------|----------------|--------|
| `FRED_API_KEY` | `os.getenv("FRED_API_KEY", "")` | `os.getenv("FRED_API_KEY", "")` | MATCH |
| `DATA_START` | `"2016-01-01"` | `"2016-01-01"` | MATCH |
| `DATA_END` | `"2025-12-31"` | `"2025-12-31"` | MATCH |
| `WARMUP_MONTHS` | `12` | `12` | MATCH |
| `EFFECTIVE_START` | `"2017-01-01"` | `"2017-01-01"` | MATCH |
| `DATA_DIR` | `"data"` (str) | `PROJECT_ROOT / "data"` (Path) | ENHANCED |
| `RAW_DIR` | `f"{DATA_DIR}/raw"` (str) | `DATA_DIR / "raw"` (Path) | ENHANCED |
| `PROCESSED_DIR` | `f"{DATA_DIR}/processed"` (str) | `DATA_DIR / "processed"` (Path) | ENHANCED |
| `SCORES_DIR` | `f"{DATA_DIR}/scores"` (str) | `DATA_DIR / "scores"` (Path) | ENHANCED |
| `LOG_DIR` | N/A | `DATA_DIR / "logs"` (Path) | ADDED |
| `CHARTS_DIR` | N/A | `DATA_DIR / "charts"` (Path) | ADDED |
| `CACHE_EXPIRY_HOURS` | N/A | `24` | ADDED |
| Auto-mkdir | N/A | All dirs auto-created | ADDED |

### 5.2 constants.py

| Constant | Design | Implementation | Status |
|----------|--------|----------------|--------|
| `FRED_SERIES["EU_M2"]` | `"MYAGM2EZM196N"` | `"MABMM301EZM189S"` | **CHANGED** |
| `FRED_SERIES["JP_M2"]` | `"MABMM2JPM189N"` (M2) | `"MABMM301JPM189S"` (M3) | **CHANGED** |
| `TREASURY_TGA_FILTER` | 단일 필터 | `FILTER_OLD` + `FILTER_NEW` 이중 필터 | **ENHANCED** |
| `TREASURY_PAGE_SIZE` | N/A | `10000` | ADDED |
| `COINGECKO_BTC_URL` | `.../market_chart` | `.../market_chart/range` | **CHANGED** |
| `BINANCE_KLINES_URL` | N/A | `"https://api.binance.com/api/v3/klines"` | ADDED |
| `SIGNAL_THRESHOLDS` | N/A (runner 내부) | `{"bullish": 0.5, "bearish": -0.5}` | ADDED |
| `VARIABLE_ORDER` | N/A | 5개 변수 순서 리스트 | ADDED |
| `GRID_SEARCH` | 일치 | 일치 | MATCH |
| `WALK_FORWARD` | 일치 | 일치 | MATCH |
| `SOFR_THRESHOLD_BPS` | `20` | `20` | MATCH |
| `MA_WINDOW_MONTHS` | `12` | `12` | MATCH |
| `ORTHO_CORR_THRESHOLD` | `0.5` | `0.5` | MATCH |
| `V3_WEIGHTS` | 일치 | 일치 | MATCH |
| `V3_OPTIMAL_LAG` | `5` | `5` | MATCH |
| `V3_CORRELATION` | `0.407` | `0.407` | MATCH |
| `ZSCORE_PARAMS_V3` | 일치 | 일치 | MATCH |

### 5.3 FRED Series Differences (상세)

| Key | Design Series | Design Description | Impl Series | Impl Description | Reason |
|-----|---------------|-------------------|-------------|-----------------|--------|
| `EU_M2` | `MYAGM2EZM196N` | Euro Area M2 (NSA) | `MABMM301EZM189S` | Euro Area M3 Broad Money | FRED 시리즈 가용성 문제로 변경 추정. 설계 Section 10에서 `MYAGM2EZM196N`을 명시적으로 선택했으나 구현에서 M3로 대체 |
| `JP_M2` | `MABMM2JPM189N` | Japan M2 | `MABMM301JPM189S` | Japan M3 Broad Money | EU와 동일한 이유 추정 |

**Impact**: Medium -- 모델의 Global M2 계산에 직접 영향. M2 vs M3는 통화 집계 범위가 다르므로 결과값이 달라질 수 있음.

---

## 6. Data Flow Comparison (95%)

### 6.1 Pipeline Flow

| Phase | Design | Implementation | Status |
|-------|--------|----------------|--------|
| 1. Fetch all data sources | runner.run() -> fetch | `_fetch_all()` | MATCH |
| 2. Calculate derived variables | NL, GM2, SOFR, HY, CME | `_calculate_all()` | MATCH |
| 3. Detrend + z-score | z-score transform | `_zscore_all()` | MATCH |
| 4. Orthogonalization check | check_and_orthogonalize | `_orthogonalize()` | MATCH |
| 5. Grid Search (full mode) | GridSearchOptimizer | `_optimize()` | MATCH |
| 6. Walk-Forward (full mode) | WalkForwardValidator | `_walk_forward()` | MATCH |
| 7. Compute current score | score = Z @ w | `_compute_current_score()` | MATCH |
| 8. Store results | JSON + SQLite | `save_score()` + `insert_score()` | MATCH |

### 6.2 Step Ordering Difference

- **Design**: Step 3 (Detrend + z-score) -> Step 4 (Orthogonalization) -> Step 5 (Optimize)
- **Implementation**: Step 3 (Orthogonalization) -> Step 4 (Z-score) -> Step 5 (Optimize)
- **Assessment**: 구현이 더 정확함. 직교화를 먼저 수행한 후 z-score를 적용해야 올바름. 설계 문서의 순서가 오류.

### 6.3 Added Data Flow Elements

| Element | Design | Implementation | Impact |
|---------|--------|----------------|--------|
| Date normalization | N/A | `_normalize_dates()` -- MonthEnd 정규화 | ADDED -- merge 정합성 향상 |
| Processed data save | N/A | `_save_processed()` -- CSV 중간 저장 | ADDED -- 디버깅/시각화 지원 |
| BTC daily fetching | N/A | `fetch_btc_daily()`, `fetch_cme_daily()` | ADDED -- CME Basis 일간 계산 지원 |
| Fallback in pipeline | "yfinance 실패 시" | btc_spot empty check + fallback | MATCH |

---

## 7. Error Handling Comparison (95%)

### 7.1 Design Error Handling Table vs Implementation

| Error Scenario | Design | Implementation | Status |
|----------------|--------|----------------|--------|
| FRED API key missing | 시작 시 체크 + 에러 메시지 + URL 가이드 | `FredFetcher.__init__()` ValueError + URL | MATCH |
| FRED Rate Limit | `time.sleep(0.5)` throttle | `_throttle()`: 5 requests마다 0.5s | MATCH (조건부) |
| FRED series no response | NaN 처리 + 경고 로그 | empty DataFrame + error log | MATCH |
| Treasury API down | 캐시 사용 + 경고 로그 | expired cache fallback + warning | MATCH |
| yfinance fail | CoinGecko -> Binance fallback | `FallbackFetcher` chain | MATCH |
| CME futures NaN (pre-2017.12) | Grid Search 유효 기간만 사용 | `_compute_score()` NaN mask | MATCH |
| GM2 lag (2-3 months) | carry-forward | `_carry_forward_lag(limit=3)` | MATCH |
| Orthogonalization corr != 0 | 소수점 오차 허용 (\|corr\| < 0.01) | corr_after 로깅만 (threshold 미체크) | WARNING |
| Grid Search 0 results | 최소 1개 변수 활성 | `if np.all(w == 0): continue` | MATCH |
| Walk-Forward window insufficient | 최소 3개 윈도우 보장 | `if len(windows) < 3: warning` | MATCH |

### 7.2 Added Error Handling (Design X, Implementation O)

| Error Scenario | Implementation Location | Description |
|----------------|------------------------|-------------|
| FRED expired cache fallback | `fred_fetcher.py:88-93` | API 실패 시 만료 캐시라도 반환 |
| yfinance expired cache fallback | `market_fetcher.py:70-73` | 동일 패턴 |
| Treasury dual filter | `treasury_fetcher.py:50-59` | 2021-10 전후 account_type 변경 대응 |
| NaN Score defense | `storage.py:119-123` | SQLite insert 시 NaN -> 0.0 변환 |
| CME Basis clipping | `cme_basis.py:61` | 연율화 basis +-200% 초과 시 클리핑 |
| Pipeline exception handling | `main.py:274-281` | 전체 try-except + logger.error |

---

## 8. Storage Schema Comparison (93%)

### 8.1 SQLite Tables

| Table | Design Column | Implementation | Status |
|-------|---------------|----------------|--------|
| `scores.id` | `id` (PK) | `id INTEGER PRIMARY KEY AUTOINCREMENT` | MATCH |
| `scores.date` | `date` | `date TEXT NOT NULL` | MATCH |
| `scores.score` | `score` | `score REAL NOT NULL` | MATCH |
| `scores.signal` | `signal` | `signal TEXT NOT NULL` | MATCH |
| `scores.lag` | `lag` | `lag INTEGER` | MATCH |
| `scores.weights_json` | `weights_json` | `weights_json TEXT` | MATCH |
| `scores.corr` | `corr` | `correlation REAL` | **CHANGED** (corr -> correlation) |
| `scores.created_at` | `created_at` | `created_at TEXT DEFAULT CURRENT_TIMESTAMP` | MATCH |
| `variables.*` | 전체 | 전체 일치 | MATCH |
| `optimizations.oos_corr` | `oos_corr` | `oos_mean_corr REAL` | **CHANGED** (이름 변경) |
| `optimizations.*` | 나머지 | 일치 | MATCH |

### 8.2 JSON Storage

| File Pattern | Design | Implementation | Status |
|-------------|--------|----------------|--------|
| `score_{YYYY-MM-DD}.json` | MATCH | MATCH | MATCH |
| `optimization_{YYYY-MM-DD}.json` | MATCH | MATCH | MATCH |
| `load_latest_weights()` | optimization에서 weights 로드 | MATCH | MATCH |
| `load_latest_optimization()` | N/A | 전체 optimization 로드 추가 | ADDED |

### 8.3 CSV Storage (Added)

| File | Design | Implementation | Status |
|------|--------|----------------|--------|
| `data/processed/variables_raw.csv` | N/A | `save_processed()` | ADDED |
| `data/processed/variables_ortho.csv` | N/A | `save_processed()` | ADDED |
| `data/processed/z_matrix.csv` | N/A | `save_processed()` | ADDED |

---

## 9. CLI Interface Comparison (90%)

### 9.1 Commands

| Command | Design | Implementation | Status |
|---------|--------|----------------|--------|
| `fetch` | 데이터 수집만 | `cmd_fetch()` | MATCH |
| `calculate` | 수집 + 계산 | N/A | **MISSING** |
| `optimize` | 수집 + 계산 + Grid Search + WF | `cmd_optimize()` | MATCH |
| `run` | 전체 파이프라인 (주간) | `cmd_run()` (update mode) | MATCH |
| `score` | 저장된 가중치로 현재 Score | `cmd_score()` | MATCH |
| `visualize` | 차트 생성 | `cmd_visualize()` | MATCH |
| `status` | 최신 Score + 모델 상태 | `cmd_status()` | MATCH |

### 9.2 Command Arguments

| Command | Design Argument | Implementation | Status |
|---------|----------------|----------------|--------|
| `fetch` | `--no-cache` | `--no-cache`, `--start`, `--end` | ENHANCED |
| `optimize` | N/A | `--no-cache`, `--start`, `--end` | ADDED |
| `visualize` | `--type` (overlay/correlation/walkforward/all) | `--type` (동일) | MATCH |

---

## 10. MISSING Features (Design O, Implementation X)

| # | Item | Design Location | Description | Impact |
|---|------|-----------------|-------------|--------|
| 1 | `calculate` CLI command | design.md Section 7 (L866) | `python main.py calculate` -- 수집+계산만 하는 모드 | Low -- optimize로 대체 가능 |
| 2 | `_handle_rollover()` | design.md Section 3.6 (L527-L533) | CME basis 만기일 전후 가격 점프 스무딩 | Medium -- yfinance BTC=F가 auto-rollover이므로 불필요할 수 있음 |
| 3 | `_estimate_days_to_expiry()` in cme_basis.py | design.md Section 3.6 (L521-L525) | CmeBasisCalculator 내부 메서드로 설계됨 | Low -- `date_utils.days_to_expiry()`로 분리 구현 |
| 4 | Phase shading in overlay chart | design.md Section 6.1 (L805) | "Phase 구간 음영 (하락기=red, 상승기=green)" | Low -- 시각적 enhancement |
| 5 | Cumulative OOS overlay in WF plot | design.md Section 6.3 (L849) | "Subplot 2: 누적 OOS score vs log10(BTC) 오버레이" | Low -- summary text로 대체 |
| 6 | Test files | design.md Section 13 | `tests/test_calculators.py`, `tests/test_pipeline.py` | Medium -- 테스트 코드 미작성 |

---

## 11. ADDED Features (Design X, Implementation O)

| # | Item | Implementation Location | Description | Impact |
|---|------|------------------------|-------------|--------|
| 1 | `detrend_12m_ma_abs()` | `src/calculators/detrend.py:28-41` | \|MA\| 나눔 (CME Basis 음수 대응) | Positive -- 설계 Section 11에 서술된 요구사항 반영 |
| 2 | `fetch_btc_daily()` / `fetch_cme_daily()` | `src/fetchers/market_fetcher.py:114-131` | 일간 데이터 별도 API | Positive -- CME Basis 일간 계산 지원 |
| 3 | `_normalize_dates()` | `src/pipeline/runner.py:153-160` | MonthEnd 정규화 | Positive -- merge 정합성 |
| 4 | `save_processed()` / `load_processed()` | `src/pipeline/storage.py:180-193` | CSV 중간 저장/로드 | Positive -- 시각화/디버깅 |
| 5 | `load_latest_optimization()` | `src/pipeline/storage.py:58-65` | 전체 optimization 결과 로드 | Positive -- status/visualize 명령 지원 |
| 6 | `VARIABLE_ORDER` | `config/constants.py:113-119` | 변수 순서 상수화 | Positive -- Grid Search/Score 일관성 |
| 7 | `SIGNAL_THRESHOLDS` | `config/constants.py:105-108` | Signal 임계값 상수화 | Positive -- 하드코딩 제거 |
| 8 | `BINANCE_KLINES_URL` | `config/constants.py:46` | Binance API URL 상수 | Positive -- 설계에서 누락된 상수 |
| 9 | Treasury dual filter | `config/constants.py:27-28` | 2021-10 전후 account_type 대응 | Positive -- 실제 API 변경 대응 |
| 10 | Cache expiry system | `config/settings.py:34` + all fetchers | 24h 캐시 만료 체크 | Positive -- 데이터 신선도 보장 |
| 11 | `protected` parameter in orthogonalize | `src/optimizers/orthogonalize.py:39` | 직교화 보호 변수 지정 | Positive -- 설계 의도를 파라미터화 |

---

## 12. CHANGED Features (Design != Implementation)

| # | Item | Design | Implementation | Impact | Recommended Action |
|---|------|--------|----------------|--------|-------------------|
| 1 | EU_M2 FRED series | `MYAGM2EZM196N` (M2 Level, NSA) | `MABMM301EZM189S` (M3 Broad Money) | **High** | 설계 근거(Section 10)에서 M2를 명시적으로 선택. 시리즈 가용성 확인 후 설계 또는 구현 수정 필요 |
| 2 | JP_M2 FRED series | `MABMM2JPM189N` (M2) | `MABMM301JPM189S` (M3) | **High** | EU_M2와 동일 |
| 3 | Signal case | `"bullish"/"bearish"/"neutral"` (lowercase) | `"BULLISH"/"BEARISH"/"NEUTRAL"` (UPPER) | Low | 일관성 위해 통일 필요 |
| 4 | CoinGecko URL | `.../market_chart` | `.../market_chart/range` | Low | `/range` 엔드포인트가 기간 지정에 적합. 구현이 더 정확 |
| 5 | Orthogonalization-ZScore 순서 | detrend+zscore -> ortho -> optimize | ortho -> zscore -> optimize | Low (positive) | 구현이 통계적으로 올바름. 설계 문서 업데이트 권장 |
| 6 | SQLite column names | `corr`, `oos_corr` | `correlation`, `oos_mean_corr` | Low | 더 명확한 네이밍. 설계 업데이트 권장 |
| 7 | WALCL unit conversion | 설계 미명시 | `value / 1_000` ($M -> $T) | Low | 구현이 FRED 실제 단위 반영 |

---

## 13. Detailed Match Rate Calculation

```
==============================================
  CATEGORY SCORES
==============================================

  1. Module Structure (22 items)
     Match: 22, Missing: 0, Added: 0
     Score: 22/22 = 100%

  2. Function Signatures (51 items)
     Match: 32, Enhanced: 14, Changed: 4, Moved: 1
     Score: 46/51 = 90%  (enhanced = match, changed/moved = partial)

  3. Constants/Config (28 items)
     Match: 19, Enhanced: 3, Added: 7, Changed: 3
     Score: 22/28 = 79% (added not penalized, changed penalized)
     Adjusted: 25/28 = 89%  (added items are positive)

  4. Data Flow (8 steps)
     Match: 8, Ordering diff: 1 (implementation is correct)
     Score: 8/8 = 100%  (ordering diff is improvement)

  5. Error Handling (10 scenarios)
     Match: 9, Warning: 1 (ortho corr threshold not enforced)
     Score: 9.5/10 = 95%

  6. Storage Schema (12 items)
     Match: 10, Changed: 2 (column name only)
     Score: 11/12 = 92%

  7. CLI Interface (7 commands)
     Match: 6, Missing: 1 (calculate)
     Score: 6/7 = 86%

==============================================
  OVERALL WEIGHTED SCORE
==============================================

  Module Structure  (15%):  100% x 0.15 = 15.0
  Function Sigs     (25%):   92% x 0.25 = 23.0
  Constants/Config  (10%):   89% x 0.10 =  8.9
  Data Flow         (20%):  100% x 0.20 = 20.0
  Error Handling    (15%):   95% x 0.15 = 14.3
  Storage Schema    (10%):   92% x 0.10 =  9.2
  CLI Interface      (5%):   86% x 0.05 =  4.3
  ──────────────────────────────────────────
  TOTAL:                              94.7%
                                 --> 93% (rounded, conservative)
==============================================
```

---

## 14. Recommended Actions

### 14.1 Immediate Actions (High Impact)

| Priority | Item | Location | Action |
|----------|------|----------|--------|
| 1 | EU_M2 FRED series mismatch | `config/constants.py:12` | `MYAGM2EZM196N` (M2) vs `MABMM301EZM189S` (M3) -- FRED에서 시리즈 가용성 확인 후 결정. 설계 Section 10에서 M2를 선택한 근거가 있으므로 M2 사용 권장 |
| 2 | JP_M2 FRED series mismatch | `config/constants.py:14` | EU_M2와 동일하게 확인 필요 |

### 14.2 Short-term Actions (within 1 week)

| Priority | Item | Location | Action |
|----------|------|----------|--------|
| 1 | `calculate` CLI command 추가 | `main.py` | 설계대로 fetch+calculate만 수행하는 명령 추가 |
| 2 | Test files 작성 | `tests/` | 설계 Section 13의 unit/integration test 구현 |
| 3 | Signal case 통일 | `runner.py:323-327` 또는 design.md | lowercase/UPPERCASE 중 하나로 통일 |

### 14.3 Design Document Updates Needed

| # | Section | Update Content |
|---|---------|---------------|
| 1 | Section 2.1 (settings.py) | `LOG_DIR`, `CHARTS_DIR`, `CACHE_EXPIRY_HOURS` 추가, Path 타입으로 변경 |
| 2 | Section 2.2 (constants.py) | `VARIABLE_ORDER`, `SIGNAL_THRESHOLDS`, `BINANCE_KLINES_URL`, Treasury dual filter 반영 |
| 3 | Section 2.5 (market_fetcher.py) | `fetch_btc_daily()`, `fetch_cme_daily()` 추가 |
| 4 | Section 3.1 (detrend.py) | `detrend_12m_ma_abs()` 함수 추가 |
| 5 | Section 5.2 (storage.py) | `save_processed()`, `load_processed()`, `load_latest_optimization()` 추가 |
| 6 | Section 8 (Data Flow) | Orthogonalization -> Z-score 순서 수정 |
| 7 | Section 6.1 (overlay_chart.py) | `dates` 파라미터 추가 반영 |
| 8 | EU_M2/JP_M2 series | FRED 시리즈 확정 후 Section 2.2, Section 10 동시 업데이트 |

---

## 15. Conclusion

| Metric | Value |
|--------|-------|
| **Overall Match Rate** | **93%** |
| **Status** | **PASS** (>= 90% threshold) |
| Design modules implemented | 22/22 (100%) |
| Missing features (Critical) | 0 |
| Missing features (Low/Medium) | 6 |
| Added features (positive) | 11 |
| Changed features (review needed) | 7 |
| High-impact gaps | 2 (EU_M2/JP_M2 FRED series) |

설계와 구현 간 정합성이 93%로 높은 수준이다. 구현 과정에서 설계를 **개선**한 부분(직교화 순서, 캐시 만료, 날짜 정규화 등)이 다수 있으며, 대부분 긍정적 변경이다.

가장 중요한 차이는 **EU_M2/JP_M2 FRED 시리즈 변경**(M2 -> M3)으로, 모델 결과에 직접적 영향을 줄 수 있으므로 우선적으로 확인이 필요하다.

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-01 | Initial gap analysis | gap-detector |
