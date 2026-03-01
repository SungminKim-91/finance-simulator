# Finance Simulator — BTC Liquidity Prediction Model

> v1.0.0 (completed) → v2.0.0 (completed, 92% Match Rate) → v2.1 web dual-band | BTC 가격 방향성 선행 예측 시뮬레이터

## Project Overview
글로벌 유동성 지표(5개 변수)를 기반으로 BTC 가격의 큰 흐름을 5-9개월 선행 예측하는 모델.
실제 데이터 크롤링 파이프라인 포함.

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

## PDCA Status
- **btc-liquidity-model v1.0.0**: Archived (Match Rate 93%) → `docs/archive/2026-03/btc-liquidity-model/`
- **btc-liquidity-v2 v2.0.0**: Archived (Match Rate 92%, 1 iteration) → `docs/archive/2026-03/btc-liquidity-v2/`
- **web-dashboard v1.0.0**: Completed (Match Rate 93.5%, 1 iteration)
- **web v2.1 dual-band**: Do phase (dual-band + combined + smoothing 구현 완료)
- **Active docs**: docs/03-analysis/web-dashboard.analysis.md
- **Archive**: docs/archive/2026-03/
