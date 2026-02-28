"""Walk-Forward 결과 시각화"""
import numpy as np
import matplotlib.pyplot as plt

from config.settings import CHARTS_DIR
from src.utils.logger import setup_logger

logger = setup_logger("walkforward_plot")


def plot_walk_forward(
    result: dict,
    save_path: str | None = None,
) -> None:
    """
    Subplot 1: 각 윈도우별 OOS corr (bar chart)
    Subplot 2: Mean ± Std 요약
    """
    windows = result.get("windows", [])
    if not windows:
        logger.warning("No walk-forward windows to plot")
        return

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Subplot 1: 윈도우별 OOS corr
    window_nums = [w["window"] for w in windows]
    correlations = [w["correlation"] for w in windows]
    colors = ["#4CAF50" if c > 0 else "#F44336" for c in correlations]

    ax1.bar(window_nums, correlations, color=colors, alpha=0.8)
    ax1.axhline(y=0, color="gray", linestyle="--", alpha=0.5)
    ax1.set_xlabel("Window #")
    ax1.set_ylabel("OOS Correlation")
    ax1.set_title("Walk-Forward: Window-by-Window OOS Correlation")
    ax1.set_xticks(window_nums)

    # 각 바에 값 표시
    for i, (wn, corr) in enumerate(zip(window_nums, correlations)):
        ax1.text(wn, corr + 0.01, f"{corr:.3f}",
                 ha="center", va="bottom", fontsize=9)

    # Subplot 2: 요약 통계
    mean_corr = result.get("mean_oos_corr", 0)
    std_corr = result.get("std_oos_corr", 0)
    all_pos = result.get("all_positive", False)

    summary_text = (
        f"Windows: {result.get('n_windows', 0)}\n"
        f"Mean OOS Corr: {mean_corr:.4f}\n"
        f"Std: {std_corr:.4f}\n"
        f"All Positive: {'Yes' if all_pos else 'No'}\n"
        f"Min: {min(correlations):.4f}\n"
        f"Max: {max(correlations):.4f}"
    )

    ax2.text(0.5, 0.5, summary_text,
             transform=ax2.transAxes,
             fontsize=14, verticalalignment="center",
             horizontalalignment="center",
             fontfamily="monospace",
             bbox=dict(boxstyle="round,pad=1", facecolor="lightyellow", alpha=0.8))
    ax2.set_title("Walk-Forward Summary")
    ax2.axis("off")

    fig.suptitle("Walk-Forward Validation Results", fontsize=14, fontweight="bold")
    fig.tight_layout()

    path = save_path or str(CHARTS_DIR / "walk_forward.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    logger.info(f"Walk-forward chart saved → {path}")
    plt.close()
