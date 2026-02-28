"""방향성 메트릭: MDA, SBD, Cosine Similarity, Kendall Tau.

Stage 2: 인덱스와 log10(BTC)의 방향 일치도를 다각도로 측정.
"""

import logging
import numpy as np
import pandas as pd
from scipy.stats import kendalltau

logger = logging.getLogger(__name__)


def _align_and_shift(
    index: pd.Series,
    target: pd.Series,
    lag: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Align two series and apply lag shift, return numpy arrays."""
    # Align on common dates first
    common = index.index.intersection(target.index)
    idx = index.loc[common].sort_index()
    tgt = target.loc[common].sort_index()

    idx_vals = idx.values.astype(float)
    tgt_vals = tgt.values.astype(float)

    if lag > 0:
        # index leads target by `lag` periods
        idx_vals = idx_vals[:-lag]
        tgt_vals = tgt_vals[lag:]
    elif lag < 0:
        idx_vals = idx_vals[-lag:]
        tgt_vals = tgt_vals[:lag]

    # Remove any remaining NaN
    mask = ~(np.isnan(idx_vals) | np.isnan(tgt_vals))
    return idx_vals[mask], tgt_vals[mask]


class WaveformMetrics:
    """Computes direction-matching metrics between index and BTC."""

    @staticmethod
    def mda(
        index: pd.Series,
        target: pd.Series,
        lag: int = 0,
    ) -> float:
        """
        Mean Directional Accuracy (Sign Concordance Rate).

        MDA = fraction of time steps where sign(delta_index) == sign(delta_target)

        Returns: 0.0~1.0 (0.5 = random, 1.0 = perfect match)
        """
        idx_vals, tgt_vals = _align_and_shift(index, target, lag)

        if len(idx_vals) < 3:
            return np.nan

        d_idx = np.diff(idx_vals)
        d_tgt = np.diff(tgt_vals)

        # Sign concordance: both positive, both negative, or both zero
        concordant = np.sign(d_idx) == np.sign(d_tgt)
        return float(np.mean(concordant))

    @staticmethod
    def sbd(
        index: pd.Series,
        target: pd.Series,
        lag: int = 0,
    ) -> float:
        """
        Shape-Based Distance.

        Uses normalized cross-correlation to measure shape similarity,
        ignoring amplitude differences.

        Returns: 0.0~2.0 (0 = identical shape, 2 = opposite)
        """
        idx_vals, tgt_vals = _align_and_shift(index, target, lag)

        if len(idx_vals) < 3:
            return np.nan

        # Normalize to zero mean, unit energy
        def normalize(x):
            x = x - np.mean(x)
            norm = np.sqrt(np.sum(x ** 2))
            if norm < 1e-10:
                return x
            return x / norm

        x = normalize(idx_vals)
        y = normalize(tgt_vals)

        # Normalized cross-correlation via FFT
        n = len(x)
        fft_size = 2 ** int(np.ceil(np.log2(2 * n - 1)))
        cc = np.real(np.fft.ifft(
            np.fft.fft(x, fft_size) * np.conj(np.fft.fft(y, fft_size))
        ))

        # SBD = 1 - max(NCC)
        ncc_max = np.max(cc)
        return float(1.0 - ncc_max)

    @staticmethod
    def cosine_similarity_derivatives(
        index: pd.Series,
        target: pd.Series,
        lag: int = 0,
    ) -> float:
        """
        Cosine similarity on first derivatives (rate of change vectors).

        cos_sim = (delta_index . delta_target) / (|delta_index| * |delta_target|)

        Returns: -1.0~1.0 (1 = same direction, -1 = opposite)
        """
        idx_vals, tgt_vals = _align_and_shift(index, target, lag)

        if len(idx_vals) < 3:
            return np.nan

        d_idx = np.diff(idx_vals)
        d_tgt = np.diff(tgt_vals)

        norm_idx = np.linalg.norm(d_idx)
        norm_tgt = np.linalg.norm(d_tgt)

        if norm_idx < 1e-10 or norm_tgt < 1e-10:
            return 0.0

        return float(np.dot(d_idx, d_tgt) / (norm_idx * norm_tgt))

    @staticmethod
    def kendall_tau(
        index: pd.Series,
        target: pd.Series,
        lag: int = 0,
    ) -> tuple[float, float]:
        """
        Kendall Tau rank correlation — robust to outliers.

        Returns: (tau, p_value)
        """
        idx_vals, tgt_vals = _align_and_shift(index, target, lag)

        if len(idx_vals) < 3:
            return (np.nan, np.nan)

        tau, p = kendalltau(idx_vals, tgt_vals)
        return (float(tau), float(p))

    @staticmethod
    def pearson_r(
        index: pd.Series,
        target: pd.Series,
        lag: int = 0,
    ) -> float:
        """Pearson correlation at given lag."""
        idx_vals, tgt_vals = _align_and_shift(index, target, lag)

        if len(idx_vals) < 3:
            return np.nan

        return float(np.corrcoef(idx_vals, tgt_vals)[0, 1])

    def cross_correlation_profile(
        self,
        index: pd.Series,
        target: pd.Series,
        max_lag: int = 15,
    ) -> pd.DataFrame:
        """
        Compute all metrics at lag=0..max_lag.

        Returns:
            DataFrame[lag, pearson_r, mda, sbd, cosine_sim,
                       kendall_tau, kendall_p]
        """
        rows = []
        for lag in range(max_lag + 1):
            tau, tau_p = self.kendall_tau(index, target, lag)
            rows.append({
                "lag": lag,
                "pearson_r": self.pearson_r(index, target, lag),
                "mda": self.mda(index, target, lag),
                "sbd": self.sbd(index, target, lag),
                "cosine_sim": self.cosine_similarity_derivatives(
                    index, target, lag),
                "kendall_tau": tau,
                "kendall_p": tau_p,
            })

        profile = pd.DataFrame(rows)

        # Check success criteria
        all_positive = bool((profile["pearson_r"] > 0).all())
        peak_lag = int(profile.loc[profile["pearson_r"].idxmax(), "lag"])

        logger.info(
            "XCORR profile: all_positive=%s, peak_lag=%d, peak_r=%.3f, "
            "peak_mda=%.3f",
            all_positive, peak_lag,
            profile["pearson_r"].max(),
            profile.loc[profile["pearson_r"].idxmax(), "mda"],
        )

        return profile
