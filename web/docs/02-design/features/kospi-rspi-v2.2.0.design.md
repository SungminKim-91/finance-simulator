# KOSPI RSPI v2.2.0 -- Design Document

> Feature: `kospi-rspi-v2.2.0`
> Created: 2026-03-06
> Status: Design
> Plan: `docs/01-plan/features/kospi-rspi-v2.2.0.plan.md`

## 1. Architecture Overview

### 1.1 Before (v2.0.0 CF/DF)

```
CF = w(cf1)*V1 + w(cf2)*V2 + w(cf3)*V3 + w(cf4)*V4  (0~100)
DF = w(df1)*D1 + w(df2)*D2 + w(df3)*D3 + w(df4)*D4  (0~100)
RSPI = CF - DF  (-100~+100, positive=selling)
```

### 1.2 After (v2.2.0 5-var + VA)

```
raw = w1*V1 + w2*V2 + w3*V3 + w4*V4 + w5*V5
RSPI = -1 * raw * VolumeAmp * 100
Range: -100 ~ +100 (negative=selling, positive=rebound)
```

## 2. File Changes

### 2.1 `kospi/config/constants.py`

DELETE:
- RSPI_CF_WEIGHTS
- RSPI_DF_WEIGHTS
- RSPI_LEVELS (5-level positive=selling)
- VLPI_* deprecated constants

ADD:
```python
RSPI_WEIGHTS = {"v1": 0.25, "v2": 0.20, "v3": 0.25, "v4": 0.20, "v5": 0.10}

RSPI_LEVELS = [
    {"min": -100, "max": -40, "key": "extreme_sell",   "label": "극단 매도"},
    {"min": -40,  "max": -20, "key": "strong_sell",    "label": "강한 매도"},
    {"min": -20,  "max": -5,  "key": "mild_sell",      "label": "약한 매도"},
    {"min": -5,   "max": 5,   "key": "neutral",        "label": "중립"},
    {"min": 5,    "max": 20,  "key": "mild_rebound",   "label": "약한 반등"},
    {"min": 20,   "max": 40,  "key": "strong_rebound",  "label": "강한 반등"},
    {"min": 40,   "max": 100, "key": "extreme_rebound", "label": "극단 반등"},
]

# V2: Foreign direction
V2_LOOKBACK = 20
V2_DIVISOR = 2.0

# V4: Individual flow thresholds (억원)
V4_CAPITULATION_PREV = 300   # 대량 매수 -> 급감 = 항복
V4_CAPITULATION_CURR = 50
V4_LARGE_BUY = 300           # 대량 매수 유지
V4_DECLINE_RATIO = 0.3       # 매수 급감 비율

# V5: Credit momentum
V5_DIVISOR = 2.0

# VA: Volume amplifier
VA_FLOOR = 0.3
VA_CEILING = 2.0
VA_LOG_SCALE = 0.5
```

KEEP:
- OVERNIGHT_WEIGHTS, OVERNIGHT_*_DIVISOR (V3)
- RSPI_SENSITIVITY, RSPI_SIGMOID_* (Impact)
- LOAN_RATE, STATUS_THRESHOLDS, etc.

### 2.2 `kospi/scripts/rspi_engine.py` -- Full Rewrite

#### Functions to DELETE (entire body):
- calc_caution_zone_pct()
- calc_cumulative_decline()
- calc_individual_flow_direction()
- calc_credit_accel_momentum()
- calc_overnight_recovery()
- calc_credit_inflow_damping()
- calc_foreign_exhaustion()
- calc_safe_buffer()
- calc_rspi() (CF-DF version)

#### Functions to KEEP:
- calc_collateral_ratio()
- classify_status_6()
- estimate_selling_volume()
- estimate_price_impact()

#### New Functions:

```python
def calc_cohort_proximity(current_price: float, cohorts: list[dict]) -> float:
    """V1: Cohort proximity to margin call (0~1, unidirectional).
    proximity = max(0, min(1, 1 - (ratio - 140) / 60))
    V1 = weighted_avg(proximity, cohort.weight)
    """

def calc_foreign_direction(foreign_flows: list, idx: int, lookback: int = 20) -> float:
    """V2: Foreign net flow z-score -> bidirectional (-1~+1).
    z = (today - avg_20d) / std_20d
    V2 = clamp(-1, 1, -z / V2_DIVISOR)
    """

def calc_overnight_signal(ewy_pct=None, koru_pct=None,
                          futures_pct=None, us_market_pct=None) -> float:
    """V3: Overnight signal, bidirectional (-1~+1).
    signal = -(pct / divisor)  # down->positive(sell), up->negative(rebound)
    weighted avg + coherence bonus (1.3x same dir, 0.7x mixed)
    """

def calc_individual_direction(individual_flows: list, idx: int) -> float:
    """V4: Individual flow pattern, bidirectional (-1~+1).
    +1.0 = capitulation (large buy -> sudden drop)
    -0.4 = large buy sustained (absorption)
    +0.5 = net sell flip
    """

def calc_credit_momentum(credit_data: list, idx: int) -> float:
    """V5: Credit balance change rate, bidirectional (-1~+1).
    V5 = clamp(-1, 1, -change_pct / V5_DIVISOR)
    +2% increase -> V5 = -1.0 (inflow = rebound signal)
    -2% decrease -> V5 = +1.0 (outflow = sell signal)
    """

def calc_volume_amplifier(volume_today: float, adv_20: float,
                          recent_5d: list[float]) -> float:
    """VA: Adaptive volume amplifier (VA_FLOOR ~ VA_CEILING).
    baseline = max(adv_20, avg(recent_5d))
    amp = 1 + VA_LOG_SCALE * log2(volume / baseline)
    """

def calc_rspi(v1, v2, v3, v4, v5, volume_amp, weights=None) -> dict:
    """RSPI = -1 * (weighted_sum) * volume_amp * 100
    Returns: {rspi, level, raw_variables, volume_amp, variable_contributions}
    """
```

#### RSPIEngine class changes:

```python
class RSPIEngine:
    def __init__(self, weights=None):
        self.weights = weights or RSPI_WEIGHTS

    def calculate_for_date(self, date, ts, cohorts,
                           overnight_data=None, current_price=None,
                           adv_shares_k=None, samsung_credit_bn=None) -> dict:
        """Calculate RSPI for a specific date.
        New: extracts foreign_flows and individual_flows from ts internally.
        New: extracts trading_value for VA from ts.
        """

    def calculate_scenario_matrix(self, v1, v2, v4, v5, volume_amp, ...) -> list:
        """Scenario matrix: fix V1/V2/V4/V5, vary V3(overnight)."""

    def get_output(self) -> dict:
        """Return {history, weights, latest}"""
```

### 2.3 `kospi/scripts/compute_models.py`

Changes in RSPI section (lines ~1800-1900):
- Remove `d2, d3, d4` from scenario_matrix call
- Add trading_value extraction for VA
- calculate_scenario_matrix signature change (v1,v2,v4,v5,amp instead of v1~v4,d2~d4)

### 2.4 `kospi/scripts/export_web.py`

Changes:
- RSPI_CONFIG: remove cf_variables/df_variables, add variables (5), add va_info
- RSPI_CONFIG.levels: 5-level -> 7-level
- RSPI_CONFIG.weights: {cf, df} -> flat {v1~v5}
- RSPI_DATA.history entries: remove cf_components/df_components, add v1~v5+amp

### 2.5 Frontend Changes

#### `CohortAnalysis.jsx`
- RSPIGauge: levels 5->7, sign flip (negative=red)
- DualBreakdown (CF|DF) -> single VariableBreakdown (V1~V5 + VA)
- ImpactTable/ScenarioMatrix: sign convention change
- RSPI_CONFIG import: cf_variables/df_variables -> variables

#### `colors.js`
- Remove rspiCF1~CF4, rspiDF1~DF4
- Add rspiV1~V5, rspiVA colors

#### `terms.jsx`
- Remove CF/DF terms
- Add V1~V5 + VA terms with v3 descriptions

## 3. Implementation Order

```
Step 1: constants.py -- add new constants, keep old for compatibility
Step 2: rspi_engine.py -- full rewrite with new functions
Step 3: Test rspi_engine.py standalone (3/3~3/5 simulation)
Step 4: compute_models.py -- update RSPI section
Step 5: export_web.py -- update RSPI_DATA/CONFIG structure
Step 6: Run pipeline: compute_models + export_web
Step 7: CohortAnalysis.jsx -- update RSPI dashboard UI
Step 8: colors.js + terms.jsx -- update
Step 9: npm run build + verify
Step 10: constants.py -- remove deprecated VLPI/old RSPI constants
```

## 4. Data Flow

```
timeseries.json
    |
    v
compute_models.py
    |-- RSPIEngine.calculate_for_date() x 262 days
    |   |-- V1: cohorts + samsung price -> proximity
    |   |-- V2: foreign_billion from ts -> z-score
    |   |-- V3: ewy/koru/sp500 from ts -> overnight signal
    |   |-- V4: individual_billion from ts -> pattern
    |   |-- V5: credit_balance_billion from ts -> momentum
    |   |-- VA: trading_value from ts -> volume amplifier
    |   `-- calc_rspi(v1~v5, amp) -> RSPI
    |
    v
model_output.json
    |
    v
export_web.py
    |-- RSPI_DATA: {history: [{date, rspi, v1~v5, amp, level}], latest, scenario_matrix}
    |-- RSPI_CONFIG: {weights, variables, levels, impact_params}
    |
    v
kospi_data.js
    |
    v
CohortAnalysis.jsx
    |-- RSPIGauge: 7-level horizontal bar
    |-- VariableBreakdown: V1~V5 bars + VA display
    `-- ScenarioMatrix: V3(overnight) variation
```

## 5. Sign Convention

```
Variable internals: positive = selling direction
  V1 high = cohort vulnerable (0~1)
  V2 positive = foreign selling
  V3 positive = overnight gap-down
  V4 positive = individual capitulation
  V5 positive = credit outflow

Formula: RSPI = -1 * raw * amp * 100

Final output: sign flipped
  RSPI negative = selling pressure (red)
  RSPI positive = rebound pressure (green)
  RSPI ~0 = neutral (gray)
```

## 6. Level Classification

```python
# 7 levels (v2.2.0), negative = selling
def classify_level(rspi):
    if rspi <= -40: return "extreme_sell"
    if rspi <= -20: return "strong_sell"
    if rspi <= -5:  return "mild_sell"
    if rspi <= 5:   return "neutral"
    if rspi <= 20:  return "mild_rebound"
    if rspi <= 40:  return "strong_rebound"
    return "extreme_rebound"
```
