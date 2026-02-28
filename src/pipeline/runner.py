"""주간 파이프라인 오케스트레이터"""
import numpy as np
import pandas as pd
from datetime import datetime

from config.settings import DATA_START, DATA_END, FRED_API_KEY
from config.constants import VARIABLE_ORDER, SIGNAL_THRESHOLDS
from src.fetchers.fred_fetcher import FredFetcher
from src.fetchers.treasury_fetcher import TreasuryFetcher
from src.fetchers.market_fetcher import MarketFetcher
from src.fetchers.fallback_fetcher import FallbackFetcher
from src.calculators.net_liquidity import NetLiquidityCalculator
from src.calculators.global_m2 import GlobalM2Calculator
from src.calculators.sofr_binary import SofrBinaryCalculator
from src.calculators.hy_spread import HySpreadCalculator
from src.calculators.cme_basis import CmeBasisCalculator
from src.calculators.detrend import zscore, compute_zscore_params
from src.optimizers.orthogonalize import check_and_orthogonalize
from src.optimizers.grid_search import GridSearchOptimizer
from src.optimizers.walk_forward import WalkForwardValidator
from src.pipeline.storage import StorageManager
from src.utils.logger import setup_logger

logger = setup_logger("pipeline")


class PipelineRunner:
    """
    모드:
      - "full": 전체 백테스트 (fetch + calc + optimize)
      - "update": 최신 데이터만 추가 (주간 실행용)
      - "score_only": 저장된 가중치로 현재 Score만 계산
    """

    def __init__(self, mode: str = "full"):
        self.mode = mode
        self.storage = StorageManager()
        self.storage.init_db()

    def run(
        self,
        start: str | None = None,
        end: str | None = None,
        use_cache: bool = True,
    ) -> dict:
        """전체 파이프라인 실행"""
        start = start or DATA_START
        end = end or DATA_END

        logger.info(f"═══ Pipeline Start (mode={self.mode}) ═══")
        logger.info(f"Period: {start} ~ {end}")

        # Step 1: Fetch
        logger.info("── Step 1: Fetching data ──")
        raw_data = self._fetch_all(start, end, use_cache)

        # Step 2: Calculate
        logger.info("── Step 2: Calculating variables ──")
        variables, log_btc = self._calculate_all(raw_data)

        # Step 3: Orthogonalize
        logger.info("── Step 3: Orthogonalization check ──")
        ortho_vars, ortho_log = self._orthogonalize(variables)

        # Step 4: Z-score
        logger.info("── Step 4: Z-score standardization ──")
        z_matrix, z_params = self._zscore_all(ortho_vars)

        if self.mode == "full":
            # Step 5: Optimize
            logger.info("── Step 5: Grid Search optimization ──")
            opt_result = self._optimize(z_matrix, log_btc)

            # Step 6: Walk-Forward
            logger.info("── Step 6: Walk-Forward validation ──")
            wf_result = self._walk_forward(
                ortho_vars, log_btc,
                opt_result["weights"], opt_result["optimal_lag"],
            )

            # Save optimization
            full_opt = {
                **opt_result,
                "walk_forward": wf_result,
                "orthogonalization": ortho_log,
                "zscore_params": z_params,
                "date": datetime.now().strftime("%Y-%m-%d"),
            }
            self.storage.save_optimization_result(full_opt)

            weights = opt_result["weights"]
            lag = opt_result["optimal_lag"]
            correlation = opt_result["correlation"]
        else:
            # score_only / update: 저장된 가중치 사용
            opt = self.storage.load_latest_optimization()
            if opt is None:
                logger.error("No saved optimization found. Run 'full' mode first.")
                return {}
            weights = opt["weights"]
            lag = opt["optimal_lag"]
            correlation = opt["correlation"]
            wf_result = opt.get("walk_forward", {})

        # Step 7: Current Score
        logger.info("── Step 7: Computing current score ──")
        score_result = self._compute_current_score(z_matrix, weights, lag, correlation)

        # Save
        self.storage.save_score(score_result)
        self.storage.insert_score(score_result)

        # Save processed data
        self._save_processed(variables, ortho_vars, z_matrix, log_btc)

        logger.info(f"═══ Pipeline Complete ═══")
        logger.info(f"Score: {score_result['score']:.4f} → {score_result['signal']}")
        logger.info(f"Optimal lag: {lag}m, corr: {correlation:.4f}")

        return score_result

    def _fetch_all(self, start: str, end: str, use_cache: bool) -> dict:
        """모든 데이터 소스에서 수집"""
        data = {}

        # FRED
        fred = FredFetcher()
        fred_data = fred.fetch_all_fred_series(start, end, use_cache=use_cache)
        data["fred"] = fred_data

        # Treasury TGA
        treasury = TreasuryFetcher()
        data["tga"] = treasury.fetch_tga(start, end, use_cache=use_cache)

        # Market
        market = MarketFetcher()
        data["dxy"] = market.fetch_dxy(start, end, use_cache=use_cache)
        data["btc_spot"] = market.fetch_btc_spot(start, end, use_cache=use_cache)
        data["cme_futures_monthly"] = market.fetch_cme_futures(start, end, use_cache=use_cache)

        # CME Basis 일간 데이터
        data["btc_daily"] = market.fetch_btc_daily(start, end, use_cache=use_cache)
        data["cme_daily"] = market.fetch_cme_daily(start, end, use_cache=use_cache)

        # BTC fallback (필요 시)
        if data["btc_spot"].empty:
            logger.warning("Yahoo BTC failed, trying fallback...")
            fallback = FallbackFetcher()
            data["btc_spot"] = fallback.fetch_btc_spot_with_fallback(start, end)

        return data

    @staticmethod
    def _normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
        """날짜를 월말(month-end)로 정규화하여 merge 정합성 확보"""
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"]) + pd.offsets.MonthEnd(0)
        # 같은 월에 중복이 생길 수 있으므로 마지막 값 유지
        df = df.drop_duplicates(subset="date", keep="last")
        return df

    def _calculate_all(self, raw: dict) -> tuple[pd.DataFrame, pd.Series]:
        """변수 계산 + log₁₀(BTC)"""
        fred = raw["fred"]

        # NL
        nl_calc = NetLiquidityCalculator()
        nl = nl_calc.calculate(fred["WALCL"], raw["tga"], fred["RRP"])

        # GM2
        gm2_calc = GlobalM2Calculator()
        gm2 = gm2_calc.calculate(
            fred["US_M2"], fred["EU_M2"], fred["CN_M2"], fred["JP_M2"]
        )

        # SOFR Binary
        sofr_calc = SofrBinaryCalculator()
        sofr = sofr_calc.calculate(fred["SOFR"], fred["IORB"])

        # HY Spread
        hy_calc = HySpreadCalculator()
        hy = hy_calc.calculate(fred["HY_SPREAD"])

        # CME Basis
        cme_calc = CmeBasisCalculator()
        cme = cme_calc.calculate(raw["cme_daily"], raw["btc_daily"])

        # ── 날짜 정규화 (모든 변수를 월말 기준으로 통일) ──
        nl = self._normalize_dates(nl)
        gm2 = self._normalize_dates(gm2)
        sofr = self._normalize_dates(sofr)
        hy = self._normalize_dates(hy)
        cme = self._normalize_dates(cme)

        # 병합 (월간, month-end 기준)
        base = nl[["date", "nl_level"]].rename(columns={"nl_level": "NL_level"})
        base = base.merge(
            gm2[["date", "gm2_level"]].rename(columns={"gm2_level": "GM2_level"}),
            on="date", how="outer",
        )
        base = base.merge(
            sofr[["date", "sofr_binary"]].rename(columns={"sofr_binary": "SOFR_binary"}),
            on="date", how="outer",
        )
        base = base.merge(
            hy[["date", "hy_level"]].rename(columns={"hy_level": "HY_level"}),
            on="date", how="outer",
        )
        base = base.merge(
            cme[["date", "basis_level"]].rename(columns={"basis_level": "CME_basis"}),
            on="date", how="outer",
        )

        base = base.sort_values("date").reset_index(drop=True)

        # BTC (log10) — 역시 월말 정규화
        btc = self._normalize_dates(raw["btc_spot"].copy())
        btc["log_btc"] = np.log10(btc["btc_spot"])
        base = base.merge(btc[["date", "log_btc"]], on="date", how="left")

        log_btc = base["log_btc"]
        variables = base.drop(columns=["log_btc"])

        logger.info(f"Variables merged: {len(variables)} months, "
                    f"columns: {list(variables.columns)}")
        return variables, log_btc

    def _orthogonalize(self, variables: pd.DataFrame) -> tuple[pd.DataFrame, list]:
        """직교화 체크 및 수행"""
        var_series = {}
        for col in VARIABLE_ORDER:
            if col in variables.columns:
                var_series[col] = variables[col]

        # GM2_level → GM2_resid 로 매핑 (직교화 대상)
        if "GM2_level" in variables.columns and "GM2_resid" not in var_series:
            var_series["GM2_resid"] = variables["GM2_level"]

        ortho_vars, ortho_log = check_and_orthogonalize(
            var_series, protected=["NL_level"]
        )

        # DataFrame 재구성
        result = variables[["date"]].copy()
        for col in VARIABLE_ORDER:
            if col in ortho_vars:
                result[col] = ortho_vars[col].values
            elif col in variables.columns:
                result[col] = variables[col].values

        return result, ortho_log

    def _zscore_all(
        self, variables: pd.DataFrame,
    ) -> tuple[pd.DataFrame, dict]:
        """모든 변수 z-score 변환"""
        z_df = variables[["date"]].copy()
        z_params = {}

        for col in VARIABLE_ORDER:
            if col in variables.columns:
                series = variables[col]
                params = compute_zscore_params(series)
                z_df[col] = zscore(series, mean=params["mean"], std=params["std"])
                z_params[col] = params

        return z_df, z_params

    def _optimize(self, z_matrix: pd.DataFrame, log_btc: pd.Series) -> dict:
        """Grid Search 최적화"""
        optimizer = GridSearchOptimizer()
        return optimizer.optimize(z_matrix, log_btc)

    def _walk_forward(
        self, raw_vars: pd.DataFrame, log_btc: pd.Series,
        weights: dict, lag: int,
    ) -> dict:
        """Walk-Forward 검증"""
        validator = WalkForwardValidator()
        return validator.validate(raw_vars, log_btc, weights, lag)

    def _compute_current_score(
        self, z_matrix: pd.DataFrame, weights: dict,
        lag: int, correlation: float,
    ) -> dict:
        """최신 Score 계산 (NaN이 아닌 마지막 행 사용)"""
        # NaN이 아닌 마지막 유효 행 찾기
        score_cols = [v for v in VARIABLE_ORDER if v in z_matrix.columns]
        valid_mask = z_matrix[score_cols].notna().any(axis=1)

        if valid_mask.any():
            latest = z_matrix.loc[valid_mask].iloc[-1]
        else:
            latest = z_matrix.iloc[-1]

        # NaN → 0으로 대체하여 score 계산
        score = 0.0
        for var in VARIABLE_ORDER:
            w = weights.get(var, 0.0)
            val = latest.get(var, 0.0)
            if pd.isna(val):
                val = 0.0
            score += w * float(val)

        signal = self._signal_from_score(score)

        return {
            "date": pd.Timestamp(latest.get("date", datetime.now())).strftime("%Y-%m-%d"),
            "score": round(score, 4),
            "signal": signal,
            "lag": lag,
            "weights": weights,
            "correlation": correlation,
            "variables": {
                var: round(float(latest.get(var, 0.0) if not pd.isna(latest.get(var, 0.0)) else 0.0), 4)
                for var in VARIABLE_ORDER
                if var in latest.index
            },
            "timestamp": datetime.now().isoformat(),
        }

    def _signal_from_score(self, score: float) -> str:
        if score > SIGNAL_THRESHOLDS["bullish"]:
            return "BULLISH"
        elif score < SIGNAL_THRESHOLDS["bearish"]:
            return "BEARISH"
        return "NEUTRAL"

    def _save_processed(self, variables, ortho_vars, z_matrix, log_btc):
        """중간 데이터 저장"""
        try:
            self.storage.save_processed("variables_raw", variables)
            self.storage.save_processed("variables_ortho", ortho_vars)
            z_with_btc = z_matrix.copy()
            z_with_btc["log_btc"] = log_btc.values
            self.storage.save_processed("z_matrix", z_with_btc)
        except Exception as e:
            logger.warning(f"Failed to save processed data: {e}")
