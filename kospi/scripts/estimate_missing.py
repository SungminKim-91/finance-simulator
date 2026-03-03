#!/usr/bin/env python3
"""
T+2 지연 데이터 추정 모듈.
신용잔고/예탁금만 추정. 반대매매는 추정하지 않음 (정확도 낮음).

추정 모델: Rolling OLS (10일 윈도우)
  ΔCredit_est = β0 + β1·(개인순매수/1조) + β2·(KOSPI수익률) + β3·(전일ΔCredit)

Usage:
    python kospi/scripts/estimate_missing.py --date 2026-03-03

Note:
    Phase 1에서는 stub 구현.
    Phase 2에서 statsmodels OLS 기반 실제 추정 구현.
"""
import argparse
import json
from pathlib import Path

import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def estimate_credit_balance(
    today_data: dict,
    historical: list[dict],
) -> dict:
    """
    신용잔고 추정 (Rolling OLS 10일).

    Args:
        today_data: 오늘 시장 데이터 (개인순매수, KOSPI 수익률 등)
        historical: 최근 10~15일 시계열 (실측 신용잔고 포함)

    Returns:
        {
            "value": float,               # 추정 잔고 (억원)
            "estimated": True,
            "confidence_interval": [lower, upper],  # ±1σ
            "estimation_method": "rolling_OLS_10d"
        }
    """
    if not historical:
        return {
            "value": None,
            "estimated": True,
            "confidence_interval": [None, None],
            "estimation_method": "no_data",
        }

    # Phase 1 — 간단한 이동평균 기반 추정 (OLS는 Phase 2에서 구현)
    recent_values = [
        h.get("credit_balance_billion")
        for h in historical[-10:]
        if h.get("credit_balance_billion") is not None
    ]

    if not recent_values:
        return {
            "value": None,
            "estimated": True,
            "confidence_interval": [None, None],
            "estimation_method": "no_data",
        }

    # 단순 평균 + 최근 추세 반영
    avg = np.mean(recent_values)
    if len(recent_values) >= 3:
        trend = (recent_values[-1] - recent_values[-3]) / 3
    else:
        trend = 0

    estimated = round(avg + trend, 0)
    std = np.std(recent_values) if len(recent_values) > 1 else avg * 0.02

    return {
        "value": float(estimated),
        "estimated": True,
        "confidence_interval": [float(estimated - std), float(estimated + std)],
        "estimation_method": "simple_trend_10d",
    }


def estimate_customer_deposit(
    today_data: dict,
    historical: list[dict],
) -> dict:
    """
    고객예탁금 추정.
    신용잔고와 동일한 방법론 적용.
    """
    if not historical:
        return {
            "value": None,
            "estimated": True,
            "confidence_interval": [None, None],
            "estimation_method": "no_data",
        }

    recent_values = [
        h.get("deposit_billion")
        for h in historical[-10:]
        if h.get("deposit_billion") is not None
    ]

    if not recent_values:
        return {
            "value": None,
            "estimated": True,
            "confidence_interval": [None, None],
            "estimation_method": "no_data",
        }

    avg = np.mean(recent_values)
    if len(recent_values) >= 3:
        trend = (recent_values[-1] - recent_values[-3]) / 3
    else:
        trend = 0

    estimated = round(avg + trend, 0)
    std = np.std(recent_values) if len(recent_values) > 1 else avg * 0.02

    return {
        "value": float(estimated),
        "estimated": True,
        "confidence_interval": [float(estimated - std), float(estimated + std)],
        "estimation_method": "simple_trend_10d",
    }


def correct_estimate(
    date: str,
    actual_value: float,
    estimated_value: float,
) -> dict:
    """
    실측 도착 시 보정 + 오차 로그 기록.

    Returns:
        {"date": str, "actual": float, "estimated": float,
         "error": float, "error_pct": float}
    """
    error = actual_value - estimated_value
    error_pct = (error / actual_value * 100) if actual_value != 0 else 0

    result = {
        "date": date,
        "actual": actual_value,
        "estimated": estimated_value,
        "error": round(error, 1),
        "error_pct": round(error_pct, 2),
    }

    # 오차 로그 파일에 기록
    log_path = DATA_DIR / "estimation_errors.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result, ensure_ascii=False) + "\n")

    return result


def main():
    parser = argparse.ArgumentParser(description="T+2 estimation module")
    parser.add_argument("--date", type=str, required=True, help="Date (YYYY-MM-DD)")
    args = parser.parse_args()

    # Load recent timeseries for historical reference
    ts_path = DATA_DIR / "timeseries.json"
    if ts_path.exists():
        with open(ts_path, "r", encoding="utf-8") as f:
            ts = json.load(f)
    else:
        ts = []
        print("[WARN] No timeseries data found. Cannot estimate.")

    today_data = {}  # Would come from fetch_daily.py output

    credit_est = estimate_credit_balance(today_data, ts)
    deposit_est = estimate_customer_deposit(today_data, ts)

    print(f"\nEstimation for {args.date}:")
    print(f"  Credit:  {credit_est['value']} B  [{credit_est['estimation_method']}]")
    print(f"  Deposit: {deposit_est['value']} B  [{deposit_est['estimation_method']}]")
    if credit_est["confidence_interval"][0]:
        print(
            f"  Credit CI: [{credit_est['confidence_interval'][0]:.0f}, "
            f"{credit_est['confidence_interval'][1]:.0f}]"
        )


if __name__ == "__main__":
    main()
