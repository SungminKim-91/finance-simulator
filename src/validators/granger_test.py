"""Granger Causality — 단방향 인과 검정.

Index -> BTC: 유의해야 함 (Index가 BTC를 예측)
BTC -> Index: 기각되어야 함 (역방향 인과 없음)
"""

import logging
import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import grangercausalitytests, adfuller

from config.constants import GRANGER_CONFIG

logger = logging.getLogger(__name__)


class GrangerCausalityTest:
    """Bidirectional Granger causality testing."""

    def test_bidirectional(
        self,
        index: pd.Series,
        target: pd.Series,
        max_lag: int = GRANGER_CONFIG["max_lag"],
        alpha: float = GRANGER_CONFIG["alpha"],
    ) -> dict:
        """
        Test both directions: Index->BTC and BTC->Index.

        Returns:
            dict with forward, reverse, unidirectional results
        """
        # Align and clean
        common = index.index.intersection(target.index)
        idx = index.loc[common].sort_index().dropna()
        tgt = target.loc[common].sort_index().dropna()
        common2 = idx.index.intersection(tgt.index)
        idx = idx.loc[common2]
        tgt = tgt.loc[common2]

        if len(idx) < max_lag + 10:
            logger.warning(
                "Insufficient data for Granger test: %d points", len(idx)
            )
            return {
                "forward": {"significant": False, "error": "insufficient data"},
                "reverse": {"significant": False, "error": "insufficient data"},
                "unidirectional": False,
            }

        # Forward: Index -> BTC (target ~ f(target_lags, index_lags))
        forward = self._run_granger(
            idx.values, tgt.values, max_lag, alpha, "Index->BTC"
        )

        # Reverse: BTC -> Index
        reverse = self._run_granger(
            tgt.values, idx.values, max_lag, alpha, "BTC->Index"
        )

        unidirectional = forward["significant"] and not reverse["significant"]

        logger.info(
            "Granger: forward=%s (p=%.4f), reverse=%s (p=%.4f), "
            "unidirectional=%s",
            forward["significant"], forward.get("best_p_value", 1.0),
            reverse["significant"], reverse.get("best_p_value", 1.0),
            unidirectional,
        )

        return {
            "forward": forward,
            "reverse": reverse,
            "unidirectional": unidirectional,
        }

    def _run_granger(
        self,
        cause: np.ndarray,
        effect: np.ndarray,
        max_lag: int,
        alpha: float,
        label: str,
    ) -> dict:
        """Run Granger test for cause -> effect direction."""
        data = np.column_stack([effect, cause])

        try:
            results = grangercausalitytests(
                data, maxlag=max_lag, verbose=False
            )
        except Exception as e:
            logger.warning("Granger test failed (%s): %s", label, e)
            return {
                "significant": False,
                "error": str(e),
            }

        lag_results = {}
        best_p = 1.0
        best_lag = 1

        for lag in range(1, max_lag + 1):
            if lag not in results:
                continue
            # Use ssr_ftest p-value
            test_result = results[lag]
            p_value = test_result[0]["ssr_ftest"][1]
            lag_results[lag] = float(p_value)

            if p_value < best_p:
                best_p = p_value
                best_lag = lag

        return {
            "lag_results": lag_results,
            "best_lag": best_lag,
            "best_p_value": float(best_p),
            "significant": best_p < alpha,
        }

    @staticmethod
    def stationarity_check(series: pd.Series) -> dict:
        """
        ADF test for stationarity (Granger prerequisite).

        Returns:
            dict with adf_stat, p_value, stationary
        """
        clean = series.dropna()
        if len(clean) < 20:
            return {
                "adf_stat": np.nan,
                "p_value": 1.0,
                "stationary": False,
                "error": "insufficient data",
            }

        try:
            result = adfuller(clean, autolag="AIC")
            adf_stat, p_value = result[0], result[1]
        except Exception as e:
            logger.warning("ADF test failed: %s", e)
            return {
                "adf_stat": np.nan,
                "p_value": 1.0,
                "stationary": False,
                "error": str(e),
            }

        return {
            "adf_stat": float(adf_stat),
            "p_value": float(p_value),
            "stationary": p_value < 0.05,
        }
