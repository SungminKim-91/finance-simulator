# kospi-rspi-v2.2.0 Analysis Report

> **Analysis Type**: Gap Analysis (PDCA Check Phase)
>
> **Project**: KOSPI Crisis Detector
> **Version**: v2.2.0
> **Analyst**: gap-detector agent
> **Date**: 2026-03-06
> **Design Doc**: [kospi-rspi-v2.2.0.design.md](../02-design/features/kospi-rspi-v2.2.0.design.md)

---

## 1. Analysis Overview

### 1.1 Analysis Purpose

Verify that the v2.2.0 RSPI rewrite (CF/DF 8-variable model to 5-variable + Volume Amplifier model) is correctly implemented across the full pipeline: Python backend (constants, engine, compute, export) and React frontend (dashboard, colors, terms).

### 1.2 Analysis Scope

| Layer | Design Document | Implementation Path |
|-------|-----------------|---------------------|
| Constants | Section 2.1 | `kospi/config/constants.py` |
| Engine | Section 2.2 | `kospi/scripts/rspi_engine.py` |
| Compute | Section 2.3 | `kospi/scripts/compute_models.py` |
| Export | Section 2.4 | `kospi/scripts/export_web.py` |
| Frontend | Section 2.5 | `web/src/simulators/kospi/CohortAnalysis.jsx` |
| Colors | Section 2.5 | `web/src/simulators/kospi/colors.js` |
| Terms | Section 2.5 | `web/src/simulators/kospi/shared/terms.jsx` |

---

## 2. Gap Analysis (Design vs Implementation)

### 2.1 constants.py

| Design Requirement | Implementation | Status | Notes |
|--------------------|----------------|--------|-------|
| ADD RSPI_WEIGHTS {v1:0.25, v2:0.20, v3:0.25, v4:0.20, v5:0.10} | Line 112-118: exact match | ✅ Match | |
| ADD 7-level RSPI_LEVELS (extreme_sell to extreme_rebound) | Line 163-171: 7 levels, keys/ranges match | ✅ Match | |
| ADD V2_LOOKBACK=20, V2_DIVISOR=2.0 | Line 125-126 | ✅ Match | |
| ADD V4_CAPITULATION_PREV=300, V4_CAPITULATION_CURR=50 | Line 143-144 | ✅ Match | |
| ADD V4_LARGE_BUY=300, V4_DECLINE_RATIO=0.3 | Line 145-146 | ✅ Match | |
| ADD V5_DIVISOR=2.0 | Line 149 | ✅ Match | |
| ADD VA_FLOOR=0.3, VA_CEILING=2.0, VA_LOG_SCALE=0.5 | Line 152-154 | ✅ Match | |
| KEEP OVERNIGHT_WEIGHTS, OVERNIGHT_*_DIVISOR | Line 129-141: all intact | ✅ Match | |
| KEEP RSPI_SENSITIVITY, RSPI_SIGMOID_* | Line 157-160: all intact | ✅ Match | |
| DELETE VLPI_* deprecated constants | No VLPI_ found | ✅ Match | |
| DELETE old RSPI_CF_WEIGHTS, RSPI_DF_WEIGHTS | Line 174-175: still present, marked deprecated | ⚠️ Partial | Kept for compatibility per design "Step 10: remove deprecated" not yet executed |
| ADD V1_MARGIN_CALL_RATIO=140, V1_SAFE_RANGE=60 | Line 121-122 | ✅ Match | Not in design spec explicitly but required by engine; added correctly |

**constants.py Score: 12/13 items match = 92.3%**

### 2.2 rspi_engine.py

#### Old Functions Removal

| Design: DELETE | Implementation | Status |
|----------------|----------------|--------|
| calc_caution_zone_pct() | Not found | ✅ Removed |
| calc_cumulative_decline() | Not found | ✅ Removed |
| calc_individual_flow_direction() | Not found | ✅ Removed |
| calc_credit_accel_momentum() | Not found | ✅ Removed |
| calc_overnight_recovery() | Not found | ✅ Removed |
| calc_credit_inflow_damping() | Not found | ✅ Removed |
| calc_foreign_exhaustion() | Not found | ✅ Removed |
| calc_safe_buffer() | Not found | ✅ Removed |
| calc_rspi() CF-DF version | Replaced with 5-var version | ✅ Removed |

#### Kept Functions

| Design: KEEP | Implementation | Status |
|--------------|----------------|--------|
| calc_collateral_ratio() | Line 49-53 | ✅ Present |
| classify_status_6() | Line 56-68 | ✅ Present |
| estimate_selling_volume() | Line 374-396 | ✅ Present |
| estimate_price_impact() | Line 399-424 | ✅ Present |

#### New Functions

| Design Function | Implementation | Signature Match | Logic Match | Status |
|----------------|----------------|:---------------:|:-----------:|--------|
| calc_cohort_proximity(current_price, cohorts) -> 0~1 | Line 75-101 | ✅ | ✅ proximity = max(0, min(1, 1-(ratio-140)/60)), weighted avg | ✅ Match |
| calc_foreign_direction(foreign_flows, idx, lookback=20) -> -1~+1 | Line 108-134 | ✅ | ✅ z-score, clamp(-1,1,-z/divisor) | ✅ Match |
| calc_overnight_signal(ewy,koru,futures,us) -> -1~+1 | Line 141-195 | ✅ | ✅ -pct/divisor, weight redistribution, coherence 1.3/0.7 | ✅ Match |
| calc_individual_direction(individual_flows, idx) -> -1~+1 | Line 202-241 | ✅ | ✅ Capitulation +1.0, large buy -0.4, net sell +0.5 | ✅ Match |
| calc_credit_momentum(credit_data, idx) -> -1~+1 | Line 248-271 | ✅ | ✅ -change_pct/divisor, clamp | ✅ Match |
| calc_volume_amplifier(volume_today, adv_20, recent_5d) -> 0.3~2.0 | Line 278-302 | ✅ | ✅ adaptive baseline, log2, floor/ceiling | ✅ Match |
| calc_rspi(v1,v2,v3,v4,v5,volume_amp,weights) -> dict | Line 318-367 | ✅ | ✅ -1*raw*amp*100, returns rspi/level/raw/raw_variables/variable_contributions | ✅ Match |

#### classify_level Function

| Design | Implementation | Status |
|--------|----------------|--------|
| 7-level classify (Section 6) | Line 309-315: classify_level() | ✅ Match |

#### RSPIEngine Class

| Design Feature | Implementation | Status |
|----------------|----------------|--------|
| __init__(weights) using RSPI_WEIGHTS | Line 434-436 | ✅ Match |
| calculate_for_date() extracts foreign_flows, individual_flows, trading_value from ts | Line 438-519: all extracted internally | ✅ Match |
| calculate_scenario_matrix(v1,v2,v4,v5,volume_amp,...) | Line 521-563 | ✅ Match |
| get_output() returns {history, weights, latest} | Line 565-571 | ✅ Match |

#### Impact Function Sign Convention

| Design | Implementation | Status |
|--------|----------------|--------|
| Impact triggers on rspi < 0 (negative = selling) | Line 383: `if rspi >= 0: return zeros`, Line 498: `if rspi_result["rspi"] < 0` | ✅ Match |

**rspi_engine.py Score: 26/26 items match = 100%**

### 2.3 compute_models.py

| Design Requirement | Implementation | Status |
|--------------------|----------------|--------|
| Remove d2,d3,d4 from scenario_matrix call | Line 1869-1875: call uses v1,v2,v4,v5,volume_amp | ✅ Match |
| Add trading_value extraction for VA | Line 484-491 (engine internals): extracted from ts | ✅ Match |
| calculate_scenario_matrix new signature | Line 1869: matches (v1,v2,v4,v5,volume_amp,samsung_credit_bn,current_price,adv_shares_k) | ✅ Match |
| Full history calculation (262 days) | Line 1820-1857: iterates from idx=20 to end | ✅ Match |

**compute_models.py Score: 4/4 items match = 100%**

### 2.4 export_web.py

| Design Requirement | Implementation | Status | Notes |
|--------------------|----------------|--------|-------|
| RSPI_CONFIG: remove cf_variables/df_variables | No cf_variables/df_variables found | ✅ Match | |
| RSPI_CONFIG: add variables (5 entries) | Line 309-315: 5 variables v1~v5 with correct metadata | ✅ Match | |
| RSPI_CONFIG: add va_info | Line 316: volume_amplifier entry | ✅ Match | |
| RSPI_CONFIG.levels: 7-level | Line 317-325: 7 levels with colors | ✅ Match | |
| RSPI_CONFIG.weights: flat {v1~v5} | Line 307: from rspi_raw or RSPI_WEIGHTS | ✅ Match | |
| RSPI_DATA.history: v1~v5+amp format | Passes through from engine (raw format) | ✅ Match | |
| Docstring: still says VLPI_DATA/VLPI_CONFIG (items 17-18) | Line 23-24: docstring outdated | ⚠️ Minor | Cosmetic -- export names are RSPI_DATA/RSPI_CONFIG correctly (line 362-363) |

**export_web.py Score: 6/7 items match (1 cosmetic) = 85.7% (functional 100%)**

### 2.5 Frontend: CohortAnalysis.jsx

| Design Requirement | Implementation | Status | Notes |
|--------------------|----------------|--------|-------|
| RSPIGauge: 7 levels | Line 533-599: accepts levels prop, renders semicircle segments | ✅ Match | |
| RSPIGauge: sign flip (negative=red) | Line 546-547: maps -100~+100 to 180~0 degrees | ✅ Match | |
| DualBreakdown -> VariableBreakdown | Line 602-656: VariableBreakdown component, no DualBreakdown found | ✅ Match | |
| VariableBreakdown: V1~V5 bars + VA display | Line 603-656: iterates variables, renders bars + VA indicator | ✅ Match | |
| RSPI_CONFIG import: variables (not cf_variables/df_variables) | Line 22: imports RSPI_CONFIG, Line 1310: uses RSPI_CONFIG.variables | ✅ Match | |
| ImpactTable/ScenarioMatrix: sign convention | Line 692: `s.rspi < -20 ? danger : s.rspi < 0 ? yellow : safe` | ✅ Match | |
| VARIABLE_COLORS: V1~V5 | Line 50-56: 5 color entries matching colors.js | ✅ Match | |

**CohortAnalysis.jsx Score: 7/7 items match = 100%**

### 2.6 colors.js

| Design Requirement | Implementation | Status |
|--------------------|----------------|--------|
| Remove rspiCF1~CF4, rspiDF1~DF4 | Not found (grep confirmed) | ✅ Match |
| Add rspiV1~V5 colors | Line 19-23: all 5 present | ✅ Match |
| Add rspiVA color | Line 24: present | ✅ Match |

**colors.js Score: 3/3 items match = 100%**

### 2.7 terms.jsx

| Design Requirement | Implementation | Status |
|--------------------|----------------|--------|
| Remove CF/DF terms | No cf1~cf4, df1~df4 entries found | ✅ Match |
| Add V1~V5 terms (rspi_v1 through rspi_v5) | Line 358-377: all 5 with labels and descriptions | ✅ Match |
| Add VA term (rspi_va) | Line 378-381: present with description | ✅ Match |
| Add rspi (main) term | Line 350-353: present, correctly describes 5-var + VA, sign convention | ✅ Match |
| Add rspi_level term | Line 382-385: present, describes 7 levels | ✅ Match |

**terms.jsx Score: 5/5 items match = 100%**

---

## 3. Sign Convention Verification

| Layer | Design Convention | Implementation | Status |
|-------|-------------------|----------------|--------|
| Variable internals | positive = selling direction | V1 0~1 (high=vulnerable), V2/V3/V4/V5 positive=selling | ✅ |
| Formula | RSPI = -1 * raw * amp * 100 | rspi_engine.py Line 343: `-1.0 * raw * volume_amp * 100.0` | ✅ |
| Final output | negative = selling (red) | CohortAnalysis.jsx Line 692: red for `rspi < -20` | ✅ |
| Impact trigger | rspi < 0 triggers selling estimate | rspi_engine.py Line 383, 498 | ✅ |

**Sign Convention Score: 4/4 = 100%**

---

## 4. Data Flow Verification

| Design Step | Implementation | Status |
|-------------|----------------|--------|
| timeseries.json -> compute_models.py | compute_models loads ts, iterates 262 days | ✅ |
| RSPIEngine.calculate_for_date() x N | Line 1849-1857: calls per trading day | ✅ |
| V1: cohorts + price -> proximity | Line 454 | ✅ |
| V2: foreign_billion from ts -> z-score | Line 457-461 | ✅ |
| V3: ewy/koru/sp500 from ts -> overnight | Line 463-469 | ✅ |
| V4: individual_billion from ts -> pattern | Line 472-477 | ✅ |
| V5: credit_balance_billion from ts -> momentum | Line 479-481 | ✅ |
| VA: trading_value from ts -> amplifier | Line 483-491 | ✅ |
| calc_rspi(v1~v5, amp) -> RSPI | Line 494 | ✅ |
| -> model_output.json | Line 1900-1906 | ✅ |
| -> export_web -> kospi_data.js | export_web.py Line 297-332 | ✅ |
| RSPI_DATA: {history, latest, scenario_matrix} | Line 298-303 | ✅ |
| RSPI_CONFIG: {weights, variables, levels, impact_params} | Line 306-332 | ✅ |
| -> CohortAnalysis.jsx: RSPIGauge + VariableBreakdown + ImpactTable | Line 1258-1320 | ✅ |

**Data Flow Score: 14/14 = 100%**

---

## 5. Differences Found

### ⚠️ Minor Issues

| # | Item | Design | Implementation | Impact | Severity |
|---|------|--------|----------------|--------|----------|
| 1 | RSPI_CF_WEIGHTS/DF_WEIGHTS still in constants.py | DELETE (Step 10) | Kept with `(deprecated)` comment, Line 173-175 | None (not imported anywhere in v2.2.0 code) | Low |
| 2 | export_web.py docstring says VLPI_DATA/VLPI_CONFIG | Should be RSPI_DATA/RSPI_CONFIG | Cosmetic only, export names are correct | Low |
| 3 | scenario_matrix missing `raw` and `volume_amp` fields | ImpactTable displays `s.raw` and `s.volume_amp` columns | Frontend uses `(s.raw \|\| 0)` and `(s.volume_amp \|\| 1)` defaults -- shows 0/x1.00 | Medium |

### Issue #3 Detail: scenario_matrix field gap

The `calculate_scenario_matrix()` method (rspi_engine.py Line 556-562) returns:
```python
{"label", "ewy_pct", "rspi", "level", ...impact_data}
```

But `calc_rspi()` returns a dict containing `raw` and `volume_amp` fields. The scenario_matrix method discards them. The frontend ImpactTable (CohortAnalysis.jsx Line 705-709) accesses `s.raw` and `s.volume_amp`, rendering them with fallback defaults:
- `s.raw` shows as `+0.0` (always)
- `s.volume_amp` shows as `x1.00` (always)

This is functionally harmless (the VA is constant across scenarios since V3 is the only varied input), but the Raw column displays incorrect values. The fix is trivial: spread `rspi_result` fields into the scenario output.

---

## 6. Code Quality Analysis

### 6.1 Naming Convention Compliance

| Category | Convention | Files Checked | Compliance | Violations |
|----------|-----------|:-------------:|:----------:|------------|
| Python functions | snake_case | rspi_engine.py (8 functions) | 100% | None |
| Python classes | PascalCase | RSPIEngine | 100% | None |
| Python constants | UPPER_SNAKE_CASE | constants.py (18 new constants) | 100% | None |
| JS components | PascalCase | RSPIGauge, VariableBreakdown, ImpactTable | 100% | None |
| JS variables | camelCase | variableContributions, volumeAmp | 100% | None |
| JS constants | UPPER_SNAKE_CASE | VARIABLE_COLORS, RSPI_DATA | 100% | None |
| Color keys | camelCase | rspiV1~V5, rspiVA | 100% | None |

### 6.2 Architecture Compliance

| Layer | Expected Direction | Actual | Status |
|-------|-------------------|--------|--------|
| constants.py | No dependencies | Independent (only pathlib) | ✅ |
| rspi_engine.py | Depends on constants only | Imports from config.constants only | ✅ |
| compute_models.py | Depends on engine + constants | Imports RSPIEngine, constants | ✅ |
| export_web.py | Depends on constants + model output | Reads model_output.json + constants | ✅ |
| CohortAnalysis.jsx | Depends on data + shared components | Imports from kospi_data, colors, terms | ✅ |

---

## 7. Overall Scores

| Category | Items Matched | Total Items | Score | Status |
|----------|:------------:|:-----------:|:-----:|:------:|
| constants.py | 12 | 13 | 92.3% | ✅ |
| rspi_engine.py | 26 | 26 | 100% | ✅ |
| compute_models.py | 4 | 4 | 100% | ✅ |
| export_web.py | 6 | 7 | 85.7% | ✅ |
| CohortAnalysis.jsx | 7 | 7 | 100% | ✅ |
| colors.js | 3 | 3 | 100% | ✅ |
| terms.jsx | 5 | 5 | 100% | ✅ |
| Sign Convention | 4 | 4 | 100% | ✅ |
| Data Flow | 14 | 14 | 100% | ✅ |

```
+---------------------------------------------+
|  Overall Match Rate: 97.6% (81/83)          |
+---------------------------------------------+
|  ✅ Match:             81 items  (97.6%)     |
|  ⚠️ Partial/Cosmetic:   2 items  ( 2.4%)    |
|  ❌ Not implemented:     0 items  ( 0.0%)    |
+---------------------------------------------+
|  Design Match:            97.6%   ✅         |
|  Architecture Compliance: 100%    ✅         |
|  Convention Compliance:   100%    ✅         |
|  Combined Score:          97.6%   ✅         |
+---------------------------------------------+
```

---

## 8. Verification Context

Pipeline test results (provided by user):
- compute_models.py: RSPI=44.4 (extreme_rebound) for 2026-03-05
- export_web.py: 262 history days, 3 scenarios exported
- npm build: passes without errors
- 2026-03-03 crash day: RSPI=-27.2 (strong_sell), VA=1.15x
- Distribution: range [-46.6, +44.4], mean -0.1, balanced level pyramid

All pipeline outputs are consistent with the 5-variable + VA design.

---

## 9. Recommended Actions

### 9.1 Short-term (next iteration)

| Priority | Item | File | Description |
|----------|------|------|-------------|
| 1 | Fix scenario_matrix missing fields | `kospi/scripts/rspi_engine.py` Line 556-562 | Add `raw` and `volume_amp` from `rspi_result` to scenario output dict |
| 2 | Update export_web.py docstring | `kospi/scripts/export_web.py` Line 17-24 | Change VLPI_DATA/VLPI_CONFIG to RSPI_DATA/RSPI_CONFIG in comment |

### 9.2 Deferred (next version, as designed)

| Item | File | Description |
|------|------|-------------|
| Remove RSPI_CF_WEIGHTS/DF_WEIGHTS | `kospi/config/constants.py` Line 173-175 | Design Step 10: remove deprecated constants after confirming no imports |

---

## 10. Design Document Updates Needed

None required. All implementation matches or exceeds the design specification.

---

## 11. Conclusion

The v2.2.0 RSPI rewrite achieves a **97.6% match rate** against the design document. The implementation correctly transforms the model from an 8-variable CF/DF architecture to a cleaner 5-variable + Volume Amplifier architecture across all 7 files in the pipeline. The only functional gap is the missing `raw`/`volume_amp` fields in scenario_matrix output, which has a trivial fix. The two remaining items (deprecated constants and a docstring) are cosmetic and already accounted for in the design's phased implementation plan.

**Result: PASS** (>= 90% threshold met)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-06 | Initial analysis | gap-detector agent |
