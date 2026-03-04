#!/usr/bin/env python3
"""
T+2 지연 데이터 추정 모듈.
신용잔고/예탁금만 추정. 반대매매는 추정하지 않음 (정확도 낮음).

추정 모델: Rolling OLS (10일 윈도우)
  ΔCredit_est = β0 + β1·(개인순매수/1조) + β2·(KOSPI수익률) + β3·(전일ΔCredit)

Usage:
    python kospi/scripts/estimate_missing.py --date 2026-03-03
"""
import argparse
import json
from pathlib import Path

import numpy as np

try:
    import pandas as pd
except ImportError:
    pd = None

try:
    from statsmodels.regression.linear_model import OLS
    from statsmodels.tools import add_constant
except ImportError:
    OLS = None
    add_constant = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

DEFAULT_WINDOW = 10


def _build_features(historical: list[dict]) -> tuple[np.ndarray, np.ndarray] | None:
    """시계열에서 OLS 학습용 X, y 추출.

    y = ΔCredit (전일 대비 신용잔고 변화, 십억원)
    X = [개인순매수/1000, KOSPI일간수익률, 전일ΔCredit]
    """
    if pd is None or len(historical) < 5:
        return None

    credits = []
    indivs = []
    kospis = []

    for h in historical:
        cb = h.get("credit_balance_billion")
        if cb is None:
            continue
        credits.append(cb)
        indivs.append(h.get("individual_billion", 0) or 0)
        kospis.append(h.get("kospi", 0) or 0)

    if len(credits) < 5:
        return None

    credits = np.array(credits, dtype=float)
    indivs = np.array(indivs, dtype=float)
    kospis = np.array(kospis, dtype=float)

    # 변화량
    d_credit = np.diff(credits)
    # KOSPI 수익률 (%)
    kospi_ret = np.diff(kospis) / np.where(kospis[:-1] != 0, kospis[:-1], 1) * 100
    # 개인 순매수 (조원 단위로 스케일)
    indiv_scaled = indivs[1:] / 1000.0
    # 전일 ΔCredit (1-lag)
    lag_d_credit = np.concatenate([[0], d_credit[:-1]])

    y = d_credit
    X = np.column_stack([indiv_scaled, kospi_ret, lag_d_credit])

    return X, y


def _ols_estimate(
    historical: list[dict],
    window: int = DEFAULT_WINDOW,
    today_data: dict | None = None,
) -> tuple[float | None, float]:
    """Rolling OLS로 오늘의 ΔCredit 추정.

    Returns:
        (delta_estimate, residual_std)
    """
    if OLS is None or len(historical) < window:
        return None, 0

    result = _build_features(historical[-window - 1:])
    if result is None:
        return None, 0

    X, y = result
    if len(y) < 3:
        return None, 0

    try:
        X_c = add_constant(X)
        model = OLS(y, X_c).fit()

        # 오늘 feature 구성
        last = historical[-1]
        prev = historical[-2] if len(historical) >= 2 else last

        indiv_today = (today_data or {}).get("individual_billion", last.get("individual_billion", 0)) or 0
        kospi_today = (today_data or {}).get("kospi", last.get("kospi", 0)) or 0
        kospi_prev = last.get("kospi", kospi_today) or kospi_today

        kospi_ret_today = (kospi_today - kospi_prev) / kospi_prev * 100 if kospi_prev else 0
        indiv_scaled_today = indiv_today / 1000.0
        lag_delta = (last.get("credit_balance_billion", 0) or 0) - (prev.get("credit_balance_billion", 0) or 0)

        x_today = np.array([1, indiv_scaled_today, kospi_ret_today, lag_delta])
        delta_est = float(model.predict(x_today.reshape(1, -1))[0])

        return delta_est, float(np.std(model.resid))
    except Exception as e:
        print(f"  [WARN] OLS fitting failed: {e}")
        return None, 0


def estimate_credit_balance(
    today_data: dict,
    historical: list[dict],
    window: int = DEFAULT_WINDOW,
) -> dict:
    """
    신용잔고 추정 (Rolling OLS 10일).

    Args:
        today_data: 오늘 시장 데이터 (개인순매수, KOSPI 수익률 등)
        historical: 최근 10~15일 시계열 (실측 신용잔고 포함)
        window: OLS 윈도우 크기

    Returns:
        {
            "value": float,               # 추정 잔고 (십억원)
            "estimated": True,
            "confidence_interval": [lower, upper],  # ±1σ
            "estimation_method": "rolling_OLS_10d" | "simple_trend_10d" | "no_data"
        }
    """
    if not historical:
        return {
            "value": None,
            "estimated": True,
            "confidence_interval": [None, None],
            "estimation_method": "no_data",
        }

    # 최근 실측값 수집
    recent_values = [
        h.get("credit_balance_billion")
        for h in historical[-window:]
        if h.get("credit_balance_billion") is not None
    ]

    if not recent_values:
        return {
            "value": None,
            "estimated": True,
            "confidence_interval": [None, None],
            "estimation_method": "no_data",
        }

    last_known = recent_values[-1]

    # OLS 추정 시도
    delta_est, resid_std = _ols_estimate(historical, window, today_data)

    if delta_est is not None:
        estimated = round(last_known + delta_est, 1)
        ci_width = max(resid_std * 1.5, abs(last_known) * 0.005)  # 최소 0.5% CI
        return {
            "value": float(estimated),
            "estimated": True,
            "confidence_interval": [
                float(round(estimated - ci_width, 1)),
                float(round(estimated + ci_width, 1)),
            ],
            "estimation_method": "rolling_OLS_10d",
        }

    # Fallback: 단순 트렌드
    avg = np.mean(recent_values)
    if len(recent_values) >= 3:
        trend = (recent_values[-1] - recent_values[-3]) / 3
    else:
        trend = 0

    estimated = round(avg + trend, 1)
    std = np.std(recent_values) if len(recent_values) > 1 else abs(avg) * 0.02

    return {
        "value": float(estimated),
        "estimated": True,
        "confidence_interval": [float(round(estimated - std, 1)), float(round(estimated + std, 1))],
        "estimation_method": "simple_trend_10d",
    }


def estimate_customer_deposit(
    today_data: dict,
    historical: list[dict],
    window: int = DEFAULT_WINDOW,
) -> dict:
    """
    고객예탁금 추정. 신용잔고와 동일한 방법론 (OLS → fallback trend).
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
        for h in historical[-window:]
        if h.get("deposit_billion") is not None
    ]

    if not recent_values:
        return {
            "value": None,
            "estimated": True,
            "confidence_interval": [None, None],
            "estimation_method": "no_data",
        }

    last_known = recent_values[-1]

    # OLS for deposit: similar feature set but y = ΔDeposit
    if OLS is not None and len(historical) >= window:
        try:
            deposits = []
            kospis = []
            for h in historical[-window - 1:]:
                dep = h.get("deposit_billion")
                if dep is None:
                    continue
                deposits.append(dep)
                kospis.append(h.get("kospi", 0) or 0)

            if len(deposits) >= 5:
                deposits = np.array(deposits, dtype=float)
                kospis = np.array(kospis, dtype=float)

                d_deposit = np.diff(deposits)
                kospi_ret = np.diff(kospis) / np.where(kospis[:-1] != 0, kospis[:-1], 1) * 100
                lag_d_dep = np.concatenate([[0], d_deposit[:-1]])

                y = d_deposit
                X = np.column_stack([kospi_ret, lag_d_dep])
                X_c = add_constant(X)

                model = OLS(y, X_c).fit()

                last = historical[-1]
                prev = historical[-2] if len(historical) >= 2 else last
                kospi_t = (today_data or {}).get("kospi", last.get("kospi", 0)) or 0
                kospi_p = last.get("kospi", kospi_t) or kospi_t
                ret_t = (kospi_t - kospi_p) / kospi_p * 100 if kospi_p else 0
                lag_d = (last.get("deposit_billion", 0) or 0) - (prev.get("deposit_billion", 0) or 0)

                x_today = np.array([1, ret_t, lag_d])
                delta_est = float(model.predict(x_today.reshape(1, -1))[0])
                resid_std = float(np.std(model.resid))

                estimated = round(last_known + delta_est, 1)
                ci_width = max(resid_std * 1.5, abs(last_known) * 0.005)
                return {
                    "value": float(estimated),
                    "estimated": True,
                    "confidence_interval": [
                        float(round(estimated - ci_width, 1)),
                        float(round(estimated + ci_width, 1)),
                    ],
                    "estimation_method": "rolling_OLS_10d",
                }
        except Exception as e:
            print(f"  [WARN] Deposit OLS failed: {e}")

    # Fallback: simple trend
    avg = np.mean(recent_values)
    if len(recent_values) >= 3:
        trend = (recent_values[-1] - recent_values[-3]) / 3
    else:
        trend = 0

    estimated = round(avg + trend, 1)
    std = np.std(recent_values) if len(recent_values) > 1 else abs(avg) * 0.02

    return {
        "value": float(estimated),
        "estimated": True,
        "confidence_interval": [float(round(estimated - std, 1)), float(round(estimated + std, 1))],
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
    log_path.parent.mkdir(parents=True, exist_ok=True)
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
