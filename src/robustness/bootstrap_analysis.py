"""Block Bootstrap 안정성 분석.

PC1 loadings, 최적 lag, MDA의 통계적 안정성을 검증.
"""

import logging
import numpy as np
import pandas as pd
from scipy.stats import binom_test

from config.constants import BOOTSTRAP_CONFIG

logger = logging.getLogger(__name__)


def _block_bootstrap_indices(
    n: int,
    block_length: int,
    rng: np.random.Generator,
) -> np.ndarray:
    """Generate block bootstrap sample indices."""
    n_blocks = int(np.ceil(n / block_length))
    starts = rng.integers(0, n - block_length + 1, size=n_blocks)
    indices = np.concatenate([
        np.arange(s, s + block_length) for s in starts
    ])
    return indices[:n]


class BootstrapAnalyzer:
    """Block Bootstrap for loading stability and lag distribution."""

    def __init__(
        self,
        n_bootstraps: int = BOOTSTRAP_CONFIG["n_bootstraps"],
        block_length: int = BOOTSTRAP_CONFIG["block_length"],
        confidence_level: float = BOOTSTRAP_CONFIG["confidence_level"],
    ):
        self.n_bootstraps = n_bootstraps
        self.block_length = block_length
        self.confidence_level = confidence_level

    def loading_stability(
        self,
        z_matrix: pd.DataFrame,
        builder_class: type,
    ) -> dict:
        """
        Bootstrap PC1 loadings 95% CI.

        Args:
            z_matrix: z-scored variable matrix
            builder_class: PCAIndexBuilder or similar with .build() method

        Returns:
            dict with mean_loadings, ci_lower, ci_upper,
                  nl_always_max, ci_excludes_zero, samples
        """
        numeric_cols = z_matrix.select_dtypes(include=[np.number]).columns.tolist()
        X = z_matrix[numeric_cols].dropna()
        n = len(X)
        n_vars = len(numeric_cols)

        rng = np.random.default_rng(42)
        loading_samples = np.zeros((self.n_bootstraps, n_vars))
        nl_max_count = 0

        # Find NL column index
        nl_idx = next(
            (i for i, c in enumerate(numeric_cols) if "NL" in c.upper()),
            0,
        )

        for b in range(self.n_bootstraps):
            boot_idx = _block_bootstrap_indices(n, self.block_length, rng)
            z_boot = X.iloc[boot_idx].reset_index(drop=True)
            z_boot.columns = numeric_cols

            try:
                builder = builder_class()
                result = builder.build(z_boot)
                loadings = [result["loadings"].get(c, 0.0) for c in numeric_cols]

                # Sign correction: NL loading should be positive
                if loadings[nl_idx] < 0:
                    loadings = [-l for l in loadings]

                loading_samples[b] = loadings

                # Check if NL has max |loading|
                if np.argmax(np.abs(loadings)) == nl_idx:
                    nl_max_count += 1

            except Exception:
                loading_samples[b] = np.nan

        # Remove failed bootstraps
        valid = ~np.any(np.isnan(loading_samples), axis=1)
        samples = loading_samples[valid]
        n_valid = len(samples)

        if n_valid < 10:
            logger.warning("Only %d valid bootstrap samples", n_valid)
            return {"error": "Insufficient valid samples"}

        alpha = 1 - self.confidence_level
        lo_pct = alpha / 2 * 100
        hi_pct = (1 - alpha / 2) * 100

        mean_loadings = {c: float(np.mean(samples[:, i]))
                         for i, c in enumerate(numeric_cols)}
        ci_lower = {c: float(np.percentile(samples[:, i], lo_pct))
                     for i, c in enumerate(numeric_cols)}
        ci_upper = {c: float(np.percentile(samples[:, i], hi_pct))
                     for i, c in enumerate(numeric_cols)}
        ci_excludes_zero = {
            c: bool(ci_lower[c] > 0 or ci_upper[c] < 0)
            for c in numeric_cols
        }

        logger.info(
            "Bootstrap loadings (%d valid): NL_always_max=%d/%d (%.1f%%)",
            n_valid, nl_max_count, n_valid,
            nl_max_count / n_valid * 100,
        )

        return {
            "mean_loadings": mean_loadings,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
            "nl_always_max": nl_max_count / n_valid > 0.95,
            "nl_max_rate": float(nl_max_count / n_valid),
            "ci_excludes_zero": ci_excludes_zero,
            "n_valid": n_valid,
            "samples": samples,
        }

    def lag_distribution(
        self,
        z_matrix: pd.DataFrame,
        target: pd.Series,
        builder_class: type,
        scorer,
    ) -> dict:
        """
        Bootstrap distribution of optimal lag.

        Args:
            scorer: CompositeWaveformScore instance
        """
        numeric_cols = z_matrix.select_dtypes(include=[np.number]).columns.tolist()
        X = z_matrix[numeric_cols].dropna()
        n = len(X)

        rng = np.random.default_rng(42)
        lag_samples = []

        for b in range(min(self.n_bootstraps, 200)):  # Limit for speed
            boot_idx = _block_bootstrap_indices(n, self.block_length, rng)
            z_boot = X.iloc[boot_idx].reset_index(drop=True)
            z_boot.columns = numeric_cols

            # Align target to same bootstrap indices
            target_aligned = target.iloc[:n]
            t_boot = target_aligned.iloc[boot_idx].reset_index(drop=True)

            try:
                builder = builder_class()
                result = builder.build(z_boot)
                index = result["index"]

                # Sign correction using NL
                nl_col = next(
                    (c for c in numeric_cols if "NL" in c.upper()),
                    numeric_cols[0],
                )
                nl_boot = z_boot[nl_col]
                corr_nl = np.corrcoef(
                    index.values[:len(nl_boot)], nl_boot.values
                )[0, 1]
                if corr_nl < 0:
                    index = -index

                opt = scorer.optimal_lag(index, t_boot, max_lag=15)
                lag_samples.append(opt["optimal_lag"])
            except Exception:
                continue

        if len(lag_samples) < 10:
            return {"error": "Insufficient valid samples"}

        lags = np.array(lag_samples)
        alpha = 1 - self.confidence_level

        return {
            "mean_lag": float(np.mean(lags)),
            "median_lag": float(np.median(lags)),
            "mode_lag": int(pd.Series(lags).mode().iloc[0]),
            "ci_lower": float(np.percentile(lags, alpha / 2 * 100)),
            "ci_upper": float(np.percentile(lags, (1 - alpha / 2) * 100)),
            "n_samples": len(lag_samples),
            "distribution": lags,
        }

    @staticmethod
    def mda_significance(
        mda_value: float,
        n_observations: int,
    ) -> dict:
        """
        MDA significance via binomial test.

        H0: MDA = 0.5 (random direction matching)
        H1: MDA > 0.5
        """
        k = int(round(mda_value * n_observations))

        try:
            # scipy >= 1.7 deprecated binom_test, use binomtest
            from scipy.stats import binomtest
            result = binomtest(k, n_observations, 0.5, alternative="greater")
            p = result.pvalue
        except ImportError:
            p = binom_test(k, n_observations, 0.5, alternative="greater")

        return {
            "mda": float(mda_value),
            "p_value": float(p),
            "significant": p < 0.05,
            "n_observations": n_observations,
        }
