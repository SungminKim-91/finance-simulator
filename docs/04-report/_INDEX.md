# PDCA Report Index

> **Completion Reports** — Feature implementation and verification records
>
> **Last Updated**: 2026-03-04
> **Status**: Active

---

## Feature Reports

### KOSPI Crisis Detector

| Feature | Version | Report | Status | Match Rate | Completion Date |
|---------|---------|--------|--------|------------|-----------------|
| **kospi-crisis-v1.1.1-bugfix** | v1.1.1 | [Link](features/kospi-crisis-v1.1.1-bugfix.report.md) | ✅ Approved | **100%** | 2026-03-04 |
| **kospi-phase4.1-data-sources** | v4.1 | [Link](features/kospi-phase4.1-data-sources.report.md) | ✅ Approved | **93%** | 2026-03-04 |
| **kospi-crisis-phase2-v1.4** | v1.4 | [Link](kospi-crisis-v1.4-refactor.report.md) | ✅ Approved | **100%** | 2026-03-04 |
| **kospi-crisis-phase2** | v1.1.0 | Archived | ✅ Approved | 98.9% | 2026-02-28 |
| **kospi-crisis-phase1** | v1.0.2 | Archived | ✅ Approved | 100% | 2026-02-10 |

### BTC Liquidity Model

| Feature | Version | Report | Status | Match Rate | Completion Date |
|---------|---------|--------|--------|------------|-----------------|
| **btc-liquidity-v2** | v2.0.0 | Archived | ✅ Approved | 92% | 2026-03-02 |
| **btc-liquidity-model** | v1.0.0 | Archived | ✅ Approved | 93% | Earlier |

---

## Latest Report: KOSPI v1.1.1 Bugfix & UX Improvement

### Overview
- **Feature**: kospi-crisis-v1.1.1-bugfix
- **Version**: v1.1.1
- **Duration**: Full PDCA cycle
- **Status**: ✅ Approved
- **Match Rate**: 100%

### Key Changes
1. **Naver Investor Scraper**: 투자자별 매매동향 282일 (개인/외국인/기관/금투)
2. **Cohort Bug Fix**: null credit carry-forward → LIFO 130, FIFO 127
3. **UI Reorder**: 반대매매 삭제, 투자자 수급 최상단
4. **Credit Toggle**: 신용잔고/고객예탁금 개별 on/off
5. **Default 3M**: 기본 기간 ALL → 3M (66일)

### Files Changed
```
kospi/scripts/
├── naver_scraper.py    (+120 lines, investor flows)
├── fetch_daily.py      (+39 lines, 6-step pipeline)
├── compute_models.py   (+13 lines, carry-forward)
└── export_web.py       (+11/-6 lines, fin_invest direct)

web/src/simulators/kospi/
└── MarketPulse.jsx     (+/-275 lines, UI overhaul)
```

### Test Results
| Category | Result |
|----------|--------|
| Naver investor 282일 | ✅ PASS |
| Cohort LIFO 130, FIFO 127 | ✅ PASS |
| export_web 13 exports | ✅ PASS |
| vite build | ✅ PASS |

---

## All Reports

### Completed Features (PDCA Approved)

1. **KOSPI Crisis Detector v1.1.1 Bugfix** (2026-03-04)
   - Report: [kospi-crisis-v1.1.1-bugfix.report.md](features/kospi-crisis-v1.1.1-bugfix.report.md)
   - Match Rate: 100%
   - Changes: Naver investor scraper, cohort null fix, MarketPulse UI overhaul

2. **KOSPI Phase 4.1 Data Sources** (2026-03-04)
   - Report: [kospi-phase4.1-data-sources.report.md](features/kospi-phase4.1-data-sources.report.md)
   - Match Rate: 93%
   - Changes: ECOS + Naver + KRX integration, 282-day real data pipeline

3. **KOSPI Crisis Detector v1.4** (2026-03-04)
   - Report: [kospi-crisis-v1.4-refactor.report.md](kospi-crisis-v1.4-refactor.report.md)
   - Match Rate: 100%
   - Changes: Loop refactoring, defense walls, 14-indicator model

2. **KOSPI Crisis Detector v1.1.0** (2026-02-28)
   - Status: Archived
   - Match Rate: 98.9%
   - Phase 2 UI improvements

3. **BTC Liquidity v2.0.0** (2026-03-02)
   - Status: Archived
   - Match Rate: 92%
   - 3-stage pipeline (PCA/ICA/DFM)

### Navigation

- [Changelog](changelog.md) — Version history and release notes
- [PDCA Status](../.pdca-status.json) — Current phase tracking

---

## Document Standards

### Report Structure
- **Summary**: One-line feature description
- **PDCA Cycle**: Plan → Design → Do → Check → Report phases
- **Design vs Implementation**: Detailed comparison table
- **Match Rate**: Quantified verification percentage
- **Lessons Learned**: What went well, areas for improvement
- **Next Steps**: Follow-up actions and improvements

### File Naming
- Format: `{feature}-v{N}-{type}.report.md` or `{feature}.report.md`
- Example: `kospi-crisis-v1.4-refactor.report.md`

### Status Indicators
- ✅ **Approved**: Completed, all tests passed (>= 90% match rate)
- 🔄 **In Progress**: Active feature in development
- ⏸️ **On Hold**: Temporarily paused
- ❌ **Deprecated**: No longer maintained
- 📦 **Archived**: Completed and archived to docs/archive/

---

## Quick Links

| Resource | Purpose |
|----------|---------|
| [Latest Report](features/kospi-crisis-v1.1.1-bugfix.report.md) | v1.1.1 bugfix & UX improvement |
| [Changelog](changelog.md) | Full version history |
| [PDCA Status](../.pdca-status.json) | Current feature phases |
| [Plan Docs](../01-plan/) | Feature planning documents |
| [Design Docs](../02-design/) | Technical design specifications |
| [Analysis Docs](../03-analysis/) | Gap analysis and verification |

---

**Report Dashboard**: `/home/sungmin/finance-simulator/web/docs/04-report/`
**Last Generated**: 2026-03-04 19:40:00 KST
