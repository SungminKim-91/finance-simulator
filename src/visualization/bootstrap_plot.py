"""Bootstrap 결과 시각화 — Loading CI + Lag 분포."""

import logging
import numpy as np

logger = logging.getLogger(__name__)


def plot_loading_ci(
    bootstrap_result: dict,
    save_path: str | None = None,
) -> None:
    """
    PC1 loadings 95% CI error bar chart.

    Args:
        bootstrap_result: output from BootstrapAnalyzer.loading_stability()
        save_path: if provided, save PNG instead of showing
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available")
        return

    mean = bootstrap_result.get("mean_loadings", {})
    ci_lo = bootstrap_result.get("ci_lower", {})
    ci_hi = bootstrap_result.get("ci_upper", {})

    if not mean:
        logger.warning("No loading data to plot")
        return

    variables = list(mean.keys())
    means = [mean[v] for v in variables]
    errors_lo = [mean[v] - ci_lo[v] for v in variables]
    errors_hi = [ci_hi[v] - mean[v] for v in variables]

    fig, ax = plt.subplots(figsize=(10, 5))
    x = np.arange(len(variables))

    ax.bar(x, means, color="steelblue", alpha=0.7, label="Mean loading")
    ax.errorbar(x, means, yerr=[errors_lo, errors_hi],
                fmt="none", ecolor="black", capsize=5, label="95% CI")
    ax.axhline(0, color="gray", linewidth=0.5, linestyle="--")

    ax.set_xticks(x)
    ax.set_xticklabels(variables, rotation=45, ha="right")
    ax.set_ylabel("Loading")
    ax.set_title(
        f"PC1 Loadings with 95% CI "
        f"(NL max rate: {bootstrap_result.get('nl_max_rate', 0):.1%})"
    )
    ax.legend()
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info("Bootstrap loading plot saved: %s", save_path)
    else:
        plt.show()
    plt.close(fig)


def plot_lag_distribution(
    lag_result: dict,
    save_path: str | None = None,
) -> None:
    """
    Bootstrap optimal lag distribution histogram.

    Args:
        lag_result: output from BootstrapAnalyzer.lag_distribution()
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        logger.warning("matplotlib not available")
        return

    lags = lag_result.get("distribution")
    if lags is None or len(lags) == 0:
        logger.warning("No lag distribution data")
        return

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.hist(lags, bins=range(0, 17), alpha=0.7, color="steelblue",
            edgecolor="white", align="left")

    # CI shading
    ci_lo = lag_result.get("ci_lower", 0)
    ci_hi = lag_result.get("ci_upper", 15)
    ax.axvspan(ci_lo, ci_hi, alpha=0.15, color="orange", label="95% CI")

    # Mode
    mode = lag_result.get("mode_lag", 0)
    ax.axvline(mode, color="red", linewidth=2, linestyle="--",
               label=f"Mode = {mode}")

    ax.set_xlabel("Optimal Lag (months)")
    ax.set_ylabel("Frequency")
    ax.set_title(
        f"Bootstrap Lag Distribution "
        f"(mean={lag_result.get('mean_lag', 0):.1f}, "
        f"median={lag_result.get('median_lag', 0):.1f})"
    )
    ax.legend()
    plt.tight_layout()

    if save_path:
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        logger.info("Lag distribution plot saved: %s", save_path)
    else:
        plt.show()
    plt.close(fig)
