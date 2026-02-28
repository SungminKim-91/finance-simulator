"""환경변수 로드 및 글로벌 설정 — v2.0"""
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# .env 로드
load_dotenv()

# ── Project Root ──
PROJECT_ROOT = Path(__file__).parent.parent

# ── API Keys ──
FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")

# ── Data Range ──
DATA_START: str = "2016-01-01"      # 전체 데이터 시작
DATA_END: str = datetime.now().strftime("%Y-%m-%d")  # v2.0: 동적 (현재 날짜)
WARMUP_MONTHS: int = 12             # 12m MA warm-up
EFFECTIVE_START: str = "2017-01-01"  # 유효 기간 시작 (warm-up 후)

# ── Frequency (v2.0) ──
DEFAULT_FREQ: str = "monthly"  # "daily" | "weekly" | "monthly"

# ── Paths ──
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
INDICES_DIR = DATA_DIR / "indices"          # v2.0: 인덱스 결과
VALIDATION_DIR = DATA_DIR / "validation"    # v2.0: 검증 결과
SCORES_DIR = DATA_DIR / "scores"
LOG_DIR = DATA_DIR / "logs"
CHARTS_DIR = DATA_DIR / "charts"

# 디렉토리 자동 생성
for d in [RAW_DIR, PROCESSED_DIR, INDICES_DIR, VALIDATION_DIR,
          SCORES_DIR, LOG_DIR, CHARTS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Cache ──
CACHE_EXPIRY_HOURS: int = 24  # 캐시 유효 시간 (시간)
