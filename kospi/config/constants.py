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

# ── v2.0.0 RSPI 상수 (VLPI 대체) ──

# RSPI Cascade Force (CF) 가중치 — 가속력 4변수
RSPI_CF_WEIGHTS = {
    "cf1": 0.30,  # V1: 주의구간 코호트 비중
    "cf2": 0.25,  # V2: 연속 하락 심각도
    "cf3": 0.25,  # V3: 개인 수급 방향
    "cf4": 0.20,  # V4: 신용잔고 가속 모멘텀
}

# RSPI Damping Force (DF) 가중치 — 감쇠력 4변수
RSPI_DF_WEIGHTS = {
    "df1": 0.30,  # D1: 야간시장 반등 강도
    "df2": 0.20,  # D2: 신용잔고 유입률
    "df3": 0.25,  # D3: 외국인 매도 소진도
    "df4": 0.25,  # D4: 안전 코호트 버퍼
}

# D1: 야간시장 감쇠 4소스 가중치
OVERNIGHT_WEIGHTS = {
    "ewy":       0.30,  # iShares MSCI South Korea ETF (1x)
    "koru":      0.25,  # Direxion Daily South Korea Bull 3X
    "futures":   0.25,  # KOSPI200 야간선물 (SGX/KRX)
    "us_market": 0.20,  # S&P500
}
OVERNIGHT_EWY_DIVISOR = 5.0       # 5% 반등 = signal 1.0
OVERNIGHT_KORU_DIVISOR = 15.0     # 15% 반등 = signal 1.0 (3x 레버리지)
OVERNIGHT_FUTURES_DIVISOR = 8.0   # 8% = 상한가 = signal 1.0
OVERNIGHT_US_DIVISOR = 3.0        # 3% 반등 = signal 1.0

# RSPI Impact Function 파라미터
RSPI_SENSITIVITY = 0.15           # RSPI=100일 때 매도 비율
RSPI_SIGMOID_K = 0.08             # sigmoid 기울기
RSPI_SIGMOID_MID = 50             # sigmoid 중점
RSPI_LIQUIDITY_FACTOR = 0.5       # 유동성 계수 (단일값, 정책 분기 제거)

# RSPI 5단계 판정 기준
RSPI_LEVELS = {
    "critical":  40,   # +40~+100: 캐스케이드 위험
    "high":      20,   # +20~+40: 하락 우세
    "medium":     0,   # 0~+20: 약한 하락
    "low":      -20,   # -20~0: 균형~약한 반등
    # -100~-20: 반등 압력 → "none"
}

# ── (deprecated) VLPI 호환 상수 — vlpi_engine.py 참조용 ──
VLPI_DEFAULT_WEIGHTS = {
    "w1": 0.25, "w2": 0.10, "w3": 0.20,
    "w4": 0.20, "w5": 0.15, "w6": 0.10,
}
POLICY_SHOCK_MAP = {
    "credit_suspension_major": 1.0, "credit_suspension_minor": 0.5,
    "credit_tightening": 0.3, "short_selling_ban": 0.2,
    "regulator_warning": 0.4, "circuit_breaker_triggered": 0.8,
}
EWY_GAP_WEIGHTS = {"ewy": 0.6, "futures": 0.3, "fx": 0.1}
EWY_GAP_DIVISOR = 5.0
VLPI_SENSITIVITY = 0.15
VLPI_SIGMOID_K = 0.08
VLPI_SIGMOID_MID = 50
VLPI_POLICY_MULTIPLIER = 1.5
VLPI_LIQUIDITY_NORMAL = 0.5
VLPI_LIQUIDITY_CRISIS = 0.4

# KOFIA API (공공데이터포털)
KOFIA_API_BASE = "https://apis.data.go.kr/1160100/service/GetFinaStatInfoSvc"
