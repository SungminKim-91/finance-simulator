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

# ── v1.5.0 공통 상수 ──
LOAN_RATE = 1 - MARGIN_RATE          # 0.55 (융자비율)
LEVERAGE = 1 / MARGIN_RATE            # 2.22 (실질 레버리지)
DAILY_LIMIT = 0.30                    # KOSPI 가격제한폭 ±30%

# 6단계 상태 분류 기준 (담보비율 %)
STATUS_THRESHOLDS = {
    "debt_exceed": 100,   # 담보비율 < 100% → 채무초과
    "forced_liq":  120,   # 담보비율 < 120% → 강제청산
    "margin_call": 140,   # 담보비율 < 140% → 마진콜
    "caution":     155,   # 담보비율 < 155% → 주의
    "good":        170,   # 담보비율 < 170% → 양호
    # >= 170% → 안전
}

# Samsung 신용잔고 추정 비중
SAMSUNG_CREDIT_WEIGHT = 0.50

# ── v2.2.0 RSPI 상수 (5변수 + 거래량 증폭기) ──

# RSPI 5변수 가중치
RSPI_WEIGHTS = {
    "v1": 0.25,  # 코호트 proximity (0~1, 단방향)
    "v2": 0.20,  # 외국인 수급 방향 (-1~+1, z-score)
    "v3": 0.25,  # 야간시장 시그널 (-1~+1, 4소스+coherence)
    "v4": 0.20,  # 개인 수급 방향 (-1~+1, 패턴)
    "v5": 0.10,  # 신용잔고 모멘텀 (-1~+1, 변화율)
}

# V1: 코호트 proximity
V1_MARGIN_CALL_RATIO = 140   # 마진콜 기준 담보비율
V1_SAFE_RANGE = 60           # proximity 감쇠 범위 (140~200%)
V1_PROXIMITY_POWER = 2.5     # 비선형 proximity 지수 (v2.3.0)

# V2: 외국인 수급 z-score
V2_LOOKBACK = 20             # z-score 계산 기간 (거래일)
V2_DIVISOR = 2.0             # z=±2 → V2=±1.0

# V3: 야간시장 4소스 가중치
OVERNIGHT_WEIGHTS = {
    "ewy":       0.30,  # iShares MSCI South Korea ETF (1x)
    "koru":      0.25,  # Direxion Daily South Korea Bull 3X
    "futures":   0.25,  # KOSPI200 야간선물 (SGX/KRX)
    "us_market": 0.20,  # S&P500
}
OVERNIGHT_EWY_DIVISOR = 5.0       # 5% 변동 = signal ±1.0
OVERNIGHT_KORU_DIVISOR = 15.0     # 15% 변동 = signal ±1.0 (3x 레버리지)
OVERNIGHT_FUTURES_DIVISOR = 8.0   # 8% = 상한가 = signal ±1.0
OVERNIGHT_US_DIVISOR = 3.0        # 3% 변동 = signal ±1.0
OVERNIGHT_COHERENCE_BONUS = 1.3   # 전원 같은 방향 → 1.3x
OVERNIGHT_COHERENCE_PENALTY = 0.7 # 방향 혼재 → 0.7x

# V4: 개인 수급 패턴 임계값 (억원)
V4_CAPITULATION_PREV = 300   # 전일 대량 매수 기준
V4_CAPITULATION_CURR = 50    # 당일 급감 기준
V4_LARGE_BUY = 300           # 대량 매수 유지 기준
V4_DECLINE_RATIO = 0.3       # 매수 급감 비율

# V5: 신용잔고 모멘텀
V5_DIVISOR = 2.0             # ±2% 변화 → V5=±1.0

# VA: 거래량 증폭기
VA_FLOOR = 0.3               # 최소 배율
VA_CEILING = 2.0             # 최대 배율
VA_LOG_SCALE = 0.5           # log2 스케일링 계수

# RSPI Impact Function 파라미터 (RSPI 음수=매도일 때 적용)
RSPI_SENSITIVITY = 0.15           # |RSPI|=100일 때 매도 비율
RSPI_SIGMOID_K = 0.08             # sigmoid 기울기
RSPI_SIGMOID_MID = 50             # sigmoid 중점
RSPI_LIQUIDITY_FACTOR = 0.5       # 유동성 계수

# RSPI 7단계 레벨 (음수=매도, 양수=반등)
RSPI_LEVELS = [
    {"min": -100, "max": -40, "key": "extreme_sell",    "label": "극단 매도"},
    {"min": -40,  "max": -20, "key": "strong_sell",     "label": "강한 매도"},
    {"min": -20,  "max": -5,  "key": "mild_sell",       "label": "약한 매도"},
    {"min": -5,   "max": 5,   "key": "neutral",         "label": "중립"},
    {"min": 5,    "max": 20,  "key": "mild_rebound",    "label": "약한 반등"},
    {"min": 20,   "max": 40,  "key": "strong_rebound",  "label": "강한 반등"},
    {"min": 40,   "max": 100, "key": "extreme_rebound", "label": "극단 반등"},
]

# KOFIA API (공공데이터포털)
KOFIA_API_BASE = "https://apis.data.go.kr/1160100/service/GetFinaStatInfoSvc"
