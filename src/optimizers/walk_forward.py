"""Walk-Forward 검증"""
import numpy as np
import pandas as pd
from scipy.stats import pearsonr

from config.constants import WALK_FORWARD, VARIABLE_ORDER
from src.calculators.detrend import zscore, compute_zscore_params
from src.utils.logger import setup_logger

logger = setup_logger("walk_forward")


class WalkForwardValidator:
    """
    Walk-Forward OOS 검증.
    expanding window (60m train) + rolling test (6m).
    """

    def __init__(
        self,
        initial_train: int | None = None,
        test_window: int | None = None,
        expanding: bool = True,
    ):
        cfg = WALK_FORWARD
        self.initial_train = initial_train or cfg["initial_train"]
        self.test_window = test_window or cfg["test_window"]
        self.expanding = expanding

    def validate(
        self,
        raw_matrix: pd.DataFrame,
        log_btc: pd.Series,
        weights: dict,
        lag: int,
        variable_names: list[str] | None = None,
    ) -> dict:
        """
        Walk-Forward OOS 검증.

        Args:
            raw_matrix: detrended (z-score 전) 변수 DataFrame
            log_btc: log₁₀(BTC) 월간
            weights: 최적 가중치
            lag: 최적 lag
            variable_names: 변수명 리스트

        Returns: {
            "n_windows": 8,
            "oos_correlations": [0.35, 0.42, ...],
            "mean_oos_corr": 0.38,
            "std_oos_corr": 0.05,
            "all_positive": True,
            "windows": [{"train_range": ..., "test_range": ..., "corr": ...}],
        }
        """
        var_names = variable_names or VARIABLE_ORDER
        total = len(raw_matrix)

        windows = self._split_windows(total)

        if len(windows) < 3:
            logger.warning(f"Only {len(windows)} windows available (min 3 recommended)")

        w_array = np.array([weights.get(v, 0.0) for v in var_names])
        oos_results = []

        for i, (train_idx, test_idx) in enumerate(windows):
            train_data = raw_matrix.iloc[train_idx]
            test_data = raw_matrix.iloc[test_idx]

            # Train에서 z-score 파라미터 계산
            z_params = {}
            for var in var_names:
                if var in train_data.columns:
                    z_params[var] = compute_zscore_params(train_data[var])

            # Test 데이터를 train 파라미터로 z-score 변환
            Z_test = np.zeros((len(test_data), len(var_names)))
            for j, var in enumerate(var_names):
                if var in test_data.columns and var in z_params:
                    p = z_params[var]
                    Z_test[:, j] = zscore(
                        test_data[var], mean=p["mean"], std=p["std"]
                    ).values
                else:
                    Z_test[:, j] = 0.0

            # Score
            score = Z_test @ w_array

            # Target (lag 적용)
            test_start = test_idx.start if hasattr(test_idx, 'start') else test_idx[0]
            test_end = test_idx.stop if hasattr(test_idx, 'stop') else test_idx[-1] + 1

            target_start = test_start + lag
            target_end = test_end + lag

            if target_end > total:
                # 데이터 부족 시 가능한 만큼만
                target_end = total
                usable = target_end - target_start
                if usable < 3:
                    continue
                score = score[:usable]

            target_slice = log_btc.iloc[target_start:target_end].values

            if len(score) != len(target_slice):
                min_len = min(len(score), len(target_slice))
                score = score[:min_len]
                target_slice = target_slice[:min_len]

            # NaN 제거
            valid = ~np.isnan(score) & ~np.isnan(target_slice)
            if valid.sum() < 3:
                continue

            try:
                r, p_val = pearsonr(score[valid], target_slice[valid])
            except Exception:
                continue

            window_result = {
                "window": i + 1,
                "train_range": f"{train_idx.start}-{train_idx.stop - 1}",
                "test_range": f"{test_start}-{test_end - 1}",
                "n_test": int(valid.sum()),
                "correlation": round(float(r), 4),
                "p_value": round(float(p_val), 4),
            }
            oos_results.append(window_result)

        # 집계
        if not oos_results:
            logger.warning("Walk-Forward produced no valid results")
            return {
                "n_windows": 0,
                "oos_correlations": [],
                "mean_oos_corr": 0.0,
                "std_oos_corr": 0.0,
                "all_positive": False,
                "windows": [],
            }

        correlations = [r["correlation"] for r in oos_results]

        result = {
            "n_windows": len(oos_results),
            "oos_correlations": correlations,
            "mean_oos_corr": round(float(np.mean(correlations)), 4),
            "std_oos_corr": round(float(np.std(correlations)), 4),
            "all_positive": all(c > 0 for c in correlations),
            "windows": oos_results,
        }

        logger.info(
            f"Walk-Forward: {result['n_windows']} windows, "
            f"mean OOS corr={result['mean_oos_corr']:.4f} ± {result['std_oos_corr']:.4f}, "
            f"all positive={result['all_positive']}"
        )

        return result

    def _split_windows(self, total_months: int) -> list[tuple[range, range]]:
        """(train_indices, test_indices) 리스트 생성"""
        windows = []
        i = 0

        while True:
            if self.expanding:
                train_start = 0
            else:
                train_start = i * self.test_window

            train_end = self.initial_train + i * self.test_window
            test_start = train_end
            test_end = test_start + self.test_window

            if test_end > total_months:
                break

            windows.append((
                range(train_start, train_end),
                range(test_start, test_end),
            ))
            i += 1

        return windows
