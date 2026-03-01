"""PCA 기반 독립 인덱스 구성 — Phase 1c에서 검증됨.

핵심: BTC 데이터를 절대 입력받지 않음.
Phase 1c에서 BTC-blind PC1이 lag=7에서 r=0.318, 모든 lag 양의 상관.
"""

import logging
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA

from config.constants import INDEX_BUILDER

logger = logging.getLogger(__name__)


class PCAIndexBuilder:
    """PCA 기반 유동성 인덱스 구성 (v2.0 primary method)."""

    def __init__(
        self,
        n_components: int = INDEX_BUILDER["n_components"],
        random_state: int = INDEX_BUILDER["random_state"],
    ):
        self.n_components = n_components
        self.random_state = random_state
        self.pca = PCA(n_components=n_components, random_state=random_state)
        self.is_fitted = False
        self._feature_names: list[str] = []

    def build(self, z_matrix: pd.DataFrame) -> dict:
        """
        z_matrix에서 PC1 인덱스 구성.

        Args:
            z_matrix: DataFrame with columns like [NL_z, GM2r_z, SOFR_z, HY_z, CME_z].
                      All variables must be detrended + z-scored.
                      NaN rows should be removed beforehand.

        Returns:
            dict with keys: index, loadings, explained_variance,
                           n_observations, method
        """
        # Validate: no BTC-related columns
        btc_cols = [c for c in z_matrix.columns
                    if "btc" in c.lower() or "bitcoin" in c.lower()]
        if btc_cols:
            raise ValueError(
                f"BTC-related columns found in z_matrix: {btc_cols}. "
                "Stage 1 must be BTC-blind."
            )

        # Store feature names (exclude date if present)
        numeric_cols = z_matrix.select_dtypes(include=[np.number]).columns.tolist()
        self._feature_names = numeric_cols

        # Fit PCA
        X = z_matrix[numeric_cols].dropna()
        self.pca.fit(X.values)
        self.is_fitted = True

        # Extract PC1
        pc1 = self.pca.transform(X.values)[:, 0]

        # Build index as Series
        index = pd.Series(pc1, index=X.index, name="liquidity_index")

        # Loadings
        loadings = dict(zip(numeric_cols, self.pca.components_[0]))
        explained_var = float(self.pca.explained_variance_ratio_[0])

        logger.info(
            "PCA built: explained_var=%.3f, loadings=%s",
            explained_var,
            {k: f"{v:.3f}" for k, v in loadings.items()},
        )

        return {
            "index": index,
            "loadings": loadings,
            "explained_variance": explained_var,
            "n_observations": len(X),
            "method": "PCA",
        }

    def transform(self, z_matrix: pd.DataFrame) -> pd.Series:
        """Transform new data using fitted PCA (for weekly updates)."""
        if not self.is_fitted:
            raise ValueError("PCA not fitted. Call build() first.")

        X = z_matrix[self._feature_names].dropna()
        pc1 = self.pca.transform(X.values)[:, 0]
        return pd.Series(pc1, index=X.index, name="liquidity_index")

    def get_loadings_dict(self) -> dict[str, float]:
        """Return current fitted PCA loadings as {variable: loading}."""
        if not self.is_fitted:
            raise ValueError("PCA not fitted. Call build() first.")
        return dict(zip(self._feature_names, self.pca.components_[0]))

    def sign_correction(
        self,
        index: pd.Series,
        reference_series: pd.Series,
        positive: bool = False,
    ) -> pd.Series:
        """
        Correct PC1 sign using a reference variable.

        PCA sign is arbitrary. We enforce a direction using economic logic:
        - HY spread: corr(PC1, HY) < 0 → higher spread = bearish
        - NL level:  corr(PC1, NL) > 0 → higher liquidity = bullish

        Args:
            reference_series: Variable to align against (HY or NL)
            positive: If True, enforce positive correlation with reference.
                      If False, enforce negative correlation (default for HY).
        """
        # Align on common index
        common = index.index.intersection(reference_series.index)
        if len(common) < 10:
            logger.warning("sign_correction: only %d common points", len(common))
            return index

        corr = np.corrcoef(index.loc[common], reference_series.loc[common])[0, 1]

        should_flip = (positive and corr < 0) or (not positive and corr > 0)

        if should_flip:
            logger.info("PC1 sign flipped (corr with ref was %.3f, positive=%s)",
                        corr, positive)
            return -index
        else:
            logger.info("PC1 sign OK (corr with ref = %.3f, positive=%s)",
                        corr, positive)
            return index
