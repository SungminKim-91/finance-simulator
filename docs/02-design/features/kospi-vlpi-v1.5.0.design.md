# KOSPI VLPI v1.5.0 — 상세 설계 문서

> Backend VLPI Engine + 6단계 분류 + 데이터 수집 확장
> 참조 Plan: `docs/01-plan/features/kospi-vlpi-v1.5.0.plan.md`
> 참조 설계: `vlpi_architecture_v2.md`, `samsung_credit_cohort_data.md`

---

## 1. 아키텍처 개요

```
┌───────────────────────────────────────────────────────────┐
│ Data Pipeline (fetch_daily.py)                            │
│  ├─ ECOS/KRX/yfinance (기존)                               │
│  ├─ EWY yfinance (신규 V4)                                 │
│  └─ KOFIA API → Naver fallback (신용잔고 D-1 개선)           │
│         │                                                 │
│         ▼                                                 │
│ compute_models.py                                         │
│  ├─ CohortBuilder (6단계 분류)                              │
│  ├─ vlpi_engine.py (신규)                                   │
│  │   ├─ Pre-VLPI Calculator (V1~V6 → 0~100)              │
│  │   └─ Impact Function (VLPI → 매도금액 → 가격영향)        │
│  └─ run_all_models() → model_output.json                  │
│         │                                                 │
│         ▼                                                 │
│ export_web.py                                             │
│  ├─ COHORT_DATA (6단계 status_map)                         │
│  ├─ VLPI_DATA (Pre-VLPI history + components + impact)    │
│  └─ VLPI_CONFIG (weights, descriptions, presets)          │
│         │                                                 │
│         ▼                                                 │
│ kospi_data.js → CohortAnalysis.jsx (v1.6.0에서 소비)       │
└───────────────────────────────────────────────────────────┘
```

---

## 2. 상수 변경: `kospi/config/constants.py`

### 2.1 담보비율 공식 변경

**기존 (v1.4.1)**:
```python
# collateral_ratio = effective_ratio / (1 - MARGIN_RATE)
# effective_ratio = 1 + (price_ratio - 1) * portfolio_beta
# → portfolio_beta로 KOSPI 하락을 증폭시켜 개별주식 손실 반영
```

**신규 (v1.5.0)**:
```python
# 담보비율(%) = 현재가 / (매수가 × LOAN_RATE) × 100
# LOAN_RATE = 1 - MARGIN_RATE = 0.55
# → 직접 주가 기반 계산 (portfolio_beta 불필요)
```

**이유**: VLPI 설계서의 samsung_credit_cohort_data 검증 결과, 직접 주가 기반 담보비율이 실제 증권사 계산과 일치. portfolio_beta 증폭은 KOSPI 지수→개별주식 변환용이었는데, VLPI는 삼성전자 직접 추적으로 불필요.

### 2.2 신규/변경 상수

```python
# ── v1.5.0 VLPI 상수 ──
LOAN_RATE = 1 - MARGIN_RATE  # 0.55 (융자비율)
LEVERAGE = 1 / MARGIN_RATE   # 2.22 (실질 레버리지)
DAILY_LIMIT = 0.30            # KOSPI 가격제한폭 ±30%

# 6단계 상태 분류 기준 (담보비율 %)
STATUS_THRESHOLDS = {
    "debt_exceed": 100,   # 담보비율 < 100% → 채무초과
    "forced_liq":  120,   # 담보비율 < 120% → 강제청산
    "margin_call": 140,   # 담보비율 < 140% → 마진콜
    "caution":     155,   # 담보비율 < 155% → 주의
    "good":        170,   # 담보비율 < 170% → 양호
    # >= 170% → 안전
}

# VLPI 기본 가중치
VLPI_DEFAULT_WEIGHTS = {
    "w1": 0.25,  # 주의구간 코호트 비중
    "w2": 0.10,  # 신용잔고 모멘텀
    "w3": 0.20,  # 정책 쇼크
    "w4": 0.20,  # 야간 갭 시그널
    "w5": 0.15,  # 연속 하락 심각도
    "w6": 0.10,  # 전일 개인 수급 방향
}

# VLPI 정책 쇼크 유형
POLICY_SHOCK_MAP = {
    "credit_suspension_major":   1.0,
    "credit_suspension_minor":   0.5,
    "credit_tightening":         0.3,
    "short_selling_ban":         0.2,
    "regulator_warning":         0.4,
    "circuit_breaker_triggered": 0.8,
}

# Samsung 신용잔고 추정 비중
SAMSUNG_CREDIT_WEIGHT = 0.50

# EWY → KOSPI 갭 파라미터
EWY_GAP_WEIGHTS = {"ewy": 0.6, "futures": 0.3, "fx": 0.1}
EWY_GAP_DIVISOR = 5.0  # 5% 하락 = signal 1.0

# Impact Function 파라미터
VLPI_SENSITIVITY = 0.15          # VLPI 100일 때 매도 비율
VLPI_SIGMOID_K = 0.08            # sigmoid 기울기
VLPI_SIGMOID_MID = 50            # sigmoid 중점
VLPI_POLICY_MULTIPLIER = 1.5     # 정책 쇼크 시 배율
VLPI_LIQUIDITY_NORMAL = 0.5      # 정상 시장 유동성
VLPI_LIQUIDITY_CRISIS = 0.4      # 위기 시장 유동성

# KOFIA API (공공데이터포털)
KOFIA_API_BASE = "https://apis.data.go.kr/1160100/service/GetFinaStatInfoSvc"
```

### 2.3 삭제/수정 대상

```python
# 삭제:
# FORCED_LIQ_LOSS_PCT = 39  → 6단계에서 담보비율 기준으로 통합
# MAINTENANCE_RATIO_FIXED → STATUS_THRESHOLDS["margin_call"]로 대체
# BETA_* 파라미터들 → portfolio_beta 미사용 (직접 주가 기반)

# 호환 유지:
MARGIN_RATE = 0.45              # 보증금률 (유지)
MAINTENANCE_RATIO = 1.40        # 호환용 (유지, 신규 코드는 STATUS_THRESHOLDS 사용)
FORCED_LIQ_LOSS_PCT = 39        # 호환용 (유지, 신규 코드 미사용)
```

---

## 3. 신규 파일: `kospi/scripts/vlpi_engine.py`

### 3.1 모듈 구조

```python
"""
VLPI Engine — 자발적 청산 압력 지수 (Voluntary Liquidation Pressure Index).

2단계 아키텍처:
  Stage 1: Pre-VLPI (6변수 → 0~100 스코어)
  Stage 2: Impact Function (VLPI → 매도금액 → 가격영향)

Usage:
    from scripts.vlpi_engine import VLPIEngine
    engine = VLPIEngine()
    result = engine.calculate(ts_data, cohorts, events, ewy_data)
"""
import math
from dataclasses import dataclass, field
from config.constants import (
    LOAN_RATE, STATUS_THRESHOLDS,
    VLPI_DEFAULT_WEIGHTS, POLICY_SHOCK_MAP,
    SAMSUNG_CREDIT_WEIGHT,
    EWY_GAP_WEIGHTS, EWY_GAP_DIVISOR,
    VLPI_SENSITIVITY, VLPI_SIGMOID_K, VLPI_SIGMOID_MID,
    VLPI_POLICY_MULTIPLIER, VLPI_LIQUIDITY_NORMAL, VLPI_LIQUIDITY_CRISIS,
)
```

### 3.2 담보비율 + 6단계 분류

```python
def calc_collateral_ratio(current_price: float, entry_price: float) -> float:
    """담보비율(%) = 현재가 / (매수가 × LOAN_RATE) × 100."""
    if entry_price <= 0:
        return 999.0
    return (current_price / (entry_price * LOAN_RATE)) * 100


def classify_status_6(collateral_ratio: float) -> str:
    """6단계 상태 분류 (Option A: 위험 우선 cascade).

    Returns: "debt_exceed" | "forced_liq" | "margin_call" | "caution" | "good" | "safe"
    """
    if collateral_ratio < STATUS_THRESHOLDS["debt_exceed"]:
        return "debt_exceed"
    if collateral_ratio < STATUS_THRESHOLDS["forced_liq"]:
        return "forced_liq"
    if collateral_ratio < STATUS_THRESHOLDS["margin_call"]:
        return "margin_call"
    if collateral_ratio < STATUS_THRESHOLDS["caution"]:
        return "caution"
    if collateral_ratio < STATUS_THRESHOLDS["good"]:
        return "good"
    return "safe"
```

### 3.3 V1: 주의구간 코호트 비중

```python
def calc_caution_zone_pct(
    current_price: float,
    cohorts: list[dict],
) -> float:
    """V1: 담보비율 140~170% 구간 코호트의 가중 비중 합산.

    Args:
        current_price: T-1 종가 (삼성전자 또는 KOSPI 기준)
        cohorts: [{entry_price, weight(0~1)}, ...]

    Returns: 0~1
    """
    caution_weight = 0.0
    total_weight = 0.0
    for c in cohorts:
        ratio = calc_collateral_ratio(current_price, c["entry_price"])
        w = c.get("weight", 0)
        total_weight += w
        if STATUS_THRESHOLDS["margin_call"] <= ratio < STATUS_THRESHOLDS["good"]:
            caution_weight += w
    return caution_weight / total_weight if total_weight > 0 else 0.0
```

### 3.4 V2: 신용잔고 모멘텀

```python
def calc_credit_momentum(
    credit_data: list[dict], idx: int, lookback: int = 3,
) -> float:
    """V2: 최근 lookback일간 유가증권 신용잔고 변화율.

    Returns: -0.3 (잔고 급증=물타기) ~ 0.7 (잔고 급감=대규모 청산)
    """
    if idx < lookback:
        return 0.0
    current = credit_data[idx].get("credit_stock")
    past = credit_data[idx - lookback].get("credit_stock")
    if current is None or past is None or past == 0:
        return 0.0
    pct_change = (current - past) / past * 100
    if pct_change > 1.0:
        return -0.3
    elif pct_change > 0:
        return 0.0
    elif pct_change > -1.0:
        return 0.3
    else:
        return 0.7
```

### 3.5 V3: 정책 쇼크

```python
def calc_policy_shock(events: list[dict]) -> float:
    """V3: 정책 이벤트 심각도 (최대값 + 나머지 30%).

    Args:
        events: [{type: str, ...}, ...]

    Returns: 0~1
    """
    if not events:
        return 0.0
    severities = sorted(
        [POLICY_SHOCK_MAP.get(e.get("type", ""), 0) for e in events],
        reverse=True,
    )
    total = severities[0]
    for s in severities[1:]:
        total += s * 0.3
    return min(total, 1.0)
```

### 3.6 V4: 야간 갭 시그널

```python
def calc_overnight_gap(
    ewy_change_pct: float,
    kospi_night_futures_pct: float | None = None,
    usdkrw_ndf_change_pct: float | None = None,
) -> float:
    """V4: 야간 시장 데이터로 갭 시그널 추정.

    Returns: -1 (강한 갭업=압력 해소) ~ 1 (강한 갭다운=압력 증가)
    """
    w_ewy = EWY_GAP_WEIGHTS["ewy"]
    w_fut = EWY_GAP_WEIGHTS["futures"]
    w_fx = EWY_GAP_WEIGHTS["fx"]

    ewy_signal = -ewy_change_pct / EWY_GAP_DIVISOR

    if kospi_night_futures_pct is not None:
        fut_signal = -kospi_night_futures_pct / EWY_GAP_DIVISOR
    else:
        fut_signal = 0
        w_ewy += w_fut
        w_fut = 0

    if usdkrw_ndf_change_pct is not None:
        fx_signal = usdkrw_ndf_change_pct / 3.0
    else:
        fx_signal = 0
        w_ewy += w_fx
        w_fx = 0

    raw = w_ewy * ewy_signal + w_fut * fut_signal + w_fx * fx_signal
    return max(min(raw, 1.0), -1.0)
```

### 3.7 V5: 연속 하락 심각도

```python
def calc_cumulative_decline(
    price_data: list[dict], idx: int, max_lookback: int = 5,
) -> float:
    """V5: 연속 하락일수 + 누적 하락률 결합 심각도.

    Returns: 0 (직전일 상승) ~ 1 (4일+ 연속 하락, 누적 15%+)
    """
    DAY_SCORES = {0: 0, 1: 0.1, 2: 0.3, 3: 0.6, 4: 0.8, 5: 0.9}
    consecutive_down = 0
    cumulative_drop = 0.0

    for i in range(idx, max(idx - max_lookback, -1), -1):
        change = price_data[i].get("change_pct", 0) or 0
        if change < 0:
            consecutive_down += 1
            cumulative_drop += change
        else:
            break

    day_score = DAY_SCORES.get(consecutive_down, 0.95)
    drop_score = min(abs(cumulative_drop) / 15.0, 1.0)
    severity = 0.4 * day_score + 0.4 * drop_score + 0.2 * (day_score * drop_score)
    return min(severity, 1.0)
```

### 3.8 V6: 전일 개인 수급 방향

```python
def calc_individual_flow_direction(
    flow_data: list[dict], idx: int,
) -> float:
    """V6: 전일 개인 순매수 규모/방향으로 투매 가능성 추정.

    Returns: 0~1 (높을수록 내일 투매 가능성 높음)
    """
    if idx < 1:
        return 0.0
    curr = flow_data[idx].get("individual", 0) or 0  # 억원
    prev = flow_data[idx - 1].get("individual", 0) or 0

    if curr > 30000:
        return 0.6   # 3만억+ 대량 순매수 = 물타기 → 잠재 투매
    if prev > 30000 and curr < 5000:
        return 1.0   # 대량 → 급감 = 항복 시작
    if prev > 20000 and curr < prev * 0.3:
        return 0.7   # 항복 진행 중
    if curr > 0:
        return 0.3   # 소규모 순매수
    return 0.2        # 순매도 = 이미 투매 소진 가능
```

### 3.9 Pre-VLPI 종합 계산

```python
@dataclass
class VLPIResult:
    """Pre-VLPI 계산 결과."""
    pre_vlpi: float                    # 0~100
    components: dict[str, float]       # V1~V6 기여분 (합 = pre_vlpi)
    raw_variables: dict[str, float]    # V1~V6 원시값
    level: str                         # "normal" | "caution" | "warning" | "danger"
    impact: dict | None = None         # Stage 2 결과 (선택)


def calc_pre_vlpi(
    v1: float, v2: float, v3: float,
    v4: float, v5: float, v6: float,
    weights: dict | None = None,
) -> VLPIResult:
    """6변수 가중합산 → Pre-VLPI 0~100 스코어.

    v2 범위 -0.3~0.7 → 정규화 0~1
    v4 범위 -1~1 → 정규화 0~1
    """
    if weights is None:
        weights = VLPI_DEFAULT_WEIGHTS

    v2_norm = (v2 + 0.3) / 1.0
    v4_norm = (v4 + 1) / 2.0

    raw = (
        weights["w1"] * v1 +
        weights["w2"] * v2_norm +
        weights["w3"] * v3 +
        weights["w4"] * v4_norm +
        weights["w5"] * v5 +
        weights["w6"] * v6
    )
    total_w = sum(weights.values())
    pre_vlpi = max(0, min(100, (raw / total_w) * 100))

    components = {
        "caution_zone":       weights["w1"] * v1 / total_w * 100,
        "credit_momentum":    weights["w2"] * v2_norm / total_w * 100,
        "policy_shock":       weights["w3"] * v3 / total_w * 100,
        "overnight_gap":      weights["w4"] * v4_norm / total_w * 100,
        "cumulative_decline": weights["w5"] * v5 / total_w * 100,
        "individual_flow":    weights["w6"] * v6 / total_w * 100,
    }

    level = (
        "danger" if pre_vlpi >= 70 else
        "warning" if pre_vlpi >= 50 else
        "caution" if pre_vlpi >= 30 else
        "normal"
    )

    return VLPIResult(
        pre_vlpi=round(pre_vlpi, 1),
        components={k: round(v, 2) for k, v in components.items()},
        raw_variables={"v1": v1, "v2": v2, "v3": v3, "v4": v4, "v5": v5, "v6": v6},
        level=level,
    )
```

### 3.10 Stage 2: Impact Function

```python
def estimate_selling_volume(
    pre_vlpi: float,
    samsung_credit_bn: float,
    sensitivity: float = VLPI_SENSITIVITY,
    policy_multiplier: float = 1.0,
) -> dict:
    """Pre-VLPI → sigmoid → 매도비율 → 매도금액.

    Args:
        pre_vlpi: 0~100
        samsung_credit_bn: 삼성전자 추정 신용잔고 (조원, 매수포지션 환산)
        sensitivity: VLPI 100일 때 매도 비율 (기본 15%)
        policy_multiplier: 정책 쇼크 배율

    Returns:
        {selling_volume_bn, selling_volume_억, sell_ratio_pct, vlpi_ratio}
    """
    vlpi_ratio = 1 / (1 + math.exp(-VLPI_SIGMOID_K * (pre_vlpi - VLPI_SIGMOID_MID)))
    sell_ratio = vlpi_ratio * sensitivity * policy_multiplier
    selling_bn = samsung_credit_bn * sell_ratio
    return {
        "selling_volume_bn": round(selling_bn, 2),
        "selling_volume_억": round(selling_bn * 10000, 0),
        "sell_ratio_pct": round(sell_ratio * 100, 2),
        "vlpi_ratio": round(vlpi_ratio, 4),
    }


def estimate_price_impact(
    selling_volume_bn: float,
    current_price: int,
    adv_shares_k: float,
    liquidity_factor: float = VLPI_LIQUIDITY_NORMAL,
) -> dict:
    """Kyle's Lambda 기반 비선형 가격영향 추정.

    Args:
        selling_volume_bn: 매도금액 (조원)
        current_price: 현재가 (원)
        adv_shares_k: 평균 일거래량 (천주)
        liquidity_factor: 유동성 계수 (높을수록 흡수 잘 함)

    Returns:
        {price_impact_pct, absorption_ratio, selling_shares_k}
    """
    selling_shares_k = selling_volume_bn * 1e9 / current_price / 1000
    absorption_ratio = selling_shares_k / adv_shares_k if adv_shares_k > 0 else 0

    if absorption_ratio < 0.1:
        impact = absorption_ratio * 0.5
    elif absorption_ratio < 0.3:
        impact = 0.05 + (absorption_ratio - 0.1) * 1.5
    else:
        impact = 0.35 + (absorption_ratio - 0.3) * 3.0

    price_impact_pct = -(impact / liquidity_factor) * 100
    return {
        "price_impact_pct": round(max(price_impact_pct, -30), 2),
        "absorption_ratio": round(absorption_ratio, 4),
        "selling_shares_k": round(selling_shares_k, 0),
    }


def run_vlpi_scenario(
    pre_vlpi: float,
    samsung_credit_bn: float,
    current_price: int,
    adv_shares_k: float,
    policy_active: bool = False,
) -> dict:
    """전체 파이프라인: VLPI → 매도 → 가격영향."""
    policy_mult = VLPI_POLICY_MULTIPLIER if policy_active else 1.0
    liq_factor = VLPI_LIQUIDITY_CRISIS if policy_active else VLPI_LIQUIDITY_NORMAL

    sell = estimate_selling_volume(pre_vlpi, samsung_credit_bn, policy_multiplier=policy_mult)
    impact = estimate_price_impact(
        sell["selling_volume_bn"], current_price, adv_shares_k, liq_factor
    )
    return {
        "pre_vlpi": pre_vlpi,
        "sell_volume_억": sell["selling_volume_억"],
        "sell_ratio_pct": sell["sell_ratio_pct"],
        "price_impact_pct": impact["price_impact_pct"],
        "absorption_ratio": impact["absorption_ratio"],
    }
```

### 3.11 VLPIEngine 통합 클래스

```python
class VLPIEngine:
    """VLPI 전체 파이프라인 오케스트레이터.

    ts(timeseries), cohorts, events, ewy 데이터를 받아
    Pre-VLPI + Impact를 계산하고 히스토리를 관리.
    """

    def __init__(self, weights: dict | None = None):
        self.weights = weights or VLPI_DEFAULT_WEIGHTS
        self.history: list[dict] = []  # 일별 VLPI 결과

    def calculate_for_date(
        self,
        date: str,
        ts: list[dict],            # timeseries (날짜순)
        cohorts: list[dict],        # [{entry_price, weight}, ...]
        events: list[dict],         # 정책 이벤트
        ewy_change_pct: float | None = None,
        samsung_credit_bn: float | None = None,
        current_price: int | None = None,
        adv_shares_k: float | None = None,
    ) -> VLPIResult:
        """특정 날짜의 Pre-VLPI + Impact 계산.

        ts에서 date 이전 데이터로 V1~V6 자동 계산.
        """
        # date의 인덱스 찾기
        idx = next((i for i, r in enumerate(ts) if r["date"] == date), len(ts) - 1)

        # T-1 종가 (삼성전자)
        t1_price = current_price or ts[idx].get("samsung", 0)

        # V1: 주의구간 비중
        v1 = calc_caution_zone_pct(t1_price, cohorts)

        # V2: 신용잔고 모멘텀
        credit_data = [
            {"credit_stock": r.get("credit_balance_billion", 0) * 1e6 / 1e6}
            for r in ts
        ]
        v2 = calc_credit_momentum(credit_data, idx)

        # V3: 정책 쇼크
        v3 = calc_policy_shock(events)

        # V4: 야간 갭
        v4 = calc_overnight_gap(ewy_change_pct or 0)

        # V5: 연속 하락
        price_data = [
            {"change_pct": r.get("samsung_change_pct") or r.get("kospi_change_pct", 0)}
            for r in ts
        ]
        v5 = calc_cumulative_decline(price_data, idx)

        # V6: 개인 수급
        flow_data = [
            {"individual": r.get("individual_billion", 0) * 10}  # 조→억 변환
            for r in ts
        ]
        v6 = calc_individual_flow_direction(flow_data, idx)

        # Pre-VLPI
        result = calc_pre_vlpi(v1, v2, v3, v4, v5, v6, self.weights)

        # Stage 2: Impact (선택)
        if samsung_credit_bn and t1_price and adv_shares_k:
            # 신용잔고를 매수포지션으로 환산
            position_bn = samsung_credit_bn / LOAN_RATE  # 융자금 → 매수포지션
            result.impact = run_vlpi_scenario(
                result.pre_vlpi, position_bn, t1_price, adv_shares_k,
                policy_active=(v3 > 0.5),
            )

        # 히스토리 저장
        self.history.append({
            "date": date,
            "pre_vlpi": result.pre_vlpi,
            "level": result.level,
            "components": result.components,
            "raw_variables": result.raw_variables,
            "impact": result.impact,
        })

        return result

    def calculate_scenario_matrix(
        self,
        v1: float, v2: float, v3_base: float, v5: float, v6: float,
        samsung_credit_bn: float,
        current_price: int,
        adv_shares_k: float,
    ) -> list[dict]:
        """밤사이 시나리오 매트릭스 생성.

        V4(EWY)를 -5%~+2.5% 범위에서 변동시켜 Pre-VLPI + Impact 테이블.
        """
        presets = [
            {"label": "낙관적", "ewy_pct": 2.5, "policy": False},
            {"label": "기본",   "ewy_pct": -1.0, "policy": False},
            {"label": "비관적", "ewy_pct": -4.0, "policy": True},
        ]
        results = []
        for p in presets:
            v3 = min(v3_base + (0.5 if p["policy"] else 0), 1.0)
            v4 = calc_overnight_gap(p["ewy_pct"])
            vlpi = calc_pre_vlpi(v1, v2, v3, v4, v5, v6, self.weights)

            position_bn = samsung_credit_bn / LOAN_RATE
            scenario = run_vlpi_scenario(
                vlpi.pre_vlpi, position_bn, current_price, adv_shares_k,
                policy_active=p["policy"],
            )
            results.append({
                "label": p["label"],
                "ewy_change_pct": p["ewy_pct"],
                "policy_shock": p["policy"],
                **scenario,
            })
        return results

    def get_output(self) -> dict:
        """model_output.json에 저장할 VLPI 데이터."""
        return {
            "history": self.history,
            "weights": self.weights,
            "latest": self.history[-1] if self.history else None,
        }
```

---

## 4. `compute_models.py` 변경

### 4.1 Cohort.classify_status() → 6단계

```python
@staticmethod
def classify_status(collateral_ratio: float, loss_pct: float = 0) -> str:
    """v1.5.0 6단계 상태 판정 (담보비율 기준).

    Note: loss_pct 인자는 하위호환용으로 유지하되 미사용.
    담보비율 = 현재가 / (매수가 × 0.55) × 100 으로 계산.
    """
    # collateral_ratio는 이미 % 단위 (예: 144.6)
    ratio_pct = collateral_ratio * 100 if collateral_ratio < 10 else collateral_ratio

    if ratio_pct < STATUS_THRESHOLDS["debt_exceed"]:
        return "debt_exceed"
    if ratio_pct < STATUS_THRESHOLDS["forced_liq"]:
        return "forced_liq"
    if ratio_pct < STATUS_THRESHOLDS["margin_call"]:
        return "margin_call"
    if ratio_pct < STATUS_THRESHOLDS["caution"]:
        return "caution"
    if ratio_pct < STATUS_THRESHOLDS["good"]:
        return "good"
    return "safe"
```

**주의**: 기존 `collateral_ratio`는 비율(1.44 = 144%) 형태, 신규는 %(144.6) 형태. 변환 로직 필요.

### 4.2 Cohort.collateral_ratio() → VLPI 공식

```python
def collateral_ratio(self, current_price: float) -> float:
    """담보비율(%) = 현재가 / (매수가 × LOAN_RATE) × 100.

    v1.5.0: portfolio_beta 미적용, 직접 주가 기반.
    current_price: 삼성전자(또는 기준 종목) 종가.
    """
    if self.entry_stock_price <= 0:
        return 999.0
    return (current_price / (self.entry_stock_price * LOAN_RATE)) * 100
```

### 4.3 adjust_cohort_with_beta() → 6단계 적용

```python
def adjust_cohort_for_vlpi(
    cohort_dict: dict, current_price: float,
) -> dict:
    """v1.5.0: 코호트에 6단계 상태 + 청산 여부 적용.

    debt_exceed/forced_liq → 100% 청산 (surviving_amount = 0)
    margin_call 이하 → 잔액 유지 (자발적 투매는 VLPI로 모델링)
    """
    entry_price = cohort_dict.get("entry_stock_price", 0) or cohort_dict.get("entry_kospi", 0)
    original_amount = cohort_dict.get("remaining_amount_billion", 0)

    if entry_price <= 0:
        ratio = 999.0
        pnl_pct = 0
    else:
        ratio = (current_price / (entry_price * LOAN_RATE)) * 100
        pnl_pct = round((current_price / entry_price - 1) * 100, 2)

    status = classify_status_6(ratio)
    is_liquidated = status in ("debt_exceed", "forced_liq")
    surviving = 0.0 if is_liquidated else original_amount

    return {
        **cohort_dict,
        "pnl_pct": pnl_pct,
        "collateral_ratio_pct": round(ratio, 1),
        "status": status,
        "remaining_amount_billion": surviving,
        "liquidated_pct": 100.0 if is_liquidated else 0.0,
    }
```

### 4.4 run_all_models() VLPI 통합

```python
# 기존 코드 이후에 추가:
from scripts.vlpi_engine import VLPIEngine, classify_status_6

# VLPI 계산 (마지막 거래일 기준)
vlpi_engine = VLPIEngine()
latest_ts = ts[-1] if ts else {}
samsung_price = latest_ts.get("samsung", 0)
samsung_credit_bn = _estimate_samsung_credit(ts)
samsung_adv = _estimate_samsung_adv(ts)

# 코호트를 VLPI 입력 형식으로 변환
vlpi_cohorts = _to_vlpi_cohorts(lifo_builder, samsung_price)

# 정책 이벤트 로드 (수동 입력 파일)
policy_events = _load_policy_events()

# EWY 데이터
ewy_pct = latest_ts.get("ewy_change_pct")

vlpi_result = vlpi_engine.calculate_for_date(
    date=latest_ts.get("date", ""),
    ts=ts,
    cohorts=vlpi_cohorts,
    events=policy_events,
    ewy_change_pct=ewy_pct,
    samsung_credit_bn=samsung_credit_bn,
    current_price=samsung_price,
    adv_shares_k=samsung_adv,
)

# 시나리오 매트릭스
scenario_matrix = vlpi_engine.calculate_scenario_matrix(
    v1=vlpi_result.raw_variables["v1"],
    v2=vlpi_result.raw_variables["v2"],
    v3_base=vlpi_result.raw_variables["v3"],
    v5=vlpi_result.raw_variables["v5"],
    v6=vlpi_result.raw_variables["v6"],
    samsung_credit_bn=samsung_credit_bn,
    current_price=samsung_price,
    adv_shares_k=samsung_adv,
)

# model_output에 VLPI 추가
output["vlpi"] = vlpi_engine.get_output()
output["vlpi"]["scenario_matrix"] = scenario_matrix
```

---

## 5. 데이터 수집 확장

### 5.1 `fetch_daily.py` — EWY 추가

```python
# YF_SYMBOLS에 추가:
YF_SYMBOLS["ewy"] = "EWY"

# extract_date_data()에 추가:
"ewy_close": ...,
"ewy_change_pct": ...,  # 전일 대비 변동률

# append_timeseries()에 추가:
"ewy_close": snapshot.get("ewy_close"),
"ewy_change_pct": snapshot.get("ewy_change_pct"),
```

### 5.2 `kofia_fetcher.py` — 금투협 신용잔고 (신규)

```python
"""
금투협(KOFIA) 신용공여잔고 데이터 수집.

소스 우선순위:
1. 공공데이터포털 API (data.go.kr, 인증키 필요)
2. FreeSIS XHR (freesis.kofia.or.kr, 리버스 엔지니어링)
3. Naver Finance fallback (D-2 지연)

환경변수: KOFIA_API_KEY (공공데이터포털)
"""
import os
import requests
from datetime import datetime

KOFIA_API_KEY = os.getenv("KOFIA_API_KEY", "")
KOFIA_API_BASE = "https://apis.data.go.kr/1160100/service/GetFinaStatInfoSvc"


def fetch_credit_balance(date: str) -> dict | None:
    """3-tier fallback으로 신용잔고 수집.

    Returns:
        {
            "date": "2026-03-04",
            "kospi_stock_credit_mm": 21778077,   # 유가증권 신용잔고 (백만원)
            "kosdaq_credit_mm": 11025996,
            "total_credit_mm": 32804073,
            "source": "kofia_api" | "freesis" | "naver",
        }
    """
    # Tier 1: 공공데이터포털 API
    if KOFIA_API_KEY:
        result = _fetch_from_data_go_kr(date)
        if result:
            return {**result, "source": "kofia_api"}

    # Tier 2: FreeSIS XHR
    result = _fetch_from_freesis(date)
    if result:
        return {**result, "source": "freesis"}

    # Tier 3: Naver fallback (기존)
    return None  # fetch_daily.py에서 naver_scraper 호출


def _fetch_from_data_go_kr(date: str) -> dict | None:
    """공공데이터포털 금융투자협회종합통계 API."""
    params = {
        "serviceKey": KOFIA_API_KEY,
        "numOfRows": 10,
        "pageNo": 1,
        "resultType": "json",
        "basDt": date.replace("-", ""),
    }
    try:
        resp = requests.get(
            f"{KOFIA_API_BASE}/getItemBasiInfo",  # 엔드포인트 확인 필요
            params=params, timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            # 파싱 로직 (API 응답 스키마에 따라)
            return _parse_kofia_response(data)
    except Exception:
        pass
    return None


def _fetch_from_freesis(date: str) -> dict | None:
    """FreeSIS SPA XHR 엔드포인트.

    Note: 리버스 엔지니어링 필요. 초기에는 None 반환.
    향후 브라우저 DevTools로 XHR 패턴 확인 후 구현.
    """
    # TODO: FreeSIS XHR 엔드포인트 구현
    return None
```

### 5.3 `fetch_daily.py` 통합

```python
# build_snapshot()에서:
from scripts.kofia_fetcher import fetch_credit_balance

# 신용잔고 수집 순서 변경:
kofia_credit = fetch_credit_balance(date_str)
if kofia_credit:
    credit_balance_billion = kofia_credit["kospi_stock_credit_mm"] / 1e3
    credit_source = kofia_credit["source"]
else:
    # 기존 naver_scraper fallback
    credit_balance_billion = naver_data.get("credit_balance_billion")
    credit_source = "naver"
```

---

## 6. `export_web.py` 변경

### 6.1 `_remap_cohorts()` — 6단계 status_map

```python
STATUS_MAP_6 = {
    "debt_exceed": "debtExceed",
    "forced_liq": "forcedLiq",
    "margin_call": "marginCall",
    "caution": "caution",
    "good": "good",
    "safe": "safe",
}

def _remap_cohorts(cohorts: list[dict]) -> list[dict]:
    result = []
    for c in cohorts:
        entry = {
            "entry_date": c.get("entry_date", ""),
            "entry_kospi": c.get("entry_kospi", 0),
            "entry_stock_price": c.get("entry_stock_price", 0),
            "amount": c.get("remaining_amount_billion", 0),
            "pnl_pct": c.get("pnl_pct", 0),
            "collateral_ratio_pct": c.get("collateral_ratio_pct", 0),
            "status": STATUS_MAP_6.get(c.get("status", "safe"), "safe"),
        }
        if c.get("liquidated_pct", 0) > 0:
            entry["liquidated_pct"] = c["liquidated_pct"]
        result.append(entry)
    return result
```

### 6.2 신규 Export: VLPI_DATA + VLPI_CONFIG

```python
# === 17. VLPI_DATA ===
vlpi_raw = model_output.get("vlpi", {})
vlpi_data = {
    "history": vlpi_raw.get("history", []),
    "latest": vlpi_raw.get("latest"),
    "scenario_matrix": vlpi_raw.get("scenario_matrix", []),
}

# === 18. VLPI_CONFIG ===
vlpi_config = {
    "weights": vlpi_raw.get("weights", VLPI_DEFAULT_WEIGHTS),
    "status_thresholds": STATUS_THRESHOLDS,
    "variables": [
        {"key": "v1", "label": "주의구간 비중", "desc": "담보비율 140~170% 코호트 비중", "range": "0~1", "weight_key": "w1"},
        {"key": "v2", "label": "신용잔고 모멘텀", "desc": "최근 3일 신용잔고 변화 방향", "range": "-0.3~0.7", "weight_key": "w2"},
        {"key": "v3", "label": "정책 쇼크", "desc": "증권사 신용제한, 서킷브레이커 등", "range": "0~1", "weight_key": "w3"},
        {"key": "v4", "label": "야간 갭", "desc": "EWY/선물 기반 갭다운 예상", "range": "-1~1", "weight_key": "w4"},
        {"key": "v5", "label": "연속 하락", "desc": "연속 하락일수 + 누적 하락률", "range": "0~1", "weight_key": "w5"},
        {"key": "v6", "label": "개인 수급", "desc": "전일 개인 순매수 패턴", "range": "0~1", "weight_key": "w6"},
    ],
    "levels": [
        {"min": 0,  "max": 30, "label": "정상", "color": "#4caf50"},
        {"min": 30, "max": 50, "label": "주의", "color": "#ffc107"},
        {"min": 50, "max": 70, "label": "경고", "color": "#ff9800"},
        {"min": 70, "max": 100, "label": "위험", "color": "#f44336"},
    ],
    "impact_params": {
        "sensitivity": VLPI_SENSITIVITY,
        "sigmoid_k": VLPI_SIGMOID_K,
        "sigmoid_mid": VLPI_SIGMOID_MID,
        "samsung_credit_weight": SAMSUNG_CREDIT_WEIGHT,
    },
}

# Write:
f.write(to_js_export("VLPI_DATA", vlpi_data))
f.write(to_js_export("VLPI_CONFIG", vlpi_config))
```

### 6.3 COHORT_DATA params 변경

```python
"params": {
    "margin_rate": MARGIN_RATE,
    "loan_rate": LOAN_RATE,
    "status_thresholds": STATUS_THRESHOLDS,
    "leverage": LEVERAGE,
    "stock_weighted": stock_credit_raw.get("stock_weighted", False),
},
```

---

## 7. Samsung 시드 데이터: `kospi/data/samsung_cohorts.json`

```json
{
  "meta": {
    "source": "samsung_credit_cohort_data.md",
    "period": "2026-02-13 ~ 2026-03-04",
    "samsung_credit_weight": 0.50
  },
  "cohorts": [
    {"id": "F", "label": "장기보유(2/13이전)", "entry_price": 181000, "weight": 0.800},
    {"id": "A", "label": "베이스(2/13~2/19)",  "entry_price": 190000, "weight": 0.009},
    {"id": "B", "label": "상승초기(2/23~2/24)", "entry_price": 196500, "weight": 0.024},
    {"id": "C", "label": "급등기(2/25~2/26)",   "entry_price": 210750, "weight": 0.016},
    {"id": "D", "label": "고점(2/27)",           "entry_price": 216500, "weight": 0.013},
    {"id": "E", "label": "급락물타기(3/3)",      "entry_price": 195100, "weight": 0.008}
  ],
  "daily_prices": [
    {"date": "2026-02-13", "close": 181200, "change_pct": 1.46, "volume": 34454192},
    {"date": "2026-02-19", "close": 190000, "change_pct": 4.86, "volume": 27049388},
    {"date": "2026-02-20", "close": 190100, "change_pct": 0.05, "volume": 24213880},
    {"date": "2026-02-23", "close": 193000, "change_pct": 1.53, "volume": 26364684},
    {"date": "2026-02-24", "close": 200000, "change_pct": 3.63, "volume": 28060617},
    {"date": "2026-02-25", "close": 203500, "change_pct": 1.75, "volume": 26987996},
    {"date": "2026-02-26", "close": 218000, "change_pct": 7.13, "volume": 30095763},
    {"date": "2026-02-27", "close": 216500, "change_pct": -0.69, "volume": 51774768},
    {"date": "2026-03-03", "close": 195100, "change_pct": -9.88, "volume": 54879010},
    {"date": "2026-03-04", "close": 172200, "change_pct": -11.74, "volume": 89225029}
  ],
  "daily_flows": [
    {"date": "2026-02-13", "individual": 7141},
    {"date": "2026-02-19", "individual": -8609},
    {"date": "2026-02-20", "individual": -9872},
    {"date": "2026-02-23", "individual": 10815},
    {"date": "2026-02-24", "individual": -22861},
    {"date": "2026-02-25", "individual": 2307},
    {"date": "2026-02-26", "individual": 6498},
    {"date": "2026-02-27", "individual": 62496},
    {"date": "2026-03-03", "individual": 57974},
    {"date": "2026-03-04", "individual": 796}
  ],
  "credit_balance": [
    {"date": "2026-02-13", "kospi_stock_mm": 20942212},
    {"date": "2026-02-19", "kospi_stock_mm": 20944448},
    {"date": "2026-02-20", "kospi_stock_mm": 20977105},
    {"date": "2026-02-23", "kospi_stock_mm": 21121450},
    {"date": "2026-02-24", "kospi_stock_mm": 21279520},
    {"date": "2026-02-25", "kospi_stock_mm": 21399130},
    {"date": "2026-02-26", "kospi_stock_mm": 21496796},
    {"date": "2026-02-27", "kospi_stock_mm": 21672790},
    {"date": "2026-03-03", "kospi_stock_mm": 21778077}
  ],
  "policy_events": [
    {"date": "2026-03-03", "type": "credit_suspension_major", "desc": "한투 신용거래 무기한 중단"},
    {"date": "2026-03-03", "type": "credit_suspension_major", "desc": "NH 신용거래 무기한 중단"}
  ]
}
```

---

## 8. 검증 시나리오

### 8.1 3/3→3/4 Pre-VLPI (핵심 검증)

```
T-1 = 3/3, 대상일 = 3/4

V1 = calc_caution_zone_pct(195100, cohorts)
  - F(181000): 195100/(181000×0.55) = 195.96% → 안전
  - A(190000): 195100/(190000×0.55) = 186.73% → 안전
  - B(196500): 195100/(196500×0.55) = 180.53% → 안전
  - C(210750): 195100/(210750×0.55) = 168.33% → 양호 (140~170 ✓)
  - D(216500): 195100/(216500×0.55) = 163.86% → 양호 (140~170 ✓)
  → V1 = (0.016 + 0.013) / 1.0 = 0.029

V2 = calc_credit_momentum (2/27→3/3: 21672790→21778077 = +0.49%)
  → V2 = 0.0

V3 = calc_policy_shock([credit_suspension_major × 2])
  → V3 = min(1.0 + 1.0×0.3, 1.0) = 1.0

V4 = calc_overnight_gap(EWY ???)
  → V4 = 0 (중립 가정, EWY 데이터 미확보)

V5 = calc_cumulative_decline (2/27: -0.69, 3/3: -9.88 = 2일 연속)
  → day=0.3, drop=10.57/15=0.705
  → V5 = 0.4×0.3 + 0.4×0.705 + 0.2×(0.3×0.705) = 0.444

V6 = calc_individual_flow_direction (3/3: +57974 > 30000)
  → V6 = 0.6

Pre-VLPI:
  v2_norm = (0+0.3)/1.0 = 0.30
  v4_norm = (0+1)/2.0 = 0.50
  raw = 0.25×0.029 + 0.10×0.30 + 0.20×1.00 + 0.20×0.50 + 0.15×0.444 + 0.10×0.60
      = 0.00725 + 0.030 + 0.200 + 0.100 + 0.0666 + 0.060
      = 0.4639
  pre_vlpi = 46.4
  → 기대값 ≈ 46 ✓ (설계서 일치)

6단계 분류 (3/4 종가 172200 기준):
  D(216500): 172200/(216500×0.55) = 144.63% → "주의" (140~155) ✓
  마진콜 코호트 = 0개 ✓
```

### 8.2 시나리오 매트릭스 (3/4 기준→3/5 예측)

```
V1=0.070, V2=0.3(추정), V3=0.5(정책 지속), V5=0.76, V6=1.0

낙관적 (EWY +2.5%): Pre-VLPI ≈ 34 → 매도 2,376억 → 가격 -0.5~1%
기본   (EWY -1.0%): Pre-VLPI ≈ 44 → 매도 7,920억 → 가격 -2~4%
비관적 (EWY -4.0%): Pre-VLPI ≈ 64 → 매도 21,780억 → 가격 -8~12%
```

---

## 9. 구현 순서

```
Step 1: constants.py (신규 상수)
Step 2: vlpi_engine.py (V1~V6 + Pre-VLPI + Impact)
Step 3: vlpi_engine.py 검증 (samsung_cohorts.json seed data)
Step 4: compute_models.py (6단계 classify_status, adjust_cohort_for_vlpi)
Step 5: compute_models.py → run_all_models() VLPI 통합
Step 6: fetch_daily.py (EWY 추가)
Step 7: kofia_fetcher.py (금투협 API, 초기 stub)
Step 8: export_web.py (VLPI_DATA, VLPI_CONFIG, 6단계 status_map)
Step 9: 전체 파이프라인 검증 (compute_models → export_web → kospi_data.js)
```

---

## 10. 하위호환 전략

### Frontend (v1.6.0까지 기존 UI 유지)
- `_remap_cohorts()`에서 6단계 → 기존 4단계 fallback 매핑 제공:
  - `debt_exceed`, `forced_liq` → `danger`
  - `margin_call` → `marginCall`
  - `caution`, `good` → `watch`
  - `safe` → `safe`
- v1.5.0에서는 `_remap_cohorts()`가 **양쪽 모두 export** (6단계 + 4단계 호환)
- CohortAnalysis.jsx는 v1.6.0까지 기존 4단계 코드 그대로 사용

### Backend
- `classify_status(collateral_ratio, loss_pct)` 시그니처 유지 (loss_pct 무시)
- 기존 `ForcedLiqSimulator`는 삭제하지 않고 deprecated 처리 (v1.7.0에서 VLPI 시뮬레이터로 대체)
- `portfolio_beta` 관련 코드는 유지 (STOCK_CREDIT 등에서 아직 사용)
