# PDCA Report Index

> **Completion Reports** — Feature implementation and verification records
>
> **Last Updated**: 2026-03-06
> **Status**: Active

---

## Feature Reports

### KOSPI Crisis Detector

| Feature | Version | Status | Match Rate | Date |
|---------|---------|--------|------------|------|
| **kospi-crisis v2.1.0** | v2.1.0 | Current | — | 2026-03-06 |
| **kospi-rspi v2.0.0** | v2.0.0 | Archived | 98.7% | 2026-03-06 |
| **kospi-vlpi v1.6.0** | v1.6.0 | Archived | 98.6% | 2026-03-05 |
| **kospi-vlpi v1.5.0** | v1.5.0 | Archived | 99.1% | 2026-03-05 |
| **kospi-crisis v1.4.0** | v1.4.0 | Approved | 100% | 2026-03-05 |
| **kospi-crisis v1.3.0** | v1.3.0 | Approved | — | 2026-03-04 |
| **kospi-crisis-phase2 v1.4** | v1.4 | Approved | 100% | 2026-03-04 |
| **kospi-crisis v1.2.0** | v1.2.0 | Approved | — | 2026-03-04 |
| **kospi-crisis-phase2** | v1.1.0 | Archived | 98.9% | 2026-02-28 |
| **kospi-crisis-phase1** | v1.0.2 | Archived | 100% | 2026-02-10 |

### BTC Liquidity Model

| Feature | Version | Status | Match Rate | Date |
|---------|---------|--------|------------|------|
| **web dual-band** | v2.1.0 | Archived | 97.4% | 2026-03-02 |
| **btc-liquidity-v2** | v2.0.0 | Archived | 92% | 2026-03-01 |
| **btc-liquidity-model** | v1.0.0 | Archived | 93% | 2026-03-01 |

---

## Latest: KOSPI v2.1.0 — RSPI 실데이터 + Raw Data

### Key Achievements (v1.3.0 → v2.1.0)
1. **v1.3.0**: 종목별 가중 모델 — 10종목 시가총액 기반 코호트
2. **v1.4.0**: 자동청산 + 백테스트 코호트 바 차트
3. **v1.5.0**: VLPI Backend — 반대매매→자발적 투매 패러다임 전환 (99.1%)
4. **v1.6.0**: VLPI Frontend — 게이지+변수분해+6단계 색상+기준일 연동 (98.6%)
5. **v2.0.0**: RSPI — VLPI→양방향(-100~+100), CF/DF 8변수 (98.7%)
6. **v2.1.0**: RSPI 실데이터 — 262일 히스토리, backfill, Raw Data 33컬럼

### Architecture Evolution
```
v1.0~1.2: 반대매매 중심 (강제청산 시뮬레이션)
v1.3:     종목별 가중 (portfolio beta)
v1.4:     담보비율 자동청산
v1.5:     VLPI (자발적 투매, 단방향 0~100)
v1.6:     VLPI Frontend (6단계 게이지)
v2.0:     RSPI (양방향 -100~+100, CF-DF)
v2.1:     실데이터 통합 + Raw Data 전면 확장
```

---

## Reports

- [kospi-crisis-v1.4-refactor.report.md](kospi-crisis-v1.4-refactor.report.md) — v1.4 Loop refactoring
- [Changelog](changelog.md) — Full version history (v1.0.0 ~ v2.1.0)
- Archive: `docs/archive/2026-03/` (VLPI v1.5.0, v1.6.0, RSPI v2.0.0)

---

**Report Dashboard**: `/home/sungmin/finance-simulator/web/docs/04-report/`
**Last Generated**: 2026-03-06 KST
