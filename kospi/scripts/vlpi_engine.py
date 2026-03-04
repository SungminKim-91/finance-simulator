#!/usr/bin/env python3
"""
VLPI Engine — 자발적 청산 압력 지수 (Voluntary Liquidation Pressure Index).

2단계 아키텍처:
  Stage 1: Pre-VLPI (6변수 → 0~100 스코어)
  Stage 2: Impact Function (VLPI → 매도금액 → 가격영향)

Usage:
    from scripts.vlpi_engine import VLPIEngine
    engine = VLPIEngine()
    result = engine.calculate_for_date(date, ts, cohorts, events, ...)
"""
import math
from dataclasses import dataclass, field
from pathlib import Path

import sys as _sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import (
    LOAN_RATE, STATUS_THRESHOLDS,
    VLPI_DEFAULT_WEIGHTS, POLICY_SHOCK_MAP,
    SAMSUNG_CREDIT_WEIGHT,
    EWY_GAP_WEIGHTS, EWY_GAP_DIVISOR,
    VLPI_SENSITIVITY, VLPI_SIGMOID_K, VLPI_SIGMOID_MID,
    VLPI_POLICY_MULTIPLIER, VLPI_LIQUIDITY_NORMAL, VLPI_LIQUIDITY_CRISIS,
)


# ──────────────────────────────────────────────
# 담보비율 + 6단계 분류
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# V1: 주의구간 코호트 비중
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# V2: 신용잔고 모멘텀
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# V3: 정책 쇼크
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# V4: 야간 갭 시그널
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# V5: 연속 하락 심각도
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# V6: 전일 개인 수급 방향
# ──────────────────────────────────────────────

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


# ──────────────────────────────────────────────
# Pre-VLPI 종합 계산
# ──────────────────────────────────────────────

@dataclass
class VLPIResult:
    """Pre-VLPI 계산 결과."""
    pre_vlpi: float                    # 0~100
    components: dict                   # V1~V6 기여분 (합 = pre_vlpi)
    raw_variables: dict                # V1~V6 원시값
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


# ──────────────────────────────────────────────
# Stage 2: Impact Function
# ──────────────────────────────────────────────

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
    """
    if current_price <= 0 or adv_shares_k <= 0:
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


# ──────────────────────────────────────────────
# VLPIEngine 통합 클래스
# ──────────────────────────────────────────────

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
        """특정 날짜의 Pre-VLPI + Impact 계산."""
        # date의 인덱스 찾기
        idx = next((i for i, r in enumerate(ts) if r["date"] == date), len(ts) - 1)

        # T-1 종가 (삼성전자)
        t1_price = current_price or ts[idx].get("samsung", 0) or 0

        # V1: 주의구간 비중
        v1 = calc_caution_zone_pct(t1_price, cohorts) if cohorts else 0.0

        # V2: 신용잔고 모멘텀
        credit_data = [
            {"credit_stock": r.get("credit_balance_billion", 0)}
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

        # V6: 개인 수급 (timeseries individual_billion은 조원 → 억원 변환)
        flow_data = [
            {"individual": (r.get("individual_billion") or 0) * 10000}
            for r in ts
        ]
        v6 = calc_individual_flow_direction(flow_data, idx)

        # Pre-VLPI
        result = calc_pre_vlpi(v1, v2, v3, v4, v5, v6, self.weights)

        # Stage 2: Impact (선택)
        if samsung_credit_bn and t1_price and adv_shares_k:
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
