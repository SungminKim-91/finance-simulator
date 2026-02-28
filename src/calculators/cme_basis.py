"""CME Basis — 기관 포지셔닝"""
import numpy as np
import pandas as pd

from src.calculators.detrend import detrend_12m_ma_abs
from src.utils.logger import setup_logger
from src.utils.date_utils import days_to_expiry, resample_to_monthly

logger = setup_logger("cme_basis")


class CmeBasisCalculator:
    """
    CME Basis = (선물 - 현물) / 현물 × (365/잔존일) × 100
    → 12m MA detrend (|MA|로 나눔)
    """

    def calculate(
        self,
        cme_futures: pd.DataFrame,
        btc_spot: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        1. 일간 basis 계산 (연율화)
        2. 월말 리샘플링
        3. 12m MA detrend (|MA| 사용)

        Args:
            cme_futures: DataFrame[date, cme_futures] — 일간
            btc_spot: DataFrame[date, btc_spot] — 일간

        Returns: DataFrame[date, basis_raw_pct, basis_annualized, basis_level]

        Edge cases:
        - 2017-12 이전: NaN
        - basis < 0 (백워데이션): 그대로 사용
        """
        # 일간 병합
        merged = cme_futures.merge(btc_spot, on="date", how="inner")
        merged = merged.sort_values("date").reset_index(drop=True)

        if merged.empty:
            logger.warning("No overlapping CME futures + spot data")
            return pd.DataFrame(
                columns=["date", "basis_raw_pct", "basis_annualized", "basis_level"]
            )

        # Raw basis (%)
        merged["basis_raw_pct"] = (
            (merged["cme_futures"] - merged["btc_spot"])
            / merged["btc_spot"] * 100
        )

        # 잔존일 계산 + 연율화
        merged["days_to_exp"] = merged["date"].apply(days_to_expiry)
        merged["basis_annualized"] = (
            merged["basis_raw_pct"] * (365.0 / merged["days_to_exp"])
        )

        # 이상값 클리핑 (연율화 basis가 ±200% 초과 시)
        merged["basis_annualized"] = merged["basis_annualized"].clip(-200, 200)

        # 월말 리샘플링
        monthly = resample_to_monthly(
            merged[["date", "basis_annualized"]],
            "basis_annualized",
        )

        # raw_pct도 월말
        raw_monthly = resample_to_monthly(
            merged[["date", "basis_raw_pct"]],
            "basis_raw_pct",
        )
        monthly = monthly.merge(raw_monthly, on="date", how="left")

        # 12m MA detrend (|MA|로 나눔 — basis는 음수 가능)
        monthly["basis_level"] = detrend_12m_ma_abs(monthly["basis_annualized"])

        result = monthly[["date", "basis_raw_pct", "basis_annualized", "basis_level"]].copy()

        valid = result["basis_level"].notna()
        logger.info(f"CME Basis: {valid.sum()} valid months "
                    f"(total {len(result)}), "
                    f"latest annualized={result['basis_annualized'].iloc[-1]:.1f}%")
        return result
