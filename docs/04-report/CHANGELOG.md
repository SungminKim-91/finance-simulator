# Changelog — Finance Simulator

## [KOSPI v1.2.0] - 2026-03-04

### Cohort Backtest Simulator + Margin Reform — 신용거래 실태 조사 반영

#### Background
- 코호트 시뮬레이터에 과거 검증(백테스트) 기능 부재 → 모델 신뢰도 확인 불가
- 담보비율 단일 threshold (130%/140%) → 증권사/종목군별 실제 분포 미반영
- 한국 신용거래 실태 조사: 95%+ 개별주식, 대형주 집중, ETF 거의 없음

#### Added
- **백테스트 모드**: 281일 중 임의 거래일 선택 → 충격% 입력 → 시뮬 vs 실제 D+1~D+5 비교
- **코호트 히스토리**: 201코호트 × 281일 일별 스냅샷 (COHORT_HISTORY export, ~745KB)
- **급변동일 자동 식별**: |일간변동| > 2% → 40건 (BACKTEST_DATES export)
- **BacktestComparison 컴포넌트**: 듀얼 라인 차트 (시뮬 vs 실제), 비교 테이블, 역산 흡수율
- **ReliabilityDashboard**: 40건 일괄 시뮬 → 방향 정확도%, RMSE%, 산점도
- **TERM 8개**: backtest, implied_absorption, direction_accuracy, backtest_rmse 등
- **위험 코호트 요약**: 백테스트 기준일 선택 시 위험/마진콜/주의 코호트 태그 표시
- **모델 한계 명시**: "개별주식 기반 신용거래의 KOSPI 지수 근사치" 가이드 박스

#### Changed
- **담보비율 분포 개편**: 증거금률 40~60%, 유지비율 A군 140%~D군 160%, 강제청산 120%~140%
- **시뮬레이션 엔진**: 단일 threshold → 3개 분포 가중 곱 (MARGIN × MAINTENANCE × FORCED_LIQ)
- **코호트 접기/더보기**: 접기 버튼이 펼친 상태에서도 표시되도록 수정
- **export_web.py**: 13→15 exports (COHORT_HISTORY, BACKTEST_DATES)

#### Data
- kospi_data.js: 324KB → 899KB (+575KB, COHORT_HISTORY + BACKTEST_DATES)

#### Documents
- Report: `docs/04-report/features/kospi-crisis-v1.2.0.report.md`

---

## [KOSPI v1.1.1] - 2026-03-04

### 투자자 수급 Naver 스크래퍼 + 코호트 bugfix + UI 개선

#### Summary
v4.1 실데이터 통합 후 발견된 5개 이슈 수정.

#### Documents
- Report: `docs/04-report/features/kospi-crisis-v1.1.1-bugfix.report.md`

---

## [KOSPI v1.1.0] - 2026-03-04

### Phase 2 UX 전면 개선 — Cohort & Forced Liquidation 초보자 친화

#### Background
- Phase 2 (Cohort & Forced Liquidation) 첫 구현 후 5라운드 사용자 피드백 반영
- 영어 전용 UI → 한글(영어) 이중 표기, 단위 통일, 가이드 박스 추가
- FX(환율) 예측 완전 제거 (정부 개입 변수로 노이즈 과다)

#### Added
- **가이드 박스 3개**: 코호트 분포, 트리거 맵, 반대매매 시뮬레이터 각 섹션에 한글 개념 설명
- **시나리오 프리셋**: "소폭 조정 -5%" / "급락 -15%" / "대폭락 -30%" 원클릭 버튼
- **Auto 흡수율**: 최근 5일 개인+금투 매수 비율 기반 자동 계산 (설계문서 반영)
- **fmtBillion() 헬퍼**: 십억원 raw → 조원/억원 표시 변환 (shared/terms.jsx)
- **TERM 6개 추가**: shock_pct, expected_kospi, forced_liq, loop_a, initial_shock, max_rounds
- **TermHint 컴포넌트**: 테이블 헤더용 "?" hover tooltip (범용)

#### Changed
- **트리거맵 헤더**: 영어 → 한글 자기설명적 ("마진콜 (추가 입금 요구 D+2)")
- **시뮬레이터 Loop Mode**: A/B/AB → **A (반대매매) 고정** (엔진 코드 보존)
- **차트 스타일**: 반대매매 Bar → TradingView volume 스타일 (하단 30%, opacity 0.35)
- **KOSPI Line**: strokeWidth 2→2.5, dot r 3→4 (protagonist)
- **전체 폰트**: 1-2px 증가 (SectionTitle 13→15, 가이드 12-13, 테이블 12, 안내 11)
- **단위 통일**: B/십억원 → fmtBillion() 조원/억원 (코호트·트리거맵·시뮬레이터)
- **Tooltip**: `cursor={false}` 하얀 박스 제거
- **TERM 3개 수정**: margin_call desc 보강, collateral_ratio, forced_liq 범위 명시

#### Removed
- **expected_fx 컬럼**: 트리거맵에서 완전 삭제
- **Loop B (환율 연쇄)**: 시뮬레이터 UI에서 제거 (엔진 보존)
- **Loop A+B Combined**: UI에서 제거
- **Foreign Sell**: 결과 카드·테이블에서 제거
- **Final FX 카드**: 시뮬레이션 결과에서 제거

#### Documents
- Plan: `docs/01-plan/features/kospi-crisis-v1.1.0.plan.md`
- Report: `docs/04-report/features/kospi-crisis-v1.1.0.report.md`
- Gap Analysis: `docs/03-analysis/kospi-crisis-phase2.analysis.md`

---

## [v2.1.0] - 2026-03-02

### Dual-Band Web Dashboard (Model D) — Match Rate 97.4%

#### Background
- v2.0 Pipeline(CWS=0.606)을 브라우저에서 시각 검증하고 싶은 요구
- NL 주도 구조적 유동성 + HY 즉각 신용위험을 분리하여 볼 수 있는 인터랙티브 대시보드 필요
- 스파이크 진단에서 변수별 극단값 처리 필요성 발견

#### Added
- **Dual-Band Architecture (Model D)**: Structural(4-var PCA, shifted) + Tactical(-HY, realtime)
- **Combined Signal**: 0.7×Structural + 0.3×EMA(Tactical) 합성 라인
- **Variable-specific Winsorize (Option H)**: NL±3σ, HY±2.5σ, GM2±2σ, CME±2σ
- **AppV2.jsx** (717줄): 4-tab dashboard (Index, Loadings, CWS Profile, Robustness)
- **export_v2_web.py** (302줄): pipeline JSON → data_v2.js 변환 + dual-band 계산
- **Interactive Controls**: lag slider(0-15m), tactical toggle, combine toggle, smoothing slider(2-12m)
- **v1/v2 Version Toggle**: main.jsx Root 컴포넌트
- **Cross-Correlation Heatmap**: 클릭으로 lag 설정
- **Live Stats**: Pearson r, MDA 실시간 재계산
- **MODEL_DEVELOPMENT.md**: 모델 개발 전체 과정 정리 문서

#### Changed
- **Sign Correction**: NL 기반 → HY 기반 (경제 논리: 유동성↑ → HY↓)
- **runner_v2.py**: uniform winsorize → variable-specific clip_map
- **pca_builder.py**: sign_correction에 `positive` 파라미터 추가

#### Performance
- Structural: r=+0.491, MDA=64.7% (lag=0)
- Tactical: r=+0.417, MDA=65.9% (lag=0)
- Pipeline CWS: 0.606, All r > 0

#### PDCA Results
- **Match Rate**: 97.4% (PASS, 0 iterations)
- **Plan Match**: 96% (27항목 중 20 exact + 5 enhanced + 2 partial)
- **Dual-Band Extensions**: 100% (10/10)
- **Added Beyond Plan**: 12개 추가 기능

#### Documents
- Analysis: `docs/03-analysis/web.analysis.md`
- Report: `docs/04-report/web.report.md`
- Model Development: `docs/MODEL_DEVELOPMENT.md`

---

## Archive Notice (2026-03-01)

PDCA 완료 문서가 아카이빙되었습니다:
- **btc-liquidity-model v1.0.0** → `docs/archive/2026-03/btc-liquidity-model/`
- **btc-liquidity-v2 v2.0.0** → `docs/archive/2026-03/btc-liquidity-v2/`

아카이브 인덱스: [`docs/archive/2026-03/_INDEX.md`](../archive/2026-03/_INDEX.md)

---

## [v2.0.0] - 2026-03-01

### BTC Liquidity v2 — 3-Stage Pipeline 완료 (Match Rate 92%)

#### Background
- v1.0.0의 Grid Search가 BTC에 과적합 (88,209 조합 직접 최적화)
- NL 가중치 0.5 하락, SOFR binary -16 spike, lag=0 방향 불일치
- Phase 1c (PCA 독립 구성)가 r=0.318이지만 모든 lag 양의 상관 → 방향성 원칙에 부합

#### Added
- **3-Stage Pipeline**: 독립 인덱스 구성 → 방향성 검증 → 과적합 방지
- **4개 Index Builder** (BTC-blind): PCA, ICA, SparsePCA, DFM (Kalman Filter)
- **CWS 복합 메트릭**: 0.4×MDA + 0.3×(1-SBD) + 0.2×CosSim + 0.1×Tau
- **Robustness 3종**: Bootstrap CI, CPCV (45-path), Deflated Test
- **Granger Causality**: 양방향 검정 (Index→BTC 유의, BTC→Index 비유의)
- **Wavelet Coherence**: pycwt 기반 주파수 영역 분석
- **SOFR Smooth Transition**: Logistic sigmoid + Markov Regime (binary 대체)
- **CLI v2.0**: build-index, validate, analyze, run, compare 5개 명령
- **Fallback Chains**: ICA→PCA, SparsePCA→PCA, DFM→PCA (안정성 보장)
- **Direction Match Visualization**: plot_index_vs_btc() 방향 매칭 시각화

#### Changed
- **최적화 방식**: Grid Search (88K 조합) → 비지도 학습 (PCA/ICA/DFM)
- **검증 메트릭**: Pearson r → CWS (방향성 + 파형 매칭)
- **SOFR 처리**: Binary(0/1) → Logistic smooth transition + Markov Regime
- **DATA_END**: 2025-12 → dynamic (datetime.now())
- **config/constants.py**: v2.0 파라미터 84줄 추가

#### New Tech Stack
- statsmodels (DFM, MarkovRegression, Granger, ADF)
- sklearn (PCA, FastICA, SparsePCA)
- pycwt (Wavelet Coherence)
- tslearn (SBD reference, 실제 FFT 자체 구현)

#### PDCA Results
- **Design-Implementation Match Rate**: 92% (PASS, 1 iteration)
- **Initial Check**: 88.5% → Fallback chains + CLI + Visualization 수정 → 92%
- **New Modules**: 14개 (25파일, ~3,200줄)
- **Gap Resolution**: 6/12 gaps resolved (남은 6개 non-blocking)

#### Remaining TODOs (v2.1)
- [ ] 테스트 파일 4개 (test_index_builders, test_validators, test_robustness, test_pipeline_v2)
- [ ] save_bootstrap() 전용 StorageManager 메서드
- [ ] SOFR pre-2018 edge cases (IOER fallback)
- [ ] DFM 일간 데이터 full integration (현재 monthly fallback)
- [ ] 실 데이터로 성공 기준 검증 (MDA>0.6, all lag positive, etc.)

#### Documents
- Plan: `docs/01-plan/features/btc-liquidity-v2.plan.md`
- Design: `docs/02-design/features/btc-liquidity-v2.design.md`
- Analysis: `docs/03-analysis/btc-liquidity-v2.analysis.md`
- Report: `docs/04-report/features/btc-liquidity-v2.report.md`

---

## [v1.0.0] - 2026-03-01

### BTC Liquidity Prediction Model 완료

#### Added
- **완전한 데이터 파이프라인**: FRED, Treasury, Yahoo Finance, CoinGecko, Binance API 통합
- **5개 변수 모델**: NL (Net Liquidity), GM2 Residual, SOFR Binary, HY Spread, CME Basis
- **최적화 엔진**: Grid Search (5변수 × lag 0-9개월) + Walk-Forward 검증
- **CLI 인터페이스**: 7가지 명령어 (fetch, calculate, optimize, run, score, visualize, status)
- **시각화 3종**: Score vs BTC overlay, Correlation heatmap, Walk-Forward results
- **저장소**: SQLite + JSON 이중 저장 + CSV 중간 저장
- **캐싱 시스템**: 24h 캐시 만료, API 호출 최소화
- **에러 처리**: 10가지 시나리오 대응 (95% 커버)

#### Changed
- **Orthogonalization 순서**: Z-score → Ortho (설계) → Ortho → Z-score (구현, 통계적으로 정확)
- **EU_M2/JP_M2 FRED 시리즈**: M2(설계) → M3(구현) [가용성 문제로 변경, 재검토 필요]
- **Treasury API 필터**: 단일 필터 → 이중 필터 (2021년 API 변경 대응)

#### Improved
- **Cache 만료 시스템**: 설계에 없던 추가 기능 (데이터 신선도)
- **Date normalization**: MonthEnd 정규화로 merge 정합성 향상
- **Processed data CSV 저장**: 디버깅/시각화 지원
- **NaN Score defense**: DB 안정성 강화
- **CME Basis clipping**: 극단값(±200%) 방지
- **Pipeline exception handling**: 전체 try-except + logger.error

#### Results
- **In-Sample Correlation**: 0.6176 (v3 대비 +52%)
- **Optimal Lag**: 9개월 (설계 기대: 4-7개월, 범위 초과)
- **Walk-Forward OOS**: Mean=0.2460, Std=0.5873, Best=0.8104 (변동성 높음)
- **Design Match Rate**: 93% (PASS, >= 90%)
- **Module Coverage**: 22/22 = 100%
- **Function Signature Match**: 46/51 = 90%

#### Known Issues
- ⚠️ EU_M2/JP_M2 FRED 시리즈 M2→M3 변경 (원본 단종 불가피, 모델 재검증 필요)
- ⚠️ Walk-Forward OOS 변동성 높음 (윈도우 크기 재검토 필요)
- ⚠️ Optimal lag가 설계 범위 초과 (모델 특성 분석 필요)

#### TODO (v1.1)
- [ ] EU_M2/JP_M2 FRED 시리즈 최종 확정
- [ ] `calculate` CLI 명령 추가
- [ ] Signal case 통일 (lowercase vs UPPERCASE)
- [ ] Walk-Forward 분석 (OOS 변동성 최소화)
- [ ] Test suite (unit + integration)
- [ ] Logging enhancement
- [ ] Documentation (README, API docs)
- [ ] Performance optimization (Grid Search 병렬화)

---

## Development Notes

### Architecture Highlights
- **5-Layer Design**: Fetchers → Calculators → Optimizers → Pipeline → Visualization
- **Modular Structure**: 22 files, 51 functions, config-driven
- **Data Flow**: FETCH → CALCULATE (+ ORTHO) → ZSCORE → OPTIMIZE → SCORE → STORE → VIZ

### Tech Stack
- **Language**: Python 3.12 + uv venv
- **Data**: pandas 2.x, numpy 2.x, scipy
- **APIs**: fredapi, yfinance, requests
- **DB**: SQLite + JSON
- **Viz**: matplotlib, seaborn

### Key Constants
- Data range: 2016-01 ~ 2025-12 (9+ years)
- Grid Search: 5 variables × 10 lag values = ~500k combinations
- Walk-Forward: 8 windows (expanding), 60m train + 6m test
- Overfitting safety: 108 months ÷ 5 variables = 21.6:1 ratio (target >= 15:1)

---

**Latest Report**: [btc-liquidity-model.report.md](./btc-liquidity-model.report.md)
