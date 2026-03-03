#!/usr/bin/env python3
"""
KOSPI 모델 연산 메인 스크립트.
fetch_daily.py 이후 실행 — 수집된 데이터로 모델 산출.

Modules:
    A: CohortBuilder — 신용잔고 코호트 생성/해소 (Phase 2)
    B: ForcedLiqSimulator — 반대매매 연쇄 시뮬레이션 (Phase 2)
    C: CrisisScorer — 위기 점수 산출 (Phase 3)
    D: BayesianScenarioTracker — 시나리오 확률 업데이트 (Phase 4)
    E: HistoricalComparator — 과거 사례 유사도 (Phase 3)

Usage:
    python kospi/scripts/compute_models.py                     # 전체 모델 실행
    python kospi/scripts/compute_models.py --module cohort     # 코호트만
    python kospi/scripts/compute_models.py --module crisis     # 위기 점수만
"""
import argparse
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


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
        ratio = self.collateral_ratio(current_kospi, margin_rate)
        if ratio >= 1.60:
            return "safe"
        if ratio >= 1.40:
            return "watch"
        if ratio >= 1.30:
            return "margin_call"
        return "forced_liq"


class CohortBuilder:
    """신용잔고 코호트 생성/해소 엔진. Phase 2에서 완전 구현."""

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


# ──────────────────────────────────────────────
# Module B: 반대매매 시뮬레이터 (Phase 2 stub)
# ──────────────────────────────────────────────

MARGIN_DISTRIBUTION = {
    0.40: 0.35,
    0.45: 0.35,
    0.50: 0.25,
    0.60: 0.05,
}

MAINTENANCE_RATIO = 1.40
FORCED_LIQ_RATIO = 1.30


class ForcedLiqSimulator:
    """반대매매 연쇄 피드백 루프 시뮬레이터. Phase 2에서 완전 구현."""

    def run(
        self,
        cohorts: list[dict],
        initial_price: float,
        price_shock_pct: float = -5.0,
        max_rounds: int = 5,
        absorption_rate: float = 0.5,
        avg_daily_trading_value: float = 10000,
        impact_coefficient: float = 1.5,
    ) -> dict:
        rounds = []
        price = initial_price * (1 + price_shock_pct / 100)

        for r in range(1, max_rounds + 1):
            forced_liq = 0
            margin_call = 0

            for c in cohorts:
                entry = c.get("entry_kospi", initial_price)
                amount = c.get("remaining_amount_billion", 0)
                for margin_rate, weight in MARGIN_DISTRIBUTION.items():
                    if entry == 0:
                        continue
                    ratio = (price / entry) / (1 - margin_rate)
                    if ratio < FORCED_LIQ_RATIO:
                        forced_liq += amount * weight
                    elif ratio < MAINTENANCE_RATIO:
                        margin_call += amount * weight

            sell_pressure = forced_liq * (1 - absorption_rate)
            impact = (
                (sell_pressure / avg_daily_trading_value) * impact_coefficient
                if avg_daily_trading_value > 0
                else 0
            )
            price = price * (1 - impact)

            rounds.append({
                "round": r,
                "price": round(price, 0),
                "forced_liq_billion": round(forced_liq, 0),
                "margin_call_billion": round(margin_call, 0),
                "absorption_rate": absorption_rate,
                "additional_drop_pct": round(impact * 100, 2),
                "cumulative_drop_pct": round(
                    (price / initial_price - 1) * 100, 2
                ),
            })

            if forced_liq < 100:
                break

        return {
            "initial_price": initial_price,
            "final_price": round(price, 0),
            "total_drop_pct": round((price / initial_price - 1) * 100, 2),
            "converged_at_round": len(rounds),
            "rounds": rounds,
        }


# ──────────────────────────────────────────────
# Module C: 위기 스코어 (Phase 3 stub)
# ──────────────────────────────────────────────

CRISIS_INDICATORS = [
    "leverage_heat",
    "flow_concentration",
    "price_deviation",
    "credit_acceleration",
    "deposit_inflow",
    "foreign_selling",
    "fx_stress",
    "short_anomaly",
    "vix_level",
    "volume_explosion",
    "forced_liq_intensity",
    "credit_deposit_ratio",
    "dram_cycle",
]


class CrisisScorer:
    """위기 점수 산출 엔진. Phase 3에서 완전 구현."""

    def compute_score_simple(self, latest: dict) -> dict:
        """Phase 1 간이 위기 점수 (0~100)."""
        score = 50  # 기본값
        return {
            "current": score,
            "classification": self.classify(score),
            "indicators": {},
            "weights": {},
            "history": [],
        }

    def classify(self, score: float) -> str:
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
# Module D: 베이지안 시나리오 (Phase 4 stub)
# ──────────────────────────────────────────────

class BayesianScenarioTracker:
    """시나리오 확률 일간 업데이트. Phase 4에서 완전 구현."""

    def __init__(self, scenarios_path: Optional[str] = None):
        self.scenarios = []
        if scenarios_path:
            path = Path(scenarios_path)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.scenarios = data.get("scenarios", [])

    def update(self, observations: dict) -> list[dict]:
        """Phase 4에서 구현."""
        return self.scenarios


# ──────────────────────────────────────────────
# Module E: 과거 사례 비교 (Phase 3 stub)
# ──────────────────────────────────────────────

class HistoricalComparator:
    """과거 사례 유사도 분석. Phase 3에서 완전 구현."""

    def compute_similarity(self, current: list, historical_cases: dict) -> dict:
        """Phase 3에서 DTW + Cosine 구현."""
        return {}


# ──────────────────────────────────────────────
# Main Pipeline
# ──────────────────────────────────────────────

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

    # Module A: Cohort (Phase 2 — stub result)
    cohort_result = {
        "active": [],
        "price_distribution": [],
        "mode": "LIFO",
        "total_active_billion": 0,
    }

    # Module B: Forced Liq (Phase 2 — stub default sim)
    forced_liq_result = {
        "shock_pct": -5,
        "rounds": [],
        "final_price": kospi * 0.95 if kospi else 0,
        "converged_at": None,
    }

    # Module C: Crisis Score (Phase 3 — simple stub)
    scorer = CrisisScorer()
    crisis_result = scorer.compute_score_simple(latest)

    # Module E: Historical (Phase 3 — stub)
    historical_result = {}

    # Assemble
    output = {
        "computed_at": datetime.now().isoformat(),
        "cohorts": cohort_result,
        "crisis_score": crisis_result,
        "forced_liq_default": forced_liq_result,
        "historical_similarity": historical_result,
    }

    # Save
    output_path = DATA_DIR / "model_output.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    print(f"Saved: {output_path}")

    return output


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
        print(f"Module '{args.module}' — Phase 2+ implementation pending.")
        result = run_all_models()  # Run all for now

    if result:
        score = result.get("crisis_score", {})
        print(f"\nCrisis Score: {score.get('current', 'N/A')} ({score.get('classification', 'N/A')})")


if __name__ == "__main__":
    main()
