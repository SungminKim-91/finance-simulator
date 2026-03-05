# Archive Index — 2026-03

## Archived Features

### btc-liquidity-model (v1.0.0)

| Item | Value |
|------|-------|
| Phase | Completed |
| Match Rate | 93% |
| Iterations | 0 |
| Started | 2026-03-01 |
| Completed | 2026-03-01 |
| Archived | 2026-03-01 |

**Documents:**
- [Plan](btc-liquidity-model/plan.md)
- [Design](btc-liquidity-model/design.md)
- [Analysis](btc-liquidity-model/analysis.md)
- [Report](btc-liquidity-model/report.md)

**Summary:** Grid Search 기반 BTC 유동성 예측 모델. 5개 변수 (NL, GM2, SOFR, HY, CME), In-sample r=0.6176, optimal lag=9m.

---

### btc-liquidity-v2 (v2.0.0)

| Item | Value |
|------|-------|
| Phase | Completed |
| Match Rate | 92% (88.5% → 92.0%, 1 iteration) |
| Iterations | 1 |
| Started | 2026-03-01 |
| Completed | 2026-03-01 |
| Archived | 2026-03-01 |

**Documents:**
- [Plan](btc-liquidity-v2/plan.md)
- [Design](btc-liquidity-v2/design.md)
- [Analysis](btc-liquidity-v2/analysis.md)
- [Report](btc-liquidity-v2/report.md)

**Summary:** 3-Stage Pipeline (BTC-blind 독립 인덱스 → 방향성 검증 → 과적합 방지). 14개 신규 모듈, PCA/ICA/SparsePCA/DFM, CWS 복합 메트릭. v1.0 과적합 문제 해결.

---

### web (v2.1.0) — Dual-Band Dashboard

| Item | Value |
|------|-------|
| Phase | Completed |
| Match Rate | 97.4% |
| Iterations | 0 |
| Started | 2026-03-01 |
| Completed | 2026-03-02 |
| Archived | 2026-03-02 |

**Documents:**
- [Analysis](web/analysis.md)
- [Report](web/report.md)
- [Model Development](web/model-development.md)

**Summary:** Dual-Band Model D — Structural(4-var PCA, shifted) + Tactical(-HY, realtime) + Combined(0.7/0.3 EMA). Variable-specific winsorize (Option H). Interactive dashboard: lag slider, tactical/combine toggle, smoothing. Structural r=+0.491, MDA=64.7%, CWS=0.606.

---

### kospi-vlpi-v1.5.0 — VLPI Backend Engine

| Item | Value |
|------|-------|
| Phase | Completed |
| Match Rate | 99.1% (94.7% → 99.1%, 1 iteration) |
| Iterations | 1 |
| Started | 2026-03-05 |
| Completed | 2026-03-05 |
| Archived | 2026-03-05 |

**Documents:**
- [Plan](kospi-vlpi-v1.5.0/kospi-vlpi-v1.5.0.plan.md)
- [Design](kospi-vlpi-v1.5.0/kospi-vlpi-v1.5.0.design.md)
- [Analysis](kospi-vlpi-v1.5.0/kospi-vlpi-v1.5.0.analysis.md)
- [Report](kospi-vlpi-v1.5.0/kospi-vlpi-v1.5.0.report.md)

**Summary:** VLPI(Voluntary Liquidation Pressure Index) Backend Engine. 반대매매→자발적 투매 패러다임 전환. 6변수 Pre-VLPI(0~100) + Sigmoid Impact Function. 6단계 상태 분류, 담보비율 LOAN_RATE 공식, EWY 야간갭, KOFIA 3-tier stub. 18 exports.

---

### kospi-vlpi-v1.6.0 — VLPI Frontend Dashboard + Date-Aware Cohort

| Item | Value |
|------|-------|
| Phase | Completed |
| Match Rate | 98.6% |
| Iterations | 0 |
| Started | 2026-03-05 |
| Completed | 2026-03-05 |
| Archived | 2026-03-05 |

**Documents:**
- [Plan](kospi-vlpi-v1.6.0/kospi-vlpi-v1.6.0.plan.md)
- [Design](kospi-vlpi-v1.6.0/kospi-vlpi-v1.6.0.design.md)
- [Analysis v1.6.0](kospi-vlpi-v1.6.0/kospi-vlpi-v1.6.0.analysis.md)
- [Analysis v1.6.1](kospi-vlpi-v1.6.0/kospi-vlpi-v1.6.1.analysis.md)
- [Report](kospi-vlpi-v1.6.0/kospi-vlpi-v1.6.0.report.md)

**Summary:** VLPI Frontend Dashboard — CohortRiskMap(게이지+변수분해), 6단계 코호트 색상, 기준일 선택 전 섹션 연동, Seed Cohort 수정(16.7T→32.2T), Section 3 시뮬레이터 비활성화(v1.6.1), 종목별 신용잔고 날짜 인식.

---

### kospi-rspi-v2.0.0 — RSPI (Retail Selling Pressure Index)

| Item | Value |
|------|-------|
| Phase | Completed |
| Match Rate | 98.7% |
| Iterations | 0 |
| Started | 2026-03-05 |
| Completed | 2026-03-06 |
| Archived | 2026-03-06 |

**Documents:**
- [Plan](kospi-rspi-v2.0.0/kospi-rspi-v2.0.0.plan.md)
- [Design](kospi-rspi-v2.0.0/kospi-rspi-v2.0.0.design.md)
- [Analysis](kospi-rspi-v2.0.0/kospi-rspi-v2.0.0.analysis.md)
- [Report](kospi-rspi-v2.0.0/kospi-rspi-v2.0.0.report.md)

**Summary:** VLPI→RSPI 전면 전환. 단방향(0~100)→양방향(-100~+100). CF(가속력) 4변수 - DF(감쇠력) 4변수. D1 야간회복(EWY+KORU+선물+미증시 4소스 coherence). rspi_engine.py 660줄 신규. 프론트엔드 RSPIGauge+DualBreakdown+ImpactTable 전면 재작성.
