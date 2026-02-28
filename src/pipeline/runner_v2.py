"""v2.0 파이프라인 오케스트레이터 — 3-Stage Pipeline.

Stage 1: 독립 인덱스 구성 (BTC-blind)
Stage 2: 방향성 검증 (BTC 참조)
Stage 3: 과적합 방지 (통계 검정)
"""

import logging
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from config.constants import (
    SUCCESS_CRITERIA, VARIABLE_ORDER_V2, XCORR_CONFIG,
)
from config.settings import INDICES_DIR, VALIDATION_DIR

logger = logging.getLogger(__name__)


class PipelineRunnerV2:
    """v2.0 3-Stage Pipeline orchestrator."""

    # Method name -> builder class mapping (lazy import)
    METHOD_MAP = {
        "pca": "src.index_builders.pca_builder.PCAIndexBuilder",
        "ica": "src.index_builders.ica_builder.ICAIndexBuilder",
        "dfm": "src.index_builders.dfm_builder.DFMIndexBuilder",
        "sparse": "src.index_builders.sparse_pca_builder.SparsePCAIndexBuilder",
    }

    def __init__(
        self,
        method: str = "pca",
        freq: str = "monthly",
    ):
        self.method = method
        self.freq = freq

    def _get_builder_class(self, method: str):
        """Lazy import of builder class."""
        if method == "pca":
            from src.index_builders.pca_builder import PCAIndexBuilder
            return PCAIndexBuilder
        elif method == "ica":
            from src.index_builders.ica_builder import ICAIndexBuilder
            return ICAIndexBuilder
        elif method == "dfm":
            from src.index_builders.dfm_builder import DFMIndexBuilder
            return DFMIndexBuilder
        elif method == "sparse":
            from src.index_builders.sparse_pca_builder import SparsePCAIndexBuilder
            return SparsePCAIndexBuilder
        else:
            raise ValueError(f"Unknown method: {method}")

    def run_stage1(
        self,
        z_matrix: pd.DataFrame,
        method: str | None = None,
        daily_matrix: pd.DataFrame | None = None,
    ) -> dict:
        """
        Stage 1: Build liquidity index (BTC-blind).

        Args:
            z_matrix: z-scored variable matrix (no BTC columns)
            method: override self.method if provided
            daily_matrix: daily frequency matrix for DFM (optional)

        Returns:
            dict with index, loadings, method info
        """
        method = method or self.method
        logger.info("=== STAGE 1: Independent Index Construction (%s) ===",
                     method.upper())

        # Fallback chain: method → PCA on failure
        fallback_used = False
        original_method = method

        try:
            result = self._build_index(z_matrix, method, daily_matrix)
        except Exception as e:
            if method in ("ica", "sparse", "dfm"):
                logger.warning(
                    "%s failed (%s), falling back to PCA", method.upper(), e
                )
                result = self._build_index(z_matrix, "pca")
                fallback_used = True
                method = "pca"
            else:
                raise

        # Sign correction: ensure positive correlation with NL
        nl_col = next(
            (c for c in z_matrix.columns if "NL" in c.upper()),
            z_matrix.columns[0],
        )
        BuilderClass = self._get_builder_class(method)
        builder = BuilderClass()
        result["index"] = builder.sign_correction(
            result["index"],
            z_matrix[nl_col].dropna(),
        ) if hasattr(builder, "sign_correction") else result["index"]

        if fallback_used:
            result["fallback_from"] = original_method
            result["fallback_reason"] = "builder failure"

        # Save index
        self._save_result(INDICES_DIR, f"index_{method}", result)

        logger.info(
            "Stage 1 complete: method=%s, n_obs=%d%s",
            method, result.get("n_observations", 0),
            f" (fallback from {original_method})" if fallback_used else "",
        )
        return result

    def _build_index(
        self,
        z_matrix: pd.DataFrame,
        method: str,
        daily_matrix: pd.DataFrame | None = None,
    ) -> dict:
        """Build index with the specified method."""
        BuilderClass = self._get_builder_class(method)
        builder = BuilderClass()

        if method == "dfm":
            if daily_matrix is not None:
                result = builder.build(daily_matrix)
            else:
                # Attempt DFM with monthly z_matrix (limited but functional)
                logger.info("DFM: no daily_matrix provided, using monthly z_matrix")
                result = builder.build(z_matrix)
        else:
            result = builder.build(z_matrix)

        return result

    def run_stage2(
        self,
        index: pd.Series,
        target: pd.Series,
        max_lag: int = XCORR_CONFIG["max_lag"],
    ) -> dict:
        """
        Stage 2: Direction validation against BTC.

        Args:
            index: liquidity index from Stage 1
            target: log10(BTC)

        Returns:
            dict with xcorr_profile, cws, granger, wavelet results
        """
        logger.info("=== STAGE 2: Direction Validation ===")

        from src.validators.waveform_metrics import WaveformMetrics
        from src.validators.composite_score import CompositeWaveformScore
        from src.validators.granger_test import GrangerCausalityTest

        metrics = WaveformMetrics()
        scorer = CompositeWaveformScore()
        granger = GrangerCausalityTest()

        # Cross-correlation profile
        profile = metrics.cross_correlation_profile(index, target, max_lag)
        all_positive = bool((profile["pearson_r"] > 0).all())

        # Composite Waveform Score
        cws_result = scorer.optimal_lag(index, target, max_lag)

        # Granger causality
        granger_result = granger.test_bidirectional(index, target)

        # Wavelet coherence (optional)
        wavelet_result = {}
        try:
            from src.validators.wavelet_coherence import WaveletCoherenceAnalyzer
            wavelet = WaveletCoherenceAnalyzer()
            wavelet_result = wavelet.analyze(index, target)
        except Exception as e:
            logger.info("Wavelet analysis skipped: %s", e)
            wavelet_result = {"available": False, "error": str(e)}

        result = {
            "xcorr_profile": profile.to_dict("records"),
            "all_positive": all_positive,
            "optimal_lag": cws_result["optimal_lag"],
            "best_cws": cws_result["best_cws"],
            "cws_profile": cws_result["profile"].to_dict("records"),
            "granger": {
                "forward_significant": granger_result["forward"].get(
                    "significant", False),
                "forward_p": granger_result["forward"].get(
                    "best_p_value", 1.0),
                "reverse_significant": granger_result["reverse"].get(
                    "significant", False),
                "reverse_p": granger_result["reverse"].get(
                    "best_p_value", 1.0),
                "unidirectional": granger_result.get("unidirectional", False),
            },
            "wavelet": {
                "available": wavelet_result.get("available", False),
                "dominant_period": wavelet_result.get("dominant_period"),
                "mean_phase_lag": wavelet_result.get("mean_phase_lag"),
            },
        }

        # Save
        self._save_result(VALIDATION_DIR, "stage2_validation", result)

        logger.info(
            "Stage 2 complete: lag=%d, cws=%.3f, all_r>0=%s, "
            "granger_uni=%s",
            result["optimal_lag"], result["best_cws"],
            result["all_positive"],
            result["granger"]["unidirectional"],
        )
        return result

    def run_stage3(
        self,
        z_matrix: pd.DataFrame,
        target: pd.Series,
        method: str | None = None,
    ) -> dict:
        """
        Stage 3: Robustness checks.

        Returns:
            dict with bootstrap, cpcv, deflated test results
        """
        method = method or self.method
        logger.info("=== STAGE 3: Robustness Analysis ===")

        BuilderClass = self._get_builder_class(method)

        from src.robustness.bootstrap_analysis import BootstrapAnalyzer
        from src.validators.composite_score import CompositeWaveformScore

        bootstrap = BootstrapAnalyzer()
        scorer = CompositeWaveformScore()

        # Bootstrap loading stability
        logger.info("Running bootstrap loading analysis...")
        loading_result = bootstrap.loading_stability(z_matrix, BuilderClass)

        # Bootstrap lag distribution
        logger.info("Running bootstrap lag distribution...")
        lag_result = bootstrap.lag_distribution(
            z_matrix, target, BuilderClass, scorer
        )

        # CPCV (if enough data)
        cpcv_result = {}
        n_obs = len(z_matrix.dropna())
        if n_obs >= 60:
            try:
                from src.robustness.cpcv import CPCVValidator
                cpcv = CPCVValidator()
                cpcv_result = cpcv.validate(
                    z_matrix, target, BuilderClass, scorer
                )
            except Exception as e:
                logger.warning("CPCV failed: %s", e)
                cpcv_result = {"error": str(e)}
        else:
            cpcv_result = {"error": f"Insufficient data ({n_obs} < 60)"}

        result = {
            "bootstrap_loadings": {
                k: v for k, v in loading_result.items()
                if k != "samples"
            },
            "bootstrap_lags": {
                k: v for k, v in lag_result.items()
                if k != "distribution"
            },
            "cpcv": cpcv_result,
        }

        # Save
        self._save_result(VALIDATION_DIR, "stage3_robustness", result)

        logger.info("Stage 3 complete")
        return result

    def run_full(
        self,
        z_matrix: pd.DataFrame,
        target: pd.Series,
    ) -> dict:
        """
        Run complete 3-Stage pipeline.

        Args:
            z_matrix: z-scored variable matrix (no BTC)
            target: log10(BTC)

        Returns:
            dict with stage1, stage2, stage3 results + success check
        """
        logger.info("=" * 60)
        logger.info("  v2.0 FULL PIPELINE START (%s, %s)",
                     self.method, self.freq)
        logger.info("=" * 60)

        # Stage 1
        stage1 = self.run_stage1(z_matrix)

        # Stage 2
        stage2 = self.run_stage2(stage1["index"], target)

        # Stage 3
        stage3 = self.run_stage3(z_matrix, target)

        # Success criteria check
        success = self._check_success_criteria(stage2, stage3)

        result = {
            "stage1": {
                "method": stage1["method"],
                "loadings": stage1["loadings"],
                "explained_variance": stage1.get("explained_variance"),
            },
            "stage2": stage2,
            "stage3": stage3,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        }

        # Print summary
        self._print_summary(result)

        return result

    def compare_all_methods(
        self,
        z_matrix: pd.DataFrame,
        target: pd.Series,
        daily_matrix: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Compare PCA, ICA, SparsePCA (+ DFM if daily_matrix provided) by CWS."""
        from src.validators.composite_score import CompositeWaveformScore
        scorer = CompositeWaveformScore()

        methods = ["pca", "ica", "sparse"]
        if daily_matrix is not None:
            methods.append("dfm")

        indices = {}
        for method in methods:
            try:
                BuilderClass = self._get_builder_class(method)
                builder = BuilderClass()

                if method == "dfm" and daily_matrix is not None:
                    result = builder.build(daily_matrix)
                else:
                    result = builder.build(z_matrix)

                idx = result["index"]

                # Sign correction
                nl_col = next(
                    (c for c in z_matrix.columns if "NL" in c.upper()),
                    z_matrix.columns[0],
                )
                if hasattr(builder, "sign_correction"):
                    idx = builder.sign_correction(idx, z_matrix[nl_col].dropna())

                indices[method.upper()] = idx
            except Exception as e:
                logger.warning("Method %s failed: %s", method, e)

        if not indices:
            return pd.DataFrame()

        return scorer.compare_methods(indices, target)

    def _check_success_criteria(
        self,
        stage2: dict,
        stage3: dict,
    ) -> dict:
        """Check all success criteria."""
        criteria = SUCCESS_CRITERIA

        # Extract values
        profile_data = stage2.get("xcorr_profile", [])
        if profile_data:
            profile = pd.DataFrame(profile_data)
            peak_idx = profile["pearson_r"].idxmax()
            mda_at_peak = profile.loc[peak_idx, "mda"]
        else:
            mda_at_peak = 0.0

        bootstrap = stage3.get("bootstrap_loadings", {})
        cpcv = stage3.get("cpcv", {})

        checks = {
            "min_mda": {
                "target": criteria["min_mda"],
                "actual": mda_at_peak,
                "pass": mda_at_peak >= criteria["min_mda"],
            },
            "all_lag_positive": {
                "target": True,
                "actual": stage2.get("all_positive", False),
                "pass": stage2.get("all_positive", False),
            },
            "bootstrap_ci": {
                "target": True,
                "actual": bootstrap.get("nl_always_max", False),
                "pass": bootstrap.get("nl_always_max", False),
            },
            "granger": {
                "target": criteria["granger_p_value"],
                "actual": stage2.get("granger", {}).get("forward_p", 1.0),
                "pass": stage2.get("granger", {}).get(
                    "forward_p", 1.0) < criteria["granger_p_value"],
            },
        }

        if cpcv and "cws_mean" in cpcv:
            checks["cpcv_mean"] = {
                "target": criteria["min_cpcv_mean"],
                "actual": cpcv["cws_mean"],
                "pass": cpcv["cws_mean"] >= criteria["min_cpcv_mean"],
            }

        checks["overall"] = all(v["pass"] for v in checks.values()
                                if isinstance(v, dict) and "pass" in v)
        return checks

    def _print_summary(self, result: dict):
        """Print pipeline summary to console."""
        s1 = result["stage1"]
        s2 = result["stage2"]
        success = result["success"]

        print("\n" + "=" * 60)
        print("  BTC LIQUIDITY v2.0 — PIPELINE RESULTS")
        print("=" * 60)
        print(f"  Method:        {s1['method']}")
        print(f"  Optimal Lag:   {s2['optimal_lag']} months")
        print(f"  Best CWS:      {s2['best_cws']:.3f}")
        print(f"  All r > 0:     {s2['all_positive']}")
        print(f"  Granger (uni): {s2['granger']['unidirectional']}")

        print(f"\n  Loadings:")
        for var, w in s1.get("loadings", {}).items():
            print(f"    {var:15s}: {w:+.3f}")

        print(f"\n  Success Criteria:")
        for key, val in success.items():
            if isinstance(val, dict):
                status = "PASS" if val["pass"] else "FAIL"
                print(f"    {key:20s}: {status} "
                      f"(target={val['target']}, actual={val['actual']})")
            elif key == "overall":
                print(f"\n  OVERALL: {'PASS' if val else 'FAIL'}")

        print("=" * 60)

    @staticmethod
    def _save_result(directory: Path, name: str, result: dict) -> str:
        """Save result as JSON."""
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        date_str = datetime.now().strftime("%Y-%m-%d")
        path = directory / f"{name}_{date_str}.json"

        # Clean non-serializable objects
        clean = {}
        for k, v in result.items():
            if isinstance(v, pd.DataFrame):
                clean[k] = v.to_dict("records")
            elif isinstance(v, pd.Series):
                clean[k] = v.tolist()
            elif isinstance(v, np.ndarray):
                clean[k] = v.tolist()
            elif isinstance(v, (np.integer, np.floating)):
                clean[k] = v.item()
            else:
                clean[k] = v

        with open(path, "w", encoding="utf-8") as f:
            json.dump(clean, f, indent=2, default=str, ensure_ascii=False)

        logger.info("Result saved: %s", path)
        return str(path)
