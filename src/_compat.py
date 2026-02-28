"""Cross-module utility functions."""

import numpy as np
import pandas as pd


def pearson_at_lag(
    index: pd.Series,
    target: pd.Series,
    lag: int,
) -> float:
    """Compute Pearson r at a given lag."""
    idx = index.values.astype(float)
    tgt = target.values.astype(float)

    n = min(len(idx), len(tgt))
    idx = idx[:n]
    tgt = tgt[:n]

    if lag > 0 and lag < n:
        idx = idx[:-lag]
        tgt = tgt[lag:]
    elif lag <= 0:
        pass
    else:
        return np.nan

    mask = ~(np.isnan(idx) | np.isnan(tgt))
    idx = idx[mask]
    tgt = tgt[mask]

    if len(idx) < 3:
        return np.nan

    return float(np.corrcoef(idx, tgt)[0, 1])
