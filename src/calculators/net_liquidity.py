"""Net Liquidity (NL) = WALCL - TGA - RRP"""
import pandas as pd

from src.calculators.detrend import detrend_12m_ma
from src.utils.logger import setup_logger
from src.utils.date_utils import resample_to_monthly

logger = setup_logger("net_liquidity")


class NetLiquidityCalculator:
    """NL = WALCL - TGA - RRP (단위: $T)"""

    def calculate(
        self,
        walcl: pd.DataFrame,
        tga: pd.DataFrame,
        rrp: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        1. 모든 시계열을 월말 기준으로 리샘플링
        2. NL = WALCL - TGA - RRP (단위: $T)
        3. NL_level = detrend_12m_ma(NL)
        4. NL_accel = NL_level.diff()

        Returns: DataFrame[date, nl_raw, nl_level, nl_accel]
        """
        monthly = self._align_to_monthly(walcl, tga, rrp)

        # NL 계산 ($T)
        monthly["nl_raw"] = monthly["walcl"] - monthly["tga"] - monthly["rrp"]

        # 12m MA detrend
        monthly["nl_level"] = detrend_12m_ma(monthly["nl_raw"])

        # 가속도
        monthly["nl_accel"] = monthly["nl_level"].diff()

        result = monthly[["date", "nl_raw", "nl_level", "nl_accel"]].copy()
        logger.info(f"NL calculated: {len(result)} months, "
                    f"latest NL={result['nl_raw'].iloc[-1]:.3f}$T")
        return result

    def _align_to_monthly(
        self,
        walcl: pd.DataFrame,
        tga: pd.DataFrame,
        rrp: pd.DataFrame,
    ) -> pd.DataFrame:
        """주간/일간 → 월말 정렬, 결측 forward-fill"""

        # WALCL: 주간 → $B를 $T로 변환 후 월말
        w = walcl.copy()
        w["value"] = w["value"] / 1_000  # $B → $T (FRED WALCL은 $M 단위)
        w_monthly = resample_to_monthly(w, "value")
        w_monthly = w_monthly.rename(columns={"value": "walcl"})

        # TGA: 이미 $T 단위 (treasury_fetcher에서 변환)
        t_monthly = resample_to_monthly(tga, "tga_balance")
        t_monthly = t_monthly.rename(columns={"tga_balance": "tga"})

        # RRP: 일간 → 월말, $B → $T
        r = rrp.copy()
        r["value"] = r["value"] / 1_000  # $B → $T (FRED RRPONTSYD는 $B 단위)
        r_monthly = resample_to_monthly(r, "value")
        r_monthly = r_monthly.rename(columns={"value": "rrp"})

        # 병합
        merged = w_monthly.merge(t_monthly, on="date", how="outer")
        merged = merged.merge(r_monthly, on="date", how="outer")
        merged = merged.sort_values("date").reset_index(drop=True)

        # Forward-fill 결측
        merged = merged.ffill()
        merged = merged.dropna()

        logger.debug(f"Monthly aligned: {len(merged)} rows")
        return merged
