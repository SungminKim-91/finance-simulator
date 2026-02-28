"""Composite Waveform Score (CWS) — 복합 방향 점수.

CWS = 0.4 * MDA + 0.3 * (1 - SBD) + 0.2 * CosSim + 0.1 * Tau

4개 메트릭을 가중 합산하여 단일 점수로 평가.
"""

import logging
import numpy as np
import pandas as pd

from config.constants import WAVEFORM_WEIGHTS, XCORR_CONFIG
from .waveform_metrics import WaveformMetrics

logger = logging.getLogger(__name__)


class CompositeWaveformScore:
    """Compute CWS: a weighted combination of direction metrics."""

    def __init__(self, weights: dict | None = None):
        self.weights = weights or WAVEFORM_WEIGHTS
        self.metrics = WaveformMetrics()

    def calculate(
        self,
        index: pd.Series,
        target: pd.Series,
        lag: int,
    ) -> dict:
        """
        Compute CWS at a specific lag.

        Returns:
            dict with cws, mda, sbd, cosine_sim, kendall_tau, kendall_p, lag
        """
        mda = self.metrics.mda(index, target, lag)
        sbd = self.metrics.sbd(index, target, lag)
        cos_sim = self.metrics.cosine_similarity_derivatives(
            index, target, lag)
        tau, tau_p = self.metrics.kendall_tau(index, target, lag)

        # Normalize components to [0, 1] range
        # MDA: already 0~1
        # SBD: 0~2, we use (1 - SBD/2) so 0->1, 2->0 — but design says (1-SBD)
        sbd_norm = max(0.0, 1.0 - sbd) if not np.isnan(sbd) else 0.0
        # CosSim: -1~1, map to 0~1: (cos_sim + 1) / 2
        cos_norm = (cos_sim + 1) / 2 if not np.isnan(cos_sim) else 0.5
        # Tau: -1~1, map to 0~1: (tau + 1) / 2
        tau_norm = (tau + 1) / 2 if not np.isnan(tau) else 0.5
        # MDA: 0~1 as-is
        mda_val = mda if not np.isnan(mda) else 0.5

        cws = (
            self.weights["MDA"] * mda_val
            + self.weights["SBD"] * sbd_norm
            + self.weights["CosSim"] * cos_norm
            + self.weights["Tau"] * tau_norm
        )

        return {
            "cws": float(cws),
            "mda": float(mda) if not np.isnan(mda) else None,
            "sbd": float(sbd) if not np.isnan(sbd) else None,
            "cosine_sim": float(cos_sim) if not np.isnan(cos_sim) else None,
            "kendall_tau": float(tau) if not np.isnan(tau) else None,
            "kendall_p": float(tau_p) if not np.isnan(tau_p) else None,
            "lag": lag,
        }

    def optimal_lag(
        self,
        index: pd.Series,
        target: pd.Series,
        max_lag: int = XCORR_CONFIG["max_lag"],
    ) -> dict:
        """
        Find optimal lag by maximizing CWS across lag=0..max_lag.

        Returns:
            dict with optimal_lag, best_cws, profile (DataFrame)
        """
        results = []
        for lag in range(max_lag + 1):
            r = self.calculate(index, target, lag)
            results.append(r)

        profile = pd.DataFrame(results)
        best_idx = profile["cws"].idxmax()
        best_row = profile.loc[best_idx]

        logger.info(
            "CWS optimal: lag=%d, cws=%.3f, mda=%.3f",
            int(best_row["lag"]), best_row["cws"],
            best_row["mda"] if best_row["mda"] is not None else 0,
        )

        return {
            "optimal_lag": int(best_row["lag"]),
            "best_cws": float(best_row["cws"]),
            "profile": profile,
        }

    def compare_methods(
        self,
        indices: dict[str, pd.Series],
        target: pd.Series,
        max_lag: int = XCORR_CONFIG["max_lag"],
    ) -> pd.DataFrame:
        """
        Compare multiple index methods by CWS.

        Args:
            indices: {"PCA": series, "ICA": series, ...}
            target: log10(BTC)

        Returns:
            DataFrame[method, optimal_lag, best_cws, mda, sbd, cos, tau]
            sorted by CWS descending
        """
        rows = []
        for method_name, idx_series in indices.items():
            result = self.optimal_lag(idx_series, target, max_lag)
            best = self.calculate(idx_series, target, result["optimal_lag"])
            rows.append({
                "method": method_name,
                "optimal_lag": result["optimal_lag"],
                "best_cws": result["best_cws"],
                "mda": best["mda"],
                "sbd": best["sbd"],
                "cosine_sim": best["cosine_sim"],
                "kendall_tau": best["kendall_tau"],
            })

        comparison = pd.DataFrame(rows).sort_values(
            "best_cws", ascending=False
        ).reset_index(drop=True)

        logger.info("Method comparison:\n%s", comparison.to_string(index=False))
        return comparison
