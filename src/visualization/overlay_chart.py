"""Score vs log₁₀(BTC) 오버레이 차트"""
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
