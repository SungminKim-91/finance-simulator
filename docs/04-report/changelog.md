# KOSPI Crisis Detector — Changelog

## [2026-03-04] - v4.1 Real Data Source Integration

### Added
- **ECOS API Integration** (`ecos_fetcher.py`): 한국은행 802Y001 일간 데이터 (KOSPI/KOSDAQ, 외국인 순매수, 거래량/대금, 시가총액)
- **Naver Finance Scraper** (`naver_scraper.py`): 고객예탁금 + 신용잔고 일간 스크래핑 (억원 단위, 294페이지 페이지네이션)
- **KRX Auth Module** (`krx_auth.py`): KRX 로그인 세션 관리 + pykrx 세션 주입
- **dotenv Integration**: `.env` 파일에서 API 키 자동 로드

### Changed
- **fetch_daily.py**: 5단계 통합 파이프라인 (env → KRX → ECOS → Naver → yfinance → merge)
- **build_snapshot()**: ECOS/Naver 데이터 수신, 우선순위 체인 (ECOS > yfinance, Naver > None)
- **run_range()**: 배치 조회 후 날짜별 병합 (기존: yfinance 단독)
- **Data fill rate**: Credit 0%→99%, Deposit 0%→99%, Foreign 0%→100%, Trading Value 0%→100%

### Known Issues
- **pykrx Investor Flows**: KRX API 포맷 변경으로 individual/institution 데이터 미수신 (foreign은 ECOS fallback)
- **PublicDataReader**: requirements에 추가되었으나 미사용

### Verified
- 282일 데이터 저장 (2025-01-01 ~ 2026-03-04)
- compute_models + export_web + vite build 성공
- **Match Rate: 93%** (Gap Analysis PASS)

---

## [2026-03-04] - v1.4 Loop B Refactoring + Loop C Cascade

### Added
- **Loop C (Fund Redemption Cascade)**: T+1~T+3 delayed cascade for 3,000~4,000억 estimated redemption volume
- **S5 Scenario (Fundamental Collapse)**: DRAM negative + AI capex reduction scenario (2,500~3,200 KOSPI range, 4% probability)
- **4 New Crisis Score Indicators**: credit_suspension (12%), institutional_selling (10%), retail_exhaustion (8%), bull_trap (4%)
- **Defense Walls (5-Stage System)**: Retail buying → Institution support → BOK FX intervention → US currency swap → IMF assistance
- **LOOP_STATUS Module**: Real-time tracking of Loop A (margin call waves) and Loop C (fund redemption)
- **CrisisAnalysis.jsx Component**: 6-section dashboard with Gauge, Breakdown, Scenarios, Drivers, Loops, Defense Walls
- **10 New TERM Dictionary Entries**: loop_c, defense_wall, observation_only, wave_pattern, absorption_rate_dynamic, etc.

### Changed
- **CRISIS_SCORE Weights**: Redistributed 13→14 indicators, new weights sum = 1.00
  - leverage_heat: 0.10, flow_concentration: 0.08, price_deviation: 0.09, credit_acceleration: 0.08, deposit_inflow: 0.05
  - vix_level: 0.06, volume_explosion: 0.05, forced_liq_intensity: 0.08, credit_deposit_ratio: 0.04, dram_cycle: 0.03
  - **NEW**: credit_suspension: 0.12, institutional_selling: 0.10, retail_exhaustion: 0.08, bull_trap: 0.04
- **SCENARIOS Probabilities**: S1=0% (deprecated), S2=8%, S3=55%, S4=33%, S5=4% (new), total = 100%
- **Historical Indicator Comparison**: Added 4 new indicators (credit_suspension, institutional_selling, retail_exhaustion, bull_trap)
- **TERM Dictionary**: 4 entries updated (fx_loop deprecated, fx_stress/foreign_selling/short_anomaly observation-only or removed)

### Removed
- **Loop B (FX-Foreign Investor Feedback Loop)**: Accuracy 50%, replaced with institutional selling metric
- **3 Unreliable Indicators**: fx_stress (observation-only), foreign_selling (observation-only), short_anomaly (removed)
- **Obsolete TERM Entries**: short_anomaly completely deleted, fx_loop marked deprecated

### Fixed
- Institution selling magnitude -5,887억 properly attributed to Loop C fund redemption
- Defense wall capacity indicators reflect actual crisis state (wall1, wall2, wall4 collapsed/destroyed)
- Crisis score weights sum validation (1.00 ✓)
- Scenario probability sum validation (1.00 ✓)

### Verified
- 8/8 validation tests passed (weights, probabilities, structure, colors, terms)
- npm build successful with new CrisisAnalysis component
- Runtime errors: 0
- **Match Rate: 100%** (Design vs Implementation)

---

## [2026-02-28] - v1.1.0 Phase 2 UX Enhancement (Previous Release)

### Added
- **CohortAnalysis.jsx**: 3-section cohort analysis with LIFO/FIFO toggle
- **Loop Status Cards**: Loop A (margin call) and Loop B (FX feedback) visualization
- **Defense Wall Placeholder**: 5-stage system scaffold (detailed in v1.4)
- **Korean Terms Expansion**: 4 new TERM definitions for cohort mechanics
- **fmtBillion Helper**: Trillion/billion KRW unit formatter

### Changed
- **Font Size**: Global increase 1-2px for readability
- **Unit Consistency**: All flows → fmtBillion() (조원/억원)
- **FX Removal**: Trigger map expected_fx column deleted (v1.4 complete removal in design)
- **Simulator Simplification**: Loop A fixed, Loop B deprecated, preset scenarios (−5%, −15%, −30%)
- **Absorption Rate**: Auto calculation from recent 5-day retail buy ratio

### Verified
- Phase 1 (Market Pulse) v1.0.2 Chart 가독성 improved
- Phase 2 (Cohort) v1.1.0 complete with 98.9% match rate

---

## [2026-02-10] - v1.0.2 Chart Readability Enhancement

### Changed
- **Y-Axis Zoom**: Domain-only (RAF + CSS transform), no SVG distortion
- **DateRangeControl**: Unified global date range with 양방향 synchronization
- **Legend Formatting**: TermLabel components with inline hover tooltips
- **Tooltip Values**: fmtBillion standardization across all charts

---

## [2026-01-28] - v1.0.1 Y-Axis Zoom UX Redesign

### Added
- **Domain-Only Y-Axis Zoom**: Drag + wheel support with clean visual
- **Credit Y-Axis Independence**: Separate zoom for left (credit) / right (deposit) axes
- **Forced Liquidation Overlay**: Area fill with threshold markers

---

## [2026-01-15] - v1.0.0 Phase 1 Market Pulse Dashboard

### Added
- **KospiApp.jsx**: 4-tab router (Pulse/Cohort/Scenario/History)
- **KospiHeader.jsx**: Persistent header (KOSPI, Samsung, Hynix, USD/KRW, VIX)
- **MarketPulse.jsx**: 1,350-line dashboard
  - Credit balance & customer deposit (independent Y-axis zoom)
  - Forced liquidation (area + threshold)
  - Investor flows (cumulative area / daily grouped bar toggle)
  - Short selling + government action event markers
  - Global context mini-charts (start/end + change %)
  - DRAM placeholder
  - Event log
- **colors.js**: KOSPI-specific palette (KOSPI, Samsung, Hynix, flows, status)
- **terms.jsx**: Korean financial term dictionary with hover tooltips
- **kospi_data.js**: Sample data structure (MARKET_DATA, CREDIT_DATA, INVESTOR_FLOWS, GLOBAL_DATA, SHORT_SELLING, COHORT_DATA)
- **Python Pipeline**: kospi/scripts/ (fetch_daily, fetch_historical, kofia_scraper, compute_models, export_web)

### Verified
- Phase 1 implementation match rate: 100%
- All interactive components tested
- Data pipeline fallback chains working

---

## Document Status

| Version | Date | Status | Completeness |
|---------|------|--------|--------------|
| **4.1** | 2026-03-04 | Approved | 93% (Real data source integration) |
| **1.4** | 2026-03-04 | Approved | 100% (All phases: Plan/Design/Do/Check/Report) |
| 1.1.0 | 2026-02-28 | Archived | 98.9% (Phase 2 UX) |
| 1.0.2 | 2026-02-10 | Archived | 100% (Chart readability) |
| 1.0.1 | 2026-01-28 | Archived | 100% (Y-axis zoom) |
| 1.0.0 | 2026-01-15 | Archived | 100% (Phase 1 launch) |

---

**Last Updated**: 2026-03-04 19:40:00 KST
