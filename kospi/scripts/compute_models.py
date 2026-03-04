#!/usr/bin/env python3
"""
KOSPI 모델 연산 메인 스크립트.
fetch_daily.py 이후 실행 — 수집된 데이터로 모델 산출.

Modules:
    A: CohortBuilder — 신용잔고 코호트 생성/해소 (Phase 2)
    B: ForcedLiqSimulator — 반대매매 연쇄 시뮬레이션 (Phase 2)
    C: CrisisScorer — 위기 점수 산출 (14개 지표 PCA 가중)
    D: BayesianScenarioTracker — 5개 시나리오 확률 업데이트
    E: HistoricalComparator — 과거 사례 DTW+Cosine 유사도

Usage:
    python kospi/scripts/compute_models.py                     # 전체 모델 실행
    python kospi/scripts/compute_models.py --module cohort     # 코호트만
    python kospi/scripts/compute_models.py --module crisis     # 위기 점수만
"""
import argparse
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from scipy.spatial.distance import cosine as cosine_dist
except ImportError:
    cosine_dist = None

try:
    from tslearn.metrics import dtw as tslearn_dtw
except ImportError:
    tslearn_dtw = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

try:
    from config.constants import TOP_10_TICKERS, STOCK_GROUP_PARAMS
except ImportError:
    TOP_10_TICKERS = {}
    STOCK_GROUP_PARAMS = {}


# ──────────────────────────────────────────────
# Module A: 코호트 모델
# ──────────────────────────────────────────────

@dataclass
class Cohort:
    cohort_id: str
    entry_date: str
    entry_kospi: float
    entry_samsung: float
    entry_hynix: float
    initial_amount_billion: float
    remaining_amount_billion: float

    def pnl_pct(self, current_kospi: float) -> float:
        if self.entry_kospi == 0:
            return 0
        return (current_kospi - self.entry_kospi) / self.entry_kospi * 100

    def collateral_ratio(self, current_kospi: float, margin_rate: float = 0.40) -> float:
        if self.entry_kospi == 0:
            return 999
        price_ratio = current_kospi / self.entry_kospi
        return price_ratio / (1 - margin_rate)

    def status(self, current_kospi: float, margin_rate: float = 0.40) -> str:
        """분포 기반 가중평균 상태 판정."""
        ratio = self.collateral_ratio(current_kospi, margin_rate)
        # 분포 기반: 각 종목군별 threshold에서 가중 판정
        forced_w = 0.0
        margin_w = 0.0
        watch_w = 0.0
        safe_w = 0.0
        for fl_ratio, fl_weight in FORCED_LIQ_DISTRIBUTION.items():
            for mt_ratio, mt_weight in MAINTENANCE_DISTRIBUTION.items():
                w = fl_weight * mt_weight
                if ratio < fl_ratio:
                    forced_w += w
                elif ratio < mt_ratio:
                    margin_w += w
                elif ratio < mt_ratio + 0.20:
                    watch_w += w
                else:
                    safe_w += w
        # 가중평균으로 최다 상태 반환
        scores = {"forced_liq": forced_w, "margin_call": margin_w, "watch": watch_w, "safe": safe_w}
        return max(scores, key=scores.get)


class CohortBuilder:
    """신용잔고 코호트 생성/해소 엔진."""

    def __init__(self, mode: str = "LIFO"):
        self.mode = mode
        self.active_cohorts: list[Cohort] = []
        self.closed_cohorts: list[Cohort] = []

    def process_day(
        self, date: str, credit_balance: float,
        prev_credit: float, kospi: float,
        samsung: float = 0, hynix: float = 0,
    ) -> None:
        delta = credit_balance - prev_credit
        if delta > 0:
            self._create_cohort(date, delta, kospi, samsung, hynix)
        elif delta < 0:
            self._repay_cohorts(abs(delta))

    def _create_cohort(self, date, amount, kospi, samsung, hynix):
        c = Cohort(
            cohort_id=date,
            entry_date=date,
            entry_kospi=kospi,
            entry_samsung=samsung,
            entry_hynix=hynix,
            initial_amount_billion=amount,
            remaining_amount_billion=amount,
        )
        self.active_cohorts.append(c)

    def _repay_cohorts(self, amount):
        remaining = amount
        if self.mode == "LIFO":
            cohorts = reversed(self.active_cohorts)
        else:
            cohorts = iter(self.active_cohorts)

        for c in cohorts:
            if remaining <= 0:
                break
            repay = min(remaining, c.remaining_amount_billion)
            c.remaining_amount_billion -= repay
            remaining -= repay
            if c.remaining_amount_billion <= 0:
                self.closed_cohorts.append(c)

        self.active_cohorts = [
            c for c in self.active_cohorts if c.remaining_amount_billion > 0
        ]

    def get_status(self, current_kospi: float) -> dict:
        active = []
        for c in self.active_cohorts:
            active.append({
                "cohort_id": c.cohort_id,
                "entry_date": c.entry_date,
                "entry_kospi": c.entry_kospi,
                "remaining_amount_billion": c.remaining_amount_billion,
                "pnl_pct": round(c.pnl_pct(current_kospi), 2),
                "collateral_ratio": round(c.collateral_ratio(current_kospi), 3),
                "status": c.status(current_kospi),
            })

        return {
            "active": active,
            "mode": self.mode,
            "total_active_billion": sum(
                c.remaining_amount_billion for c in self.active_cohorts
            ),
        }

    def get_price_distribution(self, current_kospi: float, bin_size: int = 100) -> list[dict]:
        """100pt 구간별 status 분포."""
        bins: dict[str, dict] = {}
        for c in self.active_cohorts:
            b = int(c.entry_kospi // bin_size) * bin_size
            key = f"{b}-{b + bin_size}"
            if key not in bins:
                bins[key] = {"range": key, "bin": b, "safe": 0, "watch": 0, "margin_call": 0, "forced_liq": 0}
            st = c.status(current_kospi)
            bins[key][st] += c.remaining_amount_billion
        return sorted(bins.values(), key=lambda x: x["bin"])

    def get_trigger_map(
        self, current_kospi: float, current_fx: float,
        shocks: list[float] | None = None,
    ) -> list[dict]:
        """충격별 margin_call/forced_liq 추정 (분포 기반)."""
        if shocks is None:
            shocks = [-3, -5, -10, -15, -20, -30]
        result = []
        for shock in shocks:
            expected_kospi = current_kospi * (1 + shock / 100)
            margin_call = 0.0
            forced_liq = 0.0
            for c in self.active_cohorts:
                if c.entry_kospi == 0:
                    continue
                for margin_rate, mr_w in MARGIN_DISTRIBUTION.items():
                    ratio = (expected_kospi / c.entry_kospi) / (1 - margin_rate)
                    for fl_ratio, fl_w in FORCED_LIQ_DISTRIBUTION.items():
                        for mt_ratio, mt_w in MAINTENANCE_DISTRIBUTION.items():
                            w = mr_w * fl_w * mt_w
                            if ratio < fl_ratio:
                                forced_liq += c.remaining_amount_billion * w
                            elif ratio < mt_ratio:
                                margin_call += c.remaining_amount_billion * w
            result.append({
                "shock_pct": shock,
                "expected_kospi": round(expected_kospi),
                "margin_call_billion": round(margin_call),
                "forced_liq_billion": round(forced_liq),
            })
        return result


# ──────────────────────────────────────────────
# Module A-2: 종목별 가중 코호트 매니저
# ──────────────────────────────────────────────

class StockCohortManager:
    """Top N 종목별 독립 코호트 + 잔여 코호트 관리자.

    - 각 종목: 시가총액 비중으로 시장 전체 신용잔고를 배분
    - 잔여: (전체 - Top N 합계) → residual CohortBuilder
    - 종목별 코호트는 해당 종목 가격 기반으로 status 판정
    - KOSPI 가중치로 반대매매 지수 영향 산출
    """

    def __init__(self, tickers_config: dict, mode: str = "LIFO"):
        """
        Args:
            tickers_config: {ticker: {name, group, ...}} from constants.TOP_10_TICKERS
        """
        self.tickers_config = tickers_config
        self.mode = mode
        self.builders: dict[str, CohortBuilder] = {
            t: CohortBuilder(mode) for t in tickers_config
        }
        self.residual = CohortBuilder(mode)
        self.stock_weights: dict[str, float] = {}  # KOSPI weight per stock

    def process_day(
        self, date: str, ts_row: dict, stock_credit: dict | None,
    ) -> None:
        """일별 처리: 종목별 코호트 갱신.

        Args:
            ts_row: timeseries row (kospi, samsung, hynix, credit_balance_billion, ...)
            stock_credit: {ticker: credit_billion} or None (fallback to market-level)
        """
        total_credit = ts_row.get("credit_balance_billion") or 0
        kospi = ts_row.get("kospi") or 0

        if not stock_credit or not total_credit:
            return

        # 각 종목별 처리
        top10_sum = 0
        for ticker, builder in self.builders.items():
            credit_b = stock_credit.get(ticker, 0) or 0
            top10_sum += credit_b

            # 종목 종가: timeseries에 있으면 사용, 없으면 stock_credit의 close
            stock_close = ts_row.get(f"stock_{ticker}_close") or 0

            # 이전 상태에서의 잔고 (builder의 현재 합계)
            prev_amount = sum(c.remaining_amount_billion for c in builder.active_cohorts)
            if prev_amount == 0 and credit_b > 0:
                prev_amount = credit_b * 0.98  # 첫 날 bootstrap: 약간의 신규 진입
            builder.process_day(
                date=date,
                credit_balance=credit_b,
                prev_credit=prev_amount,
                kospi=stock_close if stock_close > 0 else kospi,
                samsung=ts_row.get("samsung", 0) or 0,
                hynix=ts_row.get("hynix", 0) or 0,
            )

        # 잔여 = 전체 - Top10
        residual_credit = max(0, total_credit - top10_sum)
        prev_residual = sum(c.remaining_amount_billion for c in self.residual.active_cohorts)
        if prev_residual == 0 and residual_credit > 0:
            prev_residual = residual_credit * 0.98
        self.residual.process_day(
            date=date,
            credit_balance=residual_credit,
            prev_credit=prev_residual,
            kospi=kospi,
            samsung=ts_row.get("samsung", 0) or 0,
            hynix=ts_row.get("hynix", 0) or 0,
        )

    def set_weights(self, weights: dict[str, float]) -> None:
        """KOSPI 시가총액 가중치 설정 (from fetch_stock_market_caps)."""
        self.stock_weights = weights

    def get_stock_summary(self, current_kospi: float) -> list[dict]:
        """종목별 신용잔고 요약 (프론트엔드용)."""
        result = []
        for ticker, builder in self.builders.items():
            info = self.tickers_config[ticker]
            total = sum(c.remaining_amount_billion for c in builder.active_cohorts)
            weight = self.stock_weights.get(ticker, 0)

            # 상태 집계
            status_counts = {"safe": 0, "watch": 0, "margin_call": 0, "forced_liq": 0}
            for c in builder.active_cohorts:
                st = c.status(current_kospi)
                status_counts[st] += c.remaining_amount_billion

            result.append({
                "ticker": ticker,
                "name": info["name"],
                "group": info["group"],
                "credit_billion": round(total, 2),
                "kospi_weight_pct": round(weight * 100, 2),
                "status_breakdown": {k: round(v, 2) for k, v in status_counts.items()},
            })

        # Residual
        res_total = sum(c.remaining_amount_billion for c in self.residual.active_cohorts)
        res_status = {"safe": 0, "watch": 0, "margin_call": 0, "forced_liq": 0}
        for c in self.residual.active_cohorts:
            st = c.status(current_kospi)
            res_status[st] += c.remaining_amount_billion

        result.append({
            "ticker": "_residual",
            "name": "기타",
            "group": "mixed",
            "credit_billion": round(res_total, 2),
            "kospi_weight_pct": round((1 - sum(self.stock_weights.values())) * 100, 2),
            "status_breakdown": {k: round(v, 2) for k, v in res_status.items()},
        })

        return sorted(result, key=lambda x: x["credit_billion"], reverse=True)

    def get_weighted_trigger_map(
        self, current_kospi: float, current_fx: float,
        shocks: list[float] | None = None,
    ) -> list[dict]:
        """종목별 가중 트리거맵: 종목별 반대매매 × KOSPI 가중치 = 지수 영향."""
        if shocks is None:
            shocks = [-3, -5, -10, -15, -20, -30]

        result = []
        for shock in shocks:
            total_margin = 0
            total_forced = 0
            weighted_impact = 0

            for ticker, builder in self.builders.items():
                w = self.stock_weights.get(ticker, 0)
                tm = builder.get_trigger_map(current_kospi, current_fx, [shock])
                if tm:
                    mc = tm[0]["margin_call_billion"]
                    fl = tm[0]["forced_liq_billion"]
                    total_margin += mc
                    total_forced += fl
                    weighted_impact += fl * w

            # Residual
            res_w = 1 - sum(self.stock_weights.values())
            res_tm = self.residual.get_trigger_map(current_kospi, current_fx, [shock])
            if res_tm:
                total_margin += res_tm[0]["margin_call_billion"]
                total_forced += res_tm[0]["forced_liq_billion"]
                weighted_impact += res_tm[0]["forced_liq_billion"] * max(0, res_w)

            expected_kospi = current_kospi * (1 + shock / 100)
            result.append({
                "shock_pct": shock,
                "expected_kospi": round(expected_kospi),
                "margin_call_billion": round(total_margin),
                "forced_liq_billion": round(total_forced),
                "weighted_impact_billion": round(weighted_impact),
            })

        return result


# ──────────────────────────────────────────────
# Module B: 반대매매 시뮬레이터
# ──────────────────────────────────────────────

# 증거금률 분포 (증권사/종목별 상이)
MARGIN_DISTRIBUTION = {
    0.40: 0.30,  # 40% 증거금 (대형주 우량)
    0.45: 0.30,  # 45% (일반)
    0.50: 0.25,  # 50%
    0.60: 0.15,  # 60% (고위험)
}

# 담보유지비율 분포 (증권사 × 종목군 가중평균)
# 금투협: A군=140%, B군=145%, C군=150%, D군=160%
MAINTENANCE_DISTRIBUTION = {
    1.40: 0.45,  # A종목군 대형주
    1.45: 0.25,  # B종목군 중형주
    1.50: 0.20,  # C종목군 소형주
    1.60: 0.10,  # D종목군 고위험/테마주
}

# 강제청산 비율 분포 (유지비율 미달 후 추가담보 미납 시)
FORCED_LIQ_DISTRIBUTION = {
    1.20: 0.45,  # A종목군: 140% 미달 → D+1 미납 → ~120%에서 청산
    1.25: 0.25,  # B종목군: 145% 미달 → 125%에서 청산
    1.30: 0.20,  # C종목군: 150% 미달 → 130%에서 청산
    1.40: 0.10,  # D종목군: 160% 미달 → 140%에서 청산
}

# 호환용 단일값 (가중평균)
MAINTENANCE_RATIO = sum(k * v for k, v in MAINTENANCE_DISTRIBUTION.items())  # ~1.435
FORCED_LIQ_RATIO = sum(k * v for k, v in FORCED_LIQ_DISTRIBUTION.items())    # ~1.245


class ForcedLiqSimulator:
    """반대매매 연쇄 피드백 루프 시뮬레이터 — 이중 루프 (A: 반대매매, B: 환율-외국인)."""

    @staticmethod
    def _fx_sensitivity(fx_change_pct: float) -> float:
        """비선형 환율 민감도."""
        abs_fx = abs(fx_change_pct)
        if abs_fx <= 1:
            return 0.5
        if abs_fx <= 2:
            return 1.0
        if abs_fx <= 3:
            return 1.5
        return 2.0

    def run(
        self,
        cohorts: list[dict],
        initial_price: float,
        price_shock_pct: float = -5.0,
        max_rounds: int = 5,
        absorption_rate: float = 0.5,
        avg_daily_trading_value: float = 10000,
        impact_coefficient: float = 1.5,
        initial_fx: float = 1400.0,
        loop_mode: str = "AB",  # "A", "B", "AB"
    ) -> dict:
        rounds = []
        price = initial_price * (1 + price_shock_pct / 100)
        fx = initial_fx

        for r in range(1, max_rounds + 1):
            # Loop A: forced liquidation (분포 기반)
            forced_liq = 0
            margin_call = 0
            impact_a = 0.0
            if loop_mode in ("A", "AB"):
                for c in cohorts:
                    entry = c.get("entry_kospi", initial_price)
                    amount = c.get("remaining_amount_billion", 0)
                    if entry == 0:
                        continue
                    for margin_rate, mr_w in MARGIN_DISTRIBUTION.items():
                        ratio = (price / entry) / (1 - margin_rate)
                        for fl_ratio, fl_w in FORCED_LIQ_DISTRIBUTION.items():
                            for mt_ratio, mt_w in MAINTENANCE_DISTRIBUTION.items():
                                w = mr_w * fl_w * mt_w
                                if ratio < fl_ratio:
                                    forced_liq += amount * w
                                elif ratio < mt_ratio:
                                    margin_call += amount * w
                sell_pressure_a = forced_liq * (1 - absorption_rate)
                impact_a = (
                    (sell_pressure_a / avg_daily_trading_value) * impact_coefficient
                    if avg_daily_trading_value > 0 else 0
                )

            # Loop B: FX → foreign selling
            fx_change_pct = 0.0
            foreign_sell = 0.0
            impact_b = 0.0
            if loop_mode in ("B", "AB"):
                kospi_drop_pct = abs((price / initial_price - 1) * 100)
                fx_change_pct = kospi_drop_pct * 0.3
                sensitivity = self._fx_sensitivity(fx_change_pct)
                foreign_sell = fx_change_pct * sensitivity * 100
                sell_pressure_b = foreign_sell * (1 - absorption_rate)
                impact_b = (
                    (sell_pressure_b / avg_daily_trading_value) * impact_coefficient
                    if avg_daily_trading_value > 0 else 0
                )

            total_impact = impact_a + impact_b
            price = price * (1 - total_impact)
            fx = fx * (1 + fx_change_pct / 100)

            rounds.append({
                "round": r,
                "price": round(price, 0),
                "fx": round(fx, 0),
                "forced_liq_billion": round(forced_liq, 0),
                "margin_call_billion": round(margin_call, 0),
                "foreign_sell_billion": round(foreign_sell, 0),
                "impact_a_pct": round(impact_a * 100, 2),
                "impact_b_pct": round(impact_b * 100, 2),
                "cumulative_drop_pct": round(
                    (price / initial_price - 1) * 100, 2
                ),
            })

            if forced_liq < 100 and foreign_sell < 50:
                break

        return {
            "initial_price": initial_price,
            "initial_fx": initial_fx,
            "final_price": round(price, 0),
            "final_fx": round(fx, 0),
            "total_drop_pct": round((price / initial_price - 1) * 100, 2),
            "loop_mode": loop_mode,
            "converged_at_round": len(rounds),
            "rounds": rounds,
        }


# ──────────────────────────────────────────────
# Module C: 위기 스코어 (14개 지표 PCA 가중)
# ──────────────────────────────────────────────

CRISIS_INDICATORS = [
    "leverage_heat",
    "flow_concentration",
    "price_deviation",
    "credit_acceleration",
    "deposit_inflow",
    "vix_level",
    "volume_explosion",
    "forced_liq_intensity",
    "credit_deposit_ratio",
    "dram_cycle",
    "credit_suspension",
    "institutional_selling",
    "retail_exhaustion",
    "bull_trap",
]

# v1.4 기준 14개 지표 가중치 (kospi_data.js와 동일)
CRISIS_WEIGHTS = {
    "leverage_heat": 0.10,
    "flow_concentration": 0.08,
    "price_deviation": 0.09,
    "credit_acceleration": 0.08,
    "deposit_inflow": 0.05,
    "vix_level": 0.06,
    "volume_explosion": 0.05,
    "forced_liq_intensity": 0.08,
    "credit_deposit_ratio": 0.04,
    "dram_cycle": 0.03,
    "credit_suspension": 0.12,
    "institutional_selling": 0.10,
    "retail_exhaustion": 0.08,
    "bull_trap": 0.04,
}

# 각 지표별 raw 계산 함수의 역사적 분포 기준 (percentile 변환용)
# mean, std 는 2015~2024 한국 시장 통계 기반 추정
INDICATOR_STATS = {
    "leverage_heat": {"desc": "신용/시총", "mean": 0.028, "std": 0.008},
    "flow_concentration": {"desc": "개인편중", "mean": 1.2, "std": 0.6},
    "price_deviation": {"desc": "MA200 괴리", "mean": 0.0, "std": 0.08},
    "credit_acceleration": {"desc": "신용 증가속도", "mean": 0.5, "std": 1.5},
    "deposit_inflow": {"desc": "예탁금 변화", "mean": 0.3, "std": 2.0},
    "vix_level": {"desc": "VIX", "mean": 18.0, "std": 6.0},
    "volume_explosion": {"desc": "거래폭증", "mean": 1.0, "std": 0.4},
    "forced_liq_intensity": {"desc": "반대매매 강도", "mean": 0.015, "std": 0.01},
    "credit_deposit_ratio": {"desc": "신용/예탁", "mean": 0.20, "std": 0.05},
    "dram_cycle": {"desc": "DRAM 사이클", "mean": 0.0, "std": 5.0},
    "credit_suspension": {"desc": "신용 중단", "mean": 0.0, "std": 1.0},
    "institutional_selling": {"desc": "기관 순매도", "mean": -500, "std": 2000},
    "retail_exhaustion": {"desc": "개인 매수력 감소", "mean": 30, "std": 20},
    "bull_trap": {"desc": "불트랩", "mean": 0, "std": 1},
}


def _z_to_percentile(z: float) -> float:
    """z-score → 0~100 percentile (sigmoid 근사)."""
    # sigmoid: 1/(1 + exp(-z)) → [0,1] → [0,100]
    percentile = 100.0 / (1.0 + np.exp(-z))
    return round(max(0, min(100, percentile)), 1)


class CrisisScorer:
    """위기 점수 산출 엔진. 14개 지표 percentile → 가중 합산."""

    def __init__(self):
        self.weights = CRISIS_WEIGHTS
        self.stats = INDICATOR_STATS

    def compute_raw_indicators(self, ts: list[dict], latest: dict) -> dict[str, float]:
        """시계열에서 각 지표 raw 값 산출."""
        raw = {}

        credit = latest.get("credit_balance_billion", 0) or 0
        deposit = latest.get("deposit_billion", 0) or 0
        kospi = latest.get("kospi", 0) or 0
        vix = latest.get("vix", 0) or 0
        volume = latest.get("kospi_trading_value_billion", 0) or 0
        individual = latest.get("individual_billion", 0) or 0
        institution = latest.get("institution_billion", 0) or 0
        forced_liq = latest.get("forced_liq_billion", 0) or 0

        # 최근 N일 평균
        recent_n = min(20, len(ts))
        recent = ts[-recent_n:] if recent_n > 0 else []

        avg_credit = np.mean([r.get("credit_balance_billion", 0) or 0 for r in recent]) if recent else 0
        avg_deposit = np.mean([r.get("deposit_billion", 0) or 0 for r in recent]) if recent else 0
        avg_volume = np.mean([r.get("kospi_trading_value_billion", 0) or 0 for r in recent]) if recent else 1
        avg_individual = np.mean([r.get("individual_billion", 0) or 0 for r in recent]) if recent else 0

        # 5일 vs 20일 신용변화
        credit_5d_ago = (ts[-6].get("credit_balance_billion") or credit) if len(ts) >= 6 else credit
        credit_20d_ago = (ts[-21].get("credit_balance_billion") or credit) if len(ts) >= 21 else credit

        # KOSPI MA200 (간이 — 직접 계산 or ts 길이에 따라 조정)
        ma_window = min(200, len(ts))
        kospis = [r.get("kospi", 0) or 0 for r in ts[-ma_window:]]
        ma200 = np.mean(kospis) if kospis else kospi

        # 1. leverage_heat: 신용/시총 (시총 ≈ KOSPI × 상수)
        est_market_cap = kospi * 0.7  # ~조원 (KOSPI 2500 → 시총 ~1750조)
        raw["leverage_heat"] = credit / est_market_cap if est_market_cap > 0 else 0

        # 2. flow_concentration: |개인 순매수| / 전체 거래대금
        raw["flow_concentration"] = abs(individual) / volume if volume > 0 else 0

        # 3. price_deviation: (KOSPI - MA200) / MA200
        raw["price_deviation"] = (kospi - ma200) / ma200 if ma200 > 0 else 0

        # 4. credit_acceleration: 5일 신용 변화율 (%)
        raw["credit_acceleration"] = (
            (credit - credit_5d_ago) / credit_5d_ago * 100
            if credit_5d_ago > 0 else 0
        )

        # 5. deposit_inflow: 5일 예탁금 변화율 (%)
        deposit_5d_ago = (ts[-6].get("deposit_billion") or deposit) if len(ts) >= 6 else deposit
        raw["deposit_inflow"] = (
            (deposit - deposit_5d_ago) / deposit_5d_ago * 100
            if deposit_5d_ago > 0 else 0
        )

        # 6. vix_level
        raw["vix_level"] = vix

        # 7. volume_explosion: 금일 거래대금 / 20일 평균
        raw["volume_explosion"] = volume / avg_volume if avg_volume > 0 else 1

        # 8. forced_liq_intensity: 반대매매금액 / 신용잔고
        raw["forced_liq_intensity"] = forced_liq / credit if credit > 0 else 0

        # 9. credit_deposit_ratio
        raw["credit_deposit_ratio"] = credit / deposit if deposit > 0 else 0

        # 10. dram_cycle: placeholder (외부 데이터 필요 — 일단 0)
        raw["dram_cycle"] = 0

        # 11. credit_suspension: 신용중단 증권사 수 (외부 이벤트 — 일단 0)
        raw["credit_suspension"] = 0

        # 12. institutional_selling: 기관 순매도 (십억원, 음수 = 매도)
        raw["institutional_selling"] = institution

        # 13. retail_exhaustion: 1 - (최근5일 평균 / 20일 평균) × 100
        avg_indiv_5d = np.mean([
            r.get("individual_billion", 0) or 0 for r in ts[-5:]
        ]) if len(ts) >= 5 else individual
        avg_indiv_20d = avg_individual
        if abs(avg_indiv_20d) > 1:
            raw["retail_exhaustion"] = (1 - avg_indiv_5d / avg_indiv_20d) * 100
        else:
            raw["retail_exhaustion"] = 0

        # 14. bull_trap: 직전 반등 후 재하락 (2-day pattern)
        if len(ts) >= 3:
            k2 = ts[-3].get("kospi", 0) or 0
            k1 = ts[-2].get("kospi", 0) or 0
            k0 = kospi
            # 반등 후 하락 패턴
            raw["bull_trap"] = 1 if (k1 > k2 and k0 < k1 and k0 < k2) else 0
        else:
            raw["bull_trap"] = 0

        return raw

    def score(self, ts: list[dict], latest: dict | None = None) -> dict:
        """14개 지표 → percentile → 가중 합산 → 위기 점수."""
        if latest is None:
            latest = ts[-1] if ts else {}

        raw = self.compute_raw_indicators(ts, latest)

        indicators = {}
        weighted_sum = 0.0
        total_weight = 0.0

        for key in CRISIS_INDICATORS:
            stat = self.stats.get(key, {"mean": 0, "std": 1, "desc": key})
            raw_val = raw.get(key, 0)

            # z-score
            std = stat["std"] if stat["std"] > 0 else 1
            z = (raw_val - stat["mean"]) / std

            # 특수 처리: deposit_inflow — 감소가 위험 (부호 반전)
            if key == "deposit_inflow":
                z = -z
            # institutional_selling — 매도(음수)가 위험 (부호 반전)
            if key == "institutional_selling":
                z = -z

            percentile = _z_to_percentile(z)

            indicators[key] = {
                "value": percentile,
                "raw": round(raw_val, 4) if isinstance(raw_val, float) else raw_val,
                "desc": stat["desc"],
            }

            w = self.weights.get(key, 0)
            weighted_sum += percentile * w
            total_weight += w

        composite = round(weighted_sum / total_weight, 1) if total_weight > 0 else 50

        return {
            "current": composite,
            "classification": self.classify(composite),
            "weights": self.weights,
            "indicators": indicators,
        }

    def compute_history(self, ts: list[dict]) -> list[dict]:
        """시계열 전체에 대해 daily crisis score history 산출."""
        history = []
        for i in range(max(1, len(ts) - 60), len(ts)):
            sub_ts = ts[:i + 1]
            result = self.score(sub_ts)
            history.append({
                "date": ts[i].get("date", ""),
                "score": result["current"],
                "classification": result["classification"],
            })
        return history

    @staticmethod
    def classify(score: float) -> str:
        if score < 50:
            return "normal"
        if score < 70:
            return "caution"
        if score < 85:
            return "warning"
        if score < 95:
            return "danger"
        return "extreme"


# ──────────────────────────────────────────────
# Module D: 베이지안 시나리오 트래커
# ──────────────────────────────────────────────

SCENARIO_DEFINITIONS = [
    {
        "id": "S1", "name": "연착륙",
        "desc": "점진적 정상화, 신용 위축 완화",
        "kospi_range": [2600, 2800],
    },
    {
        "id": "S2", "name": "방어",
        "desc": "정부 안정조치 + 외국인 매도 진정",
        "kospi_range": [2400, 2600],
    },
    {
        "id": "S3", "name": "캐스케이드",
        "desc": "Loop A + Loop C 4~8주 지속, 코호트 순차 붕괴",
        "kospi_range": [2100, 2400],
    },
    {
        "id": "S4", "name": "전면위기",
        "desc": "글로벌 충격 + 국내 loop 가속",
        "kospi_range": [1800, 2100],
    },
    {
        "id": "S5", "name": "펀더멘털 붕괴",
        "desc": "DRAM 마이너스 + AI capex 삭감, 실적 전제 붕괴",
        "kospi_range": [1400, 1800],
    },
]

# 관측변수별 시나리오 log-likelihood 파라미터
# 형태: {관측변수: {시나리오별 (mean, precision)}}
SCENARIO_PARAMS = {
    "kospi_return": {
        "S1": (0.003, 50), "S2": (-0.005, 30), "S3": (-0.02, 20),
        "S4": (-0.04, 15), "S5": (-0.06, 10),
    },
    "credit_change": {
        "S1": (-0.5, 2), "S2": (-0.2, 1.5), "S3": (0.5, 1),
        "S4": (1.5, 0.8), "S5": (3.0, 0.5),
    },
    "vix_level": {
        "S1": (15, 0.1), "S2": (20, 0.08), "S3": (28, 0.05),
        "S4": (35, 0.04), "S5": (45, 0.03),
    },
    "fx_rate": {
        "S1": (1350, 0.005), "S2": (1380, 0.004), "S3": (1430, 0.003),
        "S4": (1500, 0.002), "S5": (1600, 0.001),
    },
    "institutional_flow": {
        "S1": (200, 0.002), "S2": (-200, 0.001), "S3": (-1000, 0.0008),
        "S4": (-3000, 0.0005), "S5": (-5000, 0.0003),
    },
    "retail_flow": {
        "S1": (500, 0.001), "S2": (200, 0.0008), "S3": (-200, 0.0005),
        "S4": (-1000, 0.0003), "S5": (-3000, 0.0002),
    },
}


class BayesianScenarioTracker:
    """5개 시나리오 확률 일간 업데이트 — 베이지안 log-likelihood 방법."""

    def __init__(self):
        self.scenarios = SCENARIO_DEFINITIONS
        self.params = SCENARIO_PARAMS
        # Uniform prior (log)
        n = len(self.scenarios)
        self.log_priors = [np.log(1.0 / n)] * n

    def _extract_observations(self, latest: dict, prev: dict | None = None) -> dict:
        """시계열 latest row에서 관측변수 추출."""
        kospi = latest.get("kospi", 0) or 0
        prev_kospi = (prev.get("kospi", kospi) or kospi) if prev else kospi
        credit = latest.get("credit_balance_billion", 0) or 0
        prev_credit = (prev.get("credit_balance_billion", credit) or credit) if prev else credit

        return {
            "kospi_return": (kospi - prev_kospi) / prev_kospi if prev_kospi > 0 else 0,
            "credit_change": (credit - prev_credit) / prev_credit * 100 if prev_credit > 0 else 0,
            "vix_level": latest.get("vix", 18) or 18,
            "fx_rate": latest.get("usd_krw", 1380) or 1380,
            "institutional_flow": latest.get("institution_billion", 0) or 0,
            "retail_flow": latest.get("individual_billion", 0) or 0,
        }

    def _log_likelihood(self, obs: dict, scenario_id: str) -> float:
        """관측값에 대한 시나리오별 log-likelihood (가우시안)."""
        ll = 0.0
        for var_name, var_val in obs.items():
            params = self.params.get(var_name, {}).get(scenario_id)
            if params is None:
                continue
            mean, precision = params
            # Gaussian log-likelihood: -0.5 * precision * (x - mean)^2
            ll += -0.5 * precision * (var_val - mean) ** 2
        return ll

    def update(self, ts: list[dict]) -> dict:
        """전체 시계열에 대해 시나리오 확률 히스토리 산출."""
        n_scenarios = len(self.scenarios)

        # 각 날짜에서 확률 계산
        prob_history = []
        current_probs = [1.0 / n_scenarios] * n_scenarios

        for i in range(max(1, len(ts) - 60), len(ts)):
            latest = ts[i]
            prev = ts[i - 1] if i > 0 else None
            obs = self._extract_observations(latest, prev)

            # Log-likelihood for each scenario
            log_likes = []
            for j, sc in enumerate(self.scenarios):
                ll = self._log_likelihood(obs, sc["id"])
                log_likes.append(ll)

            # Softmax → probabilities
            log_likes = np.array(log_likes)
            # Add prior (previous day's log-prob)
            log_posterior = log_likes + np.log(np.array(current_probs) + 1e-10)
            # Softmax normalization
            max_ll = np.max(log_posterior)
            exp_ll = np.exp(log_posterior - max_ll)
            probs = exp_ll / np.sum(exp_ll)

            current_probs = probs.tolist()

            row = {"date": latest.get("date", "")}
            for j, sc in enumerate(self.scenarios):
                row[sc["id"].lower()] = round(probs[j], 4)
            prob_history.append(row)

        # 현재 확률
        scenario_output = []
        for j, sc in enumerate(self.scenarios):
            scenario_output.append({
                **sc,
                "current_prob": round(current_probs[j], 4),
            })

        # Key drivers: 어떤 관측변수가 확률에 가장 큰 영향
        key_drivers = self._compute_key_drivers(ts, current_probs)

        return {
            "scenarios": scenario_output,
            "probability_history": prob_history,
            "key_drivers": key_drivers,
        }

    def _compute_key_drivers(self, ts: list[dict], current_probs: list[float]) -> list[dict]:
        """현재 확률에 가장 큰 영향을 주는 관측변수 Top 3."""
        if not ts:
            return []

        latest = ts[-1]
        prev = ts[-2] if len(ts) >= 2 else None
        obs = self._extract_observations(latest, prev)

        # 최대 확률 시나리오
        max_sc_idx = int(np.argmax(current_probs))
        max_sc = self.scenarios[max_sc_idx]

        drivers = []
        for var_name, var_val in obs.items():
            params = self.params.get(var_name, {}).get(max_sc["id"])
            if params is None:
                continue
            mean, precision = params
            # z-score 대비 편차
            std_approx = 1.0 / np.sqrt(precision) if precision > 0 else 1
            z = (var_val - mean) / std_approx if std_approx > 0 else 0
            drivers.append({
                "indicator": var_name,
                "observed": round(var_val, 2),
                "expected": round(mean, 2),
                "z_score": round(z, 2),
                "direction": "supporting" if abs(z) < 2 else "opposing",
                "scenario": max_sc["id"],
            })

        # Sort by |z_score| desc, take top 3
        drivers.sort(key=lambda d: abs(d["z_score"]), reverse=True)
        return drivers[:3]


# ──────────────────────────────────────────────
# Module E: 과거 사례 비교
# ──────────────────────────────────────────────

# 과거 사례 데이터 (직접 임베드 — historical/ 디렉터리에서 로드 시도 후 fallback)
HISTORICAL_CASES = {
    "crisis_2008": {
        "id": "crisis_2008", "name": "2008 글로벌 금융위기",
        "peak_date": "2007-10-31", "peak_kospi": 2064, "bottom_kospi": 938,
        "drop_pct": -54.6, "recovery_days": 456,
        "normalized_series": None,  # 로드 시 채워짐
    },
    "china_2015": {
        "id": "china_2015", "name": "2015 중국발 폭락",
        "peak_date": "2015-04-27", "peak_kospi": 2173, "bottom_kospi": 1829,
        "drop_pct": -15.8, "recovery_days": 89,
        "normalized_series": None,
    },
    "covid_2020": {
        "id": "covid_2020", "name": "2020 코로나 폭락",
        "peak_date": "2020-01-20", "peak_kospi": 2267, "bottom_kospi": 1457,
        "drop_pct": -35.7, "recovery_days": 210,
        "normalized_series": None,
    },
    "evergrande_2021": {
        "id": "evergrande_2021", "name": "2021 에버그란데",
        "peak_date": "2021-06-25", "peak_kospi": 3305, "bottom_kospi": 2614,
        "drop_pct": -20.9, "recovery_days": 0,  # 미회복
        "normalized_series": None,
    },
}


class HistoricalComparator:
    """과거 사례 유사도 분석 — DTW(60%) + Cosine(40%) hybrid."""

    def __init__(self):
        self.cases = dict(HISTORICAL_CASES)
        self._load_historical_data()

    def _load_historical_data(self):
        """historical/ 디렉터리에서 과거 사례 시계열 로드."""
        hist_dir = DATA_DIR / "historical"
        if not hist_dir.exists():
            return

        for case_id, case in self.cases.items():
            path = hist_dir / f"{case_id}.json"
            if path.exists():
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "normalized_series" in data:
                        case["normalized_series"] = data["normalized_series"]
                except Exception:
                    pass

    def _normalize_to_peak(self, series: list[float], peak_val: float) -> list[float]:
        """peak 대비 변화율(%)로 정규화."""
        if peak_val == 0:
            return [0.0] * len(series)
        return [(v / peak_val - 1) * 100 for v in series]

    def _dtw_distance(self, s1: list[float], s2: list[float]) -> float:
        """DTW 거리 계산. tslearn 사용 가능 시 사용, 아니면 간이 구현."""
        s1 = np.array(s1, dtype=float)
        s2 = np.array(s2, dtype=float)

        if tslearn_dtw is not None:
            try:
                dist = tslearn_dtw(s1.reshape(-1, 1), s2.reshape(-1, 1))
                return float(dist)
            except Exception:
                pass

        # Fallback: 간이 DTW
        n, m = len(s1), len(s2)
        dtw_matrix = np.full((n + 1, m + 1), np.inf)
        dtw_matrix[0, 0] = 0

        for i in range(1, n + 1):
            for j in range(1, m + 1):
                cost = abs(s1[i - 1] - s2[j - 1])
                dtw_matrix[i, j] = cost + min(
                    dtw_matrix[i - 1, j],
                    dtw_matrix[i, j - 1],
                    dtw_matrix[i - 1, j - 1],
                )

        return float(dtw_matrix[n, m])

    def _cosine_similarity(self, s1: list[float], s2: list[float]) -> float:
        """코사인 유사도."""
        a = np.array(s1, dtype=float)
        b = np.array(s2, dtype=float)

        # 길이 맞춤 (짧은 쪽에 맞춤)
        min_len = min(len(a), len(b))
        a, b = a[:min_len], b[:min_len]

        if cosine_dist is not None:
            try:
                return float(1 - cosine_dist(a, b))
            except Exception:
                pass

        # Fallback
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0
        return float(dot / (norm_a * norm_b))

    def compare(self, current_series: list[float], peak_kospi: float, window: int = 60) -> dict:
        """현재 시계열을 모든 과거 사례와 비교.

        Args:
            current_series: 최근 KOSPI 종가 시계열
            peak_kospi: 현재 시점의 고점 KOSPI
            window: 비교 윈도우 (일수)

        Returns:
            {
                "cases": [...],
                "similarities": {...},
                "overlay": [...],
                "indicator_comparison": [...]
            }
        """
        # 현재 정규화
        current_norm = self._normalize_to_peak(current_series[-window:], peak_kospi)

        cases_output = []
        similarities = {}
        overlay_data = []

        for case_id, case in self.cases.items():
            hist_norm = case.get("normalized_series")

            if hist_norm is None:
                # 과거 데이터 없으면 합성 (peak → bottom 경로)
                peak = case["peak_kospi"]
                bottom = case["bottom_kospi"]
                drop = case["drop_pct"]
                recovery = max(case.get("recovery_days", 60), 30)

                # 간이 경로 생성: 하락 후 반등
                half = min(window // 2, recovery // 3)
                hist_norm = []
                for d in range(window):
                    if d < half:
                        pct = drop * (d / half)
                    else:
                        pct = drop * (1 - 0.5 * (d - half) / (window - half))
                    hist_norm.append(round(pct, 2))

            # 길이 맞춤
            min_len = min(len(current_norm), len(hist_norm))
            c_sub = current_norm[:min_len]
            h_sub = hist_norm[:min_len]

            # DTW
            dtw_dist = self._dtw_distance(c_sub, h_sub)
            # 거리 → 유사도 [0, 1]
            max_possible = abs(min(c_sub)) + abs(min(h_sub)) + 100
            dtw_sim = max(0, 1 - dtw_dist / (max_possible * min_len ** 0.5)) if max_possible > 0 else 0

            # Cosine
            cos_sim = self._cosine_similarity(c_sub, h_sub)

            # Hybrid: 60% DTW + 40% Cosine
            hybrid = 0.6 * dtw_sim + 0.4 * cos_sim

            cases_output.append({
                "id": case_id,
                "name": case["name"],
                "peak_date": case["peak_date"],
                "peak_kospi": case["peak_kospi"],
                "bottom_kospi": case["bottom_kospi"],
                "drop_pct": case["drop_pct"],
                "recovery_days": case["recovery_days"],
            })

            similarities[case_id] = {
                "dtw": round(dtw_sim, 3),
                "cosine": round(max(0, cos_sim), 3),
                "hybrid": round(max(0, hybrid), 3),
            }

        # Overlay: 현재 vs 가장 유사한 사례
        best_case = max(similarities.items(), key=lambda x: x[1]["hybrid"])[0] if similarities else None
        if best_case:
            best_hist = self.cases[best_case].get("normalized_series")
            if best_hist is None:
                case = self.cases[best_case]
                drop = case["drop_pct"]
                half = window // 2
                best_hist = []
                for d in range(window):
                    if d < half:
                        pct = drop * (d / half)
                    else:
                        pct = drop * (1 - 0.5 * (d - half) / (window - half))
                    best_hist.append(round(pct, 2))

            for d in range(min(window, len(current_norm))):
                row = {
                    "day": d,
                    "current_pct": round(current_norm[d], 2) if d < len(current_norm) else None,
                }
                row[f"{best_case}_pct"] = round(best_hist[d], 2) if d < len(best_hist) else None
                overlay_data.append(row)

        return {
            "cases": cases_output,
            "similarities": similarities,
            "overlay": overlay_data,
        }


# ──────────────────────────────────────────────
# Main Pipeline
# ──────────────────────────────────────────────

def _identify_backtest_dates(ts: list[dict], threshold_pct: float = 2.0) -> list[dict]:
    """급변동일 식별 + D+1~D+5 실제 데이터 첨부.

    Args:
        ts: 전체 시계열
        threshold_pct: 변동률 임계값 (기본 2%)

    Returns:
        [{date, shock_pct, kospi, prev_kospi, forward: [{day, date, kospi, credit, ...}]}]
    """
    results = []
    for i in range(1, len(ts)):
        prev_kospi = ts[i - 1].get("kospi") or 0
        cur_kospi = ts[i].get("kospi") or 0
        if prev_kospi == 0:
            continue
        change_pct = (cur_kospi - prev_kospi) / prev_kospi * 100
        if abs(change_pct) < threshold_pct:
            continue

        forward = []
        for d in range(1, 6):
            if i + d >= len(ts):
                break
            fwd = ts[i + d]
            forward.append({
                "day": d,
                "date": fwd.get("date", ""),
                "kospi": fwd.get("kospi"),
                "credit_balance_billion": fwd.get("credit_balance_billion"),
                "individual_billion": fwd.get("individual_billion"),
                "foreign_billion": fwd.get("foreign_billion"),
                "institution_billion": fwd.get("institution_billion"),
                "trading_value_billion": fwd.get("kospi_trading_value_billion"),
            })

        results.append({
            "date": ts[i].get("date", ""),
            "shock_pct": round(change_pct, 2),
            "kospi": cur_kospi,
            "prev_kospi": prev_kospi,
            "forward": forward,
        })
    return results


def load_timeseries() -> list[dict]:
    path = DATA_DIR / "timeseries.json"
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def run_all_models() -> dict:
    """전체 모델 실행 파이프라인."""
    ts = load_timeseries()
    if not ts:
        print("[WARN] No timeseries data. Run fetch_daily.py first.")
        return {}

    latest = ts[-1] if ts else {}
    kospi = latest.get("kospi", 0)

    print(f"Computing models... (KOSPI: {kospi}, Date: {latest.get('date', 'N/A')})")

    # Module A: Cohort (+ history capture)
    builder_lifo = CohortBuilder(mode="LIFO")
    builder_fifo = CohortBuilder(mode="FIFO")
    last_known_credit = 0

    # Cohort history: registry (불변) + daily snapshots
    cohort_registry = {}   # {entry_date: {entry_kospi}}
    cohort_snapshots = []  # [{date, kospi, usd_krw, trading_value, amounts: {entry_date: amount}}]

    for i in range(1, len(ts)):
        prev = ts[i - 1]
        cur = ts[i]
        # carry-forward: null credit → 직전 유효값 유지 (코호트 일괄 청산 방지)
        cur_credit = cur.get("credit_balance_billion")
        prev_credit_val = prev.get("credit_balance_billion")
        if cur_credit is not None and cur_credit > 0:
            last_known_credit = cur_credit
        if prev_credit_val is None or prev_credit_val == 0:
            prev_credit_val = last_known_credit
        cur_credit_safe = cur_credit if (cur_credit is not None and cur_credit > 0) else last_known_credit
        kwargs = dict(
            date=cur.get("date", ""),
            credit_balance=cur_credit_safe,
            prev_credit=prev_credit_val,
            kospi=cur.get("kospi", 0) or 0,
            samsung=cur.get("samsung", 0) or 0,
            hynix=cur.get("hynix", 0) or 0,
        )
        builder_lifo.process_day(**kwargs)
        builder_fifo.process_day(**kwargs)

        # Capture snapshot (LIFO only — primary mode)
        cur_date = cur.get("date", "")
        amounts = {}
        for c in builder_lifo.active_cohorts:
            if c.remaining_amount_billion > 0:
                # Register new cohorts
                if c.entry_date not in cohort_registry:
                    cohort_registry[c.entry_date] = {"entry_kospi": c.entry_kospi}
                amounts[c.entry_date] = round(c.remaining_amount_billion, 1)
        cohort_snapshots.append({
            "date": cur_date,
            "kospi": cur.get("kospi"),
            "usd_krw": cur.get("usd_krw"),
            "trading_value": cur.get("kospi_trading_value_billion"),
            "amounts": amounts,
        })

    current_fx = latest.get("usd_krw", 1400) or 1400
    lifo_status = builder_lifo.get_status(kospi)
    fifo_status = builder_fifo.get_status(kospi)

    cohort_result = {
        "lifo": lifo_status["active"],
        "fifo": fifo_status["active"],
        "price_distribution_lifo": builder_lifo.get_price_distribution(kospi),
        "price_distribution_fifo": builder_fifo.get_price_distribution(kospi),
        "trigger_map": builder_lifo.get_trigger_map(kospi, current_fx),
        "current_kospi": kospi,
        "current_fx": current_fx,
        "total_active_billion": lifo_status["total_active_billion"],
    }

    # Module B: Forced Liq (3 scenarios)
    sim = ForcedLiqSimulator()
    avg_trading_val = np.mean([
        r.get("kospi_trading_value_billion", 10000) or 10000 for r in ts[-20:]
    ]) if ts else 10000

    forced_liq_scenarios = {}
    for shock in [-5, -15, -30]:
        result = sim.run(
            cohorts=[{"entry_kospi": c["entry_kospi"], "remaining_amount_billion": c["remaining_amount_billion"]}
                     for c in lifo_status["active"]],
            initial_price=kospi,
            price_shock_pct=shock,
            max_rounds=5,
            initial_fx=current_fx,
            avg_daily_trading_value=avg_trading_val,
            loop_mode="A",  # Loop A only (v1.4 기준)
        )
        forced_liq_scenarios[f"shock_{abs(shock)}"] = result
    forced_liq_result = forced_liq_scenarios

    # Module C: Crisis Score
    scorer = CrisisScorer()
    crisis_result = scorer.score(ts)
    crisis_result["history"] = scorer.compute_history(ts)
    print(f"  Crisis Score: {crisis_result['current']} ({crisis_result['classification']})")

    # Module D: Bayesian Scenario
    tracker = BayesianScenarioTracker()
    scenario_result = tracker.update(ts)
    print(f"  Scenarios: {len(scenario_result.get('scenarios', []))}")

    # Module E: Historical Comparison
    comparator = HistoricalComparator()
    kospi_series = [r.get("kospi", 0) or 0 for r in ts]
    peak_kospi = max(kospi_series) if kospi_series else kospi
    historical_result = comparator.compare(kospi_series, peak_kospi)
    print(f"  Historical: {len(historical_result.get('cases', []))} cases compared")

    # Backtest dates: 급변동일 식별
    backtest_dates = _identify_backtest_dates(ts)
    print(f"  Backtest dates: {len(backtest_dates)} events (|change| > 2%)")

    # Cohort history
    cohort_history = {
        "registry": cohort_registry,
        "snapshots": cohort_snapshots,
    }
    print(f"  Cohort history: {len(cohort_registry)} cohorts, {len(cohort_snapshots)} days")

    # Module A-2: 종목별 가중 코호트
    stock_credit_result = {}
    total_credit = latest.get("credit_balance_billion") or last_known_credit or 0
    if TOP_10_TICKERS and total_credit > 0:
        stock_mgr = StockCohortManager(TOP_10_TICKERS, mode="LIFO")

        # Determine weights: from stock_credit if available, else fetch from yfinance
        latest_sc = latest.get("stock_credit", {})
        if latest_sc:
            weights = {t: latest_sc.get(t, 0) / total_credit for t in TOP_10_TICKERS if latest_sc.get(t, 0) > 0}
        else:
            # Fallback: fetch market cap weights at compute time
            try:
                from scripts.naver_scraper import fetch_stock_market_caps
                caps = fetch_stock_market_caps(TOP_10_TICKERS)
                weights = caps.get("_weights", {})
            except Exception as e:
                print(f"  [WARN] Stock market cap fetch failed: {e}")
                weights = {}
        stock_mgr.set_weights(weights)

        # Build synthetic stock_credit for each day from weights
        for i in range(1, len(ts)):
            cur = ts[i]
            sc = cur.get("stock_credit")
            if not sc and weights:
                # Synthesize from total credit * weights
                day_credit = cur.get("credit_balance_billion") or 0
                if day_credit > 0:
                    sc = {t: round(day_credit * w, 2) for t, w in weights.items()}
            stock_mgr.process_day(cur.get("date", ""), cur, sc)

        stock_credit_result = {
            "stocks": stock_mgr.get_stock_summary(kospi),
            "weighted_trigger_map": stock_mgr.get_weighted_trigger_map(kospi, current_fx),
            "stock_weighted": True,
        }
        n_stocks = len([s for s in stock_credit_result["stocks"] if s["ticker"] != "_residual"])
        print(f"  Stock Cohorts: {n_stocks} stocks + residual")

    # Defense Walls (정적 — 수동 업데이트 필요)
    defense_walls = _compute_defense_walls(ts, latest)

    # Loop Status (정적 — 수동 업데이트 필요)
    loop_status = _compute_loop_status(ts, latest)

    # Assemble
    output = {
        "computed_at": datetime.now().isoformat(),
        "cohorts": cohort_result,
        "crisis_score": crisis_result,
        "forced_liq": forced_liq_result,
        "scenarios": scenario_result,
        "historical": historical_result,
        "defense_walls": defense_walls,
        "loop_status": loop_status,
        "cohort_history": cohort_history,
        "backtest_dates": backtest_dates,
        "stock_credit": stock_credit_result,
    }

    # Save
    output_path = DATA_DIR / "model_output.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"Saved: {output_path}")

    return output


def _compute_defense_walls(ts: list[dict], latest: dict) -> list[dict]:
    """방어벽 상태 산출 (데이터 기반 heuristic)."""
    individual = latest.get("individual_billion", 0) or 0
    institution = latest.get("institution_billion", 0) or 0
    usd_krw = latest.get("usd_krw", 1400) or 1400

    # 최근 5일 개인 매수 평균
    avg_indiv_5d = np.mean([
        r.get("individual_billion", 0) or 0 for r in ts[-5:]
    ]) if len(ts) >= 5 else individual

    # 최근 20일 개인 매수 평균
    avg_indiv_20d = np.mean([
        r.get("individual_billion", 0) or 0 for r in ts[-20:]
    ]) if len(ts) >= 20 else individual

    # Wall 1: 개인 매수
    if avg_indiv_5d > 0 and avg_indiv_20d > 0:
        indiv_ratio = avg_indiv_5d / abs(avg_indiv_20d) if avg_indiv_20d != 0 else 0
        if indiv_ratio < 0.1:
            wall1 = {"status": "collapsed", "capacity": max(0, indiv_ratio)}
        elif indiv_ratio < 0.5:
            wall1 = {"status": "weakened", "capacity": round(indiv_ratio, 2)}
        else:
            wall1 = {"status": "active", "capacity": min(1.0, round(indiv_ratio, 2))}
    else:
        wall1 = {"status": "weakened", "capacity": 0.3}

    wall1.update({
        "id": "wall1", "name": "개인 매수",
        "detail": f"최근5일 평균 {avg_indiv_5d:.0f}억 / 20일 {avg_indiv_20d:.0f}억",
    })

    # Wall 2: 연기금/기관
    if institution > 0:
        wall2 = {"status": "active", "capacity": 0.8, "detail": f"기관 순매수 {institution:.0f}억"}
    elif institution > -2000:
        wall2 = {"status": "weakened", "capacity": 0.35, "detail": f"기관 {institution:.0f}억 (소폭 매도)"}
    else:
        wall2 = {"status": "collapsed", "capacity": 0.1, "detail": f"기관 대량매도 {institution:.0f}억"}
    wall2.update({"id": "wall2", "name": "연기금/기관"})

    # Wall 3: 한은 FX 개입
    if usd_krw < 1400:
        wall3 = {"status": "active", "capacity": 0.9, "detail": f"USD/KRW {usd_krw:.0f} (안정)"}
    elif usd_krw < 1450:
        wall3 = {"status": "active", "capacity": 0.7, "detail": f"USD/KRW {usd_krw:.0f} (방어 중)"}
    elif usd_krw < 1500:
        wall3 = {"status": "weakened", "capacity": 0.4, "detail": f"USD/KRW {usd_krw:.0f} (긴장)"}
    else:
        wall3 = {"status": "collapsed", "capacity": 0.1, "detail": f"USD/KRW {usd_krw:.0f} (위기)"}
    wall3.update({"id": "wall3", "name": "한은 FX 개입"})

    # Wall 4, 5: 정적 (외부 이벤트)
    wall4 = {
        "id": "wall4", "name": "US 통화스왑",
        "status": "standby", "capacity": 0.5,
        "detail": "미발동 (요청 시 가용)",
    }
    wall5 = {
        "id": "wall5", "name": "IMF 지원",
        "status": "standby", "capacity": 1.0,
        "detail": "미발동 (외환보유고 $4,000억+)",
    }

    return [wall1, wall2, wall3, wall4, wall5]


def _compute_loop_status(ts: list[dict], latest: dict) -> dict:
    """Loop 상태 산출."""
    forced_liq = latest.get("forced_liq_billion", 0) or 0
    institution = latest.get("institution_billion", 0) or 0

    # Loop A: 반대매매 상태
    if forced_liq > 300:
        loop_a_status = "active"
        loop_a_vol = forced_liq
    elif forced_liq > 100:
        loop_a_status = "warming"
        loop_a_vol = forced_liq
    else:
        loop_a_status = "dormant"
        loop_a_vol = forced_liq

    # Loop C: 펀드 환매 (기관 매도에서 추정)
    fund_redemption_est = abs(institution) * 0.6 if institution < -1000 else 0
    if fund_redemption_est > 2000:
        loop_c_status = "active"
    elif fund_redemption_est > 500:
        loop_c_status = "warming"
    else:
        loop_c_status = "dormant"

    return {
        "loop_a": {
            "status": loop_a_status,
            "name": "반대매매 캐스케이드",
            "wave1": {"time": "08:00-09:00", "desc": "프리마켓 마진콜"},
            "wave2": {"time": "12:00-14:00", "desc": "추가담보 마감 후 강제매도"},
            "estimated_volume_billion": round(loop_a_vol),
        },
        "loop_c": {
            "status": loop_c_status,
            "name": "펀드 환매 캐스케이드",
            "delay": "T+1~T+3",
            "desc": f"기관 {institution:.0f}억 중 환매 매도 추정 {fund_redemption_est:.0f}억",
            "estimated_volume_billion": round(fund_redemption_est),
            "confidence": "low",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="KOSPI model computation")
    parser.add_argument(
        "--module",
        type=str,
        choices=["cohort", "forced_liq", "crisis", "scenario", "historical", "all"],
        default="all",
        help="Which module to run",
    )
    args = parser.parse_args()

    if args.module == "all":
        result = run_all_models()
    else:
        print(f"Module '{args.module}' — running via full pipeline.")
        result = run_all_models()

    if result:
        score = result.get("crisis_score", {})
        print(f"\nCrisis Score: {score.get('current', 'N/A')} ({score.get('classification', 'N/A')})")


if __name__ == "__main__":
    main()
