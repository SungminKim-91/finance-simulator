"""다중 비교 보정 — Deflated Sharpe Ratio 아이디어 적용.

여러 방법(PCA, ICA, DFM, SparsePCA)을 시도할 때
최고 결과가 우연인지 검정.

Bailey & de Prado (2014) 원리.
"""

import logging
import numpy as np
from scipy.stats import norm

logger = logging.getLogger(__name__)


class DeflatedTest:
    """Multiple testing correction for CWS."""

    def deflated_cws(
        self,
        cws_values: list[float],
        n_methods: int,
        n_observations: int,
    ) -> dict:
        """
        Deflated CWS: correct for multiple method trials.

        When we try N methods and pick the best CWS,
        the expected maximum CWS under null (random) is higher
        than the single-trial null. This corrects for that bias.

        Args:
            cws_values: list of CWS values from different methods
            n_methods: number of methods tried
            n_observations: time series length

        Returns:
            dict with best_cws, deflated_cws, p_value, significant
        """
        if not cws_values:
            return {
                "best_cws": 0.0,
                "deflated_cws": 0.0,
                "p_value": 1.0,
                "significant": False,
                "n_methods_tried": n_methods,
            }

        best_cws = max(cws_values)
        mean_cws = np.mean(cws_values)
        std_cws = np.std(cws_values) if len(cws_values) > 1 else 0.1

        # Expected maximum of N independent draws from normal
        # E[max(Z_1,...,Z_N)] ~ sqrt(2 * ln(N)) for large N
        if n_methods > 1:
            expected_max_shift = np.sqrt(2 * np.log(n_methods))
        else:
            expected_max_shift = 0.0

        # Deflated CWS: subtract the expected inflation
        if std_cws > 1e-10:
            z_observed = (best_cws - 0.5) / std_cws  # 0.5 = null CWS
            z_deflated = z_observed - expected_max_shift
            deflated_cws = 0.5 + z_deflated * std_cws
        else:
            deflated_cws = best_cws
            z_deflated = 0.0

        # p-value: probability of observing this deflated CWS under null
        # Null: CWS ~ N(0.5, std^2) (random direction matching)
        se = std_cws / np.sqrt(max(n_observations, 1))
        if se > 1e-10:
            z_test = (deflated_cws - 0.5) / se
            p_value = 1.0 - norm.cdf(z_test)
        else:
            p_value = 0.0 if deflated_cws > 0.5 else 1.0

        logger.info(
            "Deflated test: best_cws=%.3f, deflated=%.3f, "
            "p=%.4f, n_methods=%d",
            best_cws, deflated_cws, p_value, n_methods,
        )

        return {
            "best_cws": float(best_cws),
            "mean_cws": float(mean_cws),
            "deflated_cws": float(deflated_cws),
            "p_value": float(p_value),
            "significant": p_value < 0.05,
            "n_methods_tried": n_methods,
            "expected_max_shift": float(expected_max_shift),
        }
