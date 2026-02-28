"""SOFR Binary — 위기 감지"""
import pandas as pd

from config.constants import SOFR_THRESHOLD_BPS
from src.utils.logger import setup_logger
from src.utils.date_utils import resample_to_monthly

logger = setup_logger("sofr_binary")


class SofrBinaryCalculator:
    """SOFR - IORB > threshold → 1 (위기), else → 0"""

    def calculate(
        self,
        sofr: pd.DataFrame,
        iorb: pd.DataFrame,
        threshold_bps: int = SOFR_THRESHOLD_BPS,
    ) -> pd.DataFrame:
        """
        1. spread = SOFR - IORB (bps 단위로 변환)
        2. 월말 기준 spread 계산
        3. binary = 1 if spread > threshold else 0

        Returns: DataFrame[date, sofr_spread_bps, sofr_binary]

        참고: SOFR 2018-04 이전 없음 → 0 처리
              IORB 2021-07 이전 → 값 없으면 0 처리
        """
        # 일간 병합
        s = sofr.rename(columns={"value": "sofr_rate"})
        i = iorb.rename(columns={"value": "iorb_rate"})

        merged = s.merge(i, on="date", how="outer")
        merged = merged.sort_values("date").reset_index(drop=True)

        # 결측 처리: SOFR/IORB 없는 기간은 spread = 0 (위기 아님)
        merged["sofr_rate"] = merged["sofr_rate"].ffill()
        merged["iorb_rate"] = merged["iorb_rate"].ffill()

        # Spread (% → bps: SOFR, IORB는 이미 % 단위)
        merged["spread_pct"] = merged["sofr_rate"] - merged["iorb_rate"]
        merged["sofr_spread_bps"] = merged["spread_pct"] * 100  # % → bps

        # 월말 리샘플링
        monthly = resample_to_monthly(
            merged[["date", "sofr_spread_bps"]],
            "sofr_spread_bps",
        )

        # Binary
        monthly["sofr_binary"] = (
            monthly["sofr_spread_bps"] > threshold_bps
        ).astype(int)

        # 데이터 없는 초기 기간은 0
        monthly["sofr_binary"] = monthly["sofr_binary"].fillna(0).astype(int)

        logger.info(f"SOFR Binary: {len(monthly)} months, "
                    f"crisis months={monthly['sofr_binary'].sum()}")
        return monthly
