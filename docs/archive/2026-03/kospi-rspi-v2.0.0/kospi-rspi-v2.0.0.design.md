# KOSPI RSPI v2.0.0 Design Document — Phase A+B: Backend + Frontend Pivot

> **Summary**: VLPI → RSPI 백엔드 전면 재설계 (rspi_engine.py + constants + compute_models + export_web)
>
> **Project**: KOSPI Crisis Detector
> **Version**: v2.0.0
> **Author**: Claude + sungmin
> **Date**: 2026-03-05
> **Status**: Draft
> **Planning Doc**: [kospi-rspi-v2.0.0.plan.md](../../01-plan/features/kospi-rspi-v2.0.0.plan.md)

---

## 1. Overview

### 1.1 Design Goals

- VLPI(0~100, 단방향) → RSPI(-100~+100, 양방향) 엔진 교체
- 정책 쇼크(V3) 완전 제거, 감쇠력 4변수(D1~D4) 신규 추가
- D1: 야간시장 4소스(EWY+KORU+야간선물+US) + coherence bonus
- D2: 신용잔고 D+1 시차 정확 처리
- 기존 vlpi_engine.py 함수 최대 재사용 (독립 복사 후 수정)
- 삼성 코호트 데이터로 3/4(+17.9), 3/5(-35.0) 방향 검증

### 1.2 Design Principles

- **독립 파일**: rspi_engine.py는 vlpi_engine.py를 import하지 않음 (의존성 차단)
- **Graceful Degradation**: 야간선물/KORU 미확보 시 가용 소스로 가중치 재배분
- **D+1 시차 명시**: credit_data date = 잔고 기준일, RSPI는 항상 T-1일 잔고 사용

---

## 2. Architecture

### 2.1 Data Flow

```
fetch_daily.py (데이터 수집)
  ├── EWY, KORU, ^GSPC (yfinance) → overnight_data
  ├── KOFIA 신용잔고 → credit_data (date = 잔고 기준일)
  └── KRX 외국인 수급 → foreign_flows
        │
        ▼
compute_models.py (모델 실행)
  ├── CohortBuilder → cohorts
  ├── RSPIEngine.calculate_for_date() → rspi_result
  └── RSPIEngine.calculate_scenario_matrix() → scenario_matrix
        │
        ▼
export_web.py (웹 데이터 생성)
  ├── RSPI_DATA (latest + scenario_matrix)
  └── RSPI_CONFIG (cf/df variables, weights, levels)
        │
        ▼
kospi_data.js (프론트엔드)
```

### 2.2 File Changes Summary

| File | Action | Scope |
|------|--------|-------|
| `kospi/config/constants.py` | Modify | VLPI_* → RSPI_* 상수, OVERNIGHT_* 추가 |
| `kospi/scripts/rspi_engine.py` | **New** | 양방향 RSPI 엔진 (CF-DF) |
| `kospi/scripts/compute_models.py` | Modify | VLPIEngine → RSPIEngine 교체 |
| `kospi/scripts/export_web.py` | Modify | VLPI_DATA/CONFIG → RSPI_DATA/CONFIG |
| `kospi/scripts/fetch_daily.py` | Modify | KORU, ^GSPC ticker 추가 |

---

## 3. Step 1: constants.py 변경

### 3.1 삭제할 상수 (현재 lines 91-143)

```python
# 삭제:
VLPI_DEFAULT_WEIGHTS          # → RSPI_CF_WEIGHTS로 대체
POLICY_SHOCK_MAP              # → 정책 쇼크 제거
EWY_GAP_WEIGHTS               # → OVERNIGHT_WEIGHTS로 대체 (3소스→4소스)
EWY_GAP_DIVISOR               # → 소스별 개별 DIVISOR로 대체
VLPI_SENSITIVITY              # → RSPI_SENSITIVITY
VLPI_SIGMOID_K                # → RSPI_SIGMOID_K
VLPI_SIGMOID_MID              # → RSPI_SIGMOID_MID
VLPI_POLICY_MULTIPLIER        # → 삭제 (정책 제거)
VLPI_LIQUIDITY_NORMAL         # → RSPI_LIQUIDITY_FACTOR (단일값)
VLPI_LIQUIDITY_CRISIS         # → 삭제 (정책 분기 제거)
```

### 3.2 신규/변경 상수

```python
# ── RSPI Cascade Force (CF) Weights ──
RSPI_CF_WEIGHTS = {
    "cf1": 0.30,  # V1: 주의구간 코호트 비중
    "cf2": 0.25,  # V2: 연속 하락 심각도
    "cf3": 0.25,  # V3: 개인 수급 방향
    "cf4": 0.20,  # V4: 신용잔고 가속 모멘텀
}

# ── RSPI Damping Force (DF) Weights ──
RSPI_DF_WEIGHTS = {
    "df1": 0.30,  # D1: 야간시장 반등 강도
    "df2": 0.20,  # D2: 신용잔고 유입률
    "df3": 0.25,  # D3: 외국인 매도 소진도
    "df4": 0.25,  # D4: 안전 코호트 버퍼
}

# ── D1: Overnight Recovery Sources ──
OVERNIGHT_WEIGHTS = {
    "ewy":       0.30,  # iShares MSCI South Korea ETF (1x)
    "koru":      0.25,  # Direxion Daily South Korea Bull 3X
    "futures":   0.25,  # KOSPI200 야간선물
    "us_market": 0.20,  # S&P500
}
OVERNIGHT_EWY_DIVISOR = 5.0       # 5% 반등 = signal 1.0
OVERNIGHT_KORU_DIVISOR = 15.0     # 15% 반등 = signal 1.0 (3x)
OVERNIGHT_FUTURES_DIVISOR = 8.0   # 8% = 상한가 = signal 1.0
OVERNIGHT_US_DIVISOR = 3.0        # 3% 반등 = signal 1.0

# ── RSPI Impact Function ──
RSPI_SENSITIVITY = 0.15
RSPI_SIGMOID_K = 0.08
RSPI_SIGMOID_MID = 50
RSPI_LIQUIDITY_FACTOR = 0.5      # 단일 값 (정책 분기 제거)

# ── RSPI Level Thresholds ──
RSPI_LEVELS = {
    "critical":  40,   # +40~+100: 캐스케이드 위험
    "high":      20,   # +20~+40: 하락 우세
    "medium":     0,   # 0~+20: 약한 하락
    "low":      -20,   # -20~0: 균형~약한 반등
    # -100~-20: 반등 압력 → "none"
}
```

---

## 4. Step 2: rspi_engine.py — 핵심 엔진

### 4.1 재사용 함수 (vlpi_engine.py에서 복사, 변경 없음)

| Function | Purpose | Returns |
|----------|---------|---------|
| `calc_collateral_ratio(current_price, entry_price)` | 담보비율 계산 | float (%) |
| `classify_status_6(collateral_ratio)` | 6단계 상태 분류 | str |
| `calc_caution_zone_pct(current_price, cohorts)` | V1: 주의구간 비중 | 0~1 |
| `calc_cumulative_decline(price_data, idx, max_lookback=5)` | V2: 연속 하락 심각도 | 0~1 |
| `calc_individual_flow_direction(flow_data, idx)` | V3: 개인 수급 방향 | 0~1 |

### 4.2 수정 함수

#### `calc_credit_accel_momentum()` (V4, 기존 calc_credit_momentum 가속 부분만)

```python
def calc_credit_accel_momentum(
    credit_data: list[dict], idx: int, lookback: int = 3,
) -> float:
    """V4: 신용잔고 감소 시 가속 모멘텀.

    기존 calc_credit_momentum에서 가속(감소) 부분만 추출.
    증가(물타기)는 D2에서 감쇠력으로 처리.

    Returns: 0 (잔고 증가/유지) ~ 0.7 (급감)
    """
    pct_change = (current - past) / past * 100
    if pct_change >= 0:    return 0.0   # 증가/유지 → 가속 없음 (D2에서 처리)
    elif pct_change > -1:  return 0.3   # 소폭 감소
    else:                  return 0.7   # 급감 = 투매 진행
```

### 4.3 신규 함수

#### D1: `calc_overnight_recovery()`

```python
def calc_overnight_recovery(
    ewy_pct: float | None = None,
    koru_pct: float | None = None,
    kospi_futures_pct: float | None = None,
    us_market_pct: float | None = None,
) -> float:
    """감쇠력 D1: 야간시장 반등 강도 (4소스 + coherence).

    Algorithm:
    1. 각 소스 signal = max(pct / divisor, 0) (양수 = 반등만 감쇠로 인정)
       - ewy: pct / 5.0
       - koru: pct / 15.0 (3x 레버리지)
       - futures: pct / 8.0
       - us_market: pct / 3.0
    2. None 소스 → 가용 소스에 가중치 재배분
    3. weighted_signal = sum(weight_i * signal_i)
    4. coherence bonus:
       - 가용 소스 모두 양수 → ×1.3 (방향 일치 = 강한 반등)
       - 방향 혼재 → ×0.7
       - 가용 소스 모두 음수 → 0 (전면 하락, 감쇠 없음)
    5. return clamp(weighted_signal * coherence, 0, 1)

    Returns: 0 (감쇠 없음) ~ 1 (최대 감쇠)
    """
```

#### D2: `calc_credit_inflow_damping()`

```python
def calc_credit_inflow_damping(
    credit_data: list[dict], idx: int,
    price_data: list[dict],
) -> float:
    """감쇠력 D2: 하락일 신용 증가 = 저가매수 유입.

    *** D+1 시차 처리 ***
    credit_data[idx] = T-1일 잔고 (T일에 공시)
    price_data[idx] = T-1일 종가

    Algorithm:
    1. credit_change = (credit[idx] - credit[idx-1]) / credit[idx-1]
    2. price_change = price_data[idx]["change_pct"]  # T-1일 등락률
    3. Case:
       - 하락(-5%+) + 잔고 증가(+1%+) → 0.7~0.8 (강한 감쇠)
       - 하락(-2%~-5%) + 잔고 증가 → 0.4~0.6
       - 하락 + 잔고 감소 → 0.0 (투매 진행, 감쇠 없음)
       - 상승 + 잔고 증가 → 0.1~0.3 (약한 감쇠)
       - 데이터 부족 → 0.3 (중립 기본값)

    Returns: 0~1
    """
```

#### D3: `calc_foreign_exhaustion()`

```python
def calc_foreign_exhaustion(
    flow_data: list[dict], idx: int, lookback: int = 5,
) -> float:
    """감쇠력 D3: 외국인 매도 소진도.

    Algorithm:
    1. recent_flows = flow_data[idx-lookback:idx+1]  # 최근 N일 외국인 순매수
    2. 패턴 매칭:
       - 순매수 전환 (prev 대량매도 → curr 순매수) → 0.9
       - 매도 규모 반감 (|curr| < |prev| * 0.5) → 0.5
       - 소규모 매도 지속 → 0.3
       - 대량 매도 가속 → 0.0
    3. 3일+ 연속 순매수 확인 시 bonus ×1.2

    Returns: 0~1
    """
```

#### D4: `calc_safe_buffer()`

```python
def calc_safe_buffer(v1_caution_pct: float) -> float:
    """감쇠력 D4: 안전 코호트 버퍼 (V1의 역수, 비선형).

    safe_pct = 1.0 - v1_caution_pct

    비선형 변환:
    - safe_pct >= 0.90 → 1.0 (방화벽 건재)
    - safe_pct >= 0.70 → 0.7 + (safe_pct - 0.70) * 1.5
    - safe_pct >= 0.40 → 0.2 + (safe_pct - 0.40) * 1.67
    - safe_pct < 0.40  → max(0.05, safe_pct * 0.5)

    Returns: 0.05~1.0
    """
```

#### `calc_rspi()` — 종합 함수

```python
def calc_rspi(
    v1: float, v2: float, v3: float, v4: float,
    d1: float, d2: float, d3: float, d4: float,
    cf_weights: dict = None, df_weights: dict = None,
) -> dict:
    """RSPI = CF - DF.

    Algorithm:
    1. Normalize:
       - v4: range 0~0.7 → 0~1: v4 / 0.7
       - 나머지: 이미 0~1 범위
    2. CF = (cf1*V1_n + cf2*V2_n + cf3*V3_n + cf4*V4_n) / sum(cf_weights) * 100
    3. DF = (df1*D1 + df2*D2 + df3*D3 + df4*D4) / sum(df_weights) * 100
    4. RSPI = CF - DF (clamp -100~+100)
    5. Level: critical(40+), high(20~40), medium(0~20), low(-20~0), none(-100~-20)

    Returns: {
        "rspi": float,              # -100~+100
        "cascade_force": float,     # 0~100
        "damping_force": float,     # 0~100
        "cascade_risk": str,        # "none"|"low"|"medium"|"high"|"critical"
        "cf_components": {          # 각 변수 기여분
            "caution_zone": float, "cumulative_decline": float,
            "individual_flow": float, "credit_accel": float,
        },
        "df_components": {
            "overnight_recovery": float, "credit_inflow": float,
            "foreign_exhaustion": float, "safe_buffer": float,
        },
        "raw_variables": {"v1":..,"v2":..,"v3":..,"v4":..,"d1":..,"d2":..,"d3":..,"d4":..},
    }
    """
```

### 4.4 RSPIEngine 클래스

```python
class RSPIEngine:
    """RSPI 계산 + Impact 함수 통합 엔진."""

    def __init__(self, cf_weights=None, df_weights=None):
        self.cf_weights = cf_weights or RSPI_CF_WEIGHTS
        self.df_weights = df_weights or RSPI_DF_WEIGHTS
        self.history = []

    def calculate_for_date(
        self,
        date: str,
        ts: list[dict],
        cohorts: list[dict],           # [{entry_price, weight}]
        overnight_data: dict | None,   # {ewy_pct, koru_pct, futures_pct, us_market_pct}
        foreign_flows: list[dict] | None,  # D3용
        samsung_credit_bn: float | None = None,
        current_price: int | None = None,
        adv_shares_k: float | None = None,
    ) -> dict:
        """특정 날짜의 RSPI + Impact 계산.

        Steps:
        1. Find idx of date in ts
        2. V1 = calc_caution_zone_pct(current_kospi, cohorts)
        3. V2 = calc_cumulative_decline(ts, idx)
        4. V3 = calc_individual_flow_direction(ts, idx)
        5. V4 = calc_credit_accel_momentum(ts, idx)
        6. D1 = calc_overnight_recovery(overnight_data)
        7. D2 = calc_credit_inflow_damping(ts, idx, ts)
        8. D3 = calc_foreign_exhaustion(foreign_flows or ts, idx)
        9. D4 = calc_safe_buffer(V1)
        10. rspi_result = calc_rspi(V1~V4, D1~D4)
        11. Impact (RSPI > 0일 때만): estimate_selling_volume + estimate_price_impact
        12. Store in history
        """

    def calculate_scenario_matrix(
        self,
        v1, v2, v3, v4, d2, d3, d4,   # 고정 변수
        samsung_credit_bn, current_price, adv_shares_k,
    ) -> list[dict]:
        """D1(야간시장) 시나리오 매트릭스.

        Presets:
        - 낙관적: ewy=+2.5%, koru=+7.5%, us=+1.5% → D1 높음
        - 기본:   ewy=-1.0%, koru=-3.0%, us=-0.5% → D1 중간
        - 비관적: ewy=-4.0%, koru=-12%, us=-2.5% → D1 낮음

        각 프리셋: D1 재계산 → RSPI → Impact
        """

    def get_output(self) -> dict:
        """model_output["rspi"]에 저장할 데이터."""
        return {
            "history": self.history,
            "weights": {"cf": self.cf_weights, "df": self.df_weights},
            "latest": self.history[-1] if self.history else None,
        }
```

### 4.5 Impact Function (기존 유지, 정책 분기만 제거)

```python
# estimate_selling_volume(): RSPI > 0일 때만 실행
# - vlpi_ratio → rspi_ratio: sigmoid(max(rspi, 0))
# - policy_multiplier 파라미터 제거
# - 나머지 로직 동일

# estimate_price_impact(): 변경 없음
# - liquidity_factor: 단일 값 0.5 (정책 분기 제거)
```

---

## 5. Step 3: 검증 데이터 (samsung_cohorts.json)

### 5.1 3/4(화) RSPI 계산 검증

```
입력:
  V1 = 0.037 (주의구간 3.7%)
  V2 = 0.76 (연속 3일 하락, 누적 -7.8%)
  V3 = 1.0 (전일 대량매수 → 당일 항복)
  V4 = 0.30 (신용 소폭 감소)
  D1 = 0.0 (야간 데이터 미확보 가정)
  D2 = 0.0 (전일 잔고 감소)
  D3 = 0.0 (외국인 대량 매도 지속)
  D4 = 0.96 (안전 96.3%)

CF = (0.30×0.037 + 0.25×0.76 + 0.25×1.0 + 0.20×(0.30/0.7)) × 100 ≈ 48.9
DF = (0.30×0.0 + 0.20×0.0 + 0.25×0.0 + 0.25×0.96) × 100 ≈ 24.0~31.0
RSPI = 48.9 - 31.0 ≈ +17.9 → 하락 압력 (실제: -11.74%) ✓
```

### 5.2 3/5(수) RSPI 계산 검증

```
입력:
  V1 = 0.070 (주의구간 7.0%, 전일 폭락으로 증가)
  V2 = 0.76 (4일 연속 하락)
  V3 = 1.0 (항복 패턴)
  V4 = 0.30 (잔고 증가=투매 중단)
  D1 = 0.95 (야간선물 상한가 +8%)
  D2 = 0.63 (폭락일 잔고 +2.08% = 강한 저가매수)
  D3 = 0.90 (외국인 순매수 전환)
  D4 = 0.93 (안전 93%)

CF = (0.30×0.070 + 0.25×0.76 + 0.25×1.0 + 0.20×(0.30/0.7)) × 100 ≈ 53.6
DF = (0.30×0.95 + 0.20×0.63 + 0.25×0.90 + 0.25×0.93) × 100 ≈ 88.6
RSPI = 53.6 - 88.6 ≈ -35.0 → 반등 압력 (실제: +11.09%) ✓
```

---

## 6. Step 4: compute_models.py 변경

### 6.1 Import 변경

```python
# 기존:
from scripts.vlpi_engine import VLPIEngine
# 신규:
from scripts.rspi_engine import RSPIEngine
```

### 6.2 데이터 준비 변경

```python
# 기존 EWY만 → 4소스 overnight_data
overnight_data = {
    "ewy_pct": latest.get("ewy_change_pct"),
    "koru_pct": latest.get("koru_change_pct"),          # 신규
    "kospi_futures_pct": latest.get("kospi_futures_pct"), # 초기 None
    "us_market_pct": latest.get("us_market_change_pct"),  # 신규
}

# 외국인 수급 (D3용)
foreign_flows = [
    {"foreign": r.get("foreign_billion", 0) * 10000}  # 조원→억원
    for r in ts[-10:]
]
```

### 6.3 엔진 호출 변경

```python
# 기존:
vlpi_engine = VLPIEngine()
vlpi_result = vlpi_engine.calculate_for_date(date, ts, cohorts, events, ewy)
model_output["vlpi"] = vlpi_engine.get_output()

# 신규:
rspi_engine = RSPIEngine()
rspi_result = rspi_engine.calculate_for_date(
    date=latest.get("date", ""),
    ts=ts,
    cohorts=vlpi_cohorts,  # 기존 코호트 포맷 재사용
    overnight_data=overnight_data,
    foreign_flows=foreign_flows,
    samsung_credit_bn=samsung_credit_bn,
    current_price=int(samsung_price),
    adv_shares_k=samsung_adv,
)
rspi_result_data = rspi_engine.get_output()
rspi_result_data["scenario_matrix"] = rspi_engine.calculate_scenario_matrix(...)
model_output["rspi"] = rspi_result_data
```

---

## 7. Step 5: export_web.py 변경

### 7.1 RSPI_DATA 구조

```python
rspi_raw = model_output.get("rspi", {})
rspi_data = {
    "history": rspi_raw.get("history", []),
    "latest": rspi_raw.get("latest"),
    "scenario_matrix": rspi_raw.get("scenario_matrix", []),
}
```

### 7.2 RSPI_CONFIG 구조

```python
rspi_config = {
    "weights": rspi_raw.get("weights", {
        "cf": RSPI_CF_WEIGHTS, "df": RSPI_DF_WEIGHTS
    }),
    "status_thresholds": STATUS_THRESHOLDS,
    "cf_variables": [
        {"key": "v1", "label": "주의구간 비중", "desc": "담보비율 140~170% 코호트 비중", "range": "0~1"},
        {"key": "v2", "label": "연속 하락", "desc": "연속 하락일수 + 누적 하락률", "range": "0~1"},
        {"key": "v3", "label": "개인 수급", "desc": "전일 개인 순매수 패턴", "range": "0~1"},
        {"key": "v4", "label": "신용 가속", "desc": "신용잔고 감소 가속 모멘텀", "range": "0~0.7"},
    ],
    "df_variables": [
        {"key": "d1", "label": "야간 반등", "desc": "EWY/KORU/야간선물/US 반등 + coherence", "range": "0~1"},
        {"key": "d2", "label": "신용 유입", "desc": "하락일 신용증가 = 저가매수 (D+1 시차)", "range": "0~1"},
        {"key": "d3", "label": "외국인 소진", "desc": "외국인 매도 규모 감소/전환", "range": "0~1"},
        {"key": "d4", "label": "안전 버퍼", "desc": "안전구간 코호트 비중 (방화벽)", "range": "0~1"},
    ],
    "levels": [
        {"min": -100, "max": -20, "label": "반등 압력", "color": "#4caf50"},
        {"min": -20,  "max": 0,   "label": "균형",      "color": "#8bc34a"},
        {"min": 0,    "max": 20,  "label": "약한 하락",  "color": "#ffc107"},
        {"min": 20,   "max": 40,  "label": "하락 우세",  "color": "#ff9800"},
        {"min": 40,   "max": 100, "label": "캐스케이드", "color": "#f44336"},
    ],
    "impact_params": {
        "sensitivity": RSPI_SENSITIVITY,
        "sigmoid_k": RSPI_SIGMOID_K,
        "sigmoid_mid": RSPI_SIGMOID_MID,
    },
}
```

### 7.3 Export 변수명 변경

```python
# kospi_data.js에서:
# 기존: export const VLPI_DATA = ...
#        export const VLPI_CONFIG = ...
# 신규: export const RSPI_DATA = ...
#        export const RSPI_CONFIG = ...
```

---

## 8. Step 5b: fetch_daily.py 변경

### 8.1 YF_SYMBOLS 추가

```python
YF_SYMBOLS = {
    ...existing...,
    "ewy": "EWY",
    "koru": "KORU",      # 신규: Direxion 3x Korea Bull
    "sp500": "^GSPC",    # 신규: S&P500
}
```

### 8.2 변동률 계산 추가

```python
# extract_date_data() 내:
# KORU 변동률 (EWY와 동일 로직)
if result.get("koru_close") is not None:
    # 전일 대비 변동률 계산
    result["koru_change_pct"] = ...

# S&P500 변동률
if result.get("sp500_close") is not None:
    result["us_market_change_pct"] = ...
```

---

## 9. Implementation Order

```
Step 1: constants.py 수정 (VLPI→RSPI 상수)
  ↓
Step 2: rspi_engine.py 생성 (완전 신규 파일)
  ↓
Step 3: rspi_engine 단위 검증 (3/4, 3/5 방향 일치)
  ↓
Step 4: compute_models.py 수정 (VLPIEngine→RSPIEngine)
  ↓
Step 5a: export_web.py 수정 (VLPI→RSPI export)
  ↓
Step 5b: fetch_daily.py 수정 (KORU, ^GSPC 추가)
```

---

---

## 10. Phase B: Frontend Pivot

### 10.1 File Changes

| File | Action | Scope |
|------|--------|-------|
| `colors.js` | Modify | VLPI 6색 → RSPI CF 4색 + DF 4색 |
| `shared/terms.jsx` | Modify | VLPI 용어 → RSPI 용어 |
| `CohortAnalysis.jsx` | Modify | Import, 변수맵, Gauge, Breakdown, ImpactTable, Section 2 |

### 10.2 colors.js

```javascript
// 기존 (6 VLPI 변수):
vlpiV1~vlpiV6

// 신규 (CF 4 + DF 4):
rspiCF1: "#5c6bc0",  // V1 주의구간 (indigo)
rspiCF2: "#ef5350",  // V2 연속하락 (red)
rspiCF3: "#f59e0b",  // V3 개인수급 (amber)
rspiCF4: "#26a69a",  // V4 신용가속 (teal)
rspiDF1: "#4caf50",  // D1 야간반등 (green)
rspiDF2: "#42a5f5",  // D2 신용유입 (blue)
rspiDF3: "#ab47bc",  // D3 외국인소진 (purple)
rspiDF4: "#8bc34a",  // D4 안전버퍼 (light green)
```

### 10.3 terms.jsx

```javascript
// 기존: pre_vlpi, vlpi_gauge, vlpi_component, vlpi_impact
// 신규:
rspi: "RSPI (Retail Selling Pressure Index). 개인 매도 압력 지수 (-100~+100). CF(가속력)-DF(감쇠력)"
rspi_gauge: "RSPI 게이지. 반등압력(-100)~캐스케이드(+100) 5단계"
rspi_cf: "가속력(CF) 4변수: V1주의구간+V2하락+V3개인수급+V4신용가속"
rspi_df: "감쇠력(DF) 4변수: D1야간반등+D2신용유입+D3외국인소진+D4안전버퍼"
rspi_scenario: "D1(야간시장) 시나리오별 RSPI 예측과 매도압력"
```

### 10.4 CohortAnalysis.jsx

#### Import 변경
```javascript
// 기존:
import { VLPI_DATA, VLPI_CONFIG } from "./data/kospi_data";
// 신규:
import { RSPI_DATA, RSPI_CONFIG } from "./data/kospi_data";
```

#### Variable Mapping 변경
```javascript
// 기존: VLPI_VAR_KEY_MAP (v1~v6), VLPI_VAR_COLORS
// 신규: CF/DF component key → color 매핑
const CF_COMPONENT_COLORS = {
  caution_zone: C.rspiCF1, cumulative_decline: C.rspiCF2,
  individual_flow: C.rspiCF3, credit_accel: C.rspiCF4,
};
const DF_COMPONENT_COLORS = {
  overnight_recovery: C.rspiDF1, credit_inflow: C.rspiDF2,
  foreign_exhaustion: C.rspiDF3, safe_buffer: C.rspiDF4,
};
```

#### RSPIGauge (VLPIGauge 대체)
- 범위: 0~100 → -100~+100
- 5단계 (반등압력/균형/약한하락/하락우세/캐스케이드)
- 바늘 각도: -100=왼쪽(180°), +100=오른쪽(0°)
- 중앙(0) 표시선

#### DualBreakdown (ComponentBreakdown 대체)
- CF와 DF를 2열 그리드로 표시
- 각 변수 기여분 막대 + 수치
- CF 합계, DF 합계, RSPI = CF - DF 표시

#### ImpactTable 변경
- "정책쇼크" 열 제거
- "EWY 변동" → "야간시장" (EWY/KORU 대표값)
- "Pre-VLPI" → "RSPI"
- 매도추정/매도비율은 유지 (RSPI > 0일 때만)

#### Section 2 변경
- "VLPI 대시보드" → "RSPI 대시보드"
- 가이드 박스: VLPI 설명 → RSPI 양방향 설명
- 데이터 키: pre_vlpi → rspi, level → cascade_risk
- components → cf_components/df_components

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-03-05 | Initial Phase A design | Claude + sungmin |
| 0.2 | 2026-03-05 | Phase B frontend design added | Claude + sungmin |
