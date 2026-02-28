"""Global M2 합산 + 직교화"""
import numpy as np
import pandas as pd

from src.calculators.detrend import detrend_12m_ma
from src.utils.logger import setup_logger
from src.utils.date_utils import resample_to_monthly

logger = setup_logger("global_m2")


class GlobalM2Calculator:
    """GM2 = US_M2 + EU_M2 + CN_M2 + JP_M2, 직교화 포함"""

    def calculate(
        self,
        us_m2: pd.DataFrame,
        eu_m2: pd.DataFrame,
        cn_m2: pd.DataFrame,
        jp_m2: pd.DataFrame,
    ) -> pd.DataFrame:
        """
        1. 각국 M2를 $T로 통일
        2. GM2 = US + EU + CN + JP
        3. 래그 처리: 최신 2-3개월 → 직전값 캐리포워드
        4. GM2_level = detrend_12m_ma(GM2)

        Returns: DataFrame[date, gm2_raw, gm2_level]
        """
        # 각국 M2를 월간 정렬 (FRED 시리즈는 이미 월간이지만 확인)
        dfs = {}
        for name, df in [("us", us_m2), ("eu", eu_m2), ("cn", cn_m2), ("jp", jp_m2)]:
            d = df.copy()
            # FRED M2 시리즈는 $B 단위 → $T 변환
            d["value"] = d["value"] / 1_000
            d = d.rename(columns={"value": f"m2_{name}"})
            dfs[name] = d

        # 병합
        merged = dfs["us"]
        for name in ["eu", "cn", "jp"]:
            merged = merged.merge(dfs[name], on="date", how="outer")

        merged = merged.sort_values("date").reset_index(drop=True)

        # 래그 처리: forward-fill
        merged = self._carry_forward_lag(merged)

        # GM2 합산
        m2_cols = [f"m2_{c}" for c in ["us", "eu", "cn", "jp"]]
        merged["gm2_raw"] = merged[m2_cols].sum(axis=1)

        # 12m MA detrend
        merged["gm2_level"] = detrend_12m_ma(merged["gm2_raw"])

        result = merged[["date", "gm2_raw", "gm2_level"]].copy()
        logger.info(f"GM2 calculated: {len(result)} months, "
                    f"latest GM2={result['gm2_raw'].iloc[-1]:.2f}$T")
        return result

    def orthogonalize(
        self,
        gm2_level: pd.Series,
        nl_level: pd.Series,
    ) -> tuple[pd.Series, dict]:
        """
        GM2에서 NL과 겹치는 부분 제거 (OLS regression).

        GM2_level = β × NL_level + α + ε
        GM2_resid = ε (잔차)

        Returns:
          - gm2_resid: 직교화된 시리즈
          - params: {"beta", "alpha", "corr_before", "corr_after"}
        """
        # NaN 제거한 공통 인덱스
        valid = gm2_level.notna() & nl_level.notna()
        gm2_clean = gm2_level[valid].values
        nl_clean = nl_level[valid].values

        corr_before = float(np.corrcoef(gm2_clean, nl_clean)[0, 1])

        # OLS: GM2 = β × NL + α
        X = np.column_stack([nl_clean, np.ones(len(nl_clean))])
        beta_alpha, _, _, _ = np.linalg.lstsq(X, gm2_clean, rcond=None)
        beta, alpha = beta_alpha[0], beta_alpha[1]

        # Residual 계산 (전체 시리즈에 적용)
        gm2_resid = gm2_level - (beta * nl_level + alpha)

        # 검증
        valid2 = gm2_resid.notna() & nl_level.notna()
        corr_after = float(np.corrcoef(
            gm2_resid[valid2].values,
            nl_level[valid2].values
        )[0, 1])

        params = {
            "beta": round(float(beta), 4),
            "alpha": round(float(alpha), 4),
            "corr_before": round(corr_before, 4),
            "corr_after": round(corr_after, 4),
        }

        logger.info(f"GM2 orthogonalized: β={params['beta']}, α={params['alpha']}, "
                    f"corr {params['corr_before']:.3f} → {params['corr_after']:.3f}")

        return gm2_resid, params

    def _carry_forward_lag(
        self,
        df: pd.DataFrame,
        max_lag_months: int = 3,
    ) -> pd.DataFrame:
        """최신 래그 기간 → 직전값으로 채우기 (forward-fill)"""
        return df.ffill(limit=max_lag_months)
