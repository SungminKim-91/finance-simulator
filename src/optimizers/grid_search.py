"""5변수 파형 매칭 Grid Search"""
import itertools
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
from tqdm import tqdm

from config.constants import GRID_SEARCH, VARIABLE_ORDER
from src.utils.logger import setup_logger

logger = setup_logger("grid_search")


class GridSearchOptimizer:
    """
    Grid Search: 5변수 가중치 + lag(0-9m) 동시 탐색
    목적함수: maximize corr(score(t), log₁₀(BTC)(t+k))
    """

    def __init__(self, search_config: dict | None = None):
        self.config = search_config or GRID_SEARCH

    def optimize(
        self,
        z_matrix: pd.DataFrame,
        log_btc: pd.Series,
        variable_names: list[str] | None = None,
    ) -> dict:
        """
        Grid Search 수행.

        Args:
            z_matrix: DataFrame — 각 열이 z-score 변환된 변수
            log_btc: log₁₀(BTC) 월간 시리즈 (z_matrix와 동일 인덱스)
            variable_names: 변수명 리스트 (default: VARIABLE_ORDER)

        Returns: {
            "weights": {"NL_level": 1.5, ...},
            "optimal_lag": 5,
            "correlation": 0.45,
            "top_50": [...],
        }
        """
        var_names = variable_names or VARIABLE_ORDER

        # NaN이 있는 행 처리 (CME basis 등)
        # 각 조합마다 유효 데이터만 사용하므로 여기서는 전체 보존
        Z = z_matrix[var_names].values
        target = log_btc.values

        # 가중치 그리드 생성
        grid = self._generate_grid(var_names)
        lag_range = range(
            int(self.config["lag_months"]["min"]),
            int(self.config["lag_months"]["max"]) + 1,
        )

        logger.info(f"Grid Search: {len(grid)} weight combos × "
                    f"{len(lag_range)} lags = {len(grid) * len(lag_range)} evaluations")

        results = []

        for weights_dict in tqdm(grid, desc="Grid Search", disable=False):
            w = np.array([weights_dict.get(v, 0.0) for v in var_names])

            # 최소 1개 변수 활성 체크
            if np.all(w == 0):
                continue

            # Score 계산
            score = self._compute_score(Z, w)

            # 각 lag에서 corr 계산
            best_corr, best_lag = self._evaluate(score, target, lag_range)

            if not np.isnan(best_corr):
                results.append({
                    "weights": weights_dict.copy(),
                    "lag": best_lag,
                    "correlation": best_corr,
                })

        if not results:
            logger.error("Grid Search produced no valid results")
            return {"weights": {}, "optimal_lag": 0, "correlation": 0.0, "top_50": []}

        # 상관계수 기준 정렬
        results.sort(key=lambda x: x["correlation"], reverse=True)

        best = results[0]
        top_50 = results[:50]

        # 안정성 분석: top 50의 lag 분포
        lag_dist = {}
        for r in top_50:
            lag = r["lag"]
            lag_dist[lag] = lag_dist.get(lag, 0) + 1

        logger.info(
            f"Best: corr={best['correlation']:.4f}, "
            f"lag={best['lag']}m, weights={best['weights']}"
        )
        logger.info(f"Top 50 lag distribution: {lag_dist}")

        return {
            "weights": best["weights"],
            "optimal_lag": best["lag"],
            "correlation": best["correlation"],
            "top_50": top_50,
            "lag_distribution": lag_dist,
            "total_evaluated": len(results),
        }

    def _generate_grid(self, var_names: list[str]) -> list[dict]:
        """탐색 범위에서 모든 가중치 조합 생성"""
        ranges = {}
        for var in var_names:
            if var in self.config:
                cfg = self.config[var]
                values = np.arange(cfg["min"], cfg["max"] + cfg["step"] / 2, cfg["step"])
                ranges[var] = [round(float(v), 2) for v in values]
            else:
                ranges[var] = [0.0]

        # 모든 조합 생성
        keys = list(ranges.keys())
        value_lists = [ranges[k] for k in keys]

        grid = []
        for combo in itertools.product(*value_lists):
            grid.append(dict(zip(keys, combo)))

        return grid

    def _compute_score(
        self,
        Z: np.ndarray,
        weights: np.ndarray,
    ) -> np.ndarray:
        """score = Z @ w (NaN 행은 NaN 유지)"""
        # NaN이 있는 행 처리
        score = np.zeros(len(Z))
        for i in range(len(Z)):
            row = Z[i]
            if np.any(np.isnan(row)):
                # NaN인 변수는 가중치 0 처리
                valid_mask = ~np.isnan(row)
                score[i] = np.sum(row[valid_mask] * weights[valid_mask])
            else:
                score[i] = np.dot(row, weights)
        return score

    def _evaluate(
        self,
        score: np.ndarray,
        target: np.ndarray,
        lag_range: range,
    ) -> tuple[float, int]:
        """
        모든 lag에서 corr 계산 → (best_corr, best_lag) 반환.
        """
        best_corr = -np.inf
        best_lag = 0

        for k in lag_range:
            if k > 0:
                s = score[:-k]
                t = target[k:]
            else:
                s = score
                t = target

            # NaN 제거
            valid = ~np.isnan(s) & ~np.isnan(t)
            if valid.sum() < 20:  # 최소 데이터 포인트
                continue

            try:
                r, _ = pearsonr(s[valid], t[valid])
                if r > best_corr:
                    best_corr = r
                    best_lag = k
            except Exception:
                continue

        if best_corr == -np.inf:
            return np.nan, 0

        return float(best_corr), best_lag
