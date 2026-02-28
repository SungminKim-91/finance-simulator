"""인덱스 방법 비교 시각화 — PCA vs ICA vs SparsePCA."""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def plot_method_comparison(
    comparison: pd.DataFrame,
    save_path: str | None = None,
) -> None:
    """
    Compare index methods side-by-side.

    Args:
        comparison: DataFrame from CompositeWaveformScore.compare_methods()
            Columns: method, optimal_lag, best_cws, mda, sbd, cosine_sim, kendall_tau
        save_path: if provided, save PNG
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available")
        return

    if comparison.empty:
        logger.warning("No comparison data to plot")
        return

    fig, axes = plt.subplots(1, 3, figsize=(16, 5))

    methods = comparison["method"].tolist()
    x = np.arange(len(methods))

    # Plot 1: CWS comparison
    ax = axes[0]
    colors = ["#2196F3", "#4CAF50", "#FF9800", "#9C27B0"]
    bars = ax.bar(x, comparison["best_cws"], color=colors[:len(methods)],
                  alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(methods)
    ax.set_ylabel("CWS")
    ax.set_title("Composite Waveform Score")
    for bar, lag in zip(bars, comparison["optimal_lag"]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.01,
                f"lag={lag}", ha="center", va="bottom", fontsize=9)

    # Plot 2: Individual metrics
    ax = axes[1]
    metrics = ["mda", "cosine_sim", "kendall_tau"]
    bar_width = 0.25
    for i, metric in enumerate(metrics):
        if metric in comparison.columns:
            vals = comparison[metric].fillna(0).tolist()
            offset = (i - 1) * bar_width
            ax.bar(x + offset, vals, bar_width, label=metric, alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(methods)
    ax.set_ylabel("Score")
    ax.set_title("Direction Metrics")
    ax.legend(fontsize=8)

    # Plot 3: SBD (lower is better)
    ax = axes[2]
    if "sbd" in comparison.columns:
        sbd_vals = comparison["sbd"].fillna(1.0).tolist()
        ax.bar(x, sbd_vals, color="coral", alpha=0.8)
        ax.set_ylabel("SBD (lower = better)")
        ax.set_title("Shape-Based Distance")
    ax.set_xticks(x)
    ax.set_xticklabels(methods)

    plt.suptitle("Index Method Comparison", fontsize=14, fontweight="bold")
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info("Method comparison plot saved: %s", save_path)
    else:
        plt.show()
    plt.close(fig)
