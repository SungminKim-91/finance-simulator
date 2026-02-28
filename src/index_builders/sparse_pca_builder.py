"""Sparse PCA — 자동 변수 선택.

L1 정규화로 중요하지 않은 변수의 loading = 0.
v1.0에서 GM2=0, CME=0이 나온 결과를 비지도로 검증.
"""

import logging
import numpy as np
import pandas as pd
from sklearn.decomposition import SparsePCA

from config.constants import INDEX_BUILDER

logger = logging.getLogger(__name__)


class SparsePCAIndexBuilder:
    """Sparse PCA 기반 유동성 인덱스 (자동 변수 선택)."""

    def __init__(
        self,
        n_components: int = INDEX_BUILDER["n_components"],
        alpha: float = INDEX_BUILDER["sparse_alpha"],
        random_state: int = INDEX_BUILDER["random_state"],
    ):
        self.alpha = alpha
        self.random_state = random_state
        self.spca = SparsePCA(
            n_components=n_components,
            alpha=alpha,
            random_state=random_state,
            max_iter=500,
        )
        self.is_fitted = False
        self._feature_names: list[str] = []

    def build(self, z_matrix: pd.DataFrame) -> dict:
        """
        Sparse PCA index construction.

        Returns:
            dict with: index, loadings, nonzero_variables, sparsity, method
        """
        btc_cols = [c for c in z_matrix.columns
                    if "btc" in c.lower() or "bitcoin" in c.lower()]
        if btc_cols:
            raise ValueError(f"BTC columns found: {btc_cols}")

        numeric_cols = z_matrix.select_dtypes(include=[np.number]).columns.tolist()
        self._feature_names = numeric_cols

        X = z_matrix[numeric_cols].dropna()
        transformed = self.spca.fit_transform(X.values)
        self.is_fitted = True

        index = pd.Series(
            transformed[:, 0], index=X.index, name="liquidity_index"
        )

        # Loadings
        loadings = dict(zip(numeric_cols, self.spca.components_[0]))
        nonzero = [k for k, v in loadings.items() if abs(v) > 1e-10]
        sparsity = 1.0 - len(nonzero) / len(numeric_cols)

        logger.info(
            "SparsePCA (alpha=%.1f): nonzero=%s, sparsity=%.1f%%",
            self.alpha, nonzero, sparsity * 100,
        )

        return {
            "index": index,
            "loadings": loadings,
            "nonzero_variables": nonzero,
            "sparsity": float(sparsity),
            "n_observations": len(X),
            "method": "SparsePCA",
        }

    def alpha_sensitivity(
        self,
        z_matrix: pd.DataFrame,
        alphas: list[float] | None = None,
    ) -> pd.DataFrame:
        """
        Analyze loading changes across different alpha values.

        Returns:
            DataFrame[alpha, var1, var2, ..., n_nonzero]
        """
        if alphas is None:
            alphas = [0.1, 0.5, 1.0, 2.0, 5.0]

        numeric_cols = z_matrix.select_dtypes(include=[np.number]).columns.tolist()
        X = z_matrix[numeric_cols].dropna()

        rows = []
        for a in alphas:
            spca = SparsePCA(
                n_components=1,
                alpha=a,
                random_state=self.random_state,
                max_iter=500,
            )
            try:
                spca.fit(X.values)
                loadings = dict(zip(numeric_cols, spca.components_[0]))
                loadings["alpha"] = a
                loadings["n_nonzero"] = sum(
                    1 for v in spca.components_[0] if abs(v) > 1e-10
                )
                rows.append(loadings)
            except Exception as e:
                logger.warning("SparsePCA alpha=%.1f failed: %s", a, e)

        return pd.DataFrame(rows)
