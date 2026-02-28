"""교차상관 히트맵"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import pearsonr

from config.settings import CHARTS_DIR
from src.utils.logger import setup_logger

logger = setup_logger("correlation_heatmap")


def plot_cross_correlation(
    score: pd.Series,
    log_btc: pd.Series,
    max_lag: int = 12,
    save_path: str | None = None,
) -> None:
    """
    X축: lag (0-12개월), Y축: correlation
    Bar chart + 최적 lag 하이라이트
    """
    lags = list(range(0, max_lag + 1))
    correlations = []

    for k in lags:
        if k > 0:
            s = score.values[:-k]
            t = log_btc.values[k:]
        else:
            s = score.values
            t = log_btc.values

        valid = ~np.isnan(s) & ~np.isnan(t)
        if valid.sum() > 10:
            r, _ = pearsonr(s[valid], t[valid])
            correlations.append(r)
        else:
            correlations.append(0.0)

    # 최적 lag
    best_idx = np.argmax(correlations)
    colors = ["#FF5722" if i == best_idx else "#2196F3" for i in range(len(lags))]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.bar(lags, correlations, color=colors, alpha=0.8)
    ax.set_xlabel("Lag (months)")
    ax.set_ylabel("Pearson Correlation")
    ax.set_title("Cross-Correlation: Score vs log₁₀(BTC)")
    ax.axhline(y=0, color="gray", linestyle="--", alpha=0.3)
    ax.set_xticks(lags)

    # 최적 lag 라벨
    ax.annotate(
        f"Best: lag={lags[best_idx]}m\nr={correlations[best_idx]:.3f}",
        xy=(lags[best_idx], correlations[best_idx]),
        xytext=(lags[best_idx] + 1, correlations[best_idx] + 0.02),
        arrowprops=dict(arrowstyle="->", color="red"),
        fontsize=10, color="red",
    )

    fig.tight_layout()

    path = save_path or str(CHARTS_DIR / "cross_correlation.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    logger.info(f"Cross-correlation chart saved → {path}")
    plt.close()


def plot_variable_correlation_matrix(
    variables: pd.DataFrame,
    title: str = "Variable Correlation Matrix",
    save_path: str | None = None,
) -> None:
    """변수 간 상관 행렬 히트맵"""
    # date 컬럼 제외
    numeric_cols = variables.select_dtypes(include=[np.number]).columns
    corr_matrix = variables[numeric_cols].corr()

    fig, ax = plt.subplots(figsize=(8, 6))
    sns.heatmap(
        corr_matrix,
        annot=True,
        fmt=".3f",
        cmap="RdBu_r",
        center=0,
        vmin=-1, vmax=1,
        ax=ax,
        square=True,
    )
    ax.set_title(title)
    fig.tight_layout()

    path = save_path or str(CHARTS_DIR / "variable_correlation.png")
    plt.savefig(path, dpi=150, bbox_inches="tight")
    logger.info(f"Correlation matrix saved → {path}")
    plt.close()
