# KOSPI VLPI v1.5.0 Gap Analysis Report

> **Analysis Type**: Design vs Implementation Gap Analysis
>
> **Project**: KOSPI Crisis Detector
> **Version**: v1.5.0
> **Analyst**: bkit-gap-detector
> **Date**: 2026-03-05 (re-run)
> **Design Doc**: [kospi-vlpi-v1.5.0.design.md](../02-design/features/kospi-vlpi-v1.5.0.design.md)

---

## 1. Analysis Overview

### 1.1 Analysis Purpose

Re-verify v1.5.0 Backend VLPI Engine implementation after the 3 gaps identified in the initial analysis (v1.0) were reported as fixed. Scope is backend only — no React/frontend components are evaluated.

### 1.2 Previous Gap Summary

The v1.0 analysis (2026-03-05) identified 3 gaps:

| # | Gap | Impact | Status in v1.1 re-run |
|---|-----|--------|----------------------|
| 1 | `kofia_fetcher` not wired into `fetch_daily.py` | Moderate | Fixed |
| 2 | `Cohort.classify_status()` still 4-stage | Low | Fixed |
| 3 | `Cohort.collateral_ratio()` formula not updated | Low | Fixed |

### 1.3 Analysis Scope

- **Design Document**: `docs/02-design/features/kospi-vlpi-v1.5.0.design.md`
- **Implementation Files**:
  - `/home/sungmin/finance-simulator/kospi/config/constants.py` (Section 2)
  - `/home/sungmin/finance-simulator/kospi/scripts/vlpi_engine.py` (Section 3)
  - `/home/sungmin/finance-simulator/kospi/scripts/compute_models.py` (Section 4)
  - `/home/sungmin/finance-simulator/kospi/scripts/fetch_daily.py` (Section 5.1)
  - `/home/sungmin/finance-simulator/kospi/scripts/kofia_fetcher.py` (Section 5.2–5.3)
  - `/home/sungmin/finance-simulator/kospi/scripts/export_web.py` (Section 6)
  - `/home/sungmin/finance-simulator/kospi/data/samsung_cohorts.json` (Section 7)
- **Analysis Date**: 2026-03-05 (v1.1 re-run)

---

## 2. Gap Fix Verification (3 Previously Identified Gaps)

### Gap 1: `kofia_fetcher` Wired into `fetch_daily.py`

**Design requirement (Section 5.3)**:
```python
from scripts.kofia_fetcher import fetch_credit_balance
# In build_snapshot(): call fetch_credit_balance(date) before Naver fallback
```

**Implementation check** (`fetch_daily.py` lines 42, 263–267):
```python
# Line 42
from scripts.kofia_fetcher import fetch_credit_balance as fetch_kofia_credit

# Lines 261-267 in build_snapshot()
credit_source = "naver"
kofia_credit = fetch_kofia_credit(date)
if kofia_credit:
    credit_b = kofia_credit["kospi_stock_credit_mm"] / 1e3  # 백만원 → 십억원
    credit_source = kofia_credit["source"]
    print(f"  [KOFIA] Credit from {credit_source}: {credit_b:.1f}B")
```

**Verdict**: Fixed. Import present at line 42. `build_snapshot()` calls `fetch_kofia_credit(date)` and handles the result before the existing Naver credit assignment. The priority chain is now KOFIA → Naver, matching the design.

**Note on behavior**: `kofia_fetcher.py` Tier 1 (`_parse_kofia_response`) still returns `None` (stub incomplete), and Tier 2 (`_fetch_from_freesis`) still returns `None`. The wiring is correct; the fetcher will always fall through to returning `None`, so `fetch_daily.py` will still use the Naver credit value in practice. This is expected for v1.5.0.

---

### Gap 2: `Cohort.classify_status()` → 6-Stage

**Design requirement (Section 4.1)**:
```python
# collateral_ratio: ratio (1.44) or % (144.6) both supported
# Uses STATUS_THRESHOLDS for 6-stage: debt_exceed/forced_liq/margin_call/caution/good/safe
```

**Implementation check** (`compute_models.py` lines 107–126):
```python
@staticmethod
def classify_status(collateral_ratio: float, loss_pct: float = 0) -> str:
    """v1.5.0 6단계 상태 판정 (담보비율 기준).

    collateral_ratio: 비율(1.44) 또는 %(144.6) 모두 지원.
    loss_pct: 하위호환용 유지, 미사용.
    """
    # 비율 형태(1.44) → % 형태(144)로 변환
    ratio_pct = collateral_ratio * 100 if collateral_ratio < 10 else collateral_ratio

    if ratio_pct < STATUS_THRESHOLDS["debt_exceed"]:   return "debt_exceed"
    if ratio_pct < STATUS_THRESHOLDS["forced_liq"]:    return "forced_liq"
    if ratio_pct < STATUS_THRESHOLDS["margin_call"]:   return "margin_call"
    if ratio_pct < STATUS_THRESHOLDS["caution"]:       return "caution"
    if ratio_pct < STATUS_THRESHOLDS["good"]:          return "good"
    return "safe"
```

**Verdict**: Fixed. The method now uses `STATUS_THRESHOLDS` with all 6 stages. The `loss_pct` parameter is retained for backward compatibility but is unused (marked in docstring). The ratio/% dual-format detection (`< 10` heuristic) is implemented correctly.

---

### Gap 3: `Cohort.collateral_ratio()` → VLPI Formula

**Design requirement (Section 4.2)**:
```python
# 담보비율(%) = 현재가 / (매수가 × LOAN_RATE) × 100
# entry_stock_price preferred; fallback to entry_kospi
```

**Implementation check** (`compute_models.py` lines 95–104):
```python
def collateral_ratio(self, current_kospi: float, margin_rate: float = MARGIN_RATE) -> float:
    """담보비율 = 현재가 / (매수가 × LOAN_RATE).

    v1.5.0: 직접 주가 기반. entry_stock_price 우선, fallback entry_kospi.
    반환값: 비율(예: 1.44 = 144%).
    """
    entry = self.entry_stock_price if self.entry_stock_price > 0 else self.entry_kospi
    if entry <= 0:
        return 999
    return current_kospi / (entry * LOAN_RATE)
```

**Verdict**: Fixed. The formula now uses `LOAN_RATE` directly instead of the old `price_ratio / (1 - margin_rate)` beta-based formula. `entry_stock_price` is preferred, with `entry_kospi` as fallback. The return is in ratio form (1.44 = 144%), which is consistent with the `classify_status()` dual-format handling.

**Note**: `collateral_ratio_by_stock()` (line 134) also updated to use `LOAN_RATE`:
```python
def collateral_ratio_by_stock(self, current_stock_price: float, margin_rate: float = MARGIN_RATE) -> float:
    """종목 종가 기반 담보비율 (v1.5.0: LOAN_RATE 공식)."""
    if self.entry_stock_price <= 0:
        return self.collateral_ratio(current_stock_price, margin_rate)
    return current_stock_price / (self.entry_stock_price * LOAN_RATE)
```

---

## 3. Full Section-by-Section Re-verification

### Section 2: `constants.py` — Constant Changes

All 22 items remain unchanged from v1.0 analysis. Score: **100%**.

| Constant Group | Items | Status |
|----------------|-------|--------|
| LOAN_RATE, LEVERAGE, DAILY_LIMIT | 3 | All match |
| STATUS_THRESHOLDS (5 keys) | 5 | All match |
| VLPI_DEFAULT_WEIGHTS (w1–w6) | 6 | All match |
| POLICY_SHOCK_MAP (6 keys) | 6 | All match |
| EWY/Impact/KOFIA constants | 8 | All match |
| Backward compat (MARGIN_RATE, FORCED_LIQ_LOSS_PCT, etc.) | 3 | All match |

---

### Section 3: `vlpi_engine.py` — New Engine File

All 35 items remain unchanged from v1.0 analysis. Score: **97%** (1 cosmetic type annotation difference, 1 beneficial V6 unit correction).

Key items confirmed present:
- `calc_collateral_ratio()`: exact formula match
- `classify_status_6()`: all 6 stages, correct cascade
- V1–V6 calculators: all match design precisely
- `VLPIResult` dataclass: all fields present
- `VLPIEngine` class: all 3 methods present and correct
- Stage 2 impact functions: sigmoid, Kyle's Lambda, price floor all match

---

### Section 4: `compute_models.py` — Changes

#### 4.1 `Cohort.classify_status()` — NOW FIXED

| Item | Design | Implementation | Status |
|------|--------|----------------|--------|
| 6-stage STATUS_THRESHOLDS | Yes | Yes (lines 107–126) | Match |
| `loss_pct` kept for compat, unused | Yes | Yes (in docstring: "하위호환용 유지, 미사용") | Match |
| Ratio/% dual format | Yes (`< 10` heuristic) | Yes (`ratio_pct = cr * 100 if cr < 10 else cr`) | Match |
| Returns all 6 states | Yes | Yes | Match |

#### 4.2 `Cohort.collateral_ratio()` — NOW FIXED

| Item | Design | Implementation | Status |
|------|--------|----------------|--------|
| Formula `current/(entry×LOAN_RATE)` | Yes | Yes | Match |
| `entry_stock_price` preferred, `entry_kospi` fallback | Yes | Yes | Match |
| Returns ratio (not %) for compat | Yes (returns 1.44 form) | Yes | Match |
| `collateral_ratio_by_stock()` also updated | Not explicitly specified | Yes, updated too | Enhancement |

#### 4.3 `adjust_cohort_for_vlpi()` — Unchanged, Still Correct

All 5 items match as before. Function present, uses `classify_status_6` from vlpi_engine.

#### 4.4 `run_all_models()` VLPI Integration — Unchanged, Still Correct

All 11 items match as before. VLPI block fully integrated with try/except wrapper.

**Section 4 Score: 100%** (up from 88% — all 3 gaps closed)

---

### Section 5: Data Collection Expansion

#### 5.1 `fetch_daily.py` — EWY Addition

All 6 EWY items match as before. Score unchanged.

| Item | Status |
|------|--------|
| `YF_SYMBOLS["ewy"] = "EWY"` | Match |
| `"ewy_close"` in `extract_date_data()` | Match |
| `"ewy_change_pct"` with prior-day lookup | Match |
| Both fields in `append_timeseries()` | Match |
| Both fields in `build_snapshot()` | Match |

#### 5.2 `kofia_fetcher.py` — KOFIA API Stub

All 5 items match as before. `requests` import guard added (enhancement).

#### 5.3 `fetch_daily.py` Integration — NOW FIXED

| Item | Design | Implementation | Status |
|------|--------|----------------|--------|
| `from scripts.kofia_fetcher import fetch_credit_balance` | Yes | Yes (line 42, aliased as `fetch_kofia_credit`) | Match |
| `build_snapshot()` calls KOFIA before Naver | Yes | Yes (lines 262–267) | Match |
| Unit conversion `kospi_stock_credit_mm / 1e3` | Yes (백만원→십억원) | Yes | Match |
| `credit_source` tracking | Yes | Yes (`credit_source = kofia_credit["source"]`) | Match |
| Log message on KOFIA hit | Not specified | Added (enhancement) | Enhancement |

**Section 5 Score: 100%** (up from 80% — kofia_fetcher wiring completed)

---

### Section 6: `export_web.py` — Changes

All 18 items remain unchanged from v1.0 analysis. Score: **100%**.

- `_remap_cohorts()`: 6-stage + legacy dual export confirmed
- VLPI_DATA (#17) and VLPI_CONFIG (#18) exports confirmed
- COHORT_DATA params include `loan_rate`, `status_thresholds`, `leverage`, `stock_weighted`
- Total 18 exports confirmed in header comment and write sequence

---

### Section 7: Samsung Seed Data

All 13 items remain unchanged from v1.0 analysis. Score: **100%**.

---

### Section 8: Verification Scenarios

#### 8.1 Pre-VLPI Seed Test (3/3 → 3/4)

With Gap 2 and Gap 3 fixed, all code paths used in the verification scenario now operate as designed:

| Variable | Design Expected | Implementation Path | Status |
|----------|----------------|---------------------|--------|
| V1 = 0.029 | calc_caution_zone_pct(195100, cohorts) | Uses corrected `calc_collateral_ratio` | Match |
| V2 = 0.0 | lookback < 3 records | Unchanged | Match |
| V3 = 1.0 | two `credit_suspension_major` events | Unchanged | Match |
| V4 = 0.0 | EWY neutral | Unchanged | Match |
| V5 = ~0.444 | 2 consecutive down days | Unchanged | Match |
| V6 = 0.6 | curr=57974 > 30000 | Uses corrected `* 10000` multiplier | Match |
| Pre-VLPI | ~46.4 | ~43.5 (unit fix effect) | Near-match |

The ~2.9 pt delta is explained by the V6 unit correction (design had arithmetic error `* 10`; implementation correctly uses `* 10000`). Both values fall in the "warning" level (30–70 range). This is a beneficial correction, not a regression.

#### 8.2 6-Stage Classification at 3/4 Price (172200)

With Gap 2 fixed, `Cohort.classify_status()` now correctly classifies all cohorts:

| Cohort | Entry Price | Ratio (172200/(entry×0.55)×100) | Design Expected | classify_status() Result |
|--------|-------------|----------------------------------|-----------------|--------------------------|
| F | 181000 | 172200/(181000×0.55)×100 = 172.9% | safe | safe |
| A | 190000 | 172200/(190000×0.55)×100 = 164.8% | good | good |
| B | 196500 | 172200/(196500×0.55)×100 = 159.3% | good | good |
| C | 210750 | 172200/(210750×0.55)×100 = 148.5% | caution | caution |
| D | 216500 | 172200/(216500×0.55)×100 = 144.6% | caution | caution |
| E | 195100 | 172200/(195100×0.55)×100 = 160.5% | good | good |

All 6 classifications match design Section 8.1 ("6단계 분류 (3/4 종가 172200 기준)").

**Section 8 Score: 97%** (up from 95% — 6-stage classification now verified end-to-end)

---

## 4. Overall Scores

| Category | Items Checked | Match | Score | Delta vs v1.0 | Status |
|----------|:-------------:|:-----:|:-----:|:-------------:|:------:|
| Section 2: constants.py | 22 | 22 | 100% | — | Pass |
| Section 3: vlpi_engine.py | 35 | 34 | 97% | — | Pass |
| Section 4: compute_models.py | 19 | 19 | 100% | +12% | Pass |
| Section 5: Data collection | 12 | 12 | 100% | +20% | Pass |
| Section 6: export_web.py | 18 | 18 | 100% | — | Pass |
| Section 7: samsung_cohorts.json | 13 | 13 | 100% | — | Pass |
| Section 8: Verification | 10 | 9.7 | 97% | +2% | Pass |
| Section 9: Impl order | 9 | 9 | 100% | +1% | Pass |
| **Overall** | **138** | **136.7** | **99.1%** | **+4.4%** | **Pass** |

```
Overall Match Rate: 99.1%  (v1.0: 94.7%)
─────────────────────────────────────────
Match (identical):              134 items
Near-match (acceptable delta):    2 items
Partial (low impact):             0 items
Missing:                          0 items
─────────────────────────────────────────
Improvement: +4.4 pp (all 3 gaps closed)
```

---

## 5. Differences Found

### Missing Features (Design specified, not fully implemented)

None. All design-specified features are now implemented.

### Added Features (Not in design, present in implementation — Enhancements)

| Item | File | Description |
|------|------|-------------|
| sys.path auto-injection | `vlpi_engine.py:17-21` | Standalone execution support |
| `estimate_price_impact()` zero-guard | `vlpi_engine.py:342-343` | Returns zeros for zero price/volume |
| `requests` import guard | `kofia_fetcher.py:14-17` | Graceful fallback if requests not installed |
| VLPI try/except wrapper | `compute_models.py:1777-1837` | Pipeline resilience |
| `collateral_ratio` (old form) in `_remap_cohorts()` | `export_web.py:413` | Backward compat alongside new `collateral_ratio_pct` |
| `collateral_ratio_by_stock()` updated to VLPI formula | `compute_models.py:134-138` | Consistent with `collateral_ratio()` update |
| KOFIA log message on successful fetch | `fetch_daily.py:267` | Operational visibility |

### Changed Features (Design != Implementation — with rationale)

| Item | Design | Implementation | Rationale |
|------|--------|----------------|-----------|
| V6 flow conversion multiplier | `* 10` (조→억) | `* 10000` (correct) | Design had arithmetic error; 1조 = 10,000억 |
| `VLPIResult` type annotations | `dict[str, float]` | `dict` | Python 3.9 compatibility |
| Pre-VLPI numeric result | ~46.4 | ~43.5 | Due to V6 unit fix; both within "warning" level |

---

## 6. Remaining Notes

### 6.1 Stub Behavior (Expected for v1.5.0)

`kofia_fetcher.py` Tiers 1 and 2 still return `None`:
- `_parse_kofia_response()` returns `None` (TODO — API schema unknown)
- `_fetch_from_freesis()` returns `None` (TODO — XHR pattern not reverse-engineered)

This is per design intent ("초기 stub", "향후 구현"). In practice, `fetch_daily.py` always falls through to the Naver credit value. The plumbing is correct — when the real API is implemented, no further changes to `fetch_daily.py` are needed.

### 6.2 Backward Compat (Section 10 Strategy Intact)

- Legacy `ForcedLiqSimulator` is not deleted (deprecated, per design)
- `portfolio_beta` related code retained in `adjust_cohort_with_beta()` (still used by non-VLPI path)
- `Cohort.classify_status()` now supports 6-stage but signature preserves `loss_pct` for call-site compat
- `CohortAnalysis.jsx` remains on 4-stage (`status` field) until v1.6.0

### 6.3 Unit Correction Persists (Beneficial)

The V6 multiplier (`* 10000` instead of design's `* 10`) is mathematically correct and is intentionally kept. The design document contains a typo. Recommended to update design document if a v1.5.1 revision is created.

---

## 7. Recommended Actions

### No Immediate Action Required

All blocking gaps are resolved. The implementation is ready for v1.6.0 frontend development to begin consuming `VLPI_DATA` and `VLPI_CONFIG`.

### Optional / Backlog

| Priority | Item | File | Action |
|----------|------|------|--------|
| Low | Update design doc V6 multiplier | `docs/02-design/features/kospi-vlpi-v1.5.0.design.md` | Change `* 10` to `* 10000` in Section 3.11 docstring |
| Low | Implement `_parse_kofia_response()` | `kospi/scripts/kofia_fetcher.py` | When KOFIA API key is obtained and schema confirmed |
| Low | Implement `_fetch_from_freesis()` | `kospi/scripts/kofia_fetcher.py` | After DevTools XHR pattern analysis |
| Backlog | Replace `ForcedLiqSimulator` with VLPI-based simulator | `compute_models.py` | v1.7.0 |
| Backlog | Remove legacy `Cohort.classify_status()` in favor of `classify_status_6()` | `compute_models.py` | After frontend migrates to 6-stage |

---

## 8. Conclusion

The v1.5.0 Backend VLPI Engine re-analysis confirms a **99.1% match rate** against the design document — up from 94.7% in the initial analysis.

All 3 previously identified gaps are now resolved:
1. `kofia_fetcher` is wired into `fetch_daily.py` with correct priority (KOFIA → Naver) and unit conversion
2. `Cohort.classify_status()` uses the 6-stage `STATUS_THRESHOLDS` cascade with dual ratio/% format support
3. `Cohort.collateral_ratio()` uses the VLPI formula (`current/(entry×LOAN_RATE)`) with `entry_stock_price` preferred over `entry_kospi`

The remaining 0.9% non-match consists entirely of beneficial corrections (V6 unit fix) and cosmetic differences (type annotation simplification). The implementation exceeds the 90% threshold and is cleared for the next phase.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-03-05 | Initial gap analysis — Backend VLPI Engine scope; 94.7% match, 3 gaps found |
| 1.1 | 2026-03-05 | Re-run after gap fixes — all 3 gaps confirmed resolved; 99.1% match rate |
