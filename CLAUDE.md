# Finance Simulator — Multi-Asset Analysis Platform

> BTC Liquidity (v2.1) + KOSPI Crisis Detector (v2.1.2) | 통합 웹 대시보드

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

## KOSPI Crisis Detector v1.5.0

### Overview
신용잔고 기반 코호트 분석 + VLPI(Voluntary Liquidation Pressure Index) 자발적 투매 압력 모델. Phase 1 (Market Pulse) + Phase 2 (Cohort) + Phase 2.5 (Backtest) + Phase 3 (Stock-Weight) + Phase 4 (VLPI Backend) 완료.

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

### v1.5.0 — VLPI Backend Engine (자발적 청산 압력 지수)
- **핵심 철학 전환**: 반대매매 중심 → **자발적 투매(VLPI)** 모델. 2026.03.04 삼성전자 -11.74% 폭락에서 마진콜 코호트 0개 → 반대매매로 설명 불가, 공포 매도가 핵심
- **VLPI 2단계 아키텍처**:
  - Stage 1: Pre-VLPI (6변수 → 0~100 스코어)
  - Stage 2: Impact Function (Pre-VLPI → Sigmoid → 매도비율 → Kyle's Lambda 가격영향)
- **6단계 상태 분류**: debt_exceed → forced_liq → margin_call → caution → good → safe
- **Match Rate**: 99.1% (1 iteration)

### v1.6.0 — VLPI Frontend Dashboard + Date-Aware Cohort
- **CohortRiskMap**: 게이지 + 변수분해 시각화, 6단계 코호트 색상
- **기준일 선택**: 전 섹션 연동, Seed Cohort 수정(16.7T→32.2T)
- **Section 3 시뮬레이터**: 비활성화 (v1.6.1)
- **종목별 신용잔고**: 날짜 인식 (date-aware stock credit)
- **Match Rate**: 98.6%

### v2.0.0 — RSPI (Retail Selling Pressure Index)
- **VLPI→RSPI 전면 전환**: 단방향(0~100) → **양방향(-100~+100)** 모델
- **CF(가속력) 4변수**: V1 주의구간비중, V2 연속하락, V3 개인수급, V4 신용가속
- **DF(감쇠력) 4변수**: D1 야간회복(EWY+KORU+선물+미증시 4소스 coherence), D2 신용유입, D3 외국인소진, D4 안전완충
- **rspi_engine.py**: 660줄 신규, calc_rspi + 8개 변수 함수 + Impact Function
- **프론트엔드**: RSPIGauge + DualBreakdown + ImpactTable 전면 재작성
- **Match Rate**: 98.7%

### v2.1.0 — RSPI 실데이터 통합 + Raw Data 전면 확장
- **RSPI 전체 히스토리**: 262일 일별 RSPI 계산 (과거 기준일 선택 시에도 대시보드 작동)
- **야간 데이터 backfill**: `--backfill` 명령 (yfinance only, ECOS/Naver/KRX API 없이 5초)
  - D1 커버리지: 2/262 → 193/262 (73.7%)
- **fetch_daily.py 버그 수정**: change_pct break 위치, yfinance 7일 lookback, D-1~D-3 overnight lookback
- **Raw Data 테이블 전면 확장**: 7개 그룹 33컬럼 (시장/신용/투자자/글로벌/야간/공매도/RSPI)
  - 그룹 토글 버튼, 데이터 커버리지 통계, CSV 다운로드
- **탭 비활성화**: 위기분석/과거비교 탭 greyed out (코드 보존, 준비중 표시)
- **GLOBAL_DATA 확장**: ewy_close, ewy_change_pct, koru_close, koru_change_pct, sp500_change_pct 추가

### v2.2.0 — RSPI 5변수 + Volume Amplifier
- **RSPI 전면 재설계**: CF/DF 8변수 → 5변수(V1~V5) + Volume Amplifier
  - V1: 코호트 proximity (마진콜 근접도)
  - V2: 외국인 z-score (3일 누적 매도 강도)
  - V3: 야간 회복 (EWY+KORU+S&P500+선물 4소스 coherence)
  - V4: 개인 수급 패턴 (순매도 전환 + 가속도)
  - V5: 신용 모멘텀 (잔고 변화율)
- **Volume Amplifier**: 거래량 폭증 시 RSPI 증폭 (1.0~1.5x)
- **Impact Function**: Sigmoid → Kyle's Lambda 가격영향
- **프론트엔드**: RSPIGauge + DualBreakdown + ImpactTable + V1~V5 색상/용어
- **Match Rate**: 97.6% (1 iteration)

### v2.2.1 — Minor Fix (데이터 정합성 + Pending 상태)
- **KOFIA 거래대금 단위 수정**: divisor 10→1000 (백만원→십억원, 100x 과대 버그)
- **yfinance 거래량 제거**: ^KS11 volume 단위 불일치 → ECOS only 정책
- **RSPI pending 상태**: 야간 데이터 미확보 시 rspi=None, level="pending" (0 계산 방지)
- **V1 코호트 proximity 수정**: entry_kospi 필드명 + KOSPI 지수 가격 사용 (삼성 가격 X)
- **코호트 경로 통합**: "오늘" / 기준일 선택 모두 reconstructCohorts() 단일 경로
- **V3 lookback 제한**: 최신일은 당일만 확인 (stale overnight 데이터 사용 방지)

### v2.2.2 — V1 Look-Ahead Bias 제거
- **핵심**: 최신일 기준 133개 고정 코호트를 262일 전체에 적용 → 미래 코호트가 과거 V1에 반영 (심각한 look-ahead bias)
- **수정**: `cohort_snapshots` (날짜별 캡처) → `date_to_cohorts` dict → RSPI 루프에서 해당 날짜 코호트만 전달
- **효과**: 12/12 V1 0.1749→0.0243 (미래 고점 코호트 34개 제거), 3/4 V1 변화 없음 (최신 근처)

### v2.3.0 — V1 비선형 Proximity + 9단계 검증 프레임워크
- **V1 비선형 proximity**: `linear ** power` (power=2.5) — 마진콜 근처에서 proximity 급가속
  - ratio 200%→0.00, 185%→0.09, 170%→0.18, 155%→0.41, 145%→0.78, 140%→1.00
  - `V1_PROXIMITY_POWER = 2.5` in constants.py, RSPIEngine에 `proximity_power` 전달
- **9단계 검증 프레임워크** (`rspi_validation.py`):
  - Step 1: 변수별 분포 (V1~V5, VA)
  - Step 2: RSPI 분포 + Q1 체크 (중립 70%+)
  - Step 3: 변수별 예측력 (상관계수, quintile spread, hit rate)
  - Step 4: 시그널 강도 (4 버킷 방향 일치율) + Q3 체크 (strong 65%+)
  - Step 5: 음전환 후 전개 추적
  - Step 6: 거래량 증폭기 A/B 비교
  - Step 7: False alarm 상세 분석
  - Step 8: 가중치 민감도 (±50% 변동)
  - Step 9: V1 power 최적화 (1.0~3.0)
- **검증 결과**: 부분유효
  - Q1 FAIL (중립 25.7%), Q3 PASS (strong 83.3%), 음전환 분리 PASS
  - V3(야간) 최강 변수, V4(개인수급) 무효, power=2.5 유지 확정
  - False alarm 9건 (주범 V2 5건, V4 3건)

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
├── scripts/                     # fetch_daily, kofia_downloader, kofia_watcher, kofia_excel_parser, vlpi_engine, compute_models, export_web, ...
├── data/                        # samsung_cohorts.json (시드), daily/, kofia_excel/, kofia_excel_archive/
└── config/constants.py          # 공용 상수 (경로, 종목, VLPI 파라미터, 6단계 기준)

web/src/simulators/kospi/        # React 대시보드
├── KospiApp.jsx                 # 5탭 메인 (Pulse/Cohort/Crisis(준비중)/History(준비중)/RawData)
├── KospiHeader.jsx              # 공통 헤더 (탭 전환 시 유지)
├── MarketPulse.jsx              # Tab A: 시장 현황 (1350줄)
├── CohortAnalysis.jsx           # Tab B: 코호트 & RSPI 대시보드 (~2000줄)
├── RawDataTable.jsx             # Tab E: 전체 파이프라인 Raw Data (7그룹 33컬럼)
├── colors.js                    # 색상 팔레트
├── data/kospi_data.js           # 정적 JSON 데이터 (18 exports: MARKET_DATA~RSPI_CONFIG)
└── shared/                      # 공유 컴포넌트
    └── terms.jsx                # 용어 사전 (TERM), fmtBillion, TermLabel, TermHint, CustomLegend, CustomTooltipContent
```

### Phase 4.1 구현 범위 (v4.1 — Real Data Source Integration)
- **ecos_fetcher.py**: ECOS 802Y001 일간 데이터 (6개 항목코드: KOSPI/KOSDAQ/외국인/거래량/거래대금/시가총액)
- **naver_scraper.py**: Naver Finance sise_deposit 스크래핑 (고객예탁금 + 신용잔고, 억원, 294페이지)
- **krx_auth.py**: KRX 로그인 세션 + pykrx webio monkey-patch
- **fetch_daily.py 통합**: 5단계 파이프라인 (env → KRX → ECOS → Naver → yfinance → merge)
- **데이터 우선순위**: ECOS > yfinance (지수), pykrx > ECOS (외국인), Naver (예탁금/신용잔고), KOFIA data.go.kr (반대매매)
- **실적**: 732일 (2023-03 ~ 2026-03), Credit 100%, Deposit 100%, Foreign 100%, KOSPI 100%
- **환경변수**: `ECOS_API_KEY`, `KRX_USER_ID`, `KRX_USER_PW`, `DATA_GO_KR_API_KEY` (`.env`)

### Phase 4.2~5 (미구현, 향후)
- **Phase 4.2**: pykrx 대체 투자자 수급 소스 (individual/institution 데이터)
- **Phase 5**: Deploy (GitHub Actions cron, Vercel)

---

## PDCA Status

### Archived (docs/archive/2026-03/)
| Feature | Version | Match Rate | Iterations |
|---------|---------|-----------|------------|
| btc-liquidity-model | v1.0.0 | 93% | 0 |
| btc-liquidity-v2 | v2.0.0 | 92% | 1 |
| web dual-band | v2.1.0 | 97.4% | 0 |
| kospi-vlpi | v1.5.0 | 99.1% | 1 |
| kospi-vlpi | v1.6.0 | 98.6% | 0 |
| kospi-rspi | v2.0.0 | 98.7% | 0 |

### Completed (not yet archived)
| Feature | Version | Match Rate | Note |
|---------|---------|-----------|------|
| web-dashboard | v1.0.0 | 93.5% | BTC v1 dashboard |
| kospi-crisis | v1.0.2 | 100% | Phase 1 차트 가독성 |
| kospi-crisis-phase2 | v1.1.0 | 98.9% | Phase 2 UX |
| kospi-phase4.1 | v4.1 | 93% | 실데이터 통합 |
| kospi-crisis | v1.1.1 | 100% | Naver + bugfix |
| kospi-crisis | v1.2.0 | — | 백테스트 + 담보비율 |
| kospi-crisis | v1.3.0 | — | 종목별 가중 모델 |
| kospi-crisis | v1.4.0 | 100% | 자동청산 + 백테스트 차트 |
| kospi-crisis | v2.1.0 | — | RSPI 실데이터 + Raw Data |
| kofia-auto-download | v2.1.2 | 100% | Playwright 자동 다운로드 + crontab |
| kospi-rspi | v2.2.0 | 97.6% | 5변수 + Volume Amplifier 재설계 |
| kospi-rspi | v2.2.1 | 100% | 데이터 정합성 + pending 상태 |
| kospi-rspi | v2.2.2 | 100% | V1 look-ahead bias 제거 |
| kospi-rspi | v2.3.0 | — | V1 비선형 proximity + 9단계 검증 |
| kospi-rspi | v2.3.0-v31 | — | v3.1 곱셈 모델 + 3단계 최적화 (Q3 75.4%) |

## CLI (KOSPI)
```bash
# ── 일간 데이터 수집 ──
python -m scripts.fetch_daily                    # 오늘
python -m scripts.fetch_daily --date 2026-03-05  # 특정일
python -m scripts.fetch_daily --range START END  # 범위 (전체 API 배치)
python -m scripts.fetch_daily --backfill         # change_pct만 패치 (yfinance only, 5초)
python -m scripts.fetch_daily --backfill-credit  # credit/deposit/forced_liq KOFIA API 패치
python -m scripts.fetch_daily --import-excel "path/to/file.xlsx"  # KOFIA 엑셀 직접 import

# ── KOFIA 일간 파이프라인 (예탁금/신용잔고/반대매매) ──
# 방법 1: Playwright 자동 (공식 — crontab KST 18:00)
python -m scripts.kofia_downloader --auto       # 다운로드 + import + export_web + archive
python -m scripts.kofia_downloader              # 다운로드만 (kofia_excel/)
python -m scripts.kofia_downloader --headful    # 브라우저 표시 (디버깅)
# 방법 2: 엑셀 폴더 감시 (수동 드롭)
python -m scripts.kofia_watcher                  # kofia_excel/ 감시 (foreground)
python -m scripts.kofia_watcher --once file.xlsx  # 단발 처리

# ── 모델 계산 + 웹 내보내기 ──
python -m scripts.compute_models
python -m scripts.export_web
```

### 데이터 파이프라인 구조
```
[일간 자동] crontab KST 18:00
  kofia_cron.sh → kofia_downloader.py --auto
    → Playwright headless → FreeSIS EXCEL 다운로드
    → kofia_excel_parser.py → timeseries.json 머지
    → export_web.py → kospi_data.js

[일간 수동 / 범위]
  fetch_daily.py --range START END
    → ECOS (KOSPI/외국인/거래대금/시총, 무제한 페이지네이션)
    → Naver sise_deposit (예탁금/신용잔고, ~7년, 294페이지)
    → Naver investorDealTrendDay (투자자 수급, ~1000일)
    → yfinance (삼전/하닉/EWY/KORU/VIX/SPY, 무제한)
    → KOFIA data.go.kr (신용잔고/예탁금/반대매매, 페이지네이션)
    → merge → daily/{YYYY-MM-DD}.json + timeseries.json

[모델] compute_models.py → model_output.json → export_web.py → kospi_data.js
```

### v2.1.1 — KOFIA 엑셀 자동 파싱 + 폴더 모니터링
- **kofia_excel_parser.py**: FreeSIS "한눈에 보는 자본시장통계" 엑셀 파싱 (6개 지표 매핑)
- **kofia_watcher.py**: `kofia_excel/` 폴더 watchdog 감시 → 자동 파싱 + timeseries 머지 → `kofia_excel_archive/` 이동
- **fetch_daily.py --import-excel**: 단발 엑셀 import + export_web 자동 실행
- 엑셀 구조: 56행×5열, A열 지표명(`>`구분), B열 `YY/MM/DD`, C열 쉼표 문자열

### v2.1.2 — KOFIA 자동 다운로드 + crontab 자동화
- **kofia_downloader.py**: Playwright headless → FreeSIS "한눈에 보는 자본시장통계" EXCEL 자동 다운로드
  - `--auto`: 다운로드 → 파싱 → timeseries 머지 → export_web → archive 이동 (원스텝)
  - `--headful`: 브라우저 표시 디버깅 모드
- **kofia_cron.sh**: crontab wrapper (venv 활성화 + 로그 + 30일 로테이션)
- **crontab**: 평일 KST 18:00 자동 실행 (`0 18 * * 1-5`)
- **kofia_excel_parser.py 버그 수정**: `read_only=True` → `False` (eXbuilder6 엑셀 호환)
- **Claude Code 슬래시 명령어**: `/auto-kospi` → 수동 1회 실행
- 다운로드 흐름: FreeSIS 접속 → SPA 메뉴 클릭 → EXCEL저장 → kofia_excel/ → import → archive/

## Backlog
- **kospi Phase 5**: Deploy (GitHub Actions cron + Vercel)
- **위기분석 탭 재활성화**: CrisisAnalysis.jsx (코드 보존, disabled=true 제거로 복원)
- **과거비교 탭 재활성화**: HistoricalComp.jsx (코드 보존, disabled=true 제거로 복원)
- **gm2-data-improvement**: GM2 11개월 고착 → BTC lag 불일치
- **RSPI Q1 개선**: V3 dead zone / gating 메커니즘 (중립 비율 20.9% → 65%+ 목표)
