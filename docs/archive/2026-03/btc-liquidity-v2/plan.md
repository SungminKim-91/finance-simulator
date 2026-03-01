# Plan: BTC Liquidity Prediction Model v2.0.0

> Feature: btc-liquidity-v2
> Created: 2026-03-01
> Status: Draft
> PDCA Phase: Plan
> Based on: v1.0.0 Post-mortem + Phase 1c Reference + Methodology Research

---

## 1. Feature Overview

### 1.1 Why v2.0?

v1.0.0은 93% Design Match Rate로 완성되었으나, 근본적인 문제가 확인됨:

| 문제 | v1.0.0 현상 | 원인 |
|------|-----------|------|
| **과적합** | Grid Search 88,209 combo로 BTC에 직접 최적화 | 가중치가 결과에 맞춰짐 |
| **NL 가중치 하락** | NL=0.5 (메인 유동성이 보조지표급) | BTC 상관 최대화가 이론 무시 |
| **SOFR spike** | SOFR=-4.0 → score -16 (3개월간) | Binary 0/1 × 큰 가중치 |
| **방향 불일치** | lag=0에서 r=-0.077 (방향 반대) | SOFR spike가 전체 왜곡 |
| **Phase 1c 대비** | v1.0.0 r=0.619 vs Phase 1c r=0.318 | r은 높지만 방향이 틀림 |

**Phase 1c (PCA, BTC-blind) 대비:**
- Phase 1c: r=0.318이지만 **모든 lag(0~15)에서 양의 상관** → 방향 100% 일치
- v1.0.0: r=0.619이지만 lag=0~1에서 **음의 상관** → 단기 방향이 반대
- **결론**: r값이 낮아도 방향이 항상 맞는 Phase 1c가 더 의미 있음

### 1.2 v2.0 핵심 철학

> "결과에 짜맞춘 모델은 의미없다. PCA로 독립 구성한 인덱스가 BTC 방향과 맞아떨어지는 것이 진짜."

1. **독립 구성 원칙**: 인덱스 구성 시 BTC 데이터를 **절대** 참조하지 않음
2. **방향성 매칭**: 진폭(amplitude)이 아닌 방향(direction)의 일치가 핵심 목표
3. **이론 기반**: 경제 이론에 근거한 변수 선택, 데이터에서 자연스러운 가중치 도출
4. **과적합 배제**: 모든 선택에 통계적 검정 + Bootstrap 안정성 확인

### 1.3 목표

- **방향 일치율(MDA)**: > 0.60 at optimal lag
- **모든 lag에서 양의 상관**: lag=0~12 전부 r > 0 (Phase 1c 패턴 재현)
- **XCORR smooth hill**: lag=0에서 시작, 피크 후 감소하는 자연스러운 형태
- **Bootstrap 안정성**: PC1 loadings 95% CI에서 NL이 항상 최대
- **다중 타임스케일**: 일/주/월 선택 가능

---

## 2. Scope (v2.0.0)

### 2.1 In-Scope

#### A. 3-Stage 파이프라인

```
Stage 1: 독립 인덱스 구성 (BTC-blind)
─────────────────────────────────────
  Mixed-freq data → DFM+Kalman → PCA/ICA → Liquidity Index
  SOFR → Logistic smoothing (binary 제거)
  ※ BTC 데이터를 이 단계에서 절대 사용하지 않음

Stage 2: 방향성 검증 (사후 평가)
─────────────────────────────────────
  Index(t) vs log₁₀(BTC)(t+k):
  - Sign Concordance Rate (MDA) @ lag=0~15
  - SBD (Shape-Based Distance)
  - Cosine Similarity on derivatives
  - Kendall Tau
  → Composite Waveform Score

Stage 3: 과적합 방지
─────────────────────────────────────
  - Bootstrap: loading 안정성, lag 분포
  - CPCV: 45-path validation (purge=9m)
  - Granger Causality: 단방향 인과 검정
  - Wavelet Coherence: 시간-주파수 확인
```

#### B. 혼합 주기 처리 (Mixed-Frequency)

| 변수 | 실제 빈도 | v1.0.0 | v2.0.0 |
|------|----------|--------|--------|
| RRP, TGA, SOFR, IORB | 일별 | 월말 resample | **일별 격자 유지** |
| BTC, CME, HY, DXY | 일별 | 월말 resample | **일별 유지** |
| WALCL | 주별 | 월말 resample | 주별→일별 보간 |
| US M2, EU M3, JP M3, CN M2 | 월별 | 그대로 | **발표일만 업데이트** (NaN 칼만보간) |

방법: **DFM(Dynamic Factor Model) + 칼만 필터**
- 일별 격자에 모든 변수 배치
- 관측 없는 날 = NaN → 칼만 필터 최적 보간
- 월별 M2: 발표일에만 값, 나머지 NaN
- 결과: 매일 업데이트되는 유동성 팩터

#### C. SOFR Smooth Transition

현재 v1.0.0의 Binary (0/1) → 연속 확률로 대체:

```python
# v1.0.0: Binary (0 or 1) → weight=-4.0 → score -16 spike
sofr_binary = 1 if (sofr - iorb) > 20 else 0

# v2.0.0 Phase 1: Logistic smoothing (즉시 구현)
sofr_smooth = 1 / (1 + exp(-gamma * (spread_bps - threshold)))
# gamma=0.2: 완만한 전환, 출력: 0~1 연속값

# v2.0.0 Phase 2: Markov Regime-Switching (고급)
# P(crisis|data) → statsmodels MarkovRegression
```

#### D. 2026 데이터 포함

- `DATA_END`: "2025-12-31" → 동적 (현재 날짜 기준)
- 최신 데이터 자동 수집 및 반영

#### E. 다중 타임스케일 인터페이스

CLI 및 대시보드에서 타임스케일 선택 가능:
- `python main.py score --freq daily` (일별)
- `python main.py score --freq weekly` (주별)
- `python main.py score --freq monthly` (월별, 기본값)

### 2.2 Out-of-Scope (v2.1+)

- 실시간 트레이딩 시그널
- 포트폴리오 최적화
- 모바일 앱
- Slack/Discord 알림

---

## 3. 방법론 상세

### 3.1 Stage 1: 독립 인덱스 구성

#### 3.1.1 PCA (Principal Component Analysis) — Primary

```python
from sklearn.decomposition import PCA
pca = PCA(n_components=1)
pc1 = pca.fit_transform(z_matrix)  # z_matrix: (T, 5)
loadings = pca.components_[0]       # 변수별 기여도
explained_var = pca.explained_variance_ratio_[0]
```

- Phase 1c에서 이미 증명됨: BTC-blind PC1이 lag=7에서 r=0.318
- 모든 lag에서 양의 상관 → 방향 일치 100%
- **NL의 loading이 자연히 최대가 되는지 확인** (경제 이론과 일치)

#### 3.1.2 ICA (Independent Component Analysis) — Comparison

```python
from sklearn.decomposition import FastICA
ica = FastICA(n_components=3, random_state=42)
S = ica.fit_transform(z_matrix)
```

- PCA는 "공통 분산", ICA는 "독립적 원인 신호" 분리
- 금융 데이터는 fat-tailed (비정규분포) → ICA가 이론적으로 적합
- IC 선택: 경제적 해석으로 "유동성 IC" 선택 (BTC 참조 없이)

#### 3.1.3 DFM (Dynamic Factor Model) — Mixed-frequency

```python
from statsmodels.tsa.statespace.dynamic_factor import DynamicFactor
model = DynamicFactor(daily_matrix_with_nans, k_factors=1, factor_order=2)
result = model.fit(disp=False)
daily_factor = result.factors.filtered[0]
```

- 일/주/월 혼합 주기를 자연스럽게 통합
- 칼만 필터로 결측치 최적 보간
- 시간에 따라 factor loading 변화 가능

#### 3.1.4 Sparse PCA — Variable Selection

```python
from sklearn.decomposition import SparsePCA
spca = SparsePCA(n_components=1, alpha=1.0, random_state=42)
```

- L1 정규화 → 중요하지 않은 변수 loading = 0
- v1.0.0에서 GM2=0, CME=0으로 나온 결과를 비지도로 검증

### 3.2 Stage 2: 방향성 검증 메트릭

#### 3.2.1 복합 파형 점수 (Composite Waveform Score)

```
CWS = 0.4 × MDA + 0.3 × (1-SBD) + 0.2 × CosSim + 0.1 × Tau
```

| 메트릭 | 측정 대상 | 가중치 | 라이브러리 |
|--------|----------|:------:|-----------|
| **MDA** (Sign Concordance) | 변화 방향 일치율 | 40% | numpy |
| **SBD** (Shape-Based Distance) | 파형 형태 유사도 | 30% | tslearn |
| **Cosine Sim on dX** | 변화율 벡터 방향 | 20% | sklearn |
| **Kendall Tau** | 순위 기반 방향 일치 | 10% | scipy |

#### 3.2.2 Cross-Correlation 프로파일

- lag=0~15에서 Pearson r, MDA, Kendall tau 동시 계산
- **성공 기준**: 모든 lag에서 r > 0 (Phase 1c 패턴)
- XCORR 형태: smooth hill (lag=0에서 시작, 피크 후 감소)

#### 3.2.3 Wavelet Coherence

```python
import pycwt
WCT, aWCT, coi, freq, sig = pycwt.wct(index, btc, dt=1)
```

- 시간-주파수 영역에서 방향 일치 확인
- 위상 화살표(phase arrows)로 lead/lag 시각화
- "어떤 주기에서 선행하는가?" 분석

### 3.3 Stage 3: 과적합 방지

#### 3.3.1 Bootstrap 안정성

```python
from tsbootstrap import MovingBlockBootstrap
boot = MovingBlockBootstrap(n_bootstraps=1000, block_length=12)
```

- PC1 loadings의 95% CI 계산
- 최적 lag의 분포 확인
- MDA의 p-value (binomial test)

#### 3.3.2 CPCV (Combinatorial Purged Cross-Validation)

```python
from skfolio.model_selection import CombinatorialPurgedCV
cv = CombinatorialPurgedCV(n_folds=10, n_test_folds=2, purge_threshold=9)
```

- 10 folds, 2 test → C(10,2) = 45 경로
- purge=9 (lag 길이), embargo=2
- v1.0.0 Walk-Forward (9경로) 대비 5배 강건

#### 3.3.3 Granger Causality

```python
from statsmodels.tsa.stattools import grangercausalitytests
```

- Index → BTC 방향 인과 검정
- BTC → Index 역방향 인과가 **없음** 확인
- 인덱스의 독립성 통계적 증명

---

## 4. 변수 명세 (v2.0)

### 5개 기존 변수 — 처리 방법 변경

| # | 변수 | v1.0.0 | v2.0.0 |
|---|------|--------|--------|
| 1 | **NL Level** | 12m MA detrend → z-score → Grid Search weight=0.5 | 12m MA detrend → z-score → **PCA natural loading** |
| 2 | **GM2 Residual** | OLS 직교화 → Grid Search weight=0.0 | OLS 직교화 → **PCA natural loading** |
| 3 | **SOFR** | Binary (0/1) → weight=-4.0 → **spike** | **Logistic smooth (0~1 연속)** → PCA input |
| 4 | **HY Spread** | 12m MA detrend → Grid Search weight=-0.5 | 12m MA detrend → **PCA natural loading** |
| 5 | **CME Basis** | 12m MA detrend → Grid Search weight=0.0 | 12m MA detrend → **PCA natural loading** |

**핵심 변경**: Grid Search 가중치 → PCA/ICA 자연 loading
- 가중치를 인간이 결정하지 않음
- 데이터 공분산에서 자연스럽게 도출
- BTC를 전혀 보지 않는 완전 비지도

---

## 5. 기술 스택

### 5.1 기존 유지
| 구분 | 기술 |
|------|------|
| Language | Python 3.12 + uv |
| Data | pandas, numpy |
| APIs | fredapi, yfinance, requests |
| Storage | SQLite + JSON |
| Viz (backend) | matplotlib, seaborn |
| Viz (frontend) | React + Recharts (web/) |

### 5.2 v2.0 추가

| 구분 | 기술 | 용도 |
|------|------|------|
| PCA/ICA | scikit-learn (PCA, FastICA, SparsePCA) | 독립 인덱스 구성 |
| DFM | statsmodels (DynamicFactor) | 혼합 주기 + 칼만 필터 |
| Regime | statsmodels (MarkovRegression) | SOFR smooth transition |
| Waveform | tslearn (SBD), scipy (kendalltau) | 방향성 메트릭 |
| Wavelet | pycwt | 시간-주파수 분석 |
| CPCV | skfolio (CombinatorialPurgedCV) | 과적합 방지 |
| Bootstrap | tsbootstrap (MovingBlockBootstrap) | 안정성 검정 |
| Causality | statsmodels (grangercausalitytests) | 인과 검증 |

---

## 6. 구현 순서 (Implementation Phases)

### Phase 1: 기반 변경 (Quick Wins)
- [ ] DATA_END 동적화 (현재 날짜 기준)
- [ ] SOFR Binary → Logistic smoothing 교체
- [ ] PCA baseline 구축 (sklearn PCA, 월별 먼저)
- [ ] MDA + Kendall tau 메트릭 구현
- [ ] Phase 1c 결과 재현 검증

### Phase 2: 독립 인덱스 비교
- [ ] ICA 구현 및 PCA 대비 비교
- [ ] Sparse PCA로 자동 변수 선택
- [ ] Bootstrap 안정성 분석 (loading CI, lag 분포)
- [ ] SBD + Cosine similarity 구현
- [ ] Composite Waveform Score (CWS) 계산

### Phase 3: 혼합 주기
- [ ] 일별 데이터 수집 파이프라인 (기존 fetcher 확장)
- [ ] DFM + 칼만 필터 구현 (일별 팩터 추출)
- [ ] 타임스케일 선택 인터페이스 (daily/weekly/monthly)
- [ ] M2 발표일 기준 업데이트 로직

### Phase 4: 고급 검증
- [ ] CPCV 구현 (45-path validation)
- [ ] Granger Causality 양방향 검정
- [ ] Wavelet Coherence 시각화
- [ ] Markov Regime-Switching (SOFR 체제 확률)

### Phase 5: 시각화 + 대시보드
- [ ] 웹 대시보드 v2.0 (타임스케일 선택, 방향 메트릭)
- [ ] Wavelet coherence plot
- [ ] Bootstrap loading CI plot
- [ ] PCA vs ICA 비교 차트

### Phase 6: 검증 + 문서화
- [ ] 전체 파이프라인 통합 테스트
- [ ] v1.0.0 vs v2.0.0 비교 보고서
- [ ] CLAUDE.md, README 업데이트
- [ ] PDCA 완료 보고서

---

## 7. 파일 구조 (v2.0 추가분)

```
finance-simulator/
├── src/
│   ├── index_builders/            ★ NEW — 독립 인덱스 구성
│   │   ├── __init__.py
│   │   ├── pca_builder.py         # PCA 기반 인덱스
│   │   ├── ica_builder.py         # ICA 기반 인덱스
│   │   ├── dfm_builder.py         # DFM + 칼만 필터 (혼합 주기)
│   │   └── sparse_pca_builder.py  # Sparse PCA (변수 선택)
│   │
│   ├── validators/                ★ NEW — 방향성 검증
│   │   ├── __init__.py
│   │   ├── waveform_metrics.py    # MDA, SBD, Cosine, Kendall
│   │   ├── wavelet_coherence.py   # 시간-주파수 분석
│   │   ├── granger_test.py        # Granger Causality
│   │   └── composite_score.py     # CWS 복합 점수
│   │
│   ├── robustness/                ★ NEW — 과적합 방지
│   │   ├── __init__.py
│   │   ├── bootstrap_analysis.py  # Block bootstrap 안정성
│   │   ├── cpcv.py                # Combinatorial Purged CV
│   │   └── deflated_test.py       # 다중 비교 보정
│   │
│   ├── calculators/
│   │   ├── sofr_smooth.py         ★ NEW — Logistic/Markov smooth
│   │   └── (기존 유지)
│   │
│   └── (기존 모듈 유지)
│
├── config/
│   ├── settings.py                수정: DATA_END 동적화
│   └── constants.py               수정: v2.0 파라미터 추가
│
└── web/                           수정: v2.0 대시보드 기능 추가
```

---

## 8. 성공 기준

| 지표 | v1.0.0 실제 | v2.0 목표 | 기준 |
|------|-----------|----------|------|
| 방향 일치율 (MDA) | 미측정 | **> 0.60** | @optimal lag |
| XCORR 전 lag 양수 | lag=0: **-0.077** | **모든 lag > 0** | lag=0~12 |
| XCORR 형태 | 불규칙 (neg→jump) | **Smooth hill** | Phase 1c 패턴 |
| Bootstrap loading 안정 | 미측정 | **NL loading 항상 최대** | 95% CI |
| CPCV OOS | WF mean=0.246 | **CPCV mean > 0.15** | 45 paths |
| Granger 단방향 | 미측정 | **Index→BTC p<0.05** | BTC→Index p>0.05 |
| 타임스케일 | 월별만 | **일/주/월 선택** | CLI --freq |
| SOFR spike | score -16 (3개월) | **score ±3 이내** | smooth 처리 |

---

## 9. 리스크 & 대응

| 리스크 | 영향 | 대응 |
|--------|------|------|
| PCA r값이 v1.0.0보다 낮을 수 있음 | r=0.3 수준 | 방향 일치율이 핵심 — r보다 MDA 우선 |
| DFM 수렴 실패 | 일별 팩터 추출 불가 | 월별 PCA fallback |
| 칼만 필터 초기값 민감 | 결과 불안정 | 다중 초기값 시도 + EM 알고리즘 |
| GM2 래그 (2-3개월) | 최신 데이터 부재 | 직전값 캐리포워드 (v1.0.0과 동일) |
| Bootstrap에서 loading 불안정 | 이론적 기반 약화 | 변수 제외 또는 차분 후 재분석 |
| CPCV purge window 부족 | 정보 누출 가능 | purge=lag 길이(9m) 이상 보장 |

---

## 10. v1.0.0 → v2.0.0 마이그레이션 전략

### 유지하는 것
- 전체 Fetcher 레이어 (FRED, Treasury, Market, Fallback)
- Calculator 레이어 (NL, GM2, HY, CME 계산 로직)
- Storage 레이어 (SQLite + JSON)
- 12m MA detrend + z-score 표준화
- 직교화 (GM2 → NL OLS residual)
- CLI 인터페이스 구조

### 제거하는 것
- ❌ `src/optimizers/grid_search.py` (BTC 직접 최적화 — 과적합 원인)
- ❌ `src/calculators/sofr_binary.py` (Binary 0/1 — spike 원인)
- ❌ `config/constants.py`의 `GRID_SEARCH` 범위

### 추가하는 것
- `src/index_builders/` (PCA, ICA, DFM, Sparse PCA)
- `src/validators/` (MDA, SBD, Wavelet, Granger)
- `src/robustness/` (Bootstrap, CPCV)
- `src/calculators/sofr_smooth.py` (Logistic/Markov)

### 수정하는 것
- `config/settings.py`: DATA_END 동적화, freq 옵션
- `config/constants.py`: v2.0 파라미터
- `src/pipeline/runner.py`: 3-Stage 파이프라인
- `main.py`: --freq 옵션, v2.0 명령어

---

## 11. 의사결정 로그

| 결정 | 이유 |
|------|------|
| Grid Search 제거 | BTC에 직접 최적화 = 과적합의 근본 원인 |
| PCA 기반 인덱스 | Phase 1c에서 BTC-blind로 이미 검증됨 |
| MDA 40% 가중치 | 방향 일치가 가장 직접적인 요구사항 |
| Logistic smoothing 우선 | Markov보다 간단, 해석 명확, 즉시 구현 가능 |
| DFM for 혼합주기 | 칼만 필터가 결측치를 가장 자연스럽게 처리 |
| CPCV for 검증 | 금융 ML의 de facto 표준, Walk-Forward보다 5배 강건 |
| Bootstrap for 안정성 | 단일 결과의 우연성 배제 필수 |

---

## References

- Phase 1c: `C:\Users\admin\Downloads\phase1c_log_btc (1).jsx` — BTC-blind PCA baseline
- v1.0.0 Plan: `docs/01-plan/features/btc-liquidity-model.plan.md`
- v1.0.0 Design: `docs/02-design/features/btc-liquidity-model.design.md`
- v1.0.0 Report: `docs/04-report/btc-liquidity-model.report.md`
- de Prado (2018): CPCV — Combinatorial Purged Cross-Validation
- Ghysels (2004): MIDAS — Mixed Data Sampling
- Hamilton (1989): Markov Regime-Switching Models
- Sugihara (2012): Convergent Cross Mapping (CCM)
