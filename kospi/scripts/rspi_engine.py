#!/usr/bin/env python3
"""
RSPI Engine — Retail Selling Pressure Index (개인 매도 압력 지수).

양방향 아키텍처:
  Cascade Force (CF): 매도 가속력 V1~V4 (0~100)
  Damping Force (DF): 매도 감쇠력 D1~D4 (0~100)
  RSPI = CF - DF (범위: -100 ~ +100)

Usage:
    from scripts.rspi_engine import RSPIEngine
    engine = RSPIEngine()
    result = engine.calculate_for_date(date, ts, cohorts, overnight_data, ...)
"""
import math
from pathlib import Path

import sys as _sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import (
    LOAN_RATE, STATUS_THRESHOLDS, SAMSUNG_CREDIT_WEIGHT,
    RSPI_CF_WEIGHTS, RSPI_DF_WEIGHTS,
    OVERNIGHT_WEIGHTS,
    OVERNIGHT_EWY_DIVISOR, OVERNIGHT_KORU_DIVISOR,
    OVERNIGHT_FUTURES_DIVISOR, OVERNIGHT_US_DIVISOR,
    RSPI_SENSITIVITY, RSPI_SIGMOID_K, RSPI_SIGMOID_MID,
    RSPI_LIQUIDITY_FACTOR, RSPI_LEVELS,
)


# ──────────────────────────────────────────────
# 담보비율 + 6단계 분류 (vlpi_engine.py에서 복사)
# ──────────────────────────────────────────────

def calc_collateral_ratio(current_price: float, entry_price: float) -> float:
    """담보비율(%) = 현재가 / (매수가 × LOAN_RATE) × 100."""
    if entry_price <= 0:
        return 999.0
    return (current_price / (entry_price * LOAN_RATE)) * 100


def classify_status_6(collateral_ratio: float) -> str:
    """6단계 상태 분류."""
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


# ──────────────────────────────────────────────
# CF V1: 주의구간 코호트 비중
# ──────────────────────────────────────────────

def calc_caution_zone_pct(
    current_price: float,
    cohorts: list[dict],
) -> float:
    """V1: 담보비율 140~170% 구간 코호트의 가중 비중.

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


# ──────────────────────────────────────────────
# CF V2: 연속 하락 심각도
# ──────────────────────────────────────────────

def calc_cumulative_decline(
    price_data: list[dict], idx: int, max_lookback: int = 5,
) -> float:
    """V2: 연속 하락일수 + 누적 하락률 결합 심각도.

    Returns: 0~1
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


# ──────────────────────────────────────────────
# CF V3: 개인 수급 방향
# ──────────────────────────────────────────────

def calc_individual_flow_direction(
    flow_data: list[dict], idx: int,
) -> float:
    """V3: 전일 개인 순매수 규모/방향으로 투매 가능성 추정.

    Returns: 0~1
    """
    if idx < 1:
        return 0.0
    curr = flow_data[idx].get("individual", 0) or 0
    prev = flow_data[idx - 1].get("individual", 0) or 0

    if curr > 30000:
        return 0.6
    if prev > 30000 and curr < 5000:
        return 1.0
    if prev > 20000 and curr < prev * 0.3:
        return 0.7
    if curr > 0:
        return 0.3
    return 0.2


# ──────────────────────────────────────────────
# CF V4: 신용잔고 가속 모멘텀
# ──────────────────────────────────────────────

def calc_credit_accel_momentum(
    credit_data: list[dict], idx: int, lookback: int = 3,
) -> float:
    """V4: 신용잔고 감소 시 가속 모멘텀.

    기존 calc_credit_momentum에서 가속(감소) 부분만 추출.
    증가(물타기)는 D2에서 감쇠력으로 처리.

    Returns: 0 (잔고 증가/유지) ~ 0.7 (급감)
    """
    if idx < lookback:
        return 0.0
    current = credit_data[idx].get("credit_stock")
    past = credit_data[idx - lookback].get("credit_stock")
    if current is None or past is None or past == 0:
        return 0.0
    pct_change = (current - past) / past * 100
    if pct_change >= 0:
        return 0.0    # 증가/유지 → 가속 없음 (D2에서 처리)
    elif pct_change > -1.0:
        return 0.3    # 소폭 감소
    else:
        return 0.7    # 급감 = 투매 진행


# ──────────────────────────────────────────────
# DF D1: 야간시장 반등 강도
# ──────────────────────────────────────────────

def calc_overnight_recovery(
    ewy_pct: float | None = None,
    koru_pct: float | None = None,
    kospi_futures_pct: float | None = None,
    us_market_pct: float | None = None,
) -> float:
    """감쇠력 D1: 야간시장 반등 강도 (4소스 + coherence).

    4개 소스의 가중 평균 반등 시그널 + 방향 일치 보너스.
    양수(반등)만 감쇠로 인정. 음수(하락)는 감쇠 없음.

    Returns: 0 (감쇠 없음) ~ 1 (최대 감쇠)
    """
    sources = {
        "ewy":       (ewy_pct,            OVERNIGHT_EWY_DIVISOR),
        "koru":      (koru_pct,           OVERNIGHT_KORU_DIVISOR),
        "futures":   (kospi_futures_pct,  OVERNIGHT_FUTURES_DIVISOR),
        "us_market": (us_market_pct,      OVERNIGHT_US_DIVISOR),
    }

    # 가용 소스 필터링
    available = {}
    for key, (pct, divisor) in sources.items():
        if pct is not None:
            signal = pct / divisor  # 양수 = 반등, 음수 = 하락
            available[key] = signal

    if not available:
        return 0.0

    # 가중치 재배분 (미확보 소스 제외)
    total_avail_w = sum(OVERNIGHT_WEIGHTS[k] for k in available)
    if total_avail_w <= 0:
        return 0.0

    weighted_signal = sum(
        (OVERNIGHT_WEIGHTS[k] / total_avail_w) * max(sig, 0)
        for k, sig in available.items()
    )

    # Coherence bonus: 방향 일치도
    positive_count = sum(1 for sig in available.values() if sig > 0)
    negative_count = sum(1 for sig in available.values() if sig < 0)
    n = len(available)

    if positive_count == n:
        coherence = 1.3   # 전원 반등 → 강한 감쇠
    elif negative_count == n:
        coherence = 0.0   # 전원 하락 → 감쇠 없음
    elif positive_count > negative_count:
        coherence = 1.0   # 반등 우세
    else:
        coherence = 0.7   # 방향 혼재

    return max(0.0, min(weighted_signal * coherence, 1.0))


# ──────────────────────────────────────────────
# DF D2: 신용잔고 유입률
# ──────────────────────────────────────────────

def calc_credit_inflow_damping(
    credit_data: list[dict], idx: int,
    price_data: list[dict],
) -> float:
    """감쇠력 D2: 하락일 신용 증가 = 저가매수 유입.

    D+1 시차 처리:
    - credit_data[idx] = T-1일 잔고 (T일 공시)
    - price_data[idx] = T-1일 종가

    Returns: 0~1
    """
    if idx < 1:
        return 0.3  # 데이터 부족 → 중립 기본값

    curr_credit = credit_data[idx].get("credit_stock")
    prev_credit = credit_data[idx - 1].get("credit_stock")
    price_change = price_data[idx].get("change_pct", 0) or 0

    if curr_credit is None or prev_credit is None or prev_credit == 0:
        return 0.3

    credit_change = (curr_credit - prev_credit) / prev_credit * 100

    # 하락일 + 잔고 증가 = 저가매수 유입 → 감쇠
    if price_change < -5.0 and credit_change > 1.0:
        return 0.8   # 폭락일 대량 유입 → 강한 감쇠
    elif price_change < -2.0 and credit_change > 0.5:
        return 0.6   # 하락일 유입 → 중간 감쇠
    elif price_change < -2.0 and credit_change > 0:
        return 0.4   # 하락일 소폭 유입
    elif price_change < 0 and credit_change < -0.5:
        return 0.0   # 하락 + 잔고 감소 → 투매 진행, 감쇠 없음
    elif price_change < 0 and credit_change < 0:
        return 0.1   # 하락 + 소폭 감소
    elif credit_change > 0:
        return 0.3   # 상승일 유입 → 약한 감쇠
    else:
        return 0.2   # 기본


# ──────────────────────────────────────────────
# DF D3: 외국인 매도 소진도
# ──────────────────────────────────────────────

def calc_foreign_exhaustion(
    flow_data: list[dict], idx: int, lookback: int = 5,
) -> float:
    """감쇠력 D3: 외국인 매도 소진 정도.

    Returns: 0 (대량 매도 지속) ~ 1 (순매수 전환 확정)
    """
    if idx < 1:
        return 0.3

    curr_foreign = flow_data[idx].get("foreign", 0) or 0
    prev_foreign = flow_data[idx - 1].get("foreign", 0) or 0

    # 패턴 1: 순매수 전환 (이전 매도 → 현재 매수)
    if prev_foreign < -10000 and curr_foreign > 0:
        # 3일+ 연속 순매수 확인
        consecutive_buy = 0
        for i in range(idx, max(idx - 3, -1), -1):
            f = flow_data[i].get("foreign", 0) or 0
            if f > 0:
                consecutive_buy += 1
            else:
                break
        if consecutive_buy >= 3:
            return 1.0   # 확정 전환
        return 0.9       # 1일 전환 (확인 필요)

    # 패턴 2: 매도 규모 반감
    if prev_foreign < 0 and curr_foreign < 0:
        if abs(curr_foreign) < abs(prev_foreign) * 0.5:
            return 0.5   # 매도 규모 반감
        elif abs(curr_foreign) < abs(prev_foreign) * 0.8:
            return 0.3   # 소폭 감소

    # 패턴 3: 소규모 매도 지속
    if -5000 < curr_foreign < 0:
        return 0.3

    # 패턴 4: 대량 매도 가속
    if curr_foreign < prev_foreign and curr_foreign < -10000:
        return 0.0

    # 기타
    if curr_foreign > 0:
        return 0.7   # 순매수 (이전에 매도 아니었음)
    return 0.2


# ──────────────────────────────────────────────
# DF D4: 안전 코호트 버퍼
# ──────────────────────────────────────────────

def calc_safe_buffer(v1_caution_pct: float) -> float:
    """감쇠력 D4: 안전 코호트 비중 (V1의 역수, 비선형).

    캐스케이드의 "방화벽" 역할.

    Returns: 0.05~1.0
    """
    safe_pct = 1.0 - v1_caution_pct

    if safe_pct >= 0.90:
        return 1.0
    elif safe_pct >= 0.70:
        return 0.7 + (safe_pct - 0.70) * 1.5
    elif safe_pct >= 0.40:
        return 0.2 + (safe_pct - 0.40) * 1.67
    else:
        return max(0.05, safe_pct * 0.5)


# ──────────────────────────────────────────────
# RSPI 종합 계산
# ──────────────────────────────────────────────

def calc_rspi(
    v1: float, v2: float, v3: float, v4: float,
    d1: float, d2: float, d3: float, d4: float,
    cf_weights: dict | None = None, df_weights: dict | None = None,
) -> dict:
    """RSPI = CF - DF.

    CF 4변수 (가속력):
      V1: 주의구간 비중 (0~1)
      V2: 연속 하락 (0~1)
      V3: 개인 수급 (0~1)
      V4: 신용 가속 (0~0.7, 정규화 → 0~1)

    DF 4변수 (감쇠력):
      D1~D4: 각 0~1

    Returns: dict with rspi, cascade_force, damping_force, etc.
    """
    if cf_weights is None:
        cf_weights = RSPI_CF_WEIGHTS
    if df_weights is None:
        df_weights = RSPI_DF_WEIGHTS

    # V4 정규화: 0~0.7 → 0~1
    v4_norm = min(v4 / 0.7, 1.0) if v4 > 0 else 0.0

    # CF (0~100)
    total_cf_w = sum(cf_weights.values())
    cf_raw = (
        cf_weights["cf1"] * v1 +
        cf_weights["cf2"] * v2 +
        cf_weights["cf3"] * v3 +
        cf_weights["cf4"] * v4_norm
    )
    cascade_force = max(0, min(100, (cf_raw / total_cf_w) * 100))

    # DF (0~100)
    total_df_w = sum(df_weights.values())
    df_raw = (
        df_weights["df1"] * d1 +
        df_weights["df2"] * d2 +
        df_weights["df3"] * d3 +
        df_weights["df4"] * d4
    )
    damping_force = max(0, min(100, (df_raw / total_df_w) * 100))

    # RSPI
    rspi = max(-100, min(100, cascade_force - damping_force))

    # Level classification
    if rspi >= RSPI_LEVELS["critical"]:
        cascade_risk = "critical"
    elif rspi >= RSPI_LEVELS["high"]:
        cascade_risk = "high"
    elif rspi >= RSPI_LEVELS["medium"]:
        cascade_risk = "medium"
    elif rspi >= RSPI_LEVELS["low"]:
        cascade_risk = "low"
    else:
        cascade_risk = "none"

    # Component contributions
    cf_components = {
        "caution_zone":       round(cf_weights["cf1"] * v1 / total_cf_w * 100, 1),
        "cumulative_decline": round(cf_weights["cf2"] * v2 / total_cf_w * 100, 1),
        "individual_flow":    round(cf_weights["cf3"] * v3 / total_cf_w * 100, 1),
        "credit_accel":       round(cf_weights["cf4"] * v4_norm / total_cf_w * 100, 1),
    }
    df_components = {
        "overnight_recovery":  round(df_weights["df1"] * d1 / total_df_w * 100, 1),
        "credit_inflow":       round(df_weights["df2"] * d2 / total_df_w * 100, 1),
        "foreign_exhaustion":  round(df_weights["df3"] * d3 / total_df_w * 100, 1),
        "safe_buffer":         round(df_weights["df4"] * d4 / total_df_w * 100, 1),
    }

    return {
        "rspi": round(rspi, 1),
        "cascade_force": round(cascade_force, 1),
        "damping_force": round(damping_force, 1),
        "cascade_risk": cascade_risk,
        "cf_components": cf_components,
        "df_components": df_components,
        "raw_variables": {
            "v1": round(v1, 4), "v2": round(v2, 4),
            "v3": round(v3, 4), "v4": round(v4, 4),
            "d1": round(d1, 4), "d2": round(d2, 4),
            "d3": round(d3, 4), "d4": round(d4, 4),
        },
    }


# ──────────────────────────────────────────────
# Impact Function (RSPI > 0일 때만)
# ──────────────────────────────────────────────

def estimate_selling_volume(
    rspi: float,
    samsung_credit_bn: float,
    sensitivity: float = RSPI_SENSITIVITY,
) -> dict:
    """RSPI → sigmoid → 매도비율 → 매도금액.

    RSPI가 0 이하면 매도 없음 (반등 압력).
    """
    if rspi <= 0:
        return {
            "selling_volume_bn": 0,
            "selling_volume_억": 0,
            "sell_ratio_pct": 0,
            "rspi_ratio": 0,
        }
    rspi_ratio = 1 / (1 + math.exp(-RSPI_SIGMOID_K * (rspi - RSPI_SIGMOID_MID)))
    sell_ratio = rspi_ratio * sensitivity
    selling_bn = samsung_credit_bn * sell_ratio
    return {
        "selling_volume_bn": round(selling_bn, 2),
        "selling_volume_억": round(selling_bn * 10000, 0),
        "sell_ratio_pct": round(sell_ratio * 100, 2),
        "rspi_ratio": round(rspi_ratio, 4),
    }


def estimate_price_impact(
    selling_volume_bn: float,
    current_price: int,
    adv_shares_k: float,
    liquidity_factor: float = RSPI_LIQUIDITY_FACTOR,
) -> dict:
    """Kyle's Lambda 기반 비선형 가격영향 추정."""
    if current_price <= 0 or adv_shares_k <= 0 or selling_volume_bn <= 0:
        return {"price_impact_pct": 0, "absorption_ratio": 0, "selling_shares_k": 0}

    selling_shares_k = selling_volume_bn * 1e9 / current_price / 1000
    absorption_ratio = selling_shares_k / adv_shares_k

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


# ──────────────────────────────────────────────
# RSPIEngine 통합 클래스
# ──────────────────────────────────────────────

class RSPIEngine:
    """RSPI 전체 파이프라인 오케스트레이터."""

    def __init__(self, cf_weights=None, df_weights=None):
        self.cf_weights = cf_weights or RSPI_CF_WEIGHTS
        self.df_weights = df_weights or RSPI_DF_WEIGHTS
        self.history: list[dict] = []

    def calculate_for_date(
        self,
        date: str,
        ts: list[dict],
        cohorts: list[dict],
        overnight_data: dict | None = None,
        foreign_flows: list[dict] | None = None,
        samsung_credit_bn: float | None = None,
        current_price: int | None = None,
        adv_shares_k: float | None = None,
    ) -> dict:
        """특정 날짜의 RSPI + Impact 계산."""
        idx = next((i for i, r in enumerate(ts) if r["date"] == date), len(ts) - 1)

        t1_price = current_price or ts[idx].get("samsung", 0) or 0

        # CF 변수
        v1 = calc_caution_zone_pct(t1_price, cohorts) if cohorts else 0.0

        price_data = [
            {"change_pct": r.get("samsung_change_pct") or r.get("kospi_change_pct", 0)}
            for r in ts
        ]
        v2 = calc_cumulative_decline(price_data, idx)

        flow_data = [
            {"individual": (r.get("individual_billion") or 0) * 10000}
            for r in ts
        ]
        v3 = calc_individual_flow_direction(flow_data, idx)

        credit_data = [
            {"credit_stock": r.get("credit_balance_billion", 0)}
            for r in ts
        ]
        v4 = calc_credit_accel_momentum(credit_data, idx)

        # DF 변수
        on = overnight_data or {}
        d1 = calc_overnight_recovery(
            ewy_pct=on.get("ewy_pct"),
            koru_pct=on.get("koru_pct"),
            kospi_futures_pct=on.get("kospi_futures_pct"),
            us_market_pct=on.get("us_market_pct"),
        )

        d2 = calc_credit_inflow_damping(credit_data, idx, price_data)

        foreign_data = foreign_flows or [
            {"foreign": (r.get("foreign_billion") or 0) * 10000}
            for r in ts
        ]
        d3 = calc_foreign_exhaustion(foreign_data, min(idx, len(foreign_data) - 1))

        d4 = calc_safe_buffer(v1)

        # RSPI 종합
        rspi_result = calc_rspi(v1, v2, v3, v4, d1, d2, d3, d4,
                                self.cf_weights, self.df_weights)

        # Impact (RSPI > 0일 때만)
        impact = None
        if rspi_result["rspi"] > 0 and samsung_credit_bn and t1_price and adv_shares_k:
            position_bn = samsung_credit_bn / LOAN_RATE
            sell = estimate_selling_volume(rspi_result["rspi"], position_bn)
            if sell["selling_volume_bn"] > 0:
                price_impact = estimate_price_impact(
                    sell["selling_volume_bn"], t1_price, adv_shares_k
                )
                impact = {
                    "rspi": rspi_result["rspi"],
                    "sell_volume_억": sell["selling_volume_억"],
                    "sell_ratio_pct": sell["sell_ratio_pct"],
                    "price_impact_pct": price_impact["price_impact_pct"],
                    "absorption_ratio": price_impact["absorption_ratio"],
                }

        rspi_result["impact"] = impact

        # 히스토리 저장
        entry = {
            "date": date,
            **rspi_result,
        }
        self.history.append(entry)

        return rspi_result

    def calculate_scenario_matrix(
        self,
        v1: float, v2: float, v3: float, v4: float,
        d2: float, d3: float, d4: float,
        samsung_credit_bn: float,
        current_price: int,
        adv_shares_k: float,
    ) -> list[dict]:
        """D1(야간시장) 시나리오 매트릭스.

        V1~V4, D2~D4를 고정하고 D1만 변경하여 3종 프리셋 생성.
        """
        presets = [
            {"label": "낙관적", "ewy": 2.5,  "koru": 7.5,  "us": 1.5},
            {"label": "기본",   "ewy": -1.0, "koru": -3.0, "us": -0.5},
            {"label": "비관적", "ewy": -4.0, "koru": -12.0, "us": -2.5},
        ]
        results = []
        for p in presets:
            d1 = calc_overnight_recovery(
                ewy_pct=p["ewy"], koru_pct=p["koru"], us_market_pct=p["us"]
            )
            rspi_result = calc_rspi(v1, v2, v3, v4, d1, d2, d3, d4,
                                    self.cf_weights, self.df_weights)

            # Impact
            impact_data = {}
            if rspi_result["rspi"] > 0 and samsung_credit_bn > 0:
                position_bn = samsung_credit_bn / LOAN_RATE
                sell = estimate_selling_volume(rspi_result["rspi"], position_bn)
                if sell["selling_volume_bn"] > 0:
                    pi = estimate_price_impact(
                        sell["selling_volume_bn"], current_price, adv_shares_k
                    )
                    impact_data = {
                        "sell_volume_억": sell["selling_volume_억"],
                        "price_impact_pct": pi["price_impact_pct"],
                    }

            results.append({
                "label": p["label"],
                "ewy_pct": p["ewy"],
                "rspi": rspi_result["rspi"],
                "cascade_force": rspi_result["cascade_force"],
                "damping_force": rspi_result["damping_force"],
                "cascade_risk": rspi_result["cascade_risk"],
                **impact_data,
            })
        return results

    def get_output(self) -> dict:
        """model_output["rspi"]에 저장할 데이터."""
        return {
            "history": self.history,
            "weights": {"cf": self.cf_weights, "df": self.df_weights},
            "latest": self.history[-1] if self.history else None,
        }
