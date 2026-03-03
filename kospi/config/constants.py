"""
KOSPI Crisis Detector — 공용 상수 정의

모든 스크립트에서 공통으로 사용하는 상수를 단일 파일로 관리.
"""

from pathlib import Path

# ── 경로 상수 ──
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DAILY_DIR = DATA_DIR / "daily"
HISTORICAL_DIR = DATA_DIR / "historical"
WEB_DATA_DIR = PROJECT_ROOT.parent / "web" / "src" / "simulators" / "kospi" / "data"

# ── 종목 상수 ──
TICKERS = {"005930": "삼성전자", "000660": "SK하이닉스"}

# ── 날짜 형식 ──
DATE_FMT = "%Y%m%d"      # pykrx format
ISO_FMT = "%Y-%m-%d"     # 내부 저장 format

# ── KOFIA 스크래퍼 ──
KOFIA_BASE_URL = "https://freesis.kofia.or.kr"

# ── 반대매매 모델 파라미터 ──
MARGIN_DISTRIBUTION = {
    0.40: 0.35,   # 40% 담보비율: 전체의 35%
    0.45: 0.35,   # 45% 담보비율: 전체의 35%
    0.50: 0.25,   # 50% 담보비율: 전체의 25%
    0.60: 0.05,   # 60% 담보비율: 전체의 5%
}
MAINTENANCE_RATIO = 1.40   # 유지담보비율 140%
FORCED_LIQ_RATIO = 1.30   # 반대매매 발동 비율 130%

# ── 위기 지표 13개 ──
CRISIS_INDICATORS = [
    "leverage_heat",
    "flow_concentration",
    "price_deviation",
    "credit_acceleration",
    "deposit_inflow",
    "foreign_selling",
    "fx_stress",
    "short_anomaly",
    "vix_level",
    "volume_explosion",
    "forced_liq_intensity",
    "credit_deposit_ratio",
    "dram_cycle",
]

# ── 과거 사례 기간 ──
HISTORICAL_PERIODS = {
    "korea_2008": ("2007-01-01", "2009-12-31"),
    "korea_2011": ("2011-01-01", "2012-06-30"),
    "korea_2020": ("2019-06-01", "2020-12-31"),
    "korea_2021": ("2020-06-01", "2022-12-31"),
}
