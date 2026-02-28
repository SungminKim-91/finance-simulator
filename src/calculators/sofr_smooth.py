"""SOFR Smooth Transition — Binary(v1.0) -> 연속 확률(v2.0)

v1.0: binary(0/1) x weight=-4.0 -> score -16 spike
v2.0: Logistic smooth(0~1 연속) -> PCA 자연 loading
"""

import logging
import numpy as np
import pandas as pd

from config.constants import SOFR_LOGISTIC, SOFR_MARKOV

logger = logging.getLogger(__name__)


class SofrSmoothCalculator:
    """SOFR spread -> 연속 위기 확률 변환."""

    def calculate_logistic(
        self,
        sofr: pd.DataFrame,
        iorb: pd.DataFrame,
        gamma: float = SOFR_LOGISTIC["gamma"],
        threshold: float = SOFR_LOGISTIC["threshold_bps"],
    ) -> pd.DataFrame:
        """
        Logistic smoothing.

        P(crisis) = 1 / (1 + exp(-gamma * (spread_bps - threshold)))

        Args:
            sofr: DataFrame with columns [date, value] (daily rates)
            iorb: DataFrame with columns [date, value] (daily rates)
            gamma: transition steepness (0.1=gentle, 0.5=sharp)
            threshold: center point in bps

        Returns:
            DataFrame[date, sofr_spread_bps, sofr_smooth]
        """
        # Align dates
        sofr_s = sofr.set_index("date")["value"]
        iorb_s = iorb.set_index("date")["value"]

        # Merge on common dates
        merged = pd.DataFrame({"sofr": sofr_s, "iorb": iorb_s}).dropna()

        # Spread in basis points
        spread_bps = (merged["sofr"] - merged["iorb"]) * 100  # rate -> bps

        # Logistic transformation
        smooth = 1.0 / (1.0 + np.exp(-gamma * (spread_bps - threshold)))

        result = pd.DataFrame({
            "date": merged.index,
            "sofr_spread_bps": spread_bps.values,
            "sofr_smooth": smooth.values,
        }).reset_index(drop=True)

        logger.info(
            "SOFR smooth: %d days, spread range [%.1f, %.1f] bps, "
            "smooth range [%.4f, %.4f]",
            len(result),
            spread_bps.min(), spread_bps.max(),
            smooth.min(), smooth.max(),
        )
        return result

    def calculate_markov(
        self,
        sofr: pd.DataFrame,
        iorb: pd.DataFrame,
        k_regimes: int = SOFR_MARKOV["k_regimes"],
    ) -> pd.DataFrame:
        """
        Markov Regime-Switching model for SOFR crisis probability.

        Falls back to Logistic if statsmodels MarkovRegression fails.

        Args:
            sofr: DataFrame[date, value]
            iorb: DataFrame[date, value]
            k_regimes: number of regimes (default 2: normal/crisis)

        Returns:
            DataFrame[date, sofr_spread_bps, regime_prob, regime_label]
        """
        try:
            from statsmodels.tsa.regime_switching.markov_regression import (
                MarkovRegression,
            )
        except ImportError:
            logger.warning("statsmodels MarkovRegression not available, "
                           "falling back to Logistic")
            logistic = self.calculate_logistic(sofr, iorb)
            logistic["regime_prob"] = logistic["sofr_smooth"]
            logistic["regime_label"] = np.where(
                logistic["regime_prob"] > 0.5, "crisis", "normal"
            )
            return logistic

        # Compute spread
        sofr_s = sofr.set_index("date")["value"]
        iorb_s = iorb.set_index("date")["value"]
        merged = pd.DataFrame({"sofr": sofr_s, "iorb": iorb_s}).dropna()
        spread_bps = (merged["sofr"] - merged["iorb"]) * 100

        # Resample to monthly for Markov stability
        monthly_spread = spread_bps.resample("ME").mean().dropna()

        # Try fitting with multiple seeds
        best_result = None
        for seed in [0, 42, 123]:
            try:
                np.random.seed(seed)
                model = MarkovRegression(
                    monthly_spread,
                    k_regimes=k_regimes,
                    order=SOFR_MARKOV["order"],
                )
                result = model.fit(disp=False, maxiter=500)
                if best_result is None or result.llf > best_result.llf:
                    best_result = result
            except Exception as e:
                logger.debug("Markov seed=%d failed: %s", seed, e)
                continue

        if best_result is None:
            logger.warning("Markov fitting failed, falling back to Logistic")
            return self.calculate_logistic(sofr, iorb)

        # Identify crisis regime (higher mean spread)
        regime_means = best_result.params[
            [f"const[{i}]" for i in range(k_regimes)]
        ] if hasattr(best_result, "params") else None

        smoothed_probs = best_result.smoothed_marginal_probabilities
        # Assume regime with higher spread is "crisis"
        if regime_means is not None and len(regime_means) >= 2:
            crisis_regime = int(np.argmax(regime_means))
        else:
            crisis_regime = 1

        crisis_prob = smoothed_probs[crisis_regime]

        result_df = pd.DataFrame({
            "date": monthly_spread.index,
            "sofr_spread_bps": monthly_spread.values,
            "regime_prob": crisis_prob.values,
            "regime_label": np.where(crisis_prob.values > 0.5,
                                     "crisis", "normal"),
        }).reset_index(drop=True)

        logger.info(
            "Markov regime: %d months, crisis episodes: %d",
            len(result_df),
            (result_df["regime_label"] == "crisis").sum(),
        )
        return result_df

    def resample_to_freq(
        self,
        smooth_daily: pd.DataFrame,
        freq: str = "monthly",
    ) -> pd.DataFrame:
        """
        Resample daily smooth values to target frequency.

        Args:
            smooth_daily: DataFrame with 'date' and 'sofr_smooth' columns
            freq: "daily" | "weekly" | "monthly"

        Returns:
            Resampled DataFrame
        """
        df = smooth_daily.copy()
        df["date"] = pd.to_datetime(df["date"])
        df = df.set_index("date")

        freq_map = {"daily": None, "weekly": "W", "monthly": "ME"}
        pandas_freq = freq_map.get(freq)

        if pandas_freq is None:
            return smooth_daily

        resampled = df[["sofr_smooth"]].resample(pandas_freq).mean().dropna()
        return resampled.reset_index()
