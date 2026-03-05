#!/usr/bin/env python3
"""
RSPI Engine v2.2.0 -- Retail Selling Pressure Index (개인 매도 압력 지수).

5변수 + 거래량 증폭기 아키텍처:
  RSPI = -1 * (w1*V1 + w2*V2 + w3*V3 + w4*V4 + w5*V5) * VolumeAmp * 100

부호 규칙:
  변수 내부: 양수 = 매도 방향
  최종 출력: 부호 반전 -> 음수 = 매도 압력(빨간), 양수 = 반등 압력(초록)

범위: -100 ~ +100

Usage:
    from scripts.rspi_engine import RSPIEngine
    engine = RSPIEngine()
    result = engine.calculate_for_date(date, ts, cohorts, overnight_data)
"""
import math
from pathlib import Path

import sys as _sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import (
    LOAN_RATE, STATUS_THRESHOLDS, SAMSUNG_CREDIT_WEIGHT,
    RSPI_WEIGHTS,
    V1_MARGIN_CALL_RATIO, V1_SAFE_RANGE, V1_PROXIMITY_POWER,
    V2_LOOKBACK, V2_DIVISOR,
    OVERNIGHT_WEIGHTS,
    OVERNIGHT_EWY_DIVISOR, OVERNIGHT_KORU_DIVISOR,
    OVERNIGHT_FUTURES_DIVISOR, OVERNIGHT_US_DIVISOR,
    OVERNIGHT_COHERENCE_BONUS, OVERNIGHT_COHERENCE_PENALTY,
    V4_CAPITULATION_PREV, V4_CAPITULATION_CURR,
    V4_LARGE_BUY, V4_DECLINE_RATIO,
    V5_DIVISOR,
    VA_FLOOR, VA_CEILING, VA_LOG_SCALE,
    RSPI_SENSITIVITY, RSPI_SIGMOID_K, RSPI_SIGMOID_MID,
    RSPI_LIQUIDITY_FACTOR, RSPI_LEVELS,
)


# ──────────────────────────────────────────────
# 담보비율 + 6단계 분류 (유지)
# ──────────────────────────────────────────────

def calc_collateral_ratio(current_price: float, entry_price: float) -> float:
    """담보비율(%) = 현재가 / (매수가 * LOAN_RATE) * 100."""
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
# V1: 코호트 proximity (0~1, 단방향)
# ──────────────────────────────────────────────

def calc_cohort_proximity(current_price: float, cohorts: list[dict],
                          power: float = V1_PROXIMITY_POWER) -> float:
    """V1: 각 코호트의 마진콜(140%)까지 거리를 비선형 proximity로.

    linear = max(0, min(1, 1 - (ratio - 140) / 60))
    proximity = linear ** power  (비선형 변환, power=2.5)
    V1 = 코호트별 proximity의 금액 가중 평균

    power=2.5 효과:
      ratio 200% -> linear 0.00 -> proximity 0.00  (안전)
      ratio 185% -> linear 0.25 -> proximity 0.09  (여유)
      ratio 170% -> linear 0.50 -> proximity 0.18  (양호)
      ratio 155% -> linear 0.75 -> proximity 0.41  (주의)
      ratio 145% -> linear 0.92 -> proximity 0.78  (위험!)
      ratio 140% -> linear 1.00 -> proximity 1.00  (마진콜)

    Returns: 0 (전부 안전) ~ 1 (전부 마진콜 직전)
    """
    total_weight = 0.0
    weighted_proximity = 0.0

    for cohort in cohorts:
        entry_price = cohort.get("entry_kospi") or cohort.get("entry_price", 0)
        if entry_price <= 0:
            continue
        ratio = calc_collateral_ratio(current_price, entry_price)
        linear = max(0.0, min(1.0, 1.0 - (ratio - V1_MARGIN_CALL_RATIO) / V1_SAFE_RANGE))
        proximity = linear ** power

        w = cohort.get("remaining_amount_billion") or cohort.get("weight", 0)
        weighted_proximity += proximity * w
        total_weight += w

    return weighted_proximity / total_weight if total_weight > 0 else 0.0


# ──────────────────────────────────────────────
# V2: 외국인 수급 방향 (-1~+1, z-score)
# ──────────────────────────────────────────────

def calc_foreign_direction(foreign_flows: list[float], idx: int,
                           lookback: int = V2_LOOKBACK) -> float:
    """V2: 외국인 순매매의 z-score -> 양방향 시그널.

    z = (오늘 순매매 - N일 평균) / N일 표준편차
    V2 = clamp(-1, 1, -z / divisor)

    z = -3 (극단 매도) -> V2 = +1.0 (매도 시그널)
    z =  0 (평균)      -> V2 =  0.0
    z = +3 (극단 매수) -> V2 = -1.0 (반등 시그널)

    Returns: -1 ~ +1
    """
    if idx < 1:
        return 0.0

    start = max(0, idx - lookback + 1)
    recent = foreign_flows[start:idx + 1]
    if len(recent) < 2:
        return 0.0

    avg = sum(recent) / len(recent)
    variance = sum((x - avg) ** 2 for x in recent) / len(recent)
    std = max(variance ** 0.5, 1.0)  # 0 방지

    z = (foreign_flows[idx] - avg) / std
    return max(-1.0, min(1.0, -z / V2_DIVISOR))


# ──────────────────────────────────────────────
# V3: 야간시장 시그널 (-1~+1, 4소스 + coherence)
# ──────────────────────────────────────────────

def calc_overnight_signal(
    ewy_pct: float | None = None,
    koru_pct: float | None = None,
    futures_pct: float | None = None,
    us_market_pct: float | None = None,
) -> float:
    """V3: 4개 야간시장 소스의 가중평균 + 방향일치 보너스.

    각 소스: signal = -(변동률 / divisor)
    -> 하락이면 양수(매도), 상승이면 음수(반등)

    Coherence: 전부 같은 방향 -> x1.3, 방향 혼재 -> x0.7

    Returns: -1 (강한 갭업=반등) ~ +1 (강한 갭다운=매도)
    """
    divisors = {
        "ewy": OVERNIGHT_EWY_DIVISOR,
        "koru": OVERNIGHT_KORU_DIVISOR,
        "futures": OVERNIGHT_FUTURES_DIVISOR,
        "us_market": OVERNIGHT_US_DIVISOR,
    }
    values = {
        "ewy": ewy_pct,
        "koru": koru_pct,
        "futures": futures_pct,
        "us_market": us_market_pct,
    }

    sources = []
    for key, pct in values.items():
        if pct is not None:
            signal = -pct / divisors[key]
            sources.append({"key": key, "signal": signal, "weight": OVERNIGHT_WEIGHTS[key]})

    if not sources:
        return 0.0

    # 가중치 재배분 (미확보 소스 제외)
    total_w = sum(s["weight"] for s in sources)
    for s in sources:
        s["weight"] /= total_w

    # 가중 평균
    weighted = sum(s["signal"] * s["weight"] for s in sources)

    # Coherence
    signs = [1 if s["signal"] > 0 else -1 if s["signal"] < 0 else 0 for s in sources]
    non_zero = [s for s in signs if s != 0]
    if non_zero and len(set(non_zero)) <= 1:
        coherence = OVERNIGHT_COHERENCE_BONUS  # 전원 같은 방향
    else:
        coherence = OVERNIGHT_COHERENCE_PENALTY  # 방향 혼재

    v3 = weighted * coherence
    return max(-1.0, min(1.0, v3))


# ──────────────────────────────────────────────
# V4: 개인 수급 방향 (-1~+1, 패턴 기반)
# ──────────────────────────────────────────────

def calc_individual_direction(individual_flows: list[float], idx: int) -> float:
    """V4: 개인 순매수 패턴 -> 양방향 시그널.

    +1.0 = 항복 (대량 매수 -> 급감)
    +0.7 = 매수 급감
    +0.5 = 순매도 전환
    +0.2 = 기본 (소규모 매도)
    -0.1 = 소규모 매수
    -0.4 = 대량 매수 유지 (매도 흡수)

    Returns: -1 ~ +1
    """
    if idx < 1:
        return 0.0

    curr = individual_flows[idx]
    prev = individual_flows[idx - 1]

    # 항복: 대량 매수 -> 급감
    if prev > V4_CAPITULATION_PREV and curr < V4_CAPITULATION_CURR:
        return 1.0

    # 매수 급감
    if prev > 200 and curr < prev * V4_DECLINE_RATIO:
        return 0.7

    # 순매도 전환
    if prev > 0 and curr < 0:
        return 0.5

    # 대량 매수 유지 (매도 흡수)
    if curr > V4_LARGE_BUY:
        return -0.4

    # 소규모 매수
    if curr > 0:
        return -0.1

    # 기본 (소규모 매도)
    return 0.2


# ──────────────────────────────────────────────
# V5: 신용잔고 모멘텀 (-1~+1, 양방향)
# ──────────────────────────────────────────────

def calc_credit_momentum(credit_data: list[float], idx: int) -> float:
    """V5: 신용잔고 변화율 -> 양방향 연속 함수.

    V5 = clamp(-1, 1, -change_pct / divisor)

    +2% 증가 -> V5 = -1.0 (강한 유입 = 반등 시그널)
    0%       -> V5 =  0.0
    -2% 감소 -> V5 = +1.0 (대규모 투매 = 매도 시그널)

    시차: credit_data[idx] = T-1일 잔고 (가장 최신 확보 가능)

    Returns: -1 ~ +1
    """
    if idx < 1:
        return 0.0

    curr = credit_data[idx]
    prev = credit_data[idx - 1]

    if curr is None or prev is None or prev == 0:
        return 0.0

    change_pct = (curr - prev) / prev * 100
    return max(-1.0, min(1.0, -change_pct / V5_DIVISOR))


# ──────────────────────────────────────────────
# VA: 거래량 증폭기 (0.3~2.0)
# ──────────────────────────────────────────────

def calc_volume_amplifier(volume_today: float, adv_20: float,
                          recent_5d: list[float]) -> float:
    """VA: 적응형 기준선 + log2 스케일링.

    baseline = max(ADV_20, 최근 5일 평균)
    amp = 1 + 0.5 * log2(volume / baseline)

    ratio 0.5 -> amp 0.50 (확신 낮음)
    ratio 1.0 -> amp 1.00 (중립)
    ratio 2.0 -> amp 1.50 (확신 높음)

    Returns: VA_FLOOR ~ VA_CEILING
    """
    if volume_today <= 0 or adv_20 <= 0:
        return 1.0

    recent_avg = sum(recent_5d) / len(recent_5d) if recent_5d else adv_20
    baseline = max(adv_20, recent_avg)

    if baseline <= 0:
        return 1.0

    ratio = volume_today / baseline
    amp = 1.0 + VA_LOG_SCALE * math.log2(max(ratio, 0.01))
    return max(VA_FLOOR, min(VA_CEILING, amp))


# ──────────────────────────────────────────────
# RSPI 종합 계산
# ──────────────────────────────────────────────

def classify_level(rspi: float) -> str:
    """RSPI 값 -> 7단계 레벨 키."""
    for level in RSPI_LEVELS:
        if level["min"] <= rspi < level["max"]:
            return level["key"]
    # edge case: rspi == 100
    return RSPI_LEVELS[-1]["key"] if rspi >= 0 else RSPI_LEVELS[0]["key"]


def calc_rspi(
    v1: float, v2: float, v3: float, v4: float, v5: float,
    volume_amp: float,
    weights: dict | None = None,
) -> dict:
    """RSPI = -1 * (weighted_sum) * volume_amp * 100.

    Returns:
        rspi, level, raw, volume_amp, raw_variables, variable_contributions
    """
    w = weights or RSPI_WEIGHTS

    raw = (
        w["v1"] * v1 +
        w["v2"] * v2 +
        w["v3"] * v3 +
        w["v4"] * v4 +
        w["v5"] * v5
    )

    rspi = -1.0 * raw * volume_amp * 100.0
    rspi = max(-100.0, min(100.0, rspi))

    level = classify_level(rspi)

    # 각 변수의 기여분 (부호 반전 후, 퍼센트)
    contributions = {
        "v1": round(-w["v1"] * v1 * volume_amp * 100, 2),
        "v2": round(-w["v2"] * v2 * volume_amp * 100, 2),
        "v3": round(-w["v3"] * v3 * volume_amp * 100, 2),
        "v4": round(-w["v4"] * v4 * volume_amp * 100, 2),
        "v5": round(-w["v5"] * v5 * volume_amp * 100, 2),
    }

    return {
        "rspi": round(rspi, 1),
        "level": level,
        "raw": round(raw, 4),
        "volume_amp": round(volume_amp, 3),
        "raw_variables": {
            "v1": round(v1, 4), "v2": round(v2, 4), "v3": round(v3, 4),
            "v4": round(v4, 4), "v5": round(v5, 4),
        },
        "variable_contributions": contributions,
    }


# ──────────────────────────────────────────────
# Impact Function (RSPI 음수=매도일 때만)
# ──────────────────────────────────────────────

def estimate_selling_volume(
    rspi: float,
    samsung_credit_bn: float,
    sensitivity: float = RSPI_SENSITIVITY,
) -> dict:
    """RSPI -> sigmoid -> 매도비율 -> 매도금액.

    v2.2.0: RSPI 음수 = 매도 압력. |RSPI|를 입력으로 사용.
    """
    if rspi >= 0:
        return {"selling_volume_bn": 0, "selling_volume_억": 0,
                "sell_ratio_pct": 0, "rspi_ratio": 0}

    abs_rspi = abs(rspi)
    rspi_ratio = 1 / (1 + math.exp(-RSPI_SIGMOID_K * (abs_rspi - RSPI_SIGMOID_MID)))
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
    """RSPI v2.2.0 전체 파이프라인."""

    def __init__(self, weights=None, proximity_power=V1_PROXIMITY_POWER):
        self.weights = weights or RSPI_WEIGHTS
        self.proximity_power = proximity_power
        self.history: list[dict] = []

    def calculate_for_date(
        self,
        date: str,
        ts: list[dict],
        cohorts: list[dict],
        overnight_data: dict | None = None,
        current_price: int | None = None,
        adv_shares_k: float | None = None,
        samsung_credit_bn: float | None = None,
    ) -> dict:
        """특정 날짜의 RSPI 계산."""
        idx = next((i for i, r in enumerate(ts) if r["date"] == date), len(ts) - 1)

        t1_price = current_price or ts[idx].get("samsung", 0) or 0
        kospi_price = ts[idx].get("kospi", 0) or 0

        # V1: 코호트 proximity (KOSPI 지수 기반 — 코호트는 entry_kospi 기준, 비선형 power)
        v1 = calc_cohort_proximity(kospi_price, cohorts, power=self.proximity_power) if cohorts and kospi_price > 0 else 0.0

        # V2: 외국인 수급 z-score
        foreign_flows = [
            (r.get("foreign_billion") or 0) * 10000  # 십억원 -> 억원
            for r in ts
        ]
        v2 = calc_foreign_direction(foreign_flows, idx)

        # V3: 야간시장 시그널
        on = overnight_data or {}
        has_overnight = any(on.get(k) is not None for k in
                           ["ewy_pct", "koru_pct", "kospi_futures_pct", "us_market_pct"])

        # 최신일에 야간 데이터 미확보 → RSPI 계산 불가 (pending)
        is_latest = (idx == len(ts) - 1)
        if is_latest and not has_overnight:
            pending_result = {
                "rspi": None,
                "level": "pending",
                "raw": None,
                "volume_amp": None,
                "raw_variables": {"v1": round(v1, 4), "v2": round(v2, 4),
                                  "v3": None, "v4": None, "v5": None},
                "variable_contributions": {"v1": None, "v2": None,
                                           "v3": None, "v4": None, "v5": None},
                "impact": None,
                "pending": True,
            }
            entry = {"date": date, **pending_result}
            self.history.append(entry)
            return pending_result

        v3 = calc_overnight_signal(
            ewy_pct=on.get("ewy_pct"),
            koru_pct=on.get("koru_pct"),
            futures_pct=on.get("kospi_futures_pct"),
            us_market_pct=on.get("us_market_pct"),
        )

        # V4: 개인 수급 방향
        individual_flows = [
            (r.get("individual_billion") or 0) * 10000  # 십억원 -> 억원
            for r in ts
        ]
        v4 = calc_individual_direction(individual_flows, idx)

        # V5: 신용잔고 모멘텀
        credit_data = [r.get("credit_balance_billion") for r in ts]
        v5 = calc_credit_momentum(credit_data, idx)

        # VA: 거래량 증폭기
        trading_values = [r.get("kospi_trading_value_billion") or r.get("trading_value_billion") or 0
                          for r in ts]
        vol_today = trading_values[idx] if idx < len(trading_values) else 0
        vol_start = max(0, idx - 19)
        vol_window = trading_values[vol_start:idx + 1]
        adv_20 = sum(vol_window) / len(vol_window) if vol_window else 1
        recent_5d = trading_values[max(0, idx - 4):idx + 1]
        volume_amp = calc_volume_amplifier(vol_today, adv_20, recent_5d)

        # RSPI 종합
        rspi_result = calc_rspi(v1, v2, v3, v4, v5, volume_amp, self.weights)

        # Impact (RSPI < 0 = 매도 압력일 때만)
        impact = None
        if rspi_result["rspi"] < 0 and samsung_credit_bn and t1_price and adv_shares_k:
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
        entry = {"date": date, **rspi_result}
        self.history.append(entry)

        return rspi_result

    def calculate_scenario_matrix(
        self,
        v1: float, v2: float, v4: float, v5: float,
        volume_amp: float,
        samsung_credit_bn: float,
        current_price: int,
        adv_shares_k: float,
    ) -> list[dict]:
        """V3(야간시장)만 변경하여 3종 프리셋 시나리오 생성."""
        presets = [
            {"label": "낙관적", "ewy": 2.5, "koru": 7.5, "us": 1.5},
            {"label": "기본",   "ewy": -1.0, "koru": -3.0, "us": -0.5},
            {"label": "비관적", "ewy": -4.0, "koru": -12.0, "us": -2.5},
        ]
        results = []
        for p in presets:
            v3 = calc_overnight_signal(
                ewy_pct=p["ewy"], koru_pct=p["koru"], us_market_pct=p["us"]
            )
            rspi_result = calc_rspi(v1, v2, v3, v4, v5, volume_amp, self.weights)

            # Impact
            impact_data = {}
            if rspi_result["rspi"] < 0 and samsung_credit_bn > 0:
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
                "level": rspi_result["level"],
                "raw": rspi_result["raw"],
                "volume_amp": rspi_result["volume_amp"],
                **impact_data,
            })
        return results

    def get_output(self) -> dict:
        """model_output["rspi"]에 저장할 데이터."""
        return {
            "history": self.history,
            "weights": self.weights,
            "latest": self.history[-1] if self.history else None,
        }
