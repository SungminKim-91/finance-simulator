"""12m MA Detrend + Z-Score 표준화 — 모든 수준 변수에 공통 적용"""
import pandas as pd
import numpy as np

from config.constants import MA_WINDOW_MONTHS


def detrend_12m_ma(
    series: pd.Series,
    window: int = MA_WINDOW_MONTHS,
) -> pd.Series:
    """
    X_detrended(t) = (X(t) - MA12(X, t)) / MA12(X, t) × 100

    경제적 의미: "최근 1년 추세 대비 현재 수준이 얼마나 높은가/낮은가 (%)"

    Args:
        series: 원본 월간 시계열 (numeric)
        window: MA 윈도우 (default 12)
    Returns:
        detrended series (처음 window-1개월은 NaN)
    """
    ma = series.rolling(window=window, min_periods=window).mean()
    detrended = (series - ma) / ma * 100
    return detrended


def detrend_12m_ma_abs(
    series: pd.Series,
    window: int = MA_WINDOW_MONTHS,
) -> pd.Series:
    """
    |MA| 로 나누는 버전 (음수 MA 방지 — CME Basis 등)

    X_detrended(t) = (X(t) - MA12(X, t)) / |MA12(X, t)| × 100
    """
    ma = series.rolling(window=window, min_periods=window).mean()
    detrended = (series - ma) / ma.abs() * 100
    # MA가 0에 가까운 경우 처리
    detrended = detrended.replace([np.inf, -np.inf], np.nan)
    return detrended


def zscore(
    series: pd.Series,
    mean: float | None = None,
    std: float | None = None,
) -> pd.Series:
    """
    z = (x - μ) / σ

    Args:
        series: detrended 시계열
        mean, std: 고정 파라미터 (None이면 series에서 계산)
    Returns:
        z-score 표준화 시계열

    주의: 백테스트 기간의 μ, σ를 고정해야 미래 데이터 누출 방지
    """
    mu = mean if mean is not None else series.mean()
    sigma = std if std is not None else series.std()

    if sigma == 0 or np.isnan(sigma):
        return pd.Series(0.0, index=series.index)

    return (series - mu) / sigma


def compute_zscore_params(series: pd.Series) -> dict:
    """
    시계열에서 mean, std 계산.
    Returns: {"mean": float, "std": float}
    """
    clean = series.dropna()
    return {
        "mean": float(clean.mean()),
        "std": float(clean.std()),
    }
