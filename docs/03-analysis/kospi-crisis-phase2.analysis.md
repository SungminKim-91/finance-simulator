# KOSPI Crisis Detector Phase 2: Cohort & Forced Liquidation -- Gap Analysis

> **Analysis Type**: Gap Analysis (Design vs Implementation)
>
> **Project**: KOSPI Crisis Detector
> **Version**: Phase 2 (Cohort & Forced Liquidation)
> **Analyst**: gap-detector agent
> **Date**: 2026-03-04
> **Design Spec**: Phase 2 Implementation Plan (4 Tasks)

---

## 1. Analysis Overview

### 1.1 Analysis Purpose

Compare the Phase 2: Cohort & Forced Liquidation implementation plan (4 Tasks) against the actual codebase to determine implementation completeness, correctness, and any deviations.

### 1.2 Analysis Scope

| Task | Design Spec | Implementation File | Exists |
|------|-------------|---------------------|:------:|
| Task 1 | COHORT_DATA in kospi_data.js | `web/src/simulators/kospi/data/kospi_data.js` | Yes |
| Task 2 | CohortAnalysis.jsx (Tab B) | `web/src/simulators/kospi/CohortAnalysis.jsx` | Yes |
| Task 3 | KospiApp.jsx Tab B routing | `web/src/simulators/kospi/KospiApp.jsx` | Yes |
| Task 4 | Python compute_models.py | `kospi/scripts/compute_models.py` | Yes |

---

## 2. Task 1: kospi_data.js -- COHORT_DATA

### 2.1 buildCohorts(mode) Function

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| 42-day creditBase delta analysis | Yes | Yes -- iterates `i=1..N` computing `creditBase[i] - creditBase[i-1]` | Match |
| delta > 0 creates cohort | entry_date, entry_kospi, amount | entry_date, entry_kospi, amount (line 130-133) | Match |
| delta < 0 LIFO/FIFO repayment | LIFO/FIFO order parameter | `mode === "LIFO" ? [...cohorts].reverse() : cohorts` (line 137) | Match |
| Remove zero-balance cohorts | Remove when amount <= 0 | Splice loop at lines 145-147 | Match |
| Last-day pnl_pct calculation | (currentKospi - entryKospi) / entryKospi * 100 | Implemented at line 152 | Match |
| collateral_ratio (weighted avg) | Weighted across margin_distribution | Loop over MARGIN_DISTRIBUTION entries, weighted sum (lines 154-158) | Match |
| status classification | safe/watch/marginCall/danger | Thresholds: >=1.60 safe, >=1.40 watch, >=1.30 marginCall, else danger (lines 160-163) | Match |

**Score: 7/7 (100%)**

### 2.2 price_distribution

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| 100pt bin grouping | 100pt intervals | `Math.floor(c.entry_kospi / 100) * 100` (line 170) | Match |
| Status-based balance bucketing | Per-status amounts | `bins[key][c.status] += c.amount` (line 174) | Match |
| Sorted output | By bin | `Object.values(bins).sort((a, b) => a.bin - b.bin)` (line 176) | Match |
| Both LIFO and FIFO variants | Single price_distribution | `price_distribution_lifo` + `price_distribution_fifo` -- two variants | Enhanced |

**Note**: Design specified a single `price_distribution`; implementation provides both LIFO and FIFO variants (`price_distribution_lifo`, `price_distribution_fifo`). This is an enhancement.

**Score: 3/3 (100%) + 1 enhancement**

### 2.3 trigger_map

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| 6 shock levels | shock_pct column | `shocks = [-3, -5, -10, -15, -20, -30]` (line 181) | Match |
| expected_kospi | currentKospi * (1 + shock/100) | `Math.round(currentKospi * (1 + shock / 100))` (line 182) | Match |
| expected_fx | current_fx * (1 + abs(shock) * 0.3) | `Math.round(currentFx * (1 + Math.abs(shock) * 0.3 / 100))` (line 183) | Match |
| margin_call_billion | Per MARGIN_DISTRIBUTION | Loop with ratio < MAINTENANCE_RATIO check (lines 188-193) | Match |
| forced_liq_billion | Per MARGIN_DISTRIBUTION | Loop with ratio < FORCED_LIQ_RATIO check (line 191) | Match |

**Score: 5/5 (100%)**

### 2.4 params Object

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| margin_distribution | { 0.40: 0.35, 0.45: 0.35, 0.50: 0.25, 0.60: 0.05 } | Line 120: exact match | Match |
| maintenance_ratio | 1.40 | Line 121: `1.40` | Match |
| forced_liq_ratio | 1.30 | Line 122: `1.30` | Match |
| impact_coefficient | 1.5 | Line 123: `1.5` | Match |
| fx_sensitivity | { thresholds + multipliers } | Lines 227-232: low/mid/high/extreme with threshold + multiplier | Match |

**Score: 5/5 (100%)**

### 2.5 COHORT_DATA Export Shape

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| lifo | buildCohorts("LIFO") | Line 214: `lifo: _lifoCohorts` | Match |
| fifo | buildCohorts("FIFO") | Line 215: `fifo: _fifoCohorts` | Match |
| price_distribution | Single object | Split into `price_distribution_lifo` and `price_distribution_fifo` | Changed |
| trigger_map | Array of shock rows | Line 218: `buildTriggerMap(_currentKospi, _currentFx)` | Match |
| current_kospi | Number | Line 219 | Match |
| current_fx | Number | Line 220 | Match |
| avg_daily_trading_value_billion | Number | Line 221: computed from MARKET_DATA | Match |
| params | Object | Lines 222-233 | Match |

**Note on price_distribution**: Design specified a single `price_distribution` key. Implementation uses `price_distribution_lifo` and `price_distribution_fifo` for per-mode distributions. The CohortAnalysis.jsx consumer correctly switches between them based on cohortMode, so this is a functional enhancement, not a defect.

**Score: 7/8 (87.5%) -- 1 intentional structural change**

### Task 1 Total: 27/28 items match (96.4%)

---

## 3. Task 2: CohortAnalysis.jsx -- Tab B Component

### 3.1 Pattern Replication (MarketPulse.jsx patterns)

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| PanelBox component | Replicate pattern | Lines 29-38: `PanelBox({ children, style })` | Match |
| SectionTitle component | Replicate pattern | Lines 21-26: `SectionTitle({ children })` | Match |
| axisProps constant | Replicate pattern | Line 40: `{ stroke: C.dim, fontSize: 10, fontFamily: FONT }` | Match |
| Color palette import | Use C from colors.js | Line 14: `import { C } from "./colors"` | Match |
| COHORT_DATA import | Import from data file | Line 15: `import { COHORT_DATA } from "./data/kospi_data"` | Match |

**Score: 5/5 (100%)**

### 3.2 Section 1: Cohort Distribution Heatmap

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| LIFO/FIFO toggle | Toggle button | `ToggleGroup` with LIFO/FIFO options (line 284-287) | Match |
| Horizontal BarChart | layout="vertical" | `<BarChart data={priceDist} layout="vertical">` (line 300) | Match |
| Y-axis: KOSPI price ranges (100pt) | Price range bins | `<YAxis type="category" dataKey="range">` (line 304) | Match |
| X-axis: balance (billions) | Amount in billions | `<XAxis type="number">` with K-formatter (line 302-303) | Match |
| 4-color stacked bar | safe/watch/marginCall/danger | 4 `<Bar>` elements with `stackId="a"` (lines 311-314) | Match |
| Color: safe=#4ade80 | Green | `fill={C.safe}` -- verified C.safe = "#4ade80" in colors.js | Match |
| Color: watch=#facc15 | Yellow | `fill={C.watch}` -- verified C.watch = "#facc15" | Match |
| Color: marginCall=#fb923c | Orange | `fill={C.marginCall}` -- verified C.marginCall = "#fb923c" | Match |
| Color: danger=#ef4444 | Red | `fill={C.danger}` -- verified C.danger = "#ef4444" | Match |
| Summary: total active balance | Bottom summary | `SummaryCard label="Total Balance"` (line 293) | Match |
| Summary: safe/danger ratio | Bottom summary | Safe Ratio + Danger Ratio cards (lines 294-295) | Match |

**Score: 11/11 (100%)**

### 3.3 Section 2: Trigger Map

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| Table format | HTML table | `<table>` element at lines 330-363 | Match |
| 6 rows (shock levels) | 6 shock entries | `trigger_map.map((row) => ...)` -- 6 shocks from data | Match |
| Column: Shock % | shock_pct | `{row.shock_pct}%` (line 345) | Match |
| Column: Expected KOSPI | expected_kospi | `{row.expected_kospi.toLocaleString()}` (line 348) | Match |
| Column: Expected FX | expected_fx | `{row.expected_fx.toLocaleString()}` (line 351) | Match |
| Column: Margin Call | margin_call_billion | With trillion conversion (line 354) | Match |
| Column: Forced Liq | forced_liq_billion | With trillion conversion (line 357) | Match |
| Color intensity by shock | Gradient color | `shockColor(pct)` function: <=5 watch, <=15 marginCall, else danger (lines 248-253) | Match |
| Current KOSPI + FX display | Reference line | `Current KOSPI: ... | USD/KRW: ...` (lines 325-327) | Match |

**Score: 9/9 (100%)**

### 3.4 Section 3: Dual-Loop Simulator (Interactive)

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| Loop mode toggle | A only / B only / A+B | ToggleGroup with A/B/AB options (lines 385-389) | Match |
| Default loop mode | A+B Combined | `useState("AB")` (line 220) | Match |
| Shock slider | -1% to -50% | `SliderControl min={-50} max={-1}` (line 375) | Match |
| Rounds slider | 1 to 10 | `SliderControl min={1} max={10}` (line 377) | Match |
| Absorption presets | conservative/neutral/optimistic/custom | ToggleGroup with 4 options (lines 397-404) | Match |
| Custom absorption slider | Visible when "custom" | Conditional render with step=0.05 (lines 406-408) | Match |
| Run button | Trigger simulation | `<button onClick={handleRun}>Run Simulation</button>` (lines 415-423) | Match |

**Score: 7/7 (100%)**

### 3.5 runSimulation() Engine

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| Loop A: collateral ratio check | Per cohort, per margin rate | Nested loop at lines 122-133 | Match |
| Loop A: forced_liq threshold | ratio < 1.30 | Line 129: `ratio < 1.30` | Match |
| Loop A: sell pressure | forced_liq * (1 - absorption) | Line 134: `forcedLiq * (1 - absorptionRate)` | Match |
| Loop B: KOSPI drop -> FX change | kospi_drop_pct * 0.3 | Line 144: `kospiDropPct * 0.3` | Match |
| Loop B: nonlinear sensitivity | <=1:0.5, <=2:1.0, <=3:1.5, else:2.0 | Lines 147-150: exact match | Match |
| Loop B: foreign sell | fxChangePct * sensitivity * 100 | Line 151 | Match |
| Loop B: sell pressure B | foreignSell * (1 - absorption) | Line 152 | Match |
| total_impact | impact_A + impact_B (by loopMode) | Line 158: `impactA + impactB` | Match |
| Convergence condition | forced_liq < 100 AND foreign_sell < 50 | Line 177: exact match | Match |
| Result: ComposedChart | Line + Bar combo | `<ComposedChart>` with Line (KOSPI, FX) + Bar (forced_liq, foreign_sell) | Match |
| Result: summary cards | Final KOSPI, FX, total drop, converged round | 4 SummaryCards at lines 430-436 | Match |

**Score: 11/11 (100%)**

### 3.6 Additional Features (Beyond Design)

| Feature | Location | Description |
|---------|----------|-------------|
| Round Detail Table | Lines 484-521 | Per-round detailed table with all metrics -- not in design but useful |
| HeatmapTooltip | Lines 256-274 | Custom tooltip for the heatmap chart |
| SimTooltip | Lines 91-106 | Custom tooltip for the simulation chart |
| Dynamic height | Line 299 | `Math.max(200, priceDist.length * 40 + 40)` -- adaptive chart height |
| Conditional column display | Lines 488-491, 501-513 | Table columns toggle based on loopMode |

These are enhancements that improve usability without conflicting with design.

### Task 2 Total: 43/43 core items match (100%) + 5 enhancements

---

## 4. Task 3: KospiApp.jsx -- Tab B Routing

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| Import CohortAnalysis | Add import statement | Line 3: `import CohortAnalysis from "./CohortAnalysis"` | Match |
| Replace Placeholder with CohortAnalysis | Tab "cohort" renders CohortAnalysis | Line 53: `{tab === "cohort" && <CohortAnalysis />}` | Match |
| Tab label | "Cohort & Forced Liq." | Line 12: `label: "Cohort & Forced Liq."` | Match |
| Other tabs unchanged | Pulse, Scenario, History | Lines 52, 54, 55: Pulse renders, Scenario/History still Placeholder | Match |

### Task 3 Total: 4/4 (100%)

---

## 5. Task 4: Python compute_models.py

### 5.1 CohortBuilder Enhancements

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| get_price_distribution(bin_size) | New method | Lines 144-154: `get_price_distribution(self, current_kospi, bin_size=100)` | Match |
| 100pt bin grouping | Group by bin_size | `int(c.entry_kospi // bin_size) * bin_size` (line 148) | Match |
| Per-status distribution | safe/watch/margin_call/forced_liq | `bins[key][st] += c.remaining_amount_billion` (line 153) | Match |
| get_trigger_map(shocks) | New method | Lines 156-185: `get_trigger_map(self, current_kospi, current_fx, shocks)` | Match |
| 6 default shocks | [-3, -5, -10, -15, -20, -30] | Line 162: exact match | Match |
| FX estimation | current_fx * (1 + abs(shock) * 0.3 / 100) | Line 166: exact match | Match |
| margin_call/forced_liq per MARGIN_DISTRIBUTION | Weighted calculation | Lines 169-177: loop over margin_rate/weight | Match |

**Score: 7/7 (100%)**

### 5.2 ForcedLiqSimulator Dual-Loop Support

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| loop_mode parameter | "A", "B", "AB" | Line 228: `loop_mode: str = "AB"` | Match |
| initial_fx parameter | FX starting value | Line 227: `initial_fx: float = 1400.0` | Match |
| Loop A: forced_liq from collateral ratio | Per cohort calculation | Lines 239-255: full implementation | Match |
| Loop B: FX feedback | kospi_drop -> fx_change -> foreign_sell | Lines 257-270: full implementation | Match |
| _fx_sensitivity() | Nonlinear step function | Lines 207-216: <=1:0.5, <=2:1.0, <=3:1.5, else:2.0 | Match |
| Convergence check | forced_liq < 100 and foreign_sell < 50 | Line 290: exact match | Match |
| Result structure | rounds array + summary | Lines 276-302: complete output | Match |

**Score: 7/7 (100%)**

### 5.3 run_all_models() Integration

| Requirement | Design | Implementation | Status |
|-------------|--------|----------------|:------:|
| Use real timeseries data | Load from timeseries.json | Lines 389-394: `load_timeseries()` | Match |
| Build cohorts from actual data | Process day-by-day | Lines 410-421: loop with `builder.process_day()` | Match |
| Include price_distribution in output | In cohort_result | Line 426: `"price_distribution": builder.get_price_distribution(kospi)` | Match |
| Include trigger_map in output | In cohort_result | Line 427: `"trigger_map": builder.get_trigger_map(kospi, current_fx)` | Match |
| Run ForcedLiqSimulator with dual loop | AB mode default | Lines 431-440: `loop_mode="AB"`, `initial_fx=current_fx` | Match |

**Score: 5/5 (100%)**

### Task 4 Total: 19/19 (100%)

---

## 6. Differences Found

### 6.1 Missing Features (Design O, Implementation X)

**None found.** All 4 tasks from the design spec have been fully implemented.

### 6.2 Added Features (Design X, Implementation O)

| Item | Implementation Location | Description | Impact |
|------|------------------------|-------------|--------|
| price_distribution per mode | kospi_data.js:216-217 | Separate LIFO/FIFO distributions instead of single | Low (Enhancement) |
| Round Detail Table | CohortAnalysis.jsx:484-521 | Per-round breakdown table below simulation chart | Low (Enhancement) |
| Custom Heatmap Tooltip | CohortAnalysis.jsx:256-274 | Rich tooltip for heatmap bars | Low (Enhancement) |
| Custom Sim Tooltip | CohortAnalysis.jsx:91-106 | Rich tooltip for simulation chart | Low (Enhancement) |
| Conditional column display | CohortAnalysis.jsx:488-513 | Table columns adapt to loopMode | Low (Enhancement) |
| Adaptive chart height | CohortAnalysis.jsx:299 | Height scales with number of price bins | Low (Enhancement) |
| Active Cohorts count card | CohortAnalysis.jsx:292 | Additional summary metric | Low (Enhancement) |

### 6.3 Changed Features (Design != Implementation)

| Item | Design | Implementation | Impact |
|------|--------|----------------|--------|
| price_distribution export key | `price_distribution` (single) | `price_distribution_lifo` + `price_distribution_fifo` | Low -- consumer code handles correctly |

---

## 7. Convention Compliance

### 7.1 Naming Conventions

| Category | Convention | Files Checked | Compliance | Notes |
|----------|-----------|:-------------:|:----------:|-------|
| Components | PascalCase | 5 (CohortAnalysis, SectionTitle, PanelBox, ToggleGroup, SummaryCard, SliderControl, SimTooltip) | 100% | All PascalCase |
| Functions | camelCase | 8 (buildCohorts, buildPriceDistribution, buildTriggerMap, runSimulation, handleRun, shockColor, bizDays, mulberry32) | 100% | All camelCase |
| Constants | UPPER_SNAKE_CASE | 6 (MARGIN_DISTRIBUTION, MAINTENANCE_RATIO, FORCED_LIQ_RATIO, IMPACT_COEFFICIENT, DATES, N) | 100% | All UPPER_SNAKE_CASE |
| Files | PascalCase.jsx / camelCase.js | 3 files | 100% | CohortAnalysis.jsx, KospiApp.jsx, kospi_data.js |
| Python classes | PascalCase | 2 (CohortBuilder, ForcedLiqSimulator) | 100% | |
| Python functions | snake_case | 6 | 100% | |

### 7.2 Import Order (CohortAnalysis.jsx)

```
1. External: react, recharts                    -- Line 1-13
2. Internal relative: ./colors, ./data/...      -- Line 14-15
```

Compliance: Pass (no absolute @/ imports used in this codebase structure)

### 7.3 Architecture Compliance

The codebase follows a Starter-level clean architecture (components + lib + types), appropriate for a single-page simulator dashboard. Data layer (`data/kospi_data.js`) is separated from presentation (`CohortAnalysis.jsx`), and shared styles (`colors.js`) are extracted. Python backend follows module separation (CohortBuilder, ForcedLiqSimulator as independent classes).

---

## 8. Overall Scores

| Category | Items Checked | Match | Score | Status |
|----------|:------------:|:-----:|:-----:|:------:|
| Task 1: COHORT_DATA | 28 | 27 | 96.4% | Pass |
| Task 2: CohortAnalysis.jsx | 43 | 43 | 100% | Pass |
| Task 3: KospiApp.jsx routing | 4 | 4 | 100% | Pass |
| Task 4: compute_models.py | 19 | 19 | 100% | Pass |
| **Overall** | **94** | **93** | **98.9%** | **Pass** |

```
+---------------------------------------------+
|  Overall Match Rate: 98.9%                   |
+---------------------------------------------+
|  Match:               93 items (98.9%)       |
|  Intentional Change:   1 item  ( 1.1%)       |
|  Missing:              0 items ( 0.0%)       |
|  Enhancements:         7 items (bonus)       |
+---------------------------------------------+
```

| Category | Score | Status |
|----------|:-----:|:------:|
| Design Match | 98.9% | Pass |
| Architecture Compliance | 100% | Pass |
| Convention Compliance | 100% | Pass |
| **Overall** | **99.0%** | **Pass** |

---

## 9. Detailed File Inventory

### Files Analyzed

| File | Path | Lines | Role |
|------|------|------:|------|
| kospi_data.js | `/home/sungmin/finance-simulator/web/src/simulators/kospi/data/kospi_data.js` | 298 | Data layer: COHORT_DATA export with buildCohorts, price_distribution, trigger_map, params |
| CohortAnalysis.jsx | `/home/sungmin/finance-simulator/web/src/simulators/kospi/CohortAnalysis.jsx` | 533 | UI: 3-section Tab B (Heatmap, Trigger Map, Dual-Loop Simulator) |
| KospiApp.jsx | `/home/sungmin/finance-simulator/web/src/simulators/kospi/KospiApp.jsx` | 59 | Router: Tab B connected to CohortAnalysis |
| compute_models.py | `/home/sungmin/finance-simulator/kospi/scripts/compute_models.py` | 491 | Python backend: CohortBuilder + ForcedLiqSimulator with dual-loop |
| colors.js | `/home/sungmin/finance-simulator/web/src/simulators/kospi/colors.js` | 13 | Shared: Color palette including safe/watch/marginCall/danger |

---

## 10. Recommended Actions

### 10.1 Documentation Update

| Priority | Item | Description |
|----------|------|-------------|
| Low | Update design spec | Reflect `price_distribution_lifo`/`price_distribution_fifo` split (intentional enhancement) |
| Low | Document enhancements | Record 7 added features (round detail table, tooltips, etc.) in design doc |

### 10.2 No Immediate Actions Required

The implementation matches the design spec at 98.9%. The single structural deviation (split price_distribution) is an improvement that provides per-mode distribution data and is correctly consumed by the UI. No defects, missing features, or regressions were found.

---

## 11. Conclusion

Phase 2: Cohort & Forced Liquidation is **fully implemented** and matches the design specification with a **98.9% match rate**. All four tasks -- COHORT_DATA data layer, CohortAnalysis.jsx UI component, KospiApp.jsx tab routing, and Python compute_models.py backend -- are complete with correct business logic, proper convergence conditions, and consistent parameter usage across JS and Python layers.

The implementation includes 7 quality-of-life enhancements beyond the original design (round detail table, custom tooltips, adaptive layout, conditional column display) that improve usability without diverging from the core specification.

**Verdict: PASS -- No iteration needed.**

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2026-03-04 | Initial Phase 2 gap analysis | gap-detector agent |
