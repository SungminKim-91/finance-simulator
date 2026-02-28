"""Score vs log₁₀(BTC) 오버레이 차트 (v1.0 + v2.0)"""
import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from scipy.stats import pearsonr

from config.settings import CHARTS_DIR
from src.utils.logger import setup_logger

logger = setup_logger("overlay_chart")


def plot_score_vs_btc(
    score: pd.Series,
    log_btc: pd.Series,
    dates: pd.Series,
    lag: int = 5,
    title: str = "Liquidity Score vs log₁₀(BTC)",
    save_path: str | None = None,
) -> None:
    """
    2-axis chart:
    - 좌축: Liquidity Score (blue)
    - 우축: log₁₀(BTC) (orange, lag만큼 좌로 시프트)
    """
    fig, ax1 = plt.subplots(figsize=(14, 7))

    # Score (좌축)
    color_score = "#2196F3"
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Liquidity Score", color=color_score)
    ax1.plot(dates, score, color=color_score, linewidth=1.5, label="Score", alpha=0.9)
    ax1.tick_params(axis="y", labelcolor=color_score)
    ax1.axhline(y=0, color="gray", linestyle="--", alpha=0.3)

    # log₁₀(BTC) (우축 — lag 시프트)
    ax2 = ax1.twinx()
    color_btc = "#FF9800"
    ax2.set_ylabel(f"log₁₀(BTC) [shifted {lag}m left]", color=color_btc)

    # lag만큼 좌로 시프트 (Score가 선행)
    if lag > 0 and lag < len(log_btc):
        btc_shifted_values = log_btc.values[lag:]
        btc_shifted_dates = dates.values[:len(btc_shifted_values)]
        ax2.plot(btc_shifted_dates, btc_shifted_values,
                 color=color_btc, linewidth=1.5, label=f"log₁₀(BTC) [t+{lag}m]", alpha=0.9)
    else:
        ax2.plot(dates, log_btc, color=color_btc, linewidth=1.5, label="log₁₀(BTC)", alpha=0.9)

    ax2.tick_params(axis="y", labelcolor=color_btc)

    # 상관계수 표시
    valid = score.notna() & log_btc.notna()
    if lag > 0 and valid.sum() > lag:
        s = score.values[:-lag]
        t = log_btc.values[lag:]
        v = ~np.isnan(s) & ~np.isnan(t)
        if v.sum() > 5:
            r, _ = pearsonr(s[v], t[v])
            ax1.text(0.02, 0.95, f"r = {r:.3f} (lag={lag}m)",
                     transform=ax1.transAxes, fontsize=12,
                     verticalalignment="top",
                     bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    # 포맷
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
    plt.xticks(rotation=45)

    fig.suptitle(title, fontsize=14, fontweight="bold")
    fig.tight_layout()

    # 범례
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info(f"Chart saved → {save_path}")
    else:
        default_path = CHARTS_DIR / "score_vs_btc.png"
        plt.savefig(default_path, dpi=150, bbox_inches="tight")
        logger.info(f"Chart saved → {default_path}")

    plt.close()


def plot_index_vs_btc(
    index: pd.Series,
    log_btc: pd.Series,
    dates: pd.Series | None = None,
    lag: int = 5,
    mda: float | None = None,
    title: str = "Liquidity Index vs log₁₀(BTC)",
    save_path: str | None = None,
) -> None:
    """
    v2.0 Index vs BTC overlay with direction match/mismatch shading.

    Args:
        index: liquidity index series (z-score)
        log_btc: log10(BTC price)
        dates: datetime index (optional, inferred if None)
        lag: months to shift BTC left
        mda: MDA value to display (optional)
        title: chart title
        save_path: if provided, save PNG instead of default path
    """
    fig, ax1 = plt.subplots(figsize=(14, 7))

    if dates is None:
        dates = pd.RangeIndex(len(index))

    n = min(len(index), len(log_btc), len(dates))
    index = index.values[:n]
    log_btc_vals = log_btc.values[:n]
    date_vals = dates.values[:n]

    # Index (left axis)
    color_idx = "#2196F3"
    ax1.set_xlabel("Date")
    ax1.set_ylabel("Liquidity Index", color=color_idx)
    ax1.plot(date_vals, index, color=color_idx, linewidth=1.5,
             label="Index", alpha=0.9)
    ax1.tick_params(axis="y", labelcolor=color_idx)
    ax1.axhline(y=0, color="gray", linestyle="--", alpha=0.3)

    # log10(BTC) (right axis, shifted)
    ax2 = ax1.twinx()
    color_btc = "#FF9800"
    ax2.set_ylabel(f"log₁₀(BTC) [shifted {lag}m left]", color=color_btc)

    if lag > 0 and lag < len(log_btc_vals):
        btc_shifted = log_btc_vals[lag:]
        btc_dates = date_vals[:len(btc_shifted)]
        ax2.plot(btc_dates, btc_shifted, color=color_btc, linewidth=1.5,
                 label=f"log₁₀(BTC) [t+{lag}m]", alpha=0.9)

        # Direction match/mismatch shading
        idx_diff = np.diff(index[:len(btc_shifted)])
        btc_diff = np.diff(btc_shifted)
        for i in range(len(idx_diff)):
            same_dir = (idx_diff[i] > 0) == (btc_diff[i] > 0)
            color = "#4CAF50" if same_dir else "#F44336"
            alpha = 0.08
            if i + 1 < len(btc_dates):
                ax1.axvspan(btc_dates[i], btc_dates[i + 1],
                            alpha=alpha, color=color, linewidth=0)
    else:
        ax2.plot(date_vals, log_btc_vals, color=color_btc, linewidth=1.5,
                 label="log₁₀(BTC)", alpha=0.9)

    ax2.tick_params(axis="y", labelcolor=color_btc)

    # Correlation + MDA annotation
    info_lines = []
    if lag > 0 and lag < n:
        s = index[:-lag]
        t = log_btc_vals[lag:]
        v = ~np.isnan(s) & ~np.isnan(t)
        if v.sum() > 5:
            r, _ = pearsonr(s[v], t[v])
            info_lines.append(f"r = {r:.3f} (lag={lag}m)")
    if mda is not None:
        info_lines.append(f"MDA = {mda:.1%}")

    if info_lines:
        ax1.text(0.02, 0.95, "\n".join(info_lines),
                 transform=ax1.transAxes, fontsize=11,
                 verticalalignment="top",
                 bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5))

    # Format
    if hasattr(date_vals[0], 'strftime'):
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        ax1.xaxis.set_major_locator(mdates.MonthLocator(interval=6))
        plt.xticks(rotation=45)

    fig.suptitle(title, fontsize=14, fontweight="bold")
    fig.tight_layout()

    # Legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info(f"Index vs BTC chart saved → {save_path}")
    else:
        default_path = CHARTS_DIR / "index_vs_btc.png"
        default_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(default_path, dpi=150, bbox_inches="tight")
        logger.info(f"Index vs BTC chart saved → {default_path}")

    plt.close()
