# Finance Simulator — Multi-Asset Analysis Platform

> BTC Liquidity (v2.1) + KOSPI Crisis Detector (v1.2.0) | 통합 웹 대시보드

## Project Overview
1. **BTC Liquidity Model**: 글로벌 유동성 지표(5개 변수) 기반 BTC 가격 방향성 선행 예측
2. **KOSPI Crisis Detector**: 한국 주식시장 신용잔고 코호트 분석, 반대매매 시뮬레이션, 위기 감지

통합 프론트엔드 (`web/`) 에서 시뮬레이터 선택기로 BTC/KOSPI 전환.

## v2.1 — Dual-Band Web Dashboard

### 핵심 개선
- **Variable-specific Winsorize (Option H)**: NL±3σ, HY±2.5σ, GM2±2σ, CME±2σ
- **HY 기반 Sign Correction**: NL→HY 변경 (경제 논리: 유동성↑ → HY↓)
- **Dual-Band Architecture**: Structural(4-var PCA, shifted) + Tactical(-HY, realtime)
- **Combined Signal**: 0.7×Structural + 0.3×EMA(Tactical) 합성

### Dual-Band 모델 (Model D)
| Band | 구성 | 역할 | Lag |
|------|------|------|-----|
| **Structural** | PCA(NL, GM2, HY, CME) + Option H clip | 전체 유동성 주기 | shifted by lag |
| **Tactical** | -HY_z → EMA smoothed | 빠른 신용위험 신호 | realtime (no shift) |
| **Combined** | 0.7×Struct + 0.3×EMA(Tact) | 합성 신호 | hybrid |

### 성능
- Structural: r=+0.491, MDA=64.7% (lag=0 기준)
- Tactical: r=+0.417, MDA=65.9%
- Pipeline CWS: 0.606, All r > 0

### Web Dashboard (AppV2.jsx)
- 4탭: Index vs BTC, Loadings, CWS Profile, Robustness
- 컨트롤: Lag 슬라이더(0-15m), Tactical 토글, Combine 토글, Smooth 슬라이더(2-12m)
- v1.0 ↔ v2.0 전환 버튼 (main.jsx Root 컴포넌트)

## v2.0.0 — 3-Stage Pipeline (Completed, Match Rate 92%)

### 핵심 철학
- **독립 구성 원칙**: BTC를 절대 보지 않고 유동성 인덱스를 독립 구성 → 사후 검증
- **방향성 매칭**: 상관계수(r)보다 방향 일치(MDA)가 핵심 — score 상승 시 BTC도 상승
- **과적합 거부**: Grid Search 짜맞추기 대신 PCA/ICA/DFM 비지도 학습으로 구성
- **Phase 1c 기준**: r=0.318이지만 모든 lag에서 양의 상관, 방향 100% 일치가 진짜 성공

### 3-Stage Pipeline
1. **Stage 1 — 독립 인덱스 구성** (BTC-blind): PCA, ICA, DFM, Sparse PCA
2. **Stage 2 — 방향성 검증**: MDA, SBD, Cosine Similarity, Kendall Tau → CWS 복합 메트릭
3. **Stage 3 — 과적합 방지**: Bootstrap CI, CPCV (45-path), Granger Causality, Wavelet Coherence

### v1.0.0 Known Issues
- NL 가중치 0.5 하락 (유동성 메인 변수가 보조지표급)
- SOFR binary weight=-4.0 → score -16 spike (lag=0에서 r=-0.077)
- Grid Search 88,209 조합으로 BTC에 과적합
- Walk-Forward OOS 변동성 높음 (Std=0.5873)

### 주요 변경사항 (v1.0 → v2.0)
- SOFR: Binary(0/1) → Logistic smooth transition + Markov Regime
- 혼합 주기: 월간 집계 → DFM+Kalman 일간 그리드
- 최적화: Grid Search → 비지도 학습 (PCA/ICA/DFM)
- 검증: Pearson r → CWS (MDA+SBD+CosSim+Tau)
- 데이터: ~2025-12 → ~2026-02 (DATA_END 업데이트)

## v1.0.0 Results
- **In-Sample Correlation**: 0.6176
- **Optimal Lag**: 9개월
- **Walk-Forward OOS**: 9 windows, mean=0.246
- **Best Weights**: NL=0.5, GM2=0.0, SOFR=-4.0, HY=-0.5, CME=0.0
- **Design-Implementation Match Rate**: 93% (PASS)

## Core Variables (v4.0)
1. **NL Level** — Net Liquidity (WALCL - TGA - RRP), 미국 유동성
2. **GM2 Residual** — 미국 외 글로벌 유동성 (직교화)
3. **SOFR Binary** — 위기 감지 (SOFR - IORB > 20bps)
4. **HY Spread Level** — 신용 스프레드, 위험선호 (FRED BAMLH0A0HYM2)
5. **CME Basis** — 기관 포지셔닝 (선물-현물 연율화)

## Key Design Principles
- BTC를 target으로 직접 최적화 금지 — 유동성 지수 독립 구성 → 사후 검증
- 파형 매칭: `corr(score, log₁₀(BTC))` 최대화
- 12m MA detrend → z-score 표준화
- 과적합 방지: 변수 수 × 15 <= 데이터 포인트

## Tech Stack
**v1.0**: Python 3.12 | uv (venv) | pandas | fredapi | yfinance | scipy | matplotlib | SQLite
**v2.0 추가**: statsmodels (DFM, MarkovRegression) | sklearn (PCA, ICA, FastICA) | pycwt (Wavelet Coherence) | tslearn (DTW, SBD) | skfolio (CPCV) | tsbootstrap (Block Bootstrap)

## Data Sources
- FRED API: WALCL, RRP, SOFR, IORB, M2/M3 시리즈, HY Spread
- Treasury Fiscal Data API: TGA (키 불필요, dual filter for 2021-10 변경)
- Yahoo Finance: DXY, BTC, CME BTC Futures
- CoinGecko/Binance: BTC 현물 fallback

## CLI
```bash
# === v1.0 호환 명령 ===
python main.py fetch           # 데이터 수집만
python main.py optimize        # v1.0 Grid Search (deprecated)
python main.py score           # 현재 Score만 계산
python main.py visualize       # 차트 생성 (overlay/correlation/walkforward/xcorr/bootstrap/comparison/wavelet/all)
python main.py status          # 모델 상태 확인

# === v2.0 신규 명령 ===
python main.py build-index     # Stage 1: 인덱스 구성 (BTC-blind)
python main.py validate        # Stage 2: 방향성 검증
python main.py analyze         # Stage 3: 과적합 분석
python main.py run             # 전체 3-Stage 파이프라인
python main.py compare         # 4개 방법 비교 (PCA/ICA/SparsePCA/DFM)

# === 공통 옵션 ===
--freq daily|weekly|monthly    # 타임스케일 (기본: monthly)
--method pca|ica|dfm|sparse|all # 인덱스 방법 (기본: pca)
```

## Key Implementation Notes
- FRED EU_M2/JP_M2: 원본 M2 단종 → M3 대체 (MABMM301EZM189S, MABMM301JPM189S)
- TGA: 2021-10 기점 account_type 명칭 변경 → dual filter 대응
- 날짜 정규화: 모든 변수 MonthEnd(0)로 통일 후 merge (FRED 월초 vs resample 월말 불일치 방지)
- 캐시: 24h 만료, 만료 캐시 fallback 지원

## v2.0.0 Implementation Summary
- **신규 모듈**: 14개 (index_builders 4, validators 4, robustness 3, pipeline 1, visualization 2)
- **수정 파일**: 5개 (config 2, requirements, storage, main.py)
- **총 코드**: ~3,200줄 (25파일)
- **Fallback chains**: ICA→PCA, SparsePCA→PCA, DFM→PCA (pipeline crash 방지)
- **CLI v2.0**: 5개 신규 명령 + `--method all` + `--type wavelet`

---

## KOSPI Crisis Detector v1.2.0

### Overview
신용잔고 기반 코호트 분석, 반대매매 연쇄 시뮬레이션, 코호트 백테스트, 신뢰도 대시보드를 하나의 대시보드에서 수행. Phase 1 (Market Pulse) + Phase 2 (Cohort & Forced Liquidation) + Phase 2.5 (Backtest & Margin Reform) 완료.

### Phase 1 구현 범위 (v1.0.0 → v1.0.2)
- **main.jsx**: 시뮬레이터 선택기 (BTC ↔ KOSPI), ErrorBoundary, lazy import
- **KospiApp.jsx**: 4탭 라우팅 (Pulse/Cohort/Scenario/History), KospiHeader 통합
- **KospiHeader.jsx**: 공통 헤더 (KOSPI, 삼전, 하닉, USD/KRW, VIX) — 탭 전환 시에도 항상 표시
- **MarketPulse.jsx**: 시장 현황 대시보드 (1350줄)
  - **DateRangeControl**: Period 버튼(1M/3M/6M/1Y/ALL) + 날짜 입력(년/월/일) + Brush 양방향 동기화
  - 신용잔고 & 고객예탁금 (독립 좌/우 Y축 줌, 조원 단위)
  - 반대매매: Area Fill + Threshold 위험 기준선 (억원 단위)
  - 투자자 수급: 누적 Area / 일자별 Grouped Bar 토글, 개인+금투/외국인/기관 필터, 요약 카드
  - 공매도 + 정부 조치 이벤트 마커
  - 글로벌 컨텍스트 미니차트 4개 (시작/끝값 + 변동률%)
  - DRAM (Phase 2 placeholder)
  - 이벤트 로그
- **colors.js**: KOSPI 전용 색상 팔레트 (BTC 계승 + 확장)
- **Python 파이프라인**: `kospi/scripts/` (fetch_daily, fetch_historical, kofia_scraper, compute_models, estimate_missing, export_web)
- **kospi/config/constants.py**: 공용 상수 (경로, 종목, 날짜형식, 모델 파라미터, 위기지표)

### Phase 2 구현 범위 (v1.1.0)
- **CohortAnalysis.jsx**: Tab B 코호트 & 반대매매 (703줄, 3 섹션)
  - **Section 1 코호트 분포**: LIFO/FIFO 토글, 가격대별 수평 Stacked Bar (안전/주의/마진콜/위험 4색), 요약 카드 (총 잔고, 안전비율, 위험비율)
  - **Section 2 트리거맵**: 가이드 박스 + 한글 자기설명적 헤더 (마진콜(추가 입금 요구 D+2), 반대매매(강제 청산)), 6단계 하락 시나리오, fmtBillion 단위
  - **Section 3 시뮬레이터**: 반대매매 연쇄 시뮬레이션 (Loop A 고정), 시나리오 프리셋 (-5%/-15%/-30%), Auto 흡수율 (수급 기반), TradingView volume 차트, 라운드별 결과 테이블
- **shared/terms.jsx**: TERM 6개 추가 (shock_pct, expected_kospi, forced_liq, loop_a, initial_shock, max_rounds), fmtBillion 헬퍼, TermHint 컴포넌트
- **data/kospi_data.js**: COHORT_DATA export (buildCohorts LIFO/FIFO, price_distribution, trigger_map, params)
- **compute_models.py**: CohortBuilder (get_price_distribution, get_trigger_map), ForcedLiqSimulator (dual-loop 지원)

### v1.1.0 주요 개선 (Phase 2 UX)
- **한글화**: 전체 UI 한글(영어) 이중 표기, 가이드 박스 3개 추가
- **단위 통일**: B/십억원 → fmtBillion() 조원/억원
- **FX 제거**: 트리거맵 expected_fx 컬럼 삭제, 시뮬레이터 Loop B/AB 삭제 (정부 개입 변수 노이즈)
- **시뮬레이터 간소화**: Loop A 고정, 외국인 매도 제거, 시나리오 프리셋 3개
- **Auto 흡수율**: 최근 5일 개인+금투 매수비율 기반 자동 계산
- **TradingView volume**: 반대매매 Bar 하단 30%, KOSPI Line protagonist
- **폰트 증가**: 전체 1-2px 증가 (9→11, 10→12, 13→15)

### v1.2.0 — Backtest Simulator + Margin Reform
- **담보비율 단일 기준 (v1.4.1)**: 상위 5개 증권사 일괄 — 보증금 45%, 담보유지 140%, 청산임계 손실 39%, D+2 미납 시 D+3 반대매매
  - 분포 기반 제거 → 단일 고정값. 손실 39%↑ 코호트 자동 제거(반대매매 확정)
- **백테스트 모드**: 281일 중 임의 거래일 선택 → 충격% 입력 → 시뮬 vs 실제 D+1~D+5 비교
- **코호트 히스토리**: COHORT_HISTORY export (201코호트 × 281일 일별 스냅샷, ~745KB)
- **급변동일**: BACKTEST_DATES export (40건, |일간변동| > 2%)
- **ReliabilityDashboard**: 40건 일괄 시뮬 → 방향 정확도, RMSE, 산점도
- **BacktestComparison**: 듀얼 라인 차트 + 비교 테이블 + 역산 흡수율
- **신용거래 실태 조사**: 95%+ 개별주식, ETF 거의 없음, 대형주 집중 → 모델 한계 UI 명시
- **TERM 8개 추가**: backtest, implied_absorption, direction_accuracy 등
- **kospi_data.js**: 15 exports (기존 13 + COHORT_HISTORY + BACKTEST_DATES), ~899KB

### 차트 기능
- **niceScale**: 깔끔한 Y축 눈금 자동 계산
- **Y축 줌 (Domain-only)**: Drag + Wheel 지원, domain만 변경 (SVG 찌그러짐 없음)
- **DateRangeControl**: 글로벌 날짜 범위 (Period 버튼 + DateField + Brush) — 양방향 동기화
- **독립 줌**: Credit 좌/우축 독립 줌 (creditLeftZoom/creditRightZoom)
- **단위 표시**: Y축 라벨 (조원/억원) + Tooltip fmtBillion/fmtTooltipVal 포매팅
- **투자자 수급**: 누적 Area / 일자별 Grouped Bar 토글 + 개인+금투/외국인/기관 필터 + 요약 카드
- **용어 사전**: shared/terms.jsx — 한국어 금융 용어 hover tooltip (TERM dictionary + TermLabel + TermHint)

### 폴더 구조
```
kospi/                           # Python 데이터 파이프라인
├── scripts/                     # fetch_daily, kofia_scraper, compute_models, export_web, ...
├── data/historical/             # 과거 사례 (2008, 2015 중국, 2020, 2021)
└── config/constants.py          # 공용 상수 (경로, 종목, 모델 파라미터)

web/src/simulators/kospi/        # React 대시보드
├── KospiApp.jsx                 # 4탭 메인 + KospiHeader 통합
├── KospiHeader.jsx              # 공통 헤더 (탭 전환 시 유지)
├── MarketPulse.jsx              # Tab A: 시장 현황 (1350줄)
├── CohortAnalysis.jsx           # Tab B: 코호트 & 반대매매 + 백테스트 + 신뢰도 (~1400줄)
├── colors.js                    # 색상 팔레트
├── data/kospi_data.js           # 정적 JSON 데이터 (15 exports: MARKET_DATA~BACKTEST_DATES, ~899KB)
└── shared/                      # 공유 컴포넌트
    └── terms.jsx                # 용어 사전 (TERM), fmtBillion, TermLabel, TermHint, CustomLegend, CustomTooltipContent
```

### Phase 4.1 구현 범위 (v4.1 — Real Data Source Integration)
- **ecos_fetcher.py**: ECOS 802Y001 일간 데이터 (6개 항목코드: KOSPI/KOSDAQ/외국인/거래량/거래대금/시가총액)
- **naver_scraper.py**: Naver Finance sise_deposit 스크래핑 (고객예탁금 + 신용잔고, 억원, 294페이지)
- **krx_auth.py**: KRX 로그인 세션 + pykrx webio monkey-patch
- **fetch_daily.py 통합**: 5단계 파이프라인 (env → KRX → ECOS → Naver → yfinance → merge)
- **데이터 우선순위**: ECOS > yfinance (지수), pykrx > ECOS (외국인), Naver (예탁금/신용잔고)
- **실적**: 282일, Credit 99%, Deposit 99%, Foreign 100%, Trading Value 100%
- **환경변수**: `ECOS_API_KEY`, `KRX_USER_ID`, `KRX_USER_PW` (`.env`)

### Phase 4.2~5 (미구현, 향후)
- **Phase 4.2**: pykrx 대체 투자자 수급 소스 (individual/institution 데이터)
- **Phase 5**: Deploy (GitHub Actions cron, Vercel)

---

## PDCA Status
- **btc-liquidity-model v1.0.0**: Archived (Match Rate 93%) → `docs/archive/2026-03/btc-liquidity-model/`
- **btc-liquidity-v2 v2.0.0**: Archived (Match Rate 92%, 1 iteration) → `docs/archive/2026-03/btc-liquidity-v2/`
- **web-dashboard v1.0.0**: Completed (Match Rate 93.5%, 1 iteration)
- **web v2.1 dual-band**: Archived (Match Rate 97.4%) → `docs/archive/2026-03/web/`
- **kospi-crisis v1.0.2**: Completed (Phase 1 차트 가독성, Match Rate 100%)
- **kospi-crisis-phase2 v1.1.0**: Completed (Phase 2 UX 전면 개선, Match Rate 98.9%)
- **kospi-phase4.1-data-sources v4.1**: Completed (ECOS+Naver+KRX 실데이터 통합, Match Rate 93%)
- **kospi-crisis-v1.1.1-bugfix**: Completed (Naver investor, 코호트 bugfix, UI개선, Match Rate 100%)
- **kospi-crisis-v1.2.0**: Completed (백테스트 시뮬레이터 + 담보비율 분포 개편 + 신뢰도 대시보드)
- **Archive**: docs/archive/2026-03/

## Backlog
- **kospi-stock-weight-model**: 종목별 가중 모델 — 상위 20종목 신용잔고 추적 → 지수 가중 합산 (v1.3.0)
- **gm2-data-improvement**: 2025년 lag=6 불일치 개선 — GM2 데이터 고착(11개월), HY 단기 충격, BTC 독자 요인 → `docs/01-plan/features/gm2-data-improvement.plan.md`
- **kospi-crisis Phase 5**: Deploy (GitHub Actions cron + Vercel) — `docs/01-plan/features/kospi-crisis.plan.md`
