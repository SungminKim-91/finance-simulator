# Gap Analysis: KOSPI Crisis Detector v1.1.1 — Bugfix & UX Improvement

> Feature: `kospi-crisis-v1.1.1-bugfix` | Version: 1.1.1 | Date: 2026-03-04
> Design Reference: `docs/02-design/features/kospi-crisis-v1.1.1-bugfix.design.md`

---

## 1. Design vs Implementation Comparison

### 1.1 File Delivery

| Planned File | Delivered | Status |
|-------------|-----------|--------|
| `kospi/scripts/naver_scraper.py` (+investor) | Yes | PASS |
| `kospi/scripts/fetch_daily.py` (6-step) | Yes | PASS |
| `kospi/scripts/compute_models.py` (carry-forward) | Yes | PASS |
| `kospi/scripts/export_web.py` (fin_invest direct) | Yes | PASS |
| `web/src/simulators/kospi/MarketPulse.jsx` | Yes | PASS |
| **Total** | **5/5** | **100%** |

### 1.2 Issue Resolution

| # | Issue | Planned Fix | Delivered | Status |
|---|-------|-------------|-----------|--------|
| 1 | 신용/예탁 토글 + 3M | Toggle buttons + default 66 days | Yes | PASS |
| 2 | 비거래일 갭 | connectNulls on all Lines | Yes | PASS |
| 3 | 반대매매 삭제 + 수급 상단 | Section remove + reorder | Yes | PASS |
| 4 | 투자자 수급 데이터 | Naver investor scraper | Yes | PASS |
| 5 | 코호트 빈 결과 | null credit carry-forward | Yes | PASS |

### 1.3 Data Quality

| Metric | Before (v4.1) | After (v1.1.1) |
|--------|---------------|----------------|
| individual_billion | 0/282 (0%) | **282/282 (100%)** |
| institution_billion | 0/282 (0%) | **282/282 (100%)** |
| financial_invest_billion | N/A | **282/282 (100%)** |
| foreign_billion | 281/282 (99.6%) | **282/282 (100%)** |
| Cohort LIFO | 0 | **130** |
| Cohort FIFO | 0 | **127** |
| Trigger map (non-zero) | 0/6 | **6/6** |

---

## 2. Verification

### 2.1 Pipeline Test

```
$ python -m scripts.fetch_daily --range 2025-01-01 2026-03-04
  ECOS: 281일 | Naver: 280일 | Investor: 282일 | yfinance: 303일
  완료: 282일 저장

$ python -m scripts.compute_models
  Crisis Score: 35.9 (normal)
  Cohorts: LIFO 130, FIFO 127

$ python -m scripts.export_web
  Market: 282 | Flows: 282 | Cohorts: LIFO 130, FIFO 127

$ cd web && npx vite build
  ✓ built in 2.05s (no errors)
```

### 2.2 Removed Code

| Item | Removed | Status |
|------|---------|--------|
| `FORCED_LIQ_THRESHOLD` constant | Yes | PASS |
| `fmtHundM()` function | Yes | PASS |
| `forcedLiqZoom` state | Yes | PASS |
| `forcedLiqAxis` memo | Yes | PASS |
| 반대매매 PanelBox section | Yes | PASS |

---

## 3. Match Rate

| Category | Score |
|----------|-------|
| File Delivery | 100% |
| Issue 1 (Toggle + 3M) | 100% |
| Issue 2 (connectNulls) | 100% |
| Issue 3 (Section reorder) | 100% |
| Issue 4 (Investor data) | 100% |
| Issue 5 (Cohort fix) | 100% |
| **Overall Match Rate** | **100%** |

---

**Status**: PASS (100%)
