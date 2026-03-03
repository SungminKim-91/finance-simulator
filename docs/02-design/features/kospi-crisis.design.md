# Design: KOSPI Crisis Detector

> Feature: `kospi-crisis` | Version: 1.0.0 | Created: 2026-03-03
> Plan Reference: `docs/01-plan/features/kospi-crisis.plan.md`
> Spec Reference: `KOSPI_CRISIS_DETECTOR_SPEC v1.0`

---

## 1. Implementation Order

Phase 1을 먼저 완성한 뒤 Phase 2~4 순차 진행.

### Phase 1: Data Foundation + main.jsx + Tab A

| # | Task | File(s) | Depends |
|---|------|---------|---------|
| 1.1 | main.jsx 시뮬레이터 선택기 리팩토링 | `web/src/main.jsx` | - |
| 1.2 | KOSPI Python 의존성 설치 | `kospi/requirements.txt` | - |
| 1.3 | 과거 데이터 1회성 수집 | `kospi/scripts/fetch_historical.py` | 1.2 |
| 1.4 | 중국 2015 하드코딩 JSON | `kospi/data/historical/china_2015.json` | - |
| 1.5 | 일간 데이터 수집 파이프라인 | `kospi/scripts/fetch_daily.py` | 1.2 |
| 1.6 | 금투협 스크래퍼 | `kospi/scripts/kofia_scraper.py` | 1.2 |
| 1.7 | T+2 추정 로직 | `kospi/scripts/estimate_missing.py` | 1.5, 1.6 |
| 1.8 | 모델 연산 스크립트 | `kospi/scripts/compute_models.py` | 1.5 |
| 1.9 | Web 데이터 내보내기 | `kospi/scripts/export_web.py` | 1.8 |
| 1.10 | KospiApp 메인 + Tab A (Market Pulse) | `web/src/simulators/kospi/` | 1.9 |

### Phase 2: Cohort + Forced Liquidation + Tab B

| # | Task | File(s) | Depends |
|---|------|---------|---------|
| 2.1 | 코호트 모델 엔진 | `kospi/scripts/compute_models.py` (cohort) | Phase 1 |
| 2.2 | 반대매매 시뮬레이터 엔진 | `kospi/scripts/compute_models.py` (forced_liq) | 2.1 |
| 2.3 | Tab B (CohortAnalysis.jsx) | `web/src/simulators/kospi/` | 2.2 |

### Phase 3: Crisis Score + Historical + Tab C/D

| # | Task | File(s) | Depends |
|---|------|---------|---------|
| 3.1 | 위기 지표 13개 산출 + PCA | `kospi/scripts/compute_models.py` (crisis) | Phase 1 |
| 3.2 | 과거 사례 유사도 엔진 | `kospi/scripts/compute_models.py` (historical) | 1.3, 1.4 |
| 3.3 | Tab C (ScenarioTracker.jsx) | `web/src/simulators/kospi/` | 3.1 |
| 3.4 | Tab D (HistoricalComp.jsx) | `web/src/simulators/kospi/` | 3.2 |

### Phase 4: Bayesian Scenario Engine + Integration

| # | Task | File(s) | Depends |
|---|------|---------|---------|
| 4.1 | Bayesian 시나리오 엔진 | `kospi/scripts/compute_models.py` (scenario) | Phase 1 |
| 4.2 | 시나리오 관리 UI | Tab C 확장 | 4.1 |
| 4.3 | 전체 통합 테스트 | all | Phase 1~4 |

---

## 2. File Specifications

### 2.1 main.jsx — 시뮬레이터 선택기

```jsx
// web/src/main.jsx
import React, { useState, lazy, Suspense } from 'react';
import ReactDOM from 'react-dom/client';

// BTC (기존 — 직접 import, 코드 변경 없음)
import App from './App';
import AppV2 from './AppV2';

// KOSPI (lazy load)
const KospiApp = lazy(() => import('./simulators/kospi/KospiApp'));

const SIMULATORS = [
  { id: "btc", label: "BTC Liquidity", color: "#f59e0b" },
  { id: "kospi", label: "KOSPI Crisis", color: "#ef4444" },
  // 미래: { id: "us", label: "US Market", color: "#3b82f6" },
];

function Root() {
  const [sim, setSim] = useState("kospi");       // 기본: KOSPI
  const [btcVersion, setBtcVersion] = useState("v2");

  return (
    <>
      {/* 시뮬레이터 선택 바 — 화면 최상단 고정 */}
      <div style={simBarStyle}>
        {SIMULATORS.map(s => (
          <button key={s.id} onClick={() => setSim(s.id)} style={{
            background: sim === s.id ? s.color : "transparent",
            color: sim === s.id ? "#fff" : "#94a3b8",
            border: "none", borderRadius: 6, padding: "6px 16px",
            fontSize: 12, fontWeight: 700, cursor: "pointer",
            fontFamily: "'JetBrains Mono', monospace",
          }}>{s.label}</button>
        ))}

        {/* BTC 선택 시 v1/v2 서브토글 */}
        {sim === "btc" && (
          <div style={{ marginLeft: 8, display: "flex", gap: 2 }}>
            <button onClick={() => setBtcVersion("v1")} style={subToggle(btcVersion === "v1")}>v1</button>
            <button onClick={() => setBtcVersion("v2")} style={subToggle(btcVersion === "v2")}>v2</button>
          </div>
        )}
      </div>

      {/* 시뮬레이터 렌더링 */}
      {sim === "btc" && (btcVersion === "v1" ? <App /> : <AppV2 />)}
      {sim === "kospi" && (
        <Suspense fallback={<LoadingScreen />}>
          <KospiApp />
        </Suspense>
      )}
    </>
  );
}
```

**핵심 결정:**
- BTC 기존 코드(`App.jsx`, `AppV2.jsx`) 위치 변경 **없음** (Phase 5까지 유지)
- KOSPI는 `lazy()` import로 번들 분리
- 시뮬레이터 바는 `position: fixed, top: 0`
- BTC의 기존 v1/v2 토글은 서브토글로 축소

---

### 2.2 Python 데이터 수집

#### 2.2.1 kospi/scripts/fetch_daily.py

```python
"""
KOSPI 일간 데이터 수집 스크립트.

Usage:
    python kospi/scripts/fetch_daily.py                    # 오늘 데이터 수집
    python kospi/scripts/fetch_daily.py --date 2026-03-03  # 특정 날짜 수집
    python kospi/scripts/fetch_daily.py --range 2026-02-01 2026-03-03  # 범위 수집
"""

# === 인터페이스 ===

def fetch_market_data(date: str) -> dict:
    """D01, D09, D19, D22 — KOSPI/KOSDAQ OHLCV, 공매도, 시가총액, 거래대금
    Returns: { "kospi": {open,high,low,close,volume,trading_value_billion},
               "kosdaq": {...}, "kospi_market_cap_trillion": float }
    """

def fetch_stock_data(date: str, tickers: list[str]) -> dict:
    """D02~D03 — 삼성전자/SK하이닉스 OHLCV
    Returns: { "005930": {name,open,high,low,close,volume}, "000660": {...} }
    """

def fetch_investor_flows(date: str, tickers: list[str]) -> dict:
    """D04~D06 — 주체별 매매동향 (시장 + 종목별)
    Returns: { "market_total": {individual_billion, foreign_billion, institution_billion},
               "005930": {...}, "000660": {...} }
    """

def fetch_short_selling(date: str, tickers: list[str]) -> dict:
    """D09~D11 — 공매도 (시장 + 종목별)
    Returns: { "market_total_shares": int, "market_total_billion": float,
               "005930_shares": int, "000660_shares": int,
               "government_ban_active": bool }
    """

def fetch_global_data(date: str) -> dict:
    """D07, D08, D20, D21 — USD/KRW, WTI, VIX, S&P 500
    Returns: { "usd_krw": float, "wti": float, "vix": float, "sp500": float }
    """

def fetch_credit_data(date: str) -> dict:
    """D16~D17 — 종목별 신용잔고 (pykrx)
    Returns: { "005930": {credit_balance_billion}, "000660": {...} }
    """

def save_daily_snapshot(date: str, data: dict) -> Path:
    """저장: kospi/data/daily/{YYYY-MM-DD}.json"""

def append_timeseries(date: str, data: dict) -> None:
    """kospi/data/timeseries.json 에 append"""

def update_metadata(date: str) -> None:
    """kospi/data/metadata.json 업데이트"""
```

#### 2.2.2 kospi/scripts/kofia_scraper.py

```python
"""
금투협(KOFIA) 데이터 스크래핑.
D12~D15: 신용거래융자 잔고, 고객예탁금, 위탁매매 미수금, 반대매매 금액.
T+2 지연 — date 파라미터는 실제 데이터 기준일 (2영업일 전).

Usage:
    python kospi/scripts/kofia_scraper.py --date 2026-03-01
"""

KOFIA_BASE_URL = "https://freesis.kofia.or.kr"

def fetch_kofia_data(date: str) -> dict:
    """
    Returns: {
        "credit": { "total_balance_billion": float, "date": str },
        "deposit": { "customer_deposit_billion": float, "date": str },
        "settlement": {
            "unsettled_margin_billion": float | None,
            "forced_liquidation_billion": float | None,
            "date": str
        }
    }
    Raises: KofiaScrapingError on failure (caller handles fallback)
    """

def _scrape_credit_balance(date: str) -> float:
    """신용거래융자 잔고 (억원)"""

def _scrape_customer_deposit(date: str) -> float:
    """고객예탁금 (억원)"""

def _scrape_settlement(date: str) -> dict:
    """위탁매매 미수금 + 반대매매 금액 (억원)"""
```

#### 2.2.3 kospi/scripts/estimate_missing.py

```python
"""
T+2 지연 데이터 추정 모듈.
신용잔고/예탁금만 추정. 반대매매는 추정하지 않음.

추정 모델: Rolling OLS (10일 윈도우)
  ΔCredit_est = β0 + β1·(개인순매수/1조) + β2·(KOSPI수익률) + β3·(전일ΔCredit)
"""

def estimate_credit_balance(
    today_data: dict,           # 오늘 시장 데이터 (D01, D04)
    historical: list[dict],     # 최근 10일 시계열
) -> dict:
    """
    Returns: {
        "value": float,              # 추정 잔고 (억원)
        "estimated": True,
        "confidence_interval": [lower, upper],  # ±1σ
        "estimation_method": "rolling_OLS_10d"
    }
    """

def estimate_customer_deposit(
    today_data: dict,
    historical: list[dict],
) -> dict:
    """동일 구조 반환"""

def correct_estimate(
    date: str,
    actual_value: float,
    estimated_value: float,
) -> dict:
    """실측 도착 시 보정 + 오차 로그 기록
    Returns: { "date": str, "actual": float, "estimated": float,
               "error": float, "error_pct": float }
    """
```

#### 2.2.4 kospi/scripts/fetch_historical.py

```python
"""
과거 데이터 1회성 수집 (pykrx).
2008, 2011, 2020, 2021 한국 시장 데이터.

Usage:
    python kospi/scripts/fetch_historical.py           # 전체 수집
    python kospi/scripts/fetch_historical.py --case 2008  # 특정 사례만
"""

HISTORICAL_PERIODS = {
    "korea_2008": ("2007-01-01", "2009-12-31"),
    "korea_2011": ("2011-01-01", "2012-06-30"),
    "korea_2020": ("2019-06-01", "2020-12-31"),
    "korea_2021": ("2020-06-01", "2022-12-31"),
    "korea_2026": ("2025-01-01", "2026-12-31"),  # 현재
}

def fetch_historical_case(case_name: str, start: str, end: str) -> dict:
    """
    Returns: {
        "case_name": str,
        "period": { "start": str, "end": str },
        "peak": { "date": str, "kospi": float },
        "timeseries": [
            { "date": str, "kospi": float, "kospi_change_pct": float,
              "individual_billion": float, "foreign_billion": float,
              "institution_billion": float, "trading_value_billion": float,
              "market_cap_trillion": float }
        ]
    }
    저장: kospi/data/historical/{case_name}.json
    """
```

---

### 2.3 Python 모델 엔진

#### 2.3.1 compute_models.py 구조

```python
"""
KOSPI 모델 연산 메인 스크립트.
fetch_daily.py 이후 실행 — 수집된 데이터로 모델 산출.

Usage:
    python kospi/scripts/compute_models.py                    # 전체 모델 실행
    python kospi/scripts/compute_models.py --module cohort    # 코호트만
    python kospi/scripts/compute_models.py --module forced_liq --shock -5
"""

# === Module A: 코호트 모델 ===

class CohortBuilder:
    """신용잔고 코호트 생성/해소 엔진"""

    def __init__(self, mode: str = "LIFO"):
        self.mode = mode  # "LIFO" | "FIFO"
        self.active_cohorts: list[Cohort] = []
        self.closed_cohorts: list[Cohort] = []

    def process_day(self, date: str, credit_balance: float,
                    prev_credit: float, kospi: float,
                    samsung: float, hynix: float) -> None:
        """일간 코호트 업데이트"""
        delta = credit_balance - prev_credit
        if delta > 0:
            self._create_cohort(date, delta, kospi, samsung, hynix)
        elif delta < 0:
            self._repay_cohorts(abs(delta))

    def _create_cohort(self, date, amount, kospi, samsung, hynix):
        """새 코호트 생성"""

    def _repay_cohorts(self, amount):
        """LIFO/FIFO에 따라 코호트 상환"""

    def get_status(self, current_kospi: float) -> dict:
        """현재 모든 활성 코호트 상태 반환
        Returns: {
            "active": [{ cohort_id, entry_date, entry_kospi,
                         initial_amount_billion, remaining_amount_billion,
                         current_pnl_pct, collateral_ratio, status }],
            "price_distribution": [{ kospi_range, amount_billion,
                                     pnl_pct_avg, status }],
            "mode": "LIFO"|"FIFO",
            "total_active_billion": float
        }
        """

    def get_price_distribution(self, current_kospi: float,
                                bin_size: int = 500) -> list[dict]:
        """가격대별 코호트 분포 히스토그램"""


@dataclass
class Cohort:
    cohort_id: str           # 날짜 기반 ID (YYYY-MM-DD)
    entry_date: str
    entry_kospi: float
    entry_samsung: float
    entry_hynix: float
    initial_amount_billion: float
    remaining_amount_billion: float

    def pnl_pct(self, current_kospi: float) -> float:
        return (current_kospi - self.entry_kospi) / self.entry_kospi * 100

    def collateral_ratio(self, current_kospi: float,
                          margin_rate: float = 0.40) -> float:
        price_ratio = current_kospi / self.entry_kospi
        return price_ratio / (1 - margin_rate)

    def status(self, current_kospi: float, margin_rate: float = 0.40) -> str:
        ratio = self.collateral_ratio(current_kospi, margin_rate)
        if ratio >= 1.60: return "safe"
        if ratio >= 1.40: return "watch"
        if ratio >= 1.30: return "margin_call"
        return "forced_liq"


# === Module B: 반대매매 시뮬레이터 ===

MARGIN_DISTRIBUTION = {
    0.40: 0.35,  # A군 초우량
    0.45: 0.35,  # A군 우량
    0.50: 0.25,  # B군 중형주
    0.60: 0.05,  # 기타
}

MAINTENANCE_RATIO = 1.40      # 마진콜
FORCED_LIQ_RATIO = 1.30      # 즉시 반대매매

class ForcedLiqSimulator:
    """반대매매 연쇄 피드백 루프 시뮬레이터"""

    def run(self,
            cohorts: list[Cohort],
            initial_price: float,
            price_shock_pct: float,         # 예: -5.0
            max_rounds: int = 5,
            absorption_mode: str = "neutral",  # auto|conservative|neutral|optimistic|custom
            custom_absorption: float = 0.5,
            margin_distribution: dict = None,
            avg_daily_trading_value: float = 10_000,  # 억원
            impact_coefficient: float = 1.5,
    ) -> dict:
        """
        Returns: {
            "initial_price": float,
            "final_price": float,
            "total_drop_pct": float,
            "converged_at_round": int | None,
            "rounds": [{
                "round": int,
                "price": float,
                "forced_liq_billion": float,
                "margin_call_billion": float,
                "absorption_rate": float,
                "additional_drop_pct": float,
                "cumulative_drop_pct": float,
            }]
        }
        """

    def _compute_round(self, cohorts, price, margin_dist, absorption) -> dict:
        """단일 라운드 계산"""

    def _auto_absorption(self, individual_net_buy, trading_value,
                          gov_intervention: bool) -> float:
        """수급 기반 자동 흡수율 계산
        absorption = clip(individual_buy_ratio * 2, 0.1, 0.9)
        정부 개입 시 min 0.6
        """

    @staticmethod
    def compute_trigger_price(entry_price: float, margin_rate: float,
                               trigger_ratio: float = 1.40) -> float:
        """마진콜/강제청산 트리거 가격 역산
        trigger = entry * trigger_ratio * (1 - margin_rate)
        """


# === Module C: 위기 스코어 ===

CRISIS_INDICATORS = [
    "leverage_heat",       # I01: 신용잔고 / 시가총액
    "flow_concentration",  # I02: 개인순매수 / abs(외+기관)
    "price_deviation",     # I03: KOSPI / 200일 MA
    "credit_acceleration", # I04: 20일 신용 변화율
    "deposit_inflow",      # I05: 20일 예탁금 변화율
    "foreign_selling",     # I06: 20일 외국인 누적 순매도 / 거래대금
    "fx_stress",           # I07: 원달러 20일 변화율
    "short_anomaly",       # I08: |공매도 비중 - 20일 MA| / 20일σ
    "vix_level",           # I09: VIX 절대 + 변화율
    "volume_explosion",    # I10: 당일 거래대금 / 20일 MA
    "forced_liq_intensity",# I11: 반대매매 / 거래대금
    "credit_deposit_ratio",# I12: 신용잔고 / 예탁금
    "dram_cycle",          # I13: DRAM QoQ 전망
]

class CrisisScorer:
    """위기 점수 산출 엔진"""

    def compute_indicators(self, timeseries: pd.DataFrame) -> pd.DataFrame:
        """13개 지표 일간 계산
        Returns: DataFrame with date + 13 indicator columns
        """

    def normalize_percentile(self, indicators: pd.DataFrame) -> pd.DataFrame:
        """Historical percentile rank (0~100) 변환"""

    def compute_weights_pca(self, normalized: pd.DataFrame) -> dict:
        """PCA loadings 기반 가중치
        Returns: { indicator_name: weight }
        """

    def compute_score(self, normalized: pd.DataFrame,
                       weights: dict) -> pd.Series:
        """위기 점수 = Σ(weight_i × indicator_i), 0~100 스케일"""

    def classify(self, score: float) -> str:
        """0~50: normal, 50~70: caution, 70~85: warning,
           85~95: danger, 95+: extreme"""


# === Module D: 베이지안 시나리오 ===

class BayesianScenarioTracker:
    """시나리오 확률 일간 업데이트 엔진"""

    OBSERVATION_KEYS = [
        "foreign_daily_net_billion",
        "kospi_daily_return_pct",
        "usd_krw_level",
        "credit_daily_change_billion",
        "wti_level",
        "forced_liq_daily_billion",
    ]

    def __init__(self, scenarios_path: str):
        """kospi/data/scenarios.json 로드"""

    def update(self, today_observations: dict) -> list[dict]:
        """베이지안 업데이트 (log-sum-exp trick)
        Returns: 업데이트된 시나리오 목록 with probability_history
        """

    def identify_key_drivers(self, scenario: dict,
                              observations: dict) -> list[dict]:
        """상위 3개 영향 지표 식별
        Returns: [{ indicator, observed, expected_mean, z_score, direction }]
        """

    def save(self) -> None:
        """kospi/data/scenarios.json 저장"""


# === Module E: 과거 사례 비교 ===

class HistoricalComparator:
    """과거 사례 유사도 분석"""

    def compute_similarity(self, current_indicators: np.ndarray,
                            historical_cases: dict) -> dict:
        """DTW(60%) + Cosine(40%) 하이브리드 유사도
        Returns: { case_name: { dtw, cosine, hybrid, percentage } }
        """

    def prepare_overlay_data(self, cases: dict,
                              peak_date: str) -> list[dict]:
        """고점 대비 경과일 기준 오버레이 데이터
        Returns: [{ day_from_peak, case_name, change_pct }]
        """
```

#### 2.3.2 export_web.py

```python
"""
Python 모델 결과 → React 데이터 파일 내보내기.

Usage:
    python kospi/scripts/export_web.py
"""

def export_all() -> None:
    """
    읽기: kospi/data/timeseries.json + model_output.json + scenarios.json + historical/*.json
    쓰기: web/src/simulators/kospi/data/kospi_data.js

    출력 구조:
    export const MARKET_DATA = [...];       // 시계열 (date, kospi, samsung, hynix, ...)
    export const CREDIT_DATA = [...];       // 신용잔고, 예탁금, 반대매매
    export const INVESTOR_FLOWS = [...];    // 주체별 수급
    export const GLOBAL_DATA = [...];       // USD/KRW, WTI, VIX, S&P
    export const SHORT_SELLING = [...];     // 공매도
    export const COHORTS = {...};           // 코호트 분석 결과
    export const FORCED_LIQ_SIM = {...};    // 반대매매 시뮬레이션 기본 결과
    export const CRISIS_SCORE = {...};      // 위기 점수 + 지표별 값
    export const SCENARIOS = {...};         // 시나리오 확률 + 히스토리
    export const HISTORICAL = {...};        // 과거 사례 비교
    export const EVENTS = [...];            // 이벤트 로그
    export const META = {...};              // last_updated, data_quality
    """
```

---

### 2.4 React 컴포넌트 상세

#### 2.4.1 KospiApp.jsx — KOSPI 메인

```jsx
// web/src/simulators/kospi/KospiApp.jsx

const TABS = [
  { id: "pulse", label: "Market Pulse" },
  { id: "cohort", label: "Cohort & Forced Liq." },
  { id: "scenario", label: "Scenario Tracker" },
  { id: "history", label: "Historical Compare" },
];

export default function KospiApp() {
  const [tab, setTab] = useState("pulse");

  return (
    <div style={{ background: C.bg, minHeight: "100vh", paddingTop: 56 }}>
      {/* 공통 헤더: 위기점수 + KOSPI + 업데이트 시각 */}
      <KospiHeader />

      {/* 탭 바 */}
      <TabBar tabs={TABS} active={tab} onChange={setTab} />

      {/* 탭 콘텐츠 */}
      {tab === "pulse" && <MarketPulse />}
      {tab === "cohort" && <CohortAnalysis />}
      {tab === "scenario" && <ScenarioTracker />}
      {tab === "history" && <HistoricalComp />}
    </div>
  );
}
```

#### 2.4.2 KospiHeader.jsx — 공통 헤더

```jsx
// 화면 상단 고정 (시뮬레이터 선택 바 아래)
// 표시: 위기점수 게이지 | KOSPI 현재가+변동 | 삼전 | 하닉 | 환율 | 업데이트 시각
// estimated 데이터는 값 옆에 [추정] 뱃지

function KospiHeader() {
  // CRISIS_SCORE.current, MARKET_DATA의 마지막 행, META.last_updated 사용
  return (
    <div style={headerStyle}>
      <CrisisGauge score={CRISIS_SCORE.current} />
      <MetricCard label="KOSPI" value={latest.kospi} change={latest.kospi_change_pct} />
      <MetricCard label="삼성전자" value={latest.samsung} change={latest.samsung_change_pct} />
      <MetricCard label="SK하이닉스" value={latest.hynix} change={latest.hynix_change_pct} />
      <MetricCard label="USD/KRW" value={latest.usd_krw} change={latest.usd_krw_change_pct} inverted />
      <UpdateTime time={META.last_updated} />
    </div>
  );
}
```

#### 2.4.3 MarketPulse.jsx — Tab A

```jsx
// 레이아웃: 6개 섹션
// 1. 신용잔고 + 예탁금 시계열 (ComposedChart: Line×2 + Bar 반대매매)
//    - 기간 토글: 1M / 3M / 6M / 1Y / ALL
//    - 실측 = solid line, 추정 = dashed line + [추정] badge
// 2. 주체별 수급 (StackedBarChart: 개인/외국인/기관, 20일 누적 표시)
// 3. 공매도 현황 (LineChart + 정부조치 이벤트 ReferenceLine)
// 4. 글로벌 컨텍스트 (4개 미니차트: VIX, S&P500, WTI, USD/KRW)
// 5. DRAM 가격 추이 (LineChart: DDR5 스팟 + QoQ 전망)
// 6. 이벤트 로그 (최근 10개, 날짜 + 유형 + 설명)

// Props: 없음 (data import 직접 사용)
// State: period ("1M"|"3M"|"6M"|"1Y"|"ALL")
```

#### 2.4.4 CohortAnalysis.jsx — Tab B

```jsx
// 레이아웃: 3개 섹션
// 1. 코호트 분포 히트맵
//    - BarChart (horizontal): 가격대 × 잔고, 색상=status
//    - 각 바에 PnL%, 담보비율 표시
//    - [FIFO / LIFO] 토글 (데이터 재계산)
//
// 2. 반대매매 트리거 맵
//    - Table: KOSPI 하락 시나리오별 마진콜/강제청산 금액
//    - Price 슬라이더 (현재가 ~ -30%)
//
// 3. 연쇄 반대매매 시뮬레이터 (인터랙티브)
//    State:
//      shock: number (-1 ~ -30, default -5)
//      rounds: number (1~10, default 5)
//      absorptionMode: "auto"|"conservative"|"neutral"|"optimistic"|"custom"
//      customAbsorption: number (0.0~1.0)
//      marginDist: { 0.40: 0.35, 0.45: 0.35, 0.50: 0.25, 0.60: 0.05 }
//      simResult: null | SimResult
//
//    Controls:
//      - 초기 충격 슬라이더
//      - 라운드 슬라이더
//      - 흡수율 라디오 버튼 + 커스텀 인풋
//      - 증거금 분포 슬라이더 ×4
//      - [시뮬레이션 실행] 버튼
//
//    결과 차트:
//      - ComposedChart: X=라운드, Line=price, Bar=forced_liq
//      - 수렴 라운드 ReferenceLine
//
//    ** 시뮬레이션은 Python이 아닌 JS에서 직접 계산 (인터랙티브) **
//    ** COHORTS 데이터 + 사용자 파라미터 → 브라우저에서 즉시 계산 **

function runSimulation(cohorts, params) {
  // Python ForcedLiqSimulator와 동일한 로직을 JS로 구현
  // 이유: 슬라이더 조절 시 즉시 반응 필요 (서버 왕복 불가)
  const rounds = [];
  let price = params.initialPrice * (1 + params.shock / 100);

  for (let r = 1; r <= params.maxRounds; r++) {
    let forcedLiq = 0, marginCall = 0;
    for (const cohort of cohorts.active) {
      for (const [marginRate, weight] of Object.entries(params.marginDist)) {
        const ratio = (price / cohort.entry_kospi) / (1 - marginRate);
        if (ratio < 1.30) forcedLiq += cohort.remaining_amount_billion * weight;
        else if (ratio < 1.40) marginCall += cohort.remaining_amount_billion * weight;
      }
    }
    const absorption = params.absorptionMode === "custom"
      ? params.customAbsorption
      : ABSORPTION_PRESETS[params.absorptionMode];
    const sellPressure = forcedLiq * (1 - absorption);
    const impact = (sellPressure / params.avgTradingValue) * params.impactCoeff;
    price = price * (1 - impact);

    rounds.push({ round: r, price, forcedLiq, marginCall, absorption,
                   dropPct: impact * 100,
                   cumDropPct: (price / params.initialPrice - 1) * 100 });
    if (forcedLiq < 100) break; // 수렴
  }
  return { rounds, finalPrice: price };
}
```

#### 2.4.5 ScenarioTracker.jsx — Tab C

```jsx
// 레이아웃: 3개 섹션
// 1. 현재 확률 바 차트
//    - 4개 시나리오 horizontal bars (색상 구분)
//    - 각 바에 확률% + 변화 (↑↓)
//    - [+ 시나리오 추가] 버튼 (미래)
//
// 2. 확률 변화 시계열
//    - AreaChart (stacked): X=date, Y=0~100%
//    - 4개 시나리오 색상별 영역
//
// 3. 오늘의 Key Drivers
//    - 확률이 가장 많이 변한 시나리오의 top 3 원인 지표
//    - 지표명 + 관측값 + 예상(mean±std) + z_score + supporting/contradicting

// Props: 없음
// Data: SCENARIOS.current_probabilities, SCENARIOS.probability_history, SCENARIOS.key_drivers
```

#### 2.4.6 HistoricalComp.jsx — Tab D

```jsx
// 레이아웃: 3개 섹션
// 1. 유사도 점수
//    - BarChart (horizontal): 과거 사례별 유사도 %
//    - 색상: 유사도 높을수록 진한 색
//
// 2. 오버레이 시계열
//    - LineChart: X=고점 대비 경과일(D+0~D+60), Y=변화율%
//    - 현재 2026 = 굵은 실선
//    - 과거 사례 = 점선/대시 (체크박스로 선택)
//    State: selectedCases: string[] (체크박스)
//
// 3. 지표별 비교 테이블
//    - Table: 지표 × (현재 | 2015중국 | 2021한국 | 2008한국 | 2020한국)
//    - 위기 점수 행 강조

// Props: 없음
// Data: HISTORICAL.similarities, HISTORICAL.overlay_data, HISTORICAL.indicator_comparison
```

#### 2.4.7 공유 컴포넌트

```jsx
// shared/CrisisGauge.jsx
// Props: score: number (0~100)
// 원형 게이지, 색상: green(0~50) → yellow(50~70) → orange(70~85) → red(85+)
// 중앙에 숫자, 하단에 등급 텍스트

// shared/EstimatedBadge.jsx
// Props: estimated: boolean
// 조건부 렌더링: estimated일 때 작은 "[추정]" 뱃지 (점선 border, yellow text)

// shared/KospiHeader.jsx → 위 2.4.2 참조

// shared/MetricCard.jsx
// Props: label, value, change (%), inverted (환율 등 역방향), estimated
// 카드 형태: label 상단, value 중앙 (큰 폰트), change 하단 (색상: 상승=green, 하락=red)
```

---

### 2.5 색상 팔레트

```js
// web/src/simulators/kospi/colors.js
// BTC AppV2.jsx의 C 객체를 계승하면서 KOSPI 전용 색상 추가

export const C = {
  // 기본 (BTC와 공유)
  bg: "#020617", panel: "#0f172a", border: "#1e293b", borderHi: "#334155",
  text: "#e2e8f0", muted: "#94a3b8", dim: "#64748b",
  green: "#4ade80", red: "#f87171",

  // KOSPI 전용
  kospi: "#ef4444",           // 빨강 (메인 색상)
  samsung: "#3b82f6",         // 파랑
  hynix: "#8b5cf6",           // 보라
  individual: "#f59e0b",      // 노랑 (개인)
  foreign: "#06b6d4",         // 시안 (외국인)
  institution: "#10b981",     // 초록 (기관)
  credit: "#f97316",          // 주황 (신용잔고)
  deposit: "#22d3ee",         // 연시안 (예탁금)
  forcedLiq: "#dc2626",       // 진빨강 (반대매매)

  // 코호트 상태
  safe: "#4ade80",
  watch: "#facc15",
  marginCall: "#fb923c",
  danger: "#ef4444",

  // 시나리오
  s1: "#4ade80",  // 연착륙 (초록)
  s2: "#60a5fa",  // C방어 (파랑)
  s3: "#f97316",  // C붕괴 (주황)
  s4: "#ef4444",  // 전면위기 (빨강)
};
```

---

## 3. Data Schema

### 3.1 일간 스냅샷 (kospi/data/daily/{date}.json)

```json
{
  "date": "2026-03-03",
  "fetched_at": "2026-03-03T16:35:00+09:00",

  "market": {
    "kospi": { "open": 6033, "high": 6033, "low": 5726, "close": 5791,
               "volume": 1823456789, "trading_value_billion": 52530 },
    "kosdaq": { "open": null, "high": null, "low": null, "close": null },
    "kospi_market_cap_trillion": 2850.3
  },

  "stocks": {
    "005930": { "name": "삼성전자", "open": 209500, "high": 209500,
                "low": 192600, "close": 195100, "volume": 98234567 },
    "000660": { "name": "SK하이닉스", "open": 1050000, "high": 1050000,
                "low": 985000, "close": 1002000, "volume": 12345678 }
  },

  "investor_flows": {
    "market_total": { "individual_billion": 5800, "foreign_billion": -5150,
                      "institution_billion": -650 },
    "005930": { "individual_billion": null, "foreign_billion": null,
                "institution_billion": null },
    "000660": { "individual_billion": null, "foreign_billion": null,
                "institution_billion": null }
  },

  "credit": {
    "total_balance_billion": 32300,
    "estimated": true,
    "confidence_interval": [31800, 32800],
    "estimation_method": "rolling_OLS_10d"
  },

  "deposit": { "customer_deposit_billion": 119000, "estimated": true },

  "settlement": {
    "unsettled_margin_billion": null,
    "forced_liquidation_billion": null,
    "estimated": false
  },

  "short_selling": {
    "market_total_shares": 3388,
    "market_total_billion": 0.5,
    "005930_shares": null,
    "000660_shares": null,
    "government_ban_active": true
  },

  "global": { "usd_krw": 1467.5, "wti": 98.7, "vix": 32.5, "sp500": 5234.8 },

  "manual_inputs": {
    "dram_contract_price_qoq_pct": 5.2,
    "dram_spot_ddr5_8gb_usd": 3.85,
    "events": [
      { "date": "2026-03-03", "type": "government_action", "desc": "공매도 전면 금지 재발동" }
    ]
  }
}
```

### 3.2 시나리오 정의 (kospi/data/scenarios.json)

```json
{
  "scenarios": [
    {
      "id": "S1", "name": "연착륙",
      "description": "외국인 조기 복귀, 정부 개입 효과, 전쟁 단기 종결",
      "kospi_range": { "bottom": 5400, "top": 5800 },
      "prior_probability": 0.15,
      "current_probability": 0.03,
      "indicator_distributions": {
        "foreign_daily_net_billion": { "mean": -1.5, "std": 1.0 },
        "kospi_daily_return_pct": { "mean": -1.0, "std": 2.0 },
        "usd_krw_level": { "mean": 1430, "std": 30 },
        "credit_daily_change_billion": { "mean": -200, "std": 300 },
        "wti_level": { "mean": 85, "std": 10 },
        "forced_liq_daily_billion": { "mean": 200, "std": 150 }
      },
      "probability_history": []
    }
  ]
}
```

### 3.3 모델 출력 (kospi/data/model_output.json)

```json
{
  "computed_at": "2026-03-03T16:40:00+09:00",
  "cohorts": {
    "active": [],
    "price_distribution": [],
    "mode": "LIFO",
    "total_active_billion": 6035
  },
  "crisis_score": {
    "current": 78,
    "classification": "warning",
    "indicators": {},
    "weights": {},
    "history": []
  },
  "forced_liq_default": {
    "shock_pct": -5,
    "rounds": [],
    "final_price": 5109,
    "converged_at": 5
  },
  "historical_similarity": {}
}
```

---

## 4. Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| 반대매매 시뮬레이션 위치 | **JS (브라우저)** | 슬라이더 조절 시 즉시 반응 필요, 서버 왕복 불가 |
| 코호트 계산 위치 | **Python** | 시계열 전체 처리 + LIFO/FIFO 복잡 로직 |
| BTC 코드 이동 시점 | **Phase 5** | 현재 작동 중인 코드 건드리지 않음 |
| 데이터 포맷 | **JSON (static import)** | 기존 BTC data.js 패턴과 동일, Vite HMR 호환 |
| 과거 데이터 수집 | **pykrx (자동)** + 중국 2015 (수동) | pykrx가 2000년대까지 지원 |
| 위기 스코어 가중치 | **PCA → 백테스팅** | BTC 모델과 동일 방법론 |
| 시나리오 확률 | **Bayesian (정규분포)** | 일간 점진적 업데이트, 해석 용이 |

---

## 5. Verification Checklist

### Phase 1 완료 기준 ✅ (v1.0.0 완료)
- [x] `main.jsx` 시뮬레이터 선택기: BTC ↔ KOSPI 전환 작동
- [x] `python kospi/scripts/fetch_daily.py` 정상 실행 (D01~D22)
- [x] `python kospi/scripts/fetch_historical.py` 과거 4개 사례 수집
- [x] `kospi/data/daily/*.json` 스냅샷 생성
- [x] `python kospi/scripts/export_web.py` → `kospi_data.js` 생성
- [x] Tab A (Market Pulse) 정상 렌더링: 숫자 카드, 시계열, 수급 차트
- [x] BTC 기존 대시보드 regression 없음
- [x] 독립 좌/우 Y축 줌 (Credit/Deposit)
- [x] Y축 단위 표시 (조원/억원/십억원) + Tooltip 단위 포매팅
- [x] 투자자 수급 리디자인: 누적 Area / 일자별 Line+Area 토글, 필터, 요약 카드
- [x] 빌드 에러 없음 (Vite production build 통과)

### Phase 2 완료 기준
- [ ] 코호트 모델: LIFO/FIFO 정상 작동, 가격대 분포 출력
- [ ] 반대매매 시뮬레이터: 5라운드 내 수렴, JS 인터랙티브
- [ ] Tab B: 히트맵 + 트리거 맵 + 시뮬레이터 UI 작동

### Phase 3 완료 기준
- [ ] 13개 위기 지표 산출, PCA 가중치
- [ ] 과거 사례 유사도 (DTW + Cosine) 산출
- [ ] Tab C: 시나리오 확률 바 + 시계열
- [ ] Tab D: 오버레이 차트 + 비교 테이블

### Phase 4 완료 기준
- [ ] Bayesian 업데이트 정상 작동 (일간)
- [ ] Key Drivers 식별
- [ ] 전체 4탭 통합 테스트 통과
