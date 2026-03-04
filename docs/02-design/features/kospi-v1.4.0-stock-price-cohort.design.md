# Design: kospi-v1.4.0-stock-price-cohort

> 종목 가격 기반 코호트 상태 판정 + Hybrid Beta 정규화 시뮬레이션

**Plan 참조**: `docs/01-plan/features/kospi-v1.4.0-stock-price-cohort.plan.md`

---

## 1. 아키텍처 변경 개요

```
[기존 v1.3.0]
Cohort.status(current_kospi)          ← KOSPI 지수 기반
StockCohortManager → 종목별 builder → status(current_kospi)  ← 여전히 KOSPI
TriggerMap: shock% → 모든 종목 동일 shock%

[v1.4.0]
Cohort.status_by_stock(current_stock_price)  ← 종목 종가 기반 ★
StockCohortManager → 종목별 builder → status_by_stock(stock_close)  ★
TriggerMap: shock% → hybrid_beta × normalizer → 종목별 차등 shock%  ★
대전제: Σ(adj_shock_i × weight_i) = input_shock%  ★
Residual: 역산 (Top10 기여분 차감)  ★
```

## 2. 데이터 모델 변경

### 2-1. Cohort dataclass 확장

```python
# compute_models.py — Cohort
@dataclass
class Cohort:
    cohort_id: str
    entry_date: str
    entry_kospi: float
    entry_samsung: float
    entry_hynix: float
    initial_amount_billion: float
    remaining_amount_billion: float
    entry_stock_price: float = 0.0  # ★ NEW: 종목별 builder에서 사용하는 진입 종가
```

**영향**: CohortBuilder._create_cohort()에서 entry_stock_price 설정 필요.
기존 Module A (KOSPI 기반)는 entry_stock_price=0 유지 → fallback 동작.

### 2-2. constants.py 신규 상수

```python
# Beta 파라미터
BETA_LOOKBACK = 7              # 거래일
BETA_DOWNSIDE_WEIGHT = 0.6     # 하방 가중치
BETA_UPSIDE_WEIGHT = 0.4       # 상방 가중치
BETA_MIN_KOSPI_RETURN = 0.001  # |KOSPI 수익률| 필터 (0.1%)
BETA_CLIP_MIN = 0.5            # beta 하한
BETA_CLIP_MAX = 3.0            # beta 상한
```

### 2-3. timeseries record 확장 (fetch_daily.py)

```python
# 기존 record에 추가
record["stock_prices"] = {
    "005930": 58200,   # 삼성전자 종가
    "000660": 198000,  # SK하이닉스 종가
    ...
}
```

## 3. 핵심 함수 상세 설계

### 3-1. compute_hybrid_beta()

**위치**: `compute_models.py` (Module A-2 영역)

```python
def compute_hybrid_beta(
    stock_returns: list[float],
    kospi_returns: list[float],
    lookback: int = BETA_LOOKBACK,
    downside_w: float = BETA_DOWNSIDE_WEIGHT,
    min_kospi_ret: float = BETA_MIN_KOSPI_RETURN,
) -> float:
    """Hybrid Beta: 하방 60% + 상방 40%.

    Args:
        stock_returns: 종목 일간 수익률 (최신→과거 순)
        kospi_returns: KOSPI 일간 수익률 (최신→과거 순)

    Returns:
        beta clipped to [0.5, 3.0]

    로직:
        1. |kospi_return| < 0.1% 인 날 제외 (노이즈)
        2. kospi < 0 인 날 → downside_ratios (stock/kospi)
        3. kospi > 0 인 날 → upside_ratios (stock/kospi)
        4. beta = 0.6 × mean(downside) + 0.4 × mean(upside)
        5. fallback: 하락일 ≤1개면 전체 단순평균
        6. clip(0.5, 3.0)
    """
```

### 3-2. normalize_stock_shocks()

**위치**: `compute_models.py` (Module A-2 영역)

```python
def normalize_stock_shocks(
    betas: dict[str, float],       # {ticker: beta}
    weights: dict[str, float],     # {ticker: kospi_weight} (Top 10만, 합 < 1.0)
    kospi_shock_pct: float,        # e.g. -7.0
) -> dict[str, float]:
    """종목별 beta를 정규화하여 가중합 = kospi_shock_pct 보장.

    Returns: {ticker: adjusted_shock_pct, "_residual": residual_shock_pct}

    로직:
        1. raw_shock_i = kospi_shock_pct × beta_i (Top 10)
        2. raw_weighted_top10 = Σ(raw_shock_i × weight_i)
        3. IF raw_weighted_top10 == 0: 모든 종목 kospi_shock_pct 균등 (edge case)
        4. normalizer = (kospi_shock_pct × top10_weight_sum) / raw_weighted_top10
        5. adjusted_shock_i = raw_shock_i × normalizer
        6. residual_shock = (kospi_shock_pct - Σ(adj_shock_i × weight_i)) / residual_weight
        7. 검증: Σ(adj_shock_i × weight_i) + residual_shock × residual_weight == kospi_shock_pct

    정규화 해설:
        - Top 10 부분만 먼저 정규화: beta 비율은 유지하되, 가중합이 (kospi_shock × top10_weight_sum)
        - Residual은 나머지를 정확히 메꿈 → 대전제 100% 보장
    """
```

### 3-3. Cohort.status_by_stock() / collateral_ratio_by_stock()

**위치**: `compute_models.py` — Cohort dataclass

```python
def collateral_ratio_by_stock(self, current_stock_price: float, margin_rate: float = 0.40) -> float:
    """종목 종가 기반 담보비율."""
    if self.entry_stock_price <= 0:
        return self.collateral_ratio(current_stock_price, margin_rate)  # fallback
    price_ratio = current_stock_price / self.entry_stock_price
    return price_ratio / (1 - margin_rate)

def status_by_stock(self, current_stock_price: float, margin_rate: float = 0.40) -> str:
    """종목 종가 기반 상태 판정 (분포 기반 — 기존 status() 로직 재활용)."""
    ratio = self.collateral_ratio_by_stock(current_stock_price, margin_rate)
    # 이하 기존 status()와 동일한 분포 기반 판정
    ...
```

### 3-4. StockCohortManager 개선점

| 메서드 | 현재 (v1.3.0) | 변경 (v1.4.0) |
|--------|---------------|---------------|
| `process_day()` | `kospi=stock_close if stock_close > 0 else kospi` → Cohort에 entry_kospi로 저장 | entry_stock_price도 함께 저장 ★ |
| `get_stock_summary(current_kospi)` | `c.status(current_kospi)` | `c.status_by_stock(stock_close)` + 종목별 현재가 dict 필요 ★ |
| `get_weighted_trigger_map(current_kospi, ...)` | 모든 종목에 동일 shock% | beta 정규화 → 종목별 차등 shock% ★ |

**get_stock_summary() 시그니처 변경**:
```python
def get_stock_summary(self, stock_prices: dict[str, float], current_kospi: float) -> list[dict]:
    """종목별 현재가 기반 status 판정.

    Args:
        stock_prices: {ticker: current_close_price}
        current_kospi: fallback용 (Residual 등)
    """
    for ticker, builder in self.builders.items():
        stock_close = stock_prices.get(ticker, current_kospi)
        for c in builder.active_cohorts:
            st = c.status_by_stock(stock_close)  # ★ 종목가 기반
            ...
```

**get_weighted_trigger_map() 시그니처 변경**:
```python
def get_weighted_trigger_map(
    self, current_kospi: float, current_fx: float,
    stock_prices: dict[str, float],      # ★ NEW
    betas: dict[str, float],             # ★ NEW
    shocks: list[float] | None = None,
) -> list[dict]:
    """종목별 beta 정규화 → 차등 충격 → 반대매매 산출.

    Returns: [{
        shock_pct: -7,
        expected_kospi: 2325,
        stock_shocks: {ticker: adj_shock_pct},  ★ NEW
        margin_call_billion: 1200,
        forced_liq_billion: 800,
        weighted_impact_billion: 600,
    }]
    """
    for shock in shocks:
        adj_shocks = normalize_stock_shocks(betas, self.stock_weights, shock)
        for ticker, builder in self.builders.items():
            stock_shock = adj_shocks.get(ticker, shock)
            stock_close = stock_prices.get(ticker, current_kospi)
            expected_stock = stock_close * (1 + stock_shock / 100)
            # 각 코호트에 expected_stock으로 status_by_stock 판정
            for c in builder.active_cohorts:
                ratio = c.collateral_ratio_by_stock(expected_stock)
                ...
```

### 3-5. CohortBuilder._create_cohort() 확장

```python
def _create_cohort(self, date, amount, kospi, samsung, hynix, stock_price=0):
    c = Cohort(
        cohort_id=date,
        entry_date=date,
        entry_kospi=kospi,
        entry_samsung=samsung,
        entry_hynix=hynix,
        initial_amount_billion=amount,
        remaining_amount_billion=amount,
        entry_stock_price=stock_price,  # ★ NEW
    )
    self.active_cohorts.append(c)
```

**process_day도 stock_price 파라미터 추가**:
```python
def process_day(self, date, credit_balance, prev_credit, kospi,
                samsung=0, hynix=0, stock_price=0):  # ★ NEW
```

### 3-6. fetch_stock_daily_prices()

**위치**: `naver_scraper.py` (기존 fetch_stock_market_caps 옆)

```python
def fetch_stock_daily_prices(tickers_config: dict, start: str, end: str) -> dict[str, pd.DataFrame]:
    """Top 10 종목 일간 종가 시계열 (yfinance batch).

    Returns: {
        "005930": DataFrame(date, close, return_pct),
        "000660": DataFrame(date, close, return_pct),
        ...
    }
    """
```

### 3-7. compute_all_betas()

**위치**: `compute_models.py`

```python
def compute_all_betas(
    ts: list[dict],           # timeseries
    ref_date_idx: int,        # 기준일 인덱스
    tickers: list[str],
    lookback: int = BETA_LOOKBACK,
) -> dict[str, float]:
    """기준일 직전 lookback 거래일의 hybrid beta 산출.

    Returns: {ticker: beta, ...}

    로직:
        1. ts[ref_date_idx - lookback : ref_date_idx] 구간 추출
        2. 각 날짜의 kospi return + stock return 계산
        3. compute_hybrid_beta() 호출
    """
```

## 4. export_web.py 변경

### STOCK_CREDIT 구조 확장

```javascript
export const STOCK_CREDIT = {
  stocks: [
    {
      ticker: "005930",
      name: "삼성전자",
      group: "A",
      credit_billion: 16956.69,
      kospi_weight_pct: 52.68,
      current_price: 58200,             // ★ NEW
      beta: 1.38,                        // ★ NEW (최신 7일 hybrid beta)
      status_breakdown: {                // ★ 종목가 기반으로 변경
        safe: 14200, watch: 1800,
        margin_call: 956, forced_liq: 0,
      },
    },
    ...
  ],
  betas: {                               // ★ NEW: 전체 beta 요약
    "005930": 1.38,
    "000660": 1.72,
    ...
    "_lookback": 7,
    "_method": "hybrid_60_40",
  },
  weighted_trigger_map: [
    {
      shock_pct: -7,
      expected_kospi: 2325,
      stock_shocks: {                    // ★ NEW: 종목별 차등 충격
        "005930": -9.1,
        "000660": -11.7,
        "_residual": -4.2,
      },
      margin_call_billion: 1200,
      forced_liq_billion: 800,
      weighted_impact_billion: 600,
    },
    ...
  ],
  stock_weighted: true,
};
```

## 5. Frontend 변경

### 5-1. StockCreditBreakdown 개선

**추가 컬럼**: Beta, 현재가, 종목가 기반 상태

```
| 종목 | 신용잔고 | 비중 | KOSPI가중 | Beta | 현재가 | 상태 |
|------|----------|------|-----------|------|--------|------|
| ● 삼성전자 005930 | 16.9조 | 52.7% | 52.7% | 1.38 | 58,200 | ██ 안전 91% |
| ● SK하이닉스 000660 | 8.6조 | 26.8% | 26.8% | 1.72 | 198,000 | ██ 안전 92% |
```

### 5-2. 트리거맵 종목별 충격 표시

기존: `shock_pct` 하나만 표시
변경: 종목별 `stock_shocks` 펼침 (expand row)

```
| 충격 | 예상 KOSPI | 마진콜 | 반대매매 | 가중영향 |
|------|------------|--------|----------|----------|
| -7%  | 2,325      | 1,200B | 800B     | 600B     |
|   └ 삼전 -9.1%, 하닉 -11.7%, 현대차 -3.9%, ... 기타 -4.2% |
```

### 5-3. 시뮬레이터 백테스트 Beta 표시

백테스트 모드에서 기준일 선택 시:
- 해당 기준일 직전 7거래일 beta 자동 산출/표시
- "이 beta로 충격 -7% 적용 시 삼성 -X%, 하닉 -Y% ..." 미리보기

## 6. 구현 순서 (파일별)

| Step | 파일 | 작업 | 의존성 |
|------|------|------|--------|
| 1 | `constants.py` | BETA_* 상수 6개 추가 | 없음 |
| 2 | `compute_models.py` | Cohort: entry_stock_price, status_by_stock(), collateral_ratio_by_stock() | Step 1 |
| 3 | `compute_models.py` | CohortBuilder: process_day + _create_cohort에 stock_price 파라미터 | Step 2 |
| 4 | `naver_scraper.py` | fetch_stock_daily_prices() 추가 | 없음 |
| 5 | `compute_models.py` | compute_hybrid_beta(), compute_all_betas() | Step 1 |
| 6 | `compute_models.py` | normalize_stock_shocks() | Step 5 |
| 7 | `compute_models.py` | StockCohortManager: process_day 종목가 전달, get_stock_summary 종목가 기반 | Step 2,3 |
| 8 | `compute_models.py` | StockCohortManager: get_weighted_trigger_map beta 정규화 | Step 6,7 |
| 9 | `fetch_daily.py` | stock_prices를 timeseries에 포함 | Step 4 |
| 10 | `compute_models.py` | run_all_models()에서 beta 산출 + stock_prices 전달 | Step 5,7,8,9 |
| 11 | `export_web.py` | STOCK_CREDIT 구조 확장 (betas, stock_prices, stock_shocks) | Step 10 |
| 12 | `shared/terms.jsx` | hybrid_beta, normalized_shock, stock_price_status 용어 추가 | 없음 |
| 13 | `CohortAnalysis.jsx` | StockCreditBreakdown: beta/현재가/상태 컬럼 + 트리거맵 종목별 충격 | Step 11,12 |
| 14 | 검증 | compute_models 실행 → export → 프론트 확인 | All |

## 7. 테스트 시나리오

### 7-1. Beta 정규화 검증
```
Input: betas={삼전:1.4, 하닉:1.8, 현대차:0.6}, weights={삼전:0.527, 하닉:0.268, 현대차:0.06}
shock=-7%
Expected: Σ(adj_shock_i × weight_i) + residual_shock × residual_weight == -7.00%
```

### 7-2. 3/3-3/4 백테스트
```
기준일: 2026-02-27
충격: -7.25% (3/3 실제 KOSPI 하락)
Expected: 삼전 beta >1.0 → 삼전 코호트 중 최근 고점 진입분이 margin_call 판정
```

### 7-3. Edge cases
- KOSPI 0% 변동일 연속 7일 → beta 계산 불가 → fallback to 1.0
- 종목 종가 0 (상폐 등) → entry_stock_price=0 → fallback to KOSPI 기반
- Residual weight ≈ 0 → residual_shock 계산 skip
