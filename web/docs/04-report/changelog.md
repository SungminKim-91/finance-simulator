# KOSPI Crisis Detector — Changelog

## [2026-03-06] - v2.1.2 KOFIA 자동 다운로드 + crontab 자동화

### Added
- **kofia_downloader.py**: Playwright headless 브라우저로 FreeSIS "한눈에 보는 자본시장통계" EXCEL 자동 다운로드
  - `--auto`: 다운로드 → 파싱 → timeseries 머지 → export_web → archive 이동 (원스텝)
  - `--headful`: 브라우저 표시 디버깅 모드
- **kofia_cron.sh**: crontab wrapper (venv 활성화 + 로그 + 30일 자동 로테이션)
- **crontab 등록**: 평일 KST 18:00 자동 실행 (`0 18 * * 1-5`)
- **`/auto-kospi` 슬래시 명령어**: Claude Code 내 수동 1회 실행

### Fixed
- **kofia_excel_parser.py**: `read_only=True` → `False` (eXbuilder6 엑셀 dimensions 미인식 버그)
- **kofia_downloader.py**: auto import 완료 후 `kofia_excel_archive/`로 자동 이동

### Verified
- 다운로드: FreeSIS SPA 접속 → 메뉴 클릭 → EXCEL저장 (4초)
- 파싱: 6개 필드, 2개 날짜 (deposit, unsettled, forced_liq, credit_balance, kospi, trading_value)
- 전체 파이프라인: download → parse → merge → export_web → archive 정상 동작

---

## [2026-03-06] - v2.1.0 RSPI 실데이터 통합 + Raw Data 전면 확장

### Added
- **RSPI 전체 히스토리**: 262일 일별 RSPI 계산, 과거 기준일 선택 시에도 RSPI 대시보드 작동
- **`--backfill` 명령**: yfinance만 1회 배치 다운로드로 change_pct 경량 패치 (ECOS/Naver/KRX 호출 없음)
- **RawDataTable 전면 확장**: 7개 그룹 33컬럼 (시장/신용/투자자/글로벌/야간/공매도/RSPI)
  - 그룹 토글 버튼으로 컬럼 표시/숨기기
  - 데이터 커버리지 통계 (필드별 데이터 존재 비율)
  - CSV 다운로드 (전체 33컬럼)
- **GLOBAL_DATA 야간 데이터**: ewy_close, ewy_change_pct, koru_close, koru_change_pct, sp500_change_pct

### Changed
- **탭 비활성화**: 위기분석(Crisis), 과거비교(History) → greyed out + "(준비중)" (코드 보존)
- **D1 커버리지**: 2/262일 → 193/262일 (73.7%)

### Fixed
- **fetch_daily.py**: change_pct `break` 위치 수정 (NaN 거래일 조기 종료 방지)
- **fetch_daily.py**: yfinance 시작일 7일 확장 (전일 종가 lookback)
- **compute_models.py**: overnight D-1~D-3 lookback (최신 레코드 None 대응)
- **compute_models.py**: RSPI 전체 timeseries 루프 (latest-only → 262일)

### Verified
- npm build successful
- RSPI history: 262일, cascade_risk: none=187, low=68, medium=7
- Git: 596211b, 6380b27

---

## [2026-03-06] - v2.0.0 RSPI (Retail Selling Pressure Index)

### Added
- **VLPI→RSPI 전면 전환**: 단방향(0~100) → 양방향(-100~+100)
- **CF(가속력) 4변수**: V1 주의구간비중, V2 연속하락, V3 개인수급, V4 신용가속
- **DF(감쇠력) 4변수**: D1 야간회복(4소스 coherence), D2 신용유입, D3 외국인소진, D4 안전완충
- **rspi_engine.py**: 660줄 신규
- **프론트엔드**: RSPIGauge + DualBreakdown + ImpactTable + ScenarioMatrix 전면 재작성

### Verified
- **Match Rate: 98.7%** (PDCA archived)

---

## [2026-03-05] - v1.6.0 VLPI Frontend Dashboard + Date-Aware Cohort

### Added
- **CohortRiskMap**: 게이지 + 변수분해 시각화, 6단계 코호트 색상
- **기준일 선택**: 전 섹션 연동
- **Seed Cohort 수정**: 16.7T → 32.2T
- **종목별 신용잔고**: 날짜 인식 (date-aware)

### Changed
- **Section 3 시뮬레이터**: 비활성화 (v1.6.1, 수급기반 흡수율 불안정)

### Verified
- **Match Rate: 98.6%** (PDCA archived)

---

## [2026-03-05] - v1.5.0 VLPI Backend Engine

### Added
- **VLPI (Voluntary Liquidation Pressure Index)**: 반대매매→자발적 투매 패러다임 전환
- **2단계 아키텍처**: Pre-VLPI(6변수→0~100) + Sigmoid Impact Function
- **6단계 상태 분류**: debt_exceed→forced_liq→margin_call→caution→good→safe
- **담보비율 공식**: `현재가 / (매수가 × LOAN_RATE)` (LOAN_RATE=0.55)
- **vlpi_engine.py**: ~380줄, kofia_fetcher.py (3-tier stub)

### Verified
- **Match Rate: 99.1%** (1 iteration, PDCA archived)

---

## [2026-03-05] - v1.4.0 자동청산 + 백테스트 코호트 차트

### Added
- **코호트 자동청산**: 담보비율 기반 forced_w 비율만큼 amount 감산
- **MiniCohortChart**: 백테스트 기준일 코호트 바 차트 (위험 우선 표시)
- **청산비율 tooltip**: liquidated_pct > 0일 때 잔여비율 표시

### Verified
- Git: 42e9f61

---

## [2026-03-04] - v1.3.0 종목별 가중 모델 (Stock-Weight Cohort)

### Added
- **종목별 코호트**: 상위 10종목 신용잔고 추적, 시가총액 기반 가중 합산
- **portfolio_beta**: 종목별 beta 가중 합산 (삼성 1.30, 하닉 1.76)
- **stock_credit**: Naver 시가총액 비중 프록시

### Verified
- Git: 94ed02d

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
| **2.1.0** | 2026-03-06 | Current | RSPI 실데이터 + Raw Data 확장 |
| **2.0.0** | 2026-03-06 | Archived | 98.7% (RSPI 양방향 모델) |
| **1.6.0** | 2026-03-05 | Archived | 98.6% (VLPI Frontend) |
| **1.5.0** | 2026-03-05 | Archived | 99.1% (VLPI Backend) |
| **1.4.0** | 2026-03-05 | Approved | 자동청산 + 백테스트 차트 |
| **1.3.0** | 2026-03-04 | Approved | 종목별 가중 모델 |
| 1.4 | 2026-03-04 | Approved | 100% (Loop refactoring) |
| 1.2.0 | 2026-03-04 | Approved | 백테스트 + 담보비율 |
| 1.1.0 | 2026-02-28 | Archived | 98.9% (Phase 2 UX) |
| 1.0.2 | 2026-02-10 | Archived | 100% (Chart readability) |
| 1.0.1 | 2026-01-28 | Archived | 100% (Y-axis zoom) |
| 1.0.0 | 2026-01-15 | Archived | 100% (Phase 1 launch) |

---

**Last Updated**: 2026-03-06 KST
