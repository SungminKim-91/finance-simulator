"""DFM(Dynamic Factor Model) — 혼합 주기 인덱스 구성.

일/주/월 혼합 주기 데이터를 통합하는 Dynamic Factor Model.
칼만 필터로 결측치(NaN) 최적 보간.
"""

import logging
import numpy as np
import pandas as pd

from config.constants import DFM_CONFIG

logger = logging.getLogger(__name__)


class DFMIndexBuilder:
    """DFM + Kalman filter for mixed-frequency index."""

    def __init__(
        self,
        k_factors: int = DFM_CONFIG["k_factors"],
        factor_order: int = DFM_CONFIG["factor_order"],
    ):
        self.k_factors = k_factors
        self.factor_order = factor_order
        self.model = None
        self.result = None
        self.is_fitted = False

    def build(self, daily_matrix: pd.DataFrame) -> dict:
        """
        Extract common factor from daily matrix with NaN.

        Args:
            daily_matrix: DataFrame[date(daily), var1, var2, ...]
                          NaN where no observation exists.

        Returns:
            dict with: daily_factor, filtered_factor, smoothed_factor,
                      factor_loadings, log_likelihood, aic, bic, method
        """
        try:
            from statsmodels.tsa.statespace.dynamic_factor import DynamicFactor
        except ImportError:
            logger.error("statsmodels DynamicFactor not available")
            raise

        btc_cols = [c for c in daily_matrix.columns
                    if "btc" in c.lower() or "bitcoin" in c.lower()]
        if btc_cols:
            raise ValueError(f"BTC columns found: {btc_cols}")

        numeric_cols = daily_matrix.select_dtypes(
            include=[np.number]
        ).columns.tolist()

        data = daily_matrix[numeric_cols].copy()

        # Standardize each column (handle NaN)
        for col in numeric_cols:
            mean = data[col].mean()
            std = data[col].std()
            if std > 1e-10:
                data[col] = (data[col] - mean) / std

        # Fit DFM with multiple attempts
        best_result = None
        for max_iter in [DFM_CONFIG["max_iter"], DFM_CONFIG["max_iter"] * 2]:
            try:
                model = DynamicFactor(
                    data,
                    k_factors=self.k_factors,
                    factor_order=self.factor_order,
                )
                result = model.fit(
                    disp=False,
                    maxiter=max_iter,
                    method="em",
                )
                if best_result is None or result.llf > best_result.llf:
                    best_result = result
                    self.model = model
                break
            except Exception as e:
                logger.warning(
                    "DFM fit attempt (max_iter=%d) failed: %s", max_iter, e
                )
                continue

        if best_result is None:
            raise RuntimeError(
                "DFM fitting failed. Consider using PCA on monthly data."
            )

        self.result = best_result
        self.is_fitted = True

        # Extract factors
        filtered = best_result.factors.filtered[0]
        smoothed = best_result.factors.smoothed[0]

        daily_factor = pd.Series(
            smoothed, index=data.index, name="liquidity_index"
        )

        # Factor loadings
        n_vars = len(numeric_cols)
        loadings_arr = best_result.params[:n_vars]
        loadings = dict(zip(numeric_cols, loadings_arr))

        logger.info(
            "DFM built: %d obs, LL=%.1f, AIC=%.1f, loadings=%s",
            len(data), best_result.llf, best_result.aic,
            {k: f"{v:.3f}" for k, v in loadings.items()},
        )

        return {
            "daily_factor": daily_factor,
            "filtered_factor": pd.Series(
                filtered, index=data.index, name="filtered"
            ),
            "smoothed_factor": pd.Series(
                smoothed, index=data.index, name="smoothed"
            ),
            "factor_loadings": loadings,
            "log_likelihood": float(best_result.llf),
            "aic": float(best_result.aic),
            "bic": float(best_result.bic),
            "n_observations": len(data),
            "method": "DFM",
        }

    def resample_to_freq(
        self,
        daily_factor: pd.Series,
        freq: str = "monthly",
    ) -> pd.Series:
        """Resample daily factor to target frequency."""
        freq_map = {"daily": None, "weekly": "W", "monthly": "ME"}
        pandas_freq = freq_map.get(freq)

        if pandas_freq is None:
            return daily_factor

        return daily_factor.resample(pandas_freq).last().dropna()

    @staticmethod
    def prepare_daily_matrix(
        variables: dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        """
        Place mixed-frequency variables on a daily grid.

        Args:
            variables: {
                "NL": daily_df with [date, value],
                "GM2r": monthly_df with [date, value],
                "SOFR_smooth": daily_df with [date, value],
                "HY": monthly_df with [date, value],
                "CME": daily_df with [date, value],
            }

        Returns:
            DataFrame with daily business day index, NaN where no observation.
        """
        # Find date range
        all_dates = []
        for name, df in variables.items():
            dates = pd.to_datetime(df["date"] if "date" in df.columns
                                   else df.index)
            all_dates.extend(dates)

        min_date = min(all_dates)
        max_date = max(all_dates)

        # Create business day index
        daily_index = pd.bdate_range(min_date, max_date)

        result = pd.DataFrame(index=daily_index)

        for name, df in variables.items():
            if "date" in df.columns:
                s = df.set_index("date")["value"]
            else:
                s = df.iloc[:, 0] if isinstance(df, pd.DataFrame) else df

            s.index = pd.to_datetime(s.index)
            result[name] = s.reindex(daily_index)
            # NaN where no observation — Kalman will interpolate

        logger.info(
            "Daily matrix: %d days, %d vars, NaN rates: %s",
            len(result), len(variables),
            {c: f"{result[c].isna().mean():.1%}" for c in result.columns},
        )

        return result
