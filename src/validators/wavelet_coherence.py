"""Wavelet Coherence — 시간-주파수 방향 분석.

"어떤 주기(frequency)에서 선행(lead)하는가?" 분석.
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class WaveletCoherenceAnalyzer:
    """Wavelet coherence analysis between index and BTC."""

    def analyze(
        self,
        index: pd.Series,
        target: pd.Series,
        dt: float = 1.0,
    ) -> dict:
        """
        Compute wavelet coherence.

        Args:
            index: liquidity index
            target: log10(BTC)
            dt: time step (1.0 = 1 month)

        Returns:
            dict with coherence, phase, coi, freqs, significance,
                  dominant_period, mean_phase_lag
        """
        try:
            import pycwt
        except ImportError:
            logger.warning("pycwt not installed. Skipping wavelet analysis.")
            return {"error": "pycwt not installed", "available": False}

        # Align series
        common = index.index.intersection(target.index)
        idx = index.loc[common].sort_index()
        tgt = target.loc[common].sort_index()

        x = idx.values.astype(float)
        y = tgt.values.astype(float)

        # Standardize
        x = (x - x.mean()) / x.std()
        y = (y - y.mean()) / y.std()

        try:
            WCT, aWCT, coi, freqs, sig = pycwt.wct(
                x, y, dt,
                dj=1/12,
                s0=-1,
                J=-1,
                significance_level=0.95,
                normalize=True,
            )
        except Exception as e:
            logger.error("Wavelet coherence computation failed: %s", e)
            return {"error": str(e), "available": True}

        # Find dominant period (highest mean coherence)
        periods = 1.0 / freqs
        mean_coherence = np.mean(np.abs(WCT) ** 2, axis=1)
        dominant_idx = np.argmax(mean_coherence)
        dominant_period = float(periods[dominant_idx])

        # Mean phase lag at dominant period
        phase_at_dominant = aWCT[dominant_idx, :]
        mean_phase = float(np.mean(phase_at_dominant))
        # Convert phase to time lag (in units of dt)
        mean_phase_lag = mean_phase / (2 * np.pi) * dominant_period

        logger.info(
            "Wavelet: dominant_period=%.1f months, "
            "mean_phase_lag=%.1f months, "
            "max_coherence=%.3f",
            dominant_period, mean_phase_lag, mean_coherence[dominant_idx],
        )

        return {
            "coherence": np.abs(WCT) ** 2,
            "phase": aWCT,
            "coi": coi,
            "freqs": freqs,
            "periods": periods,
            "significance": sig,
            "dominant_period": dominant_period,
            "mean_phase_lag": float(mean_phase_lag),
            "mean_coherence_profile": mean_coherence,
            "available": True,
            "n_observations": len(x),
        }

    def plot_coherence(
        self,
        result: dict,
        save_path: str | None = None,
    ) -> None:
        """Plot wavelet coherence contour with phase arrows."""
        if result.get("error") or not result.get("available"):
            logger.warning("Cannot plot: wavelet analysis not available")
            return

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.warning("matplotlib not available for plotting")
            return

        coherence = result["coherence"]
        periods = result["periods"]
        coi = result["coi"]

        fig, ax = plt.subplots(figsize=(12, 6))

        # Contour plot
        t = np.arange(coherence.shape[1])
        T, P = np.meshgrid(t, periods)
        cs = ax.contourf(T, P, coherence, levels=20, cmap="jet")
        plt.colorbar(cs, ax=ax, label="Coherence")

        # COI
        ax.fill_between(t, coi, max(periods),
                         alpha=0.3, color="white", hatch="//")

        ax.set_yscale("log")
        ax.set_ylabel("Period (months)")
        ax.set_xlabel("Time (months)")
        ax.set_title(
            f"Wavelet Coherence "
            f"(dominant={result['dominant_period']:.0f}m, "
            f"phase_lag={result['mean_phase_lag']:.1f}m)"
        )
        ax.invert_yaxis()

        plt.tight_layout()

        if save_path:
            fig.savefig(save_path, dpi=150, bbox_inches="tight")
            logger.info("Wavelet plot saved: %s", save_path)
        else:
            plt.show()

        plt.close(fig)
