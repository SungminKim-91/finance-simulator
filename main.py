#!/usr/bin/env python3
"""
Finance Simulator — BTC Liquidity Prediction Model v2.0.0

Usage:
    # === v1.0 호환 명령 ===
    python main.py fetch            # 데이터 수집만
    python main.py optimize         # v1.0 Grid Search (deprecated)

    # === v2.0 신규 명령 ===
    python main.py build-index      # Stage 1: 인덱스 구성 (BTC-blind)
    python main.py validate         # Stage 2: 방향성 검증
    python main.py analyze          # Stage 3: 과적합 분석
    python main.py run              # 전체 3-Stage 파이프라인
    python main.py compare          # 4개 방법 비교

    # === 공통 옵션 ===
    --freq daily|weekly|monthly     # 타임스케일 (기본: monthly)
    --method pca|ica|dfm|sparse     # 인덱스 방법 (기본: pca)
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# 프로젝트 루트를 path에 추가
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import DATA_START, DATA_END, CHARTS_DIR
from src.pipeline.runner import PipelineRunner
from src.pipeline.storage import StorageManager
from src.utils.logger import setup_logger

logger = setup_logger("main")


def cmd_fetch(args):
    """데이터 수집만"""
    runner = PipelineRunner(mode="full")
    raw = runner._fetch_all(
        args.start or DATA_START,
        args.end or DATA_END,
        use_cache=not args.no_cache,
    )
    print(f"\n[Fetch Complete] {len(raw)} data sources collected")
    for key, df in raw.items():
        if hasattr(df, '__len__'):
            if isinstance(df, dict):
                total = sum(len(v) for v in df.values())
                print(f"  {key}: {len(df)} series ({total} total rows)")
            else:
                print(f"  {key}: {len(df)} rows")


def cmd_optimize(args):
    """전체 최적화"""
    runner = PipelineRunner(mode="full")
    result = runner.run(
        start=args.start or DATA_START,
        end=args.end or DATA_END,
        use_cache=not args.no_cache,
    )

    if result:
        print("\n" + "=" * 60)
        print("  BTC LIQUIDITY MODEL — OPTIMIZATION COMPLETE")
        print("=" * 60)
        print(f"  Score:       {result['score']:+.4f}")
        print(f"  Signal:      {result['signal']}")
        print(f"  Optimal Lag: {result['lag']} months")
        print(f"  Correlation: {result['correlation']:.4f}")
        print(f"  Weights:")
        for var, w in result.get("weights", {}).items():
            print(f"    {var:15s}: {w:+.1f}")
        print("=" * 60)


def cmd_run(args):
    """주간 실행 (update mode)"""
    runner = PipelineRunner(mode="update")
    result = runner.run(use_cache=not args.no_cache)
    _print_score(result)


def cmd_score(args):
    """저장된 가중치로 현재 Score"""
    runner = PipelineRunner(mode="score_only")
    result = runner.run(use_cache=True)
    _print_score(result)


def cmd_visualize(args):
    """차트 생성"""
    storage = StorageManager()

    z_data = storage.load_processed("z_matrix")
    if z_data is None:
        print("No processed data found. Run 'optimize' first.")
        return

    opt = storage.load_latest_optimization()
    if opt is None:
        print("No optimization result found. Run 'optimize' first.")
        return

    from config.constants import VARIABLE_ORDER
    import numpy as np

    weights = opt["weights"]
    lag = opt["optimal_lag"]

    # Score 계산
    score_values = []
    for _, row in z_data.iterrows():
        s = sum(weights.get(v, 0.0) * float(row.get(v, 0.0)) for v in VARIABLE_ORDER)
        score_values.append(s)

    import pandas as pd
    z_data["score"] = score_values

    viz_type = args.type

    if viz_type in ("overlay", "all"):
        from src.visualization.overlay_chart import plot_score_vs_btc
        plot_score_vs_btc(
            score=z_data["score"],
            log_btc=z_data["log_btc"],
            dates=z_data["date"],
            lag=lag,
        )
        print(f"  Overlay chart → {CHARTS_DIR / 'score_vs_btc.png'}")

    if viz_type in ("correlation", "all"):
        from src.visualization.correlation_heatmap import (
            plot_cross_correlation,
            plot_variable_correlation_matrix,
        )
        plot_cross_correlation(z_data["score"], z_data["log_btc"])
        print(f"  Cross-correlation → {CHARTS_DIR / 'cross_correlation.png'}")

        var_cols = [c for c in VARIABLE_ORDER if c in z_data.columns]
        if var_cols:
            plot_variable_correlation_matrix(z_data[var_cols])
            print(f"  Variable corr matrix → {CHARTS_DIR / 'variable_correlation.png'}")

    if viz_type in ("walkforward", "all"):
        wf = opt.get("walk_forward")
        if wf and wf.get("windows"):
            from src.visualization.walkforward_plot import plot_walk_forward
            plot_walk_forward(wf)
            print(f"  Walk-forward → {CHARTS_DIR / 'walk_forward.png'}")
        else:
            print("  No walk-forward data available")

    print("\nVisualization complete!")


def cmd_status(args):
    """최신 Score + 모델 상태"""
    storage = StorageManager()
    storage.init_db()

    # 최신 optimization
    opt = storage.load_latest_optimization()

    # Score 히스토리
    history = storage.get_score_history(n=6)

    print("\n" + "=" * 60)
    print("  BTC LIQUIDITY MODEL — STATUS")
    print("=" * 60)

    if opt:
        print(f"  Model Version:  v4.0 (5 variables)")
        print(f"  Last Optimized: {opt.get('date', 'N/A')}")
        print(f"  Correlation:    {opt.get('correlation', 0):.4f}")
        print(f"  Optimal Lag:    {opt.get('optimal_lag', 0)} months")
        wf = opt.get("walk_forward", {})
        print(f"  OOS Mean Corr:  {wf.get('mean_oos_corr', 0):.4f}")
        print(f"  All Positive:   {wf.get('all_positive', False)}")
        print(f"\n  Weights:")
        for var, w in opt.get("weights", {}).items():
            print(f"    {var:15s}: {w:+.1f}")
    else:
        print("  No optimization found. Run: python main.py optimize")

    if history:
        print(f"\n  Recent Scores:")
        for h in history:
            print(f"    {h['date']}  Score={h['score']:+.4f}  "
                  f"Signal={h['signal']}  Corr={h['corr']:.4f}")
    else:
        print("\n  No score history yet.")

    print("=" * 60)


# ═══════════════════════════════════════
# v2.0 Commands
# ═══════════════════════════════════════

def cmd_build_index(args):
    """Stage 1: Build liquidity index (BTC-blind)"""
    from src.pipeline.runner_v2 import PipelineRunnerV2

    storage = StorageManager()
    z_data = storage.load_processed("z_matrix")
    if z_data is None:
        print("No z_matrix found. Run 'python main.py optimize' first to generate data.")
        return

    from config.constants import VARIABLE_ORDER_V2
    var_cols = [c for c in VARIABLE_ORDER_V2 if c in z_data.columns]
    # Fallback to v1 variable names if v2 not available
    if not var_cols:
        from config.constants import VARIABLE_ORDER
        var_cols = [c for c in VARIABLE_ORDER if c in z_data.columns]

    z_matrix = z_data[var_cols].copy()
    z_matrix.index = range(len(z_matrix))

    runner = PipelineRunnerV2(method=args.method, freq=args.freq)
    result = runner.run_stage1(z_matrix)

    print(f"\n[Stage 1] Index built: method={result['method']}")
    print(f"  Observations: {result['n_observations']}")
    if "explained_variance" in result:
        print(f"  Explained var: {result['explained_variance']:.3f}")
    print(f"  Loadings:")
    for var, w in result.get("loadings", {}).items():
        print(f"    {var:15s}: {w:+.3f}")


def cmd_validate(args):
    """Stage 2: Direction validation"""
    from src.pipeline.runner_v2 import PipelineRunnerV2

    storage = StorageManager()
    z_data = storage.load_processed("z_matrix")
    if z_data is None:
        print("No data found. Run 'optimize' then 'build-index' first.")
        return

    if "log_btc" not in z_data.columns:
        print("No log_btc column in z_matrix. Run 'optimize' first.")
        return

    from config.constants import VARIABLE_ORDER_V2, VARIABLE_ORDER
    var_cols = [c for c in VARIABLE_ORDER_V2 if c in z_data.columns]
    if not var_cols:
        var_cols = [c for c in VARIABLE_ORDER if c in z_data.columns]

    z_matrix = z_data[var_cols].copy()
    z_matrix.index = range(len(z_matrix))
    target = z_data["log_btc"].copy()
    target.index = range(len(target))

    runner = PipelineRunnerV2(method=args.method, freq=args.freq)
    stage1 = runner.run_stage1(z_matrix)
    result = runner.run_stage2(stage1["index"], target)

    print(f"\n[Stage 2] Validation complete")
    print(f"  Optimal lag: {result['optimal_lag']} months")
    print(f"  Best CWS:    {result['best_cws']:.3f}")
    print(f"  All r > 0:   {result['all_positive']}")
    print(f"  Granger uni: {result['granger']['unidirectional']}")


def cmd_analyze(args):
    """Stage 3: Robustness analysis"""
    from src.pipeline.runner_v2 import PipelineRunnerV2

    storage = StorageManager()
    z_data = storage.load_processed("z_matrix")
    if z_data is None:
        print("No data found. Run 'optimize' first.")
        return

    from config.constants import VARIABLE_ORDER_V2, VARIABLE_ORDER
    var_cols = [c for c in VARIABLE_ORDER_V2 if c in z_data.columns]
    if not var_cols:
        var_cols = [c for c in VARIABLE_ORDER if c in z_data.columns]

    z_matrix = z_data[var_cols].copy()
    z_matrix.index = range(len(z_matrix))
    target = z_data["log_btc"].copy()
    target.index = range(len(target))

    runner = PipelineRunnerV2(method=args.method, freq=args.freq)
    result = runner.run_stage3(z_matrix, target)

    bootstrap = result.get("bootstrap_loadings", {})
    print(f"\n[Stage 3] Robustness analysis complete")
    print(f"  NL always max: {bootstrap.get('nl_always_max', 'N/A')}")
    print(f"  NL max rate:   {bootstrap.get('nl_max_rate', 0):.1%}")

    cpcv = result.get("cpcv", {})
    if "cws_mean" in cpcv:
        print(f"  CPCV paths:    {cpcv.get('n_paths', 0)}")
        print(f"  CPCV CWS mean: {cpcv['cws_mean']:.3f}")


def cmd_run_v2(args):
    """Full 3-Stage pipeline"""
    from src.pipeline.runner_v2 import PipelineRunnerV2

    storage = StorageManager()
    z_data = storage.load_processed("z_matrix")
    if z_data is None:
        print("No z_matrix found. Run 'python main.py optimize' first.")
        return

    from config.constants import VARIABLE_ORDER_V2, VARIABLE_ORDER
    var_cols = [c for c in VARIABLE_ORDER_V2 if c in z_data.columns]
    if not var_cols:
        var_cols = [c for c in VARIABLE_ORDER if c in z_data.columns]

    z_matrix = z_data[var_cols].copy()
    z_matrix.index = range(len(z_matrix))
    target = z_data["log_btc"].copy()
    target.index = range(len(target))

    runner = PipelineRunnerV2(method=args.method, freq=args.freq)
    runner.run_full(z_matrix, target)


def cmd_compare(args):
    """Compare all index methods"""
    from src.pipeline.runner_v2 import PipelineRunnerV2

    storage = StorageManager()
    z_data = storage.load_processed("z_matrix")
    if z_data is None:
        print("No z_matrix found. Run 'python main.py optimize' first.")
        return

    from config.constants import VARIABLE_ORDER_V2, VARIABLE_ORDER
    var_cols = [c for c in VARIABLE_ORDER_V2 if c in z_data.columns]
    if not var_cols:
        var_cols = [c for c in VARIABLE_ORDER if c in z_data.columns]

    z_matrix = z_data[var_cols].copy()
    z_matrix.index = range(len(z_matrix))
    target = z_data["log_btc"].copy()
    target.index = range(len(target))

    runner = PipelineRunnerV2(freq=args.freq)
    comparison = runner.compare_all_methods(z_matrix, target)

    print("\n[Method Comparison]")
    print(comparison.to_string(index=False))


def _print_score(result: dict):
    """Score 결과 출력"""
    if not result:
        print("No result available.")
        return

    print("\n" + "=" * 60)
    print("  BTC LIQUIDITY MODEL — CURRENT SCORE")
    print("=" * 60)
    print(f"  Date:        {result.get('date', 'N/A')}")
    print(f"  Score:       {result['score']:+.4f}")
    print(f"  Signal:      {result['signal']}")
    print(f"  Lag:         {result.get('lag', 'N/A')} months")
    print(f"  Correlation: {result.get('correlation', 0):.4f}")
    print(f"\n  Variables (z-score):")
    for var, val in result.get("variables", {}).items():
        print(f"    {var:15s}: {val:+.4f}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="BTC Liquidity Prediction Model v2.0.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # v1.0 commands
  python main.py optimize              # Full v1.0 optimization
  python main.py fetch --no-cache      # Force re-fetch all data

  # v2.0 commands
  python main.py build-index --method pca   # Stage 1: PCA index
  python main.py validate --method pca      # Stage 2: Direction check
  python main.py analyze --method pca       # Stage 3: Robustness
  python main.py run --method pca           # Full 3-Stage pipeline
  python main.py compare                    # Compare PCA/ICA/SparsePCA
        """,
    )

    # Global options (v2.0)
    parser.add_argument(
        "--freq", choices=["daily", "weekly", "monthly"],
        default="monthly", help="Time frequency (v2.0)",
    )
    parser.add_argument(
        "--method", choices=["pca", "ica", "dfm", "sparse"],
        default="pca", help="Index building method (v2.0)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # === v1.0 commands ===
    p_fetch = subparsers.add_parser("fetch", help="Fetch all data sources")
    p_fetch.add_argument("--no-cache", action="store_true", help="Force re-fetch")
    p_fetch.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    p_fetch.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")

    p_opt = subparsers.add_parser("optimize", help="[v1.0] Full Grid Search optimization")
    p_opt.add_argument("--no-cache", action="store_true", help="Force re-fetch")
    p_opt.add_argument("--start", type=str, help="Start date")
    p_opt.add_argument("--end", type=str, help="End date")

    p_run_v1 = subparsers.add_parser("score", help="[v1.0] Current score only")

    # === v2.0 commands ===
    subparsers.add_parser("build-index",
        help="[v2.0] Stage 1: Build liquidity index (BTC-blind)")

    subparsers.add_parser("validate",
        help="[v2.0] Stage 2: Direction validation against BTC")

    subparsers.add_parser("analyze",
        help="[v2.0] Stage 3: Robustness analysis")

    subparsers.add_parser("run",
        help="[v2.0] Full 3-Stage pipeline")

    subparsers.add_parser("compare",
        help="[v2.0] Compare all index methods (PCA/ICA/Sparse)")

    # === shared commands ===
    p_viz = subparsers.add_parser("visualize", help="Generate charts")
    p_viz.add_argument(
        "--type",
        choices=["overlay", "correlation", "walkforward",
                 "xcorr", "bootstrap", "comparison", "all"],
        default="all",
        help="Chart type",
    )

    p_status = subparsers.add_parser("status", help="Show model status")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    commands = {
        # v1.0
        "fetch": cmd_fetch,
        "optimize": cmd_optimize,
        "score": cmd_score,
        "visualize": cmd_visualize,
        "status": cmd_status,
        # v2.0
        "build-index": cmd_build_index,
        "validate": cmd_validate,
        "analyze": cmd_analyze,
        "run": cmd_run_v2,
        "compare": cmd_compare,
    }

    try:
        commands[args.command](args)
    except KeyboardInterrupt:
        print("\nInterrupted by user.")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
