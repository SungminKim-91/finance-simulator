"""Combinatorial Purged Cross-Validation (CPCV).

de Prado (2018) — 45-path validation.
v1.0 Walk-Forward (9 paths) 대비 5x more robust.
"""

import logging
from itertools import combinations

import numpy as np
import pandas as pd

from config.constants import CPCV_CONFIG

logger = logging.getLogger(__name__)


class CPCVValidator:
    """CPCV: Combinatorial Purged Cross-Validation."""

    def __init__(
        self,
        n_folds: int = CPCV_CONFIG["n_folds"],
        n_test_folds: int = CPCV_CONFIG["n_test_folds"],
        purge_threshold: int = CPCV_CONFIG["purge_threshold"],
        embargo: int = CPCV_CONFIG["embargo"],
    ):
        self.n_folds = n_folds
        self.n_test_folds = n_test_folds
        self.purge = purge_threshold
        self.embargo = embargo

    def _generate_splits(
        self,
        n_samples: int,
    ) -> list[tuple[np.ndarray, np.ndarray]]:
        """
        Generate C(n_folds, n_test_folds) splits with purge + embargo.

        Returns:
            list of (train_indices, test_indices)
        """
        fold_size = n_samples // self.n_folds
        folds = []

        for i in range(self.n_folds):
            start = i * fold_size
            end = start + fold_size if i < self.n_folds - 1 else n_samples
            folds.append(np.arange(start, end))

        splits = []
        for test_combo in combinations(range(self.n_folds), self.n_test_folds):
            test_idx = np.concatenate([folds[i] for i in test_combo])
            test_start = test_idx.min()
            test_end = test_idx.max()

            # All indices
            all_idx = np.arange(n_samples)

            # Purge: remove purge_threshold before test start
            purge_start = max(0, test_start - self.purge)
            # Embargo: remove embargo after test end
            embargo_end = min(n_samples, test_end + self.embargo + 1)

            # Train = all - test - purge zone - embargo zone
            purge_embargo_zone = np.arange(purge_start, embargo_end)
            train_idx = np.setdiff1d(all_idx, purge_embargo_zone)

            if len(train_idx) < 20:
                continue

            splits.append((train_idx, test_idx))

        logger.info(
            "CPCV: %d splits from C(%d,%d), purge=%d, embargo=%d",
            len(splits), self.n_folds, self.n_test_folds,
            self.purge, self.embargo,
        )
        return splits

    def validate(
        self,
        z_matrix: pd.DataFrame,
        target: pd.Series,
        builder_class: type,
        scorer,
    ) -> dict:
        """
        Run CPCV validation.

        Args:
            z_matrix: z-scored variable matrix
            target: log10(BTC)
            builder_class: PCAIndexBuilder or similar
            scorer: CompositeWaveformScore instance

        Returns:
            dict with n_paths, cws_mean, cws_std, cws_all,
                  mda_mean, all_positive_rate, worst/best_path
        """
        numeric_cols = z_matrix.select_dtypes(
            include=[np.number]
        ).columns.tolist()
        X = z_matrix[numeric_cols].dropna()

        # Align target
        common = X.index.intersection(target.index)
        X = X.loc[common]
        tgt = target.loc[common]

        n = len(X)
        splits = self._generate_splits(n)

        if not splits:
            return {"error": "No valid splits generated"}

        results = []
        for train_idx, test_idx in splits:
            try:
                # Build index on train set
                z_train = X.iloc[train_idx].copy()
                z_train.columns = numeric_cols
                builder = builder_class()
                build_result = builder.build(z_train)

                # Transform test set
                z_test = X.iloc[test_idx].copy()
                z_test.columns = numeric_cols
                index_oos = builder.transform(z_test)

                # Sign correction using NL
                nl_col = next(
                    (c for c in numeric_cols if "NL" in c.upper()),
                    numeric_cols[0],
                )
                nl_train = z_train[nl_col]
                train_index = build_result["index"]
                corr_nl = np.corrcoef(
                    train_index.values[:len(nl_train)],
                    nl_train.values[:len(train_index)],
                )[0, 1]
                if corr_nl < 0:
                    index_oos = -index_oos

                # Score OOS
                target_oos = tgt.iloc[test_idx]
                cws_result = scorer.optimal_lag(index_oos, target_oos,
                                                max_lag=12)

                # Also get pearson r at optimal lag
                from .._compat import pearson_at_lag
                r = pearson_at_lag(index_oos, target_oos,
                                   cws_result["optimal_lag"])

                results.append({
                    "cws": cws_result["best_cws"],
                    "optimal_lag": cws_result["optimal_lag"],
                    "mda": cws_result["profile"].iloc[
                        cws_result["optimal_lag"]
                    ]["mda"] if "mda" in cws_result["profile"].columns else None,
                    "pearson_r": r,
                })

            except Exception as e:
                logger.debug("CPCV split failed: %s", e)
                continue

        if len(results) < 5:
            return {"error": f"Only {len(results)} valid paths"}

        df = pd.DataFrame(results)

        cws_values = df["cws"].values
        r_values = df["pearson_r"].dropna().values

        return {
            "n_paths": len(results),
            "cws_mean": float(np.mean(cws_values)),
            "cws_std": float(np.std(cws_values)),
            "cws_all": cws_values.tolist(),
            "mda_mean": float(df["mda"].dropna().mean())
            if df["mda"].dropna().any() else None,
            "all_positive_rate": float(np.mean(r_values > 0))
            if len(r_values) > 0 else None,
            "pearson_r_mean": float(np.mean(r_values))
            if len(r_values) > 0 else None,
            "worst_path": results[int(np.argmin(cws_values))],
            "best_path": results[int(np.argmax(cws_values))],
        }
