"""v4.0 모델 상수 — 최적화 후 업데이트"""

# ══════════════════════════════════════════
# FRED 시리즈 매핑
# ══════════════════════════════════════════
FRED_SERIES: dict[str, str] = {
    "WALCL": "WALCL",              # Fed Balance Sheet (주간)
    "RRP": "RRPONTSYD",            # Reverse Repo (일간)
    "SOFR": "SOFR",                # SOFR rate (일간)
    "IORB": "IORB",                # Interest on Reserve Balances (일간)
    "US_M2": "M2SL",               # US M2 Money Supply (월간)
    "EU_M2": "MABMM301EZM189S",   # Euro Area M3 Broad Money (월간, ~2023-11)
    "CN_M2": "MYAGM2CNM189N",     # China M2 (월간, ~2019-08, 이후 carry-forward)
    "JP_M2": "MABMM301JPM189S",   # Japan M3 Broad Money (월간, ~2023-11)
    "HY_SPREAD": "BAMLH0A0HYM2",  # ICE BofA US HY OAS (월간)
}

# ══════════════════════════════════════════
# Treasury Fiscal Data API (TGA)
# ══════════════════════════════════════════
TREASURY_TGA_ENDPOINT = (
    "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
    "/v1/accounting/dts/operating_cash_balance"
)
TREASURY_TGA_FIELDS = "record_date,open_today_bal,account_type"
# 2021-10 이전: "Federal Reserve Account", 이후: "Treasury General Account (TGA) Closing Balance"
TREASURY_TGA_FILTER_OLD = "account_type:eq:Federal Reserve Account"
TREASURY_TGA_FILTER_NEW = "account_type:eq:Treasury General Account (TGA) Closing Balance"
TREASURY_PAGE_SIZE = 10000

# ══════════════════════════════════════════
# Market Tickers (yfinance)
# ══════════════════════════════════════════
TICKERS: dict[str, str] = {
    "DXY": "DX-Y.NYB",
    "BTC_SPOT": "BTC-USD",
    "CME_BTC_FUTURES": "BTC=F",
}

# ══════════════════════════════════════════
# Fallback APIs
# ══════════════════════════════════════════
COINGECKO_BTC_URL = (
    "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart/range"
)
BINANCE_KLINES_URL = "https://api.binance.com/api/v3/klines"

# ══════════════════════════════════════════
# 변수 변환 파라미터
# ══════════════════════════════════════════
SOFR_THRESHOLD_BPS: int = 20       # SOFR binary 임계값 (basis points)
MA_WINDOW_MONTHS: int = 12         # 12m MA detrend 윈도우

# ══════════════════════════════════════════
# Grid Search 탐색 범위
# ══════════════════════════════════════════
GRID_SEARCH: dict = {
    "NL_level":    {"min": 0.5, "max": 5.5, "step": 0.5},
    "GM2_resid":   {"min": 0.0, "max": 4.0, "step": 0.5},
    "SOFR_binary": {"min": -4.0, "max": 0.0, "step": 0.5},
    "HY_level":    {"min": -4.0, "max": 0.0, "step": 0.5},
    "CME_basis":   {"min": -2.0, "max": 3.0, "step": 0.5},
    "lag_months":  {"min": 0, "max": 9, "step": 1},
}

# ══════════════════════════════════════════
# Walk-Forward 파라미터
# ══════════════════════════════════════════
WALK_FORWARD: dict = {
    "initial_train": 60,   # 초기 훈련 윈도우 (월)
    "test_window": 6,      # 테스트 윈도우 (월)
    "expanding": True,     # expanding window
}

# ══════════════════════════════════════════
# 직교화
# ══════════════════════════════════════════
ORTHO_CORR_THRESHOLD: float = 0.5

# ══════════════════════════════════════════
# v3.0 기준값 (비교용)
# ══════════════════════════════════════════
V3_WEIGHTS: dict = {
    "NL_level": 1.5,
    "GM2_resid": 2.0,
    "SOFR_binary": -2.5,
}
V3_OPTIMAL_LAG: int = 5
V3_CORRELATION: float = 0.407

# ══════════════════════════════════════════
# Z-Score 파라미터 (v3.0 기준 — 실제 데이터 수집 후 재계산)
# ══════════════════════════════════════════
ZSCORE_PARAMS_V3: dict = {
    "NL_level":  {"mean": 2.3800, "std": 9.6004},
    "NL_accel":  {"mean": 0.0119, "std": 3.6226},
    "GM2_level": {"mean": 2.5455, "std": 2.8769},
    "DXY_level": {"mean": 0.0023, "std": 3.6039},
    "SOFR_bin":  {"mean": 0.1204, "std": 0.3269},
}

# ══════════════════════════════════════════
# Signal 분류 임계값
# ══════════════════════════════════════════
SIGNAL_THRESHOLDS: dict = {
    "bullish": 0.5,
    "bearish": -0.5,
}

# ══════════════════════════════════════════
# 변수 순서 (Grid Search, Score 계산 시 통일)
# ══════════════════════════════════════════
VARIABLE_ORDER: list[str] = [
    "NL_level",
    "GM2_resid",
    "SOFR_binary",
    "HY_level",
    "CME_basis",
]
