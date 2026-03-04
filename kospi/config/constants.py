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

# ── Top 10 종목 (시총 상위, 신용잔고 집중) ──
TOP_10_TICKERS = {
    "005930": {"name": "삼성전자", "group": "A"},
    "000660": {"name": "SK하이닉스", "group": "A"},
    "005380": {"name": "현대차", "group": "A"},
    "000270": {"name": "기아", "group": "A"},
    "035420": {"name": "NAVER", "group": "A"},
    "006400": {"name": "삼성SDI", "group": "A"},
    "373220": {"name": "LG에너지솔루션", "group": "A"},
    "068270": {"name": "셀트리온", "group": "A"},
    "105560": {"name": "KB금융", "group": "A"},
    "005490": {"name": "POSCO홀딩스", "group": "A"},
}

# ── 신용거래 파라미터 (v1.4.1 — 상위 5개 증권사 일괄 적용) ──
# 보증금률 45%, 담보유지 140%, 청산임계 손실률 39%
# D+2 미납 시 D+3 반대매매
MARGIN_RATE = 0.45             # 보증금률 (증거금률)
MAINTENANCE_RATIO_FIXED = 1.40 # 담보유지비율 140%
FORCED_LIQ_LOSS_PCT = 39       # 손실률 39% 이상 → 즉시 반대매매

# 종목군별 파라미터 (v1.4.1: 전 종목군 동일)
STOCK_GROUP_PARAMS = {
    "A": {"margin": 0.45, "maintenance": 1.40, "forced_liq_loss_pct": 39},
}

# ── 날짜 형식 ──
DATE_FMT = "%Y%m%d"      # pykrx format
ISO_FMT = "%Y-%m-%d"     # 내부 저장 format

# ── KOFIA 스크래퍼 ──
KOFIA_BASE_URL = "https://freesis.kofia.or.kr"

# ── 반대매매 모델 파라미터 (v1.4.1 단일값) ──
# 분포 기반 → 단일 고정값으로 전환 (상위 5개 증권사 동일)
MAINTENANCE_RATIO = 1.40   # 담보유지비율 140%
FORCED_LIQ_RATIO = 1.40   # (호환용) — 실제 청산은 손실률 39% 기준

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
# ── Hybrid Beta 파라미터 (v1.4.0) ──
BETA_LOOKBACK = 7              # 거래일
BETA_DOWNSIDE_WEIGHT = 0.6     # 하방 가중치
BETA_UPSIDE_WEIGHT = 0.4       # 상방 가중치
BETA_MIN_KOSPI_RETURN = 0.001  # |KOSPI 수익률| 필터 (0.1%)
BETA_CLIP_MIN = 0.5            # beta 하한
BETA_CLIP_MAX = 3.0            # beta 상한

# ── 과거 사례 기간 ──
HISTORICAL_PERIODS = {
    "korea_2008": ("2007-01-01", "2009-12-31"),
    "korea_2011": ("2011-01-01", "2012-06-30"),
    "korea_2020": ("2019-06-01", "2020-12-31"),
    "korea_2021": ("2020-06-01", "2022-12-31"),
}
