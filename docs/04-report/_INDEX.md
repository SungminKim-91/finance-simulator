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
| **kospi-crisis-phase2-v1.4** | v1.4 | [Link](kospi-crisis-v1.4-refactor.report.md) | ✅ Approved | **100%** | 2026-03-04 |
| **kospi-crisis-phase2** | v1.1.0 | Archived | ✅ Approved | 98.9% | 2026-02-28 |
| **kospi-crisis-phase1** | v1.0.2 | Archived | ✅ Approved | 100% | 2026-02-10 |

### BTC Liquidity Model

| Feature | Version | Report | Status | Match Rate | Completion Date |
|---------|---------|--------|--------|------------|-----------------|
| **btc-liquidity-v2** | v2.0.0 | Archived | ✅ Approved | 92% | 2026-03-02 |
| **btc-liquidity-model** | v1.0.0 | Archived | ✅ Approved | 93% | Earlier |

---

## Latest Report: KOSPI Crisis Detector v1.4

### Overview
- **Feature**: kospi-crisis-phase2 (Phase 2 refactoring)
- **Version**: v1.1.0 → v1.4
- **Duration**: Full PDCA cycle
- **Status**: ✅ Approved
- **Match Rate**: 100% (8/8 verification tests passed)

### Key Changes
1. **Loop B Removed**: FX-foreign investor feedback (50% accuracy → unreliable)
2. **Loop C Added**: Fund redemption cascade (T+1~T+3 delayed mechanics)
3. **Crisis Score**: 13→14 indicators (new: credit_suspension, institutional_selling, retail_exhaustion, bull_trap)
4. **Scenarios**: 4→5 (S5 Fundamental Collapse added)
5. **Defense Walls**: 5-stage system (retail → institution → BOK → US → IMF)

### Files Changed
```
web/src/simulators/kospi/
├── colors.js                 (+1 line, S5 color)
├── data/kospi_data.js        (+100 lines, data restructure)
├── shared/terms.jsx          (+30 lines, 14 TERM updates)
├── CrisisAnalysis.jsx        (+150 lines, NEW component, 6 sections)
└── HistoricalComp.jsx        (0 lines, auto-updated from data)
```

### Test Results
| Category | Result |
|----------|--------|
| Weights validation | ✅ PASS |
| Probabilities validation | ✅ PASS |
| Defense walls | ✅ PASS |
| Loop structure | ✅ PASS |
| Color definitions | ✅ PASS |
| Terms dictionary | ✅ PASS |
| Build (npm) | ✅ PASS |
| Runtime | ✅ PASS |

---

## All Reports

### Completed Features (PDCA Approved)

1. **KOSPI Crisis Detector v1.4** (2026-03-04)
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
| [Latest Report](kospi-crisis-v1.4-refactor.report.md) | v1.4 completion details |
| [Changelog](changelog.md) | Full version history |
| [PDCA Status](../.pdca-status.json) | Current feature phases |
| [Plan Docs](../01-plan/) | Feature planning documents |
| [Design Docs](../02-design/) | Technical design specifications |
| [Analysis Docs](../03-analysis/) | Gap analysis and verification |

---

**Report Dashboard**: `/home/sungmin/finance-simulator/web/docs/04-report/`
**Last Generated**: 2026-03-04 16:35:00 KST
