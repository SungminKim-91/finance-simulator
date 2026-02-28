"""ICA 기반 독립 인덱스 구성 — PCA 비교용.

ICA: 통계적 독립 성분 분리.
금융 데이터는 fat-tailed (비정규분포) -> ICA가 이론적으로 적합할 수 있음.
"""

import logging
import numpy as np
import pandas as pd
from sklearn.decomposition import FastICA

from config.constants import INDEX_BUILDER

logger = logging.getLogger(__name__)


class ICAIndexBuilder:
    """ICA 기반 유동성 인덱스 구성."""

    def __init__(
        self,
        n_components: int = INDEX_BUILDER["max_components"],
        random_state: int = INDEX_BUILDER["random_state"],
    ):
        self.n_components = n_components
        self.random_state = random_state
        self.ica = FastICA(
            n_components=n_components,
            random_state=random_state,
            max_iter=500,
            tol=1e-4,
        )
        self.is_fitted = False
        self._feature_names: list[str] = []

    def build(self, z_matrix: pd.DataFrame) -> dict:
        """
        Extract independent components from z_matrix.

        IC selection: choose IC most correlated with NL_z (BTC-blind).

        Returns:
            dict with: components, index, selected_ic, mixing_matrix, method
        """
        # Validate BTC-blind
        btc_cols = [c for c in z_matrix.columns
                    if "btc" in c.lower() or "bitcoin" in c.lower()]
        if btc_cols:
            raise ValueError(f"BTC columns found: {btc_cols}")

        numeric_cols = z_matrix.select_dtypes(include=[np.number]).columns.tolist()
        self._feature_names = numeric_cols

        # Limit n_components to number of features
        n_comp = min(self.n_components, len(numeric_cols))
        if n_comp != self.n_components:
            self.ica = FastICA(
                n_components=n_comp,
                random_state=self.random_state,
                max_iter=500,
                tol=1e-4,
            )

        X = z_matrix[numeric_cols].dropna()

        try:
            S = self.ica.fit_transform(X.values)
        except Exception as e:
            logger.error("ICA fitting failed: %s", e)
            raise

        self.is_fitted = True

        components = pd.DataFrame(
            S,
            index=X.index,
            columns=[f"IC_{i}" for i in range(n_comp)],
        )

        # Select liquidity IC: highest |corr| with NL
        nl_col = next((c for c in numeric_cols if "NL" in c.upper()), numeric_cols[0])
        nl_series = X[nl_col]

        selected_ic, selected_idx = self.select_liquidity_ic(
            components, nl_series
        )

        return {
            "components": components,
            "index": selected_ic,
            "selected_ic": selected_idx,
            "mixing_matrix": self.ica.mixing_,
            "n_observations": len(X),
            "method": "ICA",
        }

    def select_liquidity_ic(
        self,
        components: pd.DataFrame,
        nl_series: pd.Series,
    ) -> tuple[pd.Series, int]:
        """
        Select IC most correlated with NL (BTC-blind selection).

        Sign-corrects so the selected IC correlates positively with NL.
        """
        common = components.index.intersection(nl_series.index)
        nl = nl_series.loc[common]

        best_corr = 0.0
        best_idx = 0
        best_series = components.iloc[:, 0]

        for i, col in enumerate(components.columns):
            ic = components.loc[common, col]
            corr = np.corrcoef(ic, nl)[0, 1]
            if abs(corr) > abs(best_corr):
                best_corr = corr
                best_idx = i
                best_series = components[col].copy()

        # Sign correction: positive corr with NL
        if best_corr < 0:
            best_series = -best_series
            logger.info("ICA IC_%d sign flipped (corr with NL was %.3f)",
                        best_idx, best_corr)

        best_series.name = "liquidity_index"
        logger.info("ICA selected IC_%d, |corr| with NL = %.3f",
                     best_idx, abs(best_corr))
        return best_series, best_idx
