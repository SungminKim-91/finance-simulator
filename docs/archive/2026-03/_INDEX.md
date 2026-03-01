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
