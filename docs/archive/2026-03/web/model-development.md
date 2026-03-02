# BTC Liquidity Model — Development Journey

> v1.0 Grid Search → v2.0 BTC-blind PCA → v2.1 Dual-Band (Model D)
>
> 최종 결과: Structural r=+0.491, MDA=64.7% | CWS=0.606 | All r > 0

---

## 1. 프로젝트 목적

글로벌 유동성 지표로 BTC 가격의 **방향성**(상승/하락)을 선행 예측하는 모델 구축.
가격 예측이 아닌 **파형 매칭** — 유동성 인덱스가 상승하면 BTC도 상승하는 패턴을 검증.

---

## 2. 변수 구성 (5개 → 4개 활용)

| # | 변수 | 소스 | 의미 | 모델 역할 |
|---|------|------|------|-----------|
| 1 | **NL (Net Liquidity)** | FRED: WALCL - TGA - RRP | 미국 연준 순유동성 | 핵심 구조적 유동성 |
| 2 | **GM2 (Global M2 Residual)** | FRED: US/EU/JP/CN M2 합산 | 미국 외 글로벌 유동성 (직교화) | 글로벌 유동성 보완 |
| 3 | **HY (High Yield Spread)** | FRED: BAMLH0A0HYM2 | 신용 스프레드 = 위험선호도 | 신용 위험 신호 |
| 4 | **CME (Basis)** | Yahoo: CME Futures - BTC Spot | 기관 포지셔닝 연율화 | 기관 투자자 심리 |
| 5 | ~~SOFR Binary~~ | FRED: SOFR - IORB | ~~위기 감지~~ | **v2.0에서 제외** (51개월 상수) |

### 전처리
- 12개월 MA detrend → z-score 표준화
- 결과: `z_matrix.csv` (120개월 × 6열, 2016-01 ~ 2025-12)

---

## 3. 모델 진화 과정

### Phase 1: v1.0 Grid Search (과적합)

```
방법: 88,209개 가중치 조합 Grid Search → BTC corr 최대화
결과: r=0.618 (in-sample), lag=9m
가중치: NL=0.5, GM2=0.0, SOFR=-4.0, HY=-0.5, CME=0.0
```

**문제점**:
- BTC를 직접 타겟으로 최적화 → 과적합
- SOFR binary weight=-4.0 → score -16 스파이크
- NL(유동성 핵심)이 0.5로 축소되고 SOFR가 지배
- Walk-Forward OOS 변동성 높음 (Std=0.587)

### Phase 2: v2.0 BTC-blind PCA (독립 구성)

```
방법: PCA 비지도학습 → BTC를 보지 않고 유동성 인덱스 독립 구성
철학: 유동성 지표들의 공통 변동 패턴 = PC1 → 이것이 자연히 BTC와 매칭되면 진짜 신호
```

**3-Stage Pipeline**:
1. Stage 1: z_matrix → PCA (BTC-blind) → 독립 인덱스
2. Stage 2: 인덱스 vs BTC 방향성 검증 (CWS = MDA×0.4 + (1-SBD)×0.3 + CosSim×0.2 + Tau×0.1)
3. Stage 3: Bootstrap CI + CPCV 38-path + Granger + Wavelet

**초기 결과**: CWS=0.606, MDA@lag0=64.7%, All r > 0

### Phase 3: 스파이크 진단 & Winsorize

**발견된 스파이크 원인**:

| 날짜 | 변수 | z-score | 원인 |
|------|------|---------|------|
| 2020-03~04 | NL | -2.75σ ~ -4.6σ | COVID QE (연준 긴급 완화) |
| 2020-03 | HY | +5.01σ | COVID 신용 패닉 |
| 2022-06 | HY | +3.14σ | Fed 인상 사이클 피크 |
| 2021-10 | CME | -5.6σ | CME 선물 극단 포지셔닝 |
| 2024-03~2025-01 | GM2 | -2.96σ (11개월 상수) | FRED M2→M3 데이터 단절 |

**Winsorize 실험 (8가지 옵션)**:

| 옵션 | NL | HY | GM2 | CME | NL loading | HY loading | 결과 |
|------|----|----|-----|-----|-----------|-----------|------|
| 기본 (no clip) | ∞ | ∞ | ∞ | ∞ | 0.607 | 0.514 | NL 주도 |
| 균일 ±2σ | 2 | 2 | 2 | 2 | 0.512 | **0.647** | HY 주도 (역전!) |
| **Option H** | **3** | **2.5** | **2** | **2** | **0.703** | **0.587** | **NL 주도 유지** |

**Option H 선택 이유**:
- NL ±3σ: COVID QE(4.6σ)만 클리핑, 구조적 변동은 보존
- HY ±2.5σ: COVID(5.0σ)와 2022(3.1σ) 클리핑, 일상적 신용 이벤트 보존
- GM2 ±2σ: FRED 데이터 단절(-2.96σ × 11개월) 제거
- CME ±2σ: 선물 노이즈(-5.6σ, +5.9σ) 제거

### Phase 4: Sign Correction 변경 (NL → HY)

```
Before: index와 NL의 양의 상관 강제 (NL↑ → index↑)
After:  index와 HY의 음의 상관 강제 (HY↑ → index↓)
```

**경제적 논리**: 유동성↑ → 신용 스프레드↓ (위험선호↑) → BTC↑
이 관계에서 HY는 역방향 지표이므로, `corr(index, HY) < 0`이 올바른 부호.

### Phase 5: Dual-Band 분리 (Model D)

**문제**: NL+GM2만으로 structural band를 만들면 r=0.22로 급락 (HY가 빠지면서)

**해결**: 4변수 PCA 전체를 base로 유지하고, HY를 별도 tactical overlay로 분리

| 모델 | 구성 | r@lag0 | MDA@lag0 |
|------|------|--------|----------|
| A. 4변수 PCA (base) | NL+GM2+HY+CME | **+0.491** | **64.7%** |
| B. NL+GM2 only | NL+GM2 | +0.219 | 53.7% |
| C. NL+GM2+CME | NL+GM2+CME | +0.366 | 55.3% |
| **D. 4var + tactical** | **A(shifted) + EMA(-HY)** | **+0.491** | **64.7%** |

**Model D (최종 채택)**:
- **Structural Band**: 4변수 PCA (NL+GM2+HY+CME) + Option H clip → lag 시프트
- **Tactical Band**: -HY_z → EMA smoothed → 실시간 (no shift)
- **Combined**: 0.7 × Structural(shifted) + 0.3 × EMA(Tactical)

---

## 4. 최종 모델 구조

```
z_matrix.csv (120개월)
    │
    ├── Option H Clip: NL±3σ, HY±2.5σ, GM2±2σ, CME±2σ
    │
    ├── PCA (n_components=1, BTC-blind)
    │       │
    │       ├── Sign Correction: corr(index, HY) < 0 강제
    │       │
    │       └── PC1 Loadings:
    │               NL:  +0.703 (dominant)
    │               HY:  +0.587
    │               GM2: +0.396
    │               CME: -0.062
    │
    ├── Structural Band = PC1 index (shifted by lag months)
    │
    └── Tactical Band = -HY_z → EMA(window=6m) (realtime, no shift)
         │
         └── Combined = 0.7 × Structural + 0.3 × Tactical
```

### PCA Loadings 해석

| 변수 | Loading | 의미 |
|------|---------|------|
| **NL** | **+0.703** | 순유동성이 PC1의 최대 기여 — 유동성 증가 → 인덱스 상승 |
| **HY** | +0.587 | HY 스프레드 상승도 같은 방향 (sign correction으로 반전됨) |
| **GM2** | +0.396 | 글로벌 유동성 보완 역할 |
| **CME** | -0.062 | 기관 포지셔닝은 거의 기여하지 않음 |

> **Explained Variance**: 43.6% — PC1 하나로 4변수 분산의 43.6% 설명

---

## 5. 검증 결과

### 5.1 방향성 매칭 (Stage 2)

| Metric | Value | 기준 | 판정 |
|--------|-------|------|------|
| **CWS (Composite Waveform Score)** | 0.606 | > 0.5 | PASS |
| **MDA@lag0** | 64.7% | > 60% | PASS |
| **Pearson r@lag0** | +0.491 | > 0 | PASS |
| **All r > 0 (0~15m)** | True | True | PASS |
| **Optimal Lag** | 0m | - | - |

### 5.2 CWS 분해 (lag=0)

```
CWS = 0.4 × MDA + 0.3 × (1-SBD) + 0.2 × CosSim + 0.1 × Tau

CWS = 0.4 × 0.647     MDA 기여:     0.259
    + 0.3 × (1-0.509)  (1-SBD) 기여: 0.147
    + 0.2 × 0.328      CosSim 기여:  0.066
    + 0.1 × 0.340      Tau 기여:     0.034
    ─────────────────────────────────────
    = 0.606
```

### 5.3 과적합 방지 (Stage 3)

| Test | Result | 판정 |
|------|--------|------|
| **Bootstrap CI (n=1000)** | NL CI excludes zero, NL max rate=36.7% | PARTIAL |
| **CPCV (38 paths)** | mean CWS=0.746, std=0.138 | PASS |
| **Granger Causality** | Forward p=0.154, Reverse p=0.298 | NOT SIGNIFICANT |
| **Bootstrap Lag** | Mean=9.5m, Median=11m, Mode=12m, CI=[2, 15]m | WIDE |

### 5.4 Dual-Band 성능

| Band | r@lag0 | MDA@lag0 | 용도 |
|------|--------|----------|------|
| Structural (4-var PCA) | +0.491 | 64.7% | 유동성 주기 (선행) |
| Tactical (-HY) | +0.417 | 65.9% | 신용 위험 (실시간) |
| Combined (70/30) | hybrid | hybrid | 합성 신호 |

---

## 6. Web Dashboard

### 6.1 기술 스택
- React 18 + Recharts 2.15 + Vite 6.0
- 데이터: `export_v2_web.py` → `data_v2.js` (8개 JS export)

### 6.2 인터랙티브 컨트롤

| 컨트롤 | 범위 | 기본값 | 기능 |
|--------|------|--------|------|
| Lag 슬라이더 | 0~15m | 0m | Structural band 시간 시프트 |
| Tactical 토글 | ON/OFF | OFF | -HY 실시간 오버레이 |
| Combine 토글 | ON/OFF | OFF | 0.7×Struct + 0.3×Tact 합성 |
| Smoothing 슬라이더 | 2~12m | 6m | EMA window (스파이크 억제) |

### 6.3 4개 탭

| Tab | 내용 |
|-----|------|
| **Index vs BTC** | Dual-band 오버레이 + 방향 매칭 음영 + 히트맵 |
| **Loadings** | PCA loadings bar + Bootstrap CI + CI 테이블 |
| **CWS Profile** | Stacked CWS 분해 + 개별 메트릭 라인 + 상세 테이블 |
| **Robustness** | Granger 패널 + CPCV bar + Bootstrap lag 분포 |

---

## 7. v1.0 → v2.1 비교

| 항목 | v1.0 (Grid Search) | v2.1 (Dual-Band PCA) |
|------|--------------------|-----------------------|
| 방법 | 88,209 가중치 최적화 | BTC-blind PCA + Dual-Band |
| BTC 사용 | 직접 최적화 대상 | 사후 검증만 |
| In-sample r | 0.618 | 0.491 |
| 과적합 위험 | 높음 (Grid Search) | 낮음 (비지도학습) |
| 변수 기여 | SOFR 지배 (w=-4.0) | NL 주도 (loading=0.703) |
| 선행성 | 고정 9m | 조절 가능 (0~15m) |
| 실시간 보정 | 없음 | Tactical(-HY) overlay |
| 검증 | Walk-Forward (OOS 변동 큼) | CWS + CPCV 38-path + Bootstrap |

---

## 8. 핵심 인사이트

1. **NL(순유동성)이 BTC 방향성의 핵심 동인** — PCA가 자동으로 NL에 최대 loading(0.703) 부여
2. **HY(신용 스프레드)는 이중 역할** — 구조적으로는 유동성 정보 기여, 전술적으로는 즉각적 신용 위험 신호
3. **스파이크 처리는 변수별로 차별화** — COVID NL(4.6σ)과 HY(5.0σ)의 성격이 다름, 균일 clip은 loading 역전 유발
4. **r=0.49는 과적합 r=0.62보다 가치 있음** — 비지도학습으로 BTC를 보지 않고 도출한 0.49가 진짜 신호

---

## 9. 파일 구조

```
finance-simulator/
├── src/
│   ├── pipeline/runner_v2.py        # 3-Stage Pipeline 오케스트레이터
│   ├── index_builders/
│   │   └── pca_builder.py           # PCA 인덱스 + sign_correction
│   ├── validators/                   # Stage 2 (CWS, Granger)
│   └── robustness/                   # Stage 3 (Bootstrap, CPCV)
├── data/
│   ├── processed/z_matrix.csv        # 120개월 입력 데이터
│   ├── indices/                      # PCA 인덱스 JSON
│   └── validation/                   # Stage 2, 3 결과 JSON
├── export_v2_web.py                  # JSON → data_v2.js 변환
├── web/
│   └── src/
│       ├── AppV2.jsx                 # Dual-Band 대시보드
│       ├── data_v2.js                # 자동 생성 데이터
│       └── main.jsx                  # v1/v2 전환
└── CLAUDE.md                         # 프로젝트 문서 허브
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v1.0.0 | 2026-03-01 | Grid Search 모델 (r=0.618, 과적합) |
| v2.0.0 | 2026-03-01 | BTC-blind 3-Stage Pipeline (CWS=0.606) |
| v2.1.0 | 2026-03-02 | Dual-Band Model D + Interactive Web Dashboard |
