"""HY Spread Level — 신용 스프레드 (위험선호)"""
import pandas as pd

from src.calculators.detrend import detrend_12m_ma
from src.utils.logger import setup_logger
from src.utils.date_utils import resample_to_monthly

logger = setup_logger("hy_spread")


class HySpreadCalculator:
    """ICE BofA US High Yield OAS → 월말 리샘플링 → 12m MA detrend"""

    def calculate(
        self,
        hy_oas: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        1. 일간 → 월말 리샘플링
        2. HY_level = detrend_12m_ma(HY_OAS)

        Args:
            hy_oas: DataFrame[date, value] — FRED BAMLH0A0HYM2 (일간)

        Returns: DataFrame[date, hy_raw, hy_level]
        """
        df = hy_oas.copy()
        df = df.rename(columns={"value": "hy_raw"})
        df = df.sort_values("date").reset_index(drop=True)

        # 일간 → 월말 리샘플링
        df = resample_to_monthly(df, "hy_raw")

        # 12m MA detrend
        df["hy_level"] = detrend_12m_ma(df["hy_raw"])

        result = df[["date", "hy_raw", "hy_level"]].copy()

        valid = result["hy_level"].notna()
        logger.info(f"HY Spread: {valid.sum()} valid months (of {len(result)}), "
                    f"latest HY OAS={result['hy_raw'].iloc[-1]:.2f}pp")
        return result
