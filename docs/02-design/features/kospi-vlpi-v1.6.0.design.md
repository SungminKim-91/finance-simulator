# KOSPI VLPI v1.6.0 — Frontend Cohort Redesign Design Document

> **Summary**: 코호트 탭 6단계 상태 전환 + VLPI 대시보드 (Gauge/Breakdown/Impact/RiskMap) 신규 구현
>
> **Project**: Finance Simulator — KOSPI Crisis Detector
> **Version**: v1.6.0
> **Date**: 2026-03-05
> **Status**: Draft
> **Planning Doc**: [kospi-vlpi-v1.6.0.plan.md](../../01-plan/features/kospi-vlpi-v1.6.0.plan.md)

---

## 1. Overview

### 1.1 Design Goals

1. **6단계 상태 분류 시각화**: backend `status_6` 필드를 직접 소비하여 4색→6색 전환
2. **VLPI 대시보드**: Pre-VLPI 스코어를 Gauge + Component Breakdown + Impact Table + Risk Map으로 시각화
3. **코드 정리**: 미사용/대체 컴포넌트 삭제 (ReliabilityDashboard, BacktestComparison, TriggerMapTable)
4. **하위호환**: Section 3 시뮬레이터 기존 로직 유지 (v1.7.0에서 교체)

### 1.2 Design Principles

- **Backend 데이터 신뢰**: `status_6` 필드 직접 사용, 프론트엔드 `classifyStatus()` JS 함수 제거
- **점진적 마이그레이션**: Section 3 시뮬레이터는 `status` (4단계) 유지, Section 1/2만 `status_6` 전환
- **순수 SVG**: VLPI Gauge는 recharts 미지원 → SVG arc 직접 구현 (외부 의존성 없음)
- **최소 변경**: 기존 공통 컴포넌트 (SectionTitle, PanelBox, SummaryCard 등) 재사용

---

## 2. Architecture

### 2.1 Component Diagram

```
CohortAnalysis.jsx (main export)
├── [공통] SectionTitle, PanelBox, SummaryCard, ToggleGroup, SliderControl
│
├── Section 1: 코호트 분포 (6단계)
│   ├── STATUS_COLORS_6, STATUS_LABELS_6 (신규 상수)
│   ├── CohortBarLabel6 (6단계 색상)
│   ├── CohortTooltip6 (6단계 색상 + liquidated_pct)
│   ├── Horizontal BarChart (recharts, 6색 Cell)
│   └── Summary Cards (총잔고, 주의구간%, 위험비율%)
│
├── Section 1.5: StockCreditBreakdown (6단계 색상 적용)
│
├── Section 2: VLPI 대시보드 (신규, 트리거맵 대체)
│   ├── VLPIGauge (순수 SVG 반원 게이지)
│   ├── ComponentBreakdown (recharts 수평 BarChart)
│   ├── ImpactTable (시나리오 매트릭스 테이블)
│   └── CohortRiskMap (recharts ScatterChart + ReferenceLines)
│
├── Section 3: 시뮬레이터 (기존 유지, v1.7.0까지)
│   ├── runSimulation() (기존 로직)
│   ├── BacktestComparison (삭제 ←)
│   └── SimTooltip, 라운드 테이블
│
└── [삭제] ReliabilityDashboard, BacktestComparison, TriggerMapTable
```

### 2.2 Data Flow

```
kospi_data.js exports
├── COHORT_DATA (lifo/fifo 코호트, status + status_6 이중 필드)
├── VLPI_DATA (history, latest, scenario_matrix)
├── VLPI_CONFIG (weights, status_thresholds, variables, levels, impact_params)
├── COHORT_HISTORY (백테스트용 스냅샷, 기존 유지)
├── STOCK_CREDIT (종목별 가중, 기존 유지)
└── [삭제 import] BACKTEST_DATES

CohortAnalysis.jsx
├── Section 1: COHORT_DATA.lifo/fifo → status_6 필드로 6색 렌더
├── Section 2: VLPI_DATA + VLPI_CONFIG → Gauge/Breakdown/Impact/RiskMap
└── Section 3: COHORT_DATA + COHORT_HISTORY → 시뮬레이터 (기존)
```

### 2.3 Dependencies

| Component | Depends On | Purpose |
|-----------|-----------|---------|
| Section 1 (6단계) | COHORT_DATA, VLPI_CONFIG.status_thresholds | 6색 상태 바 + 담보비율 기준값 |
| VLPIGauge | VLPI_DATA.latest, VLPI_CONFIG.levels | 반원 게이지 SVG |
| ComponentBreakdown | VLPI_DATA.latest.components, VLPI_CONFIG.variables/weights | V1~V6 기여분 바 |
| ImpactTable | VLPI_DATA.scenario_matrix | 3행 시나리오 테이블 |
| CohortRiskMap | COHORT_DATA.lifo/fifo, VLPI_CONFIG.status_thresholds | 담보비율 산점도 |
| Section 3 | COHORT_DATA, COHORT_HISTORY, INVESTOR_FLOWS | 기존 시뮬레이터 (변경 없음) |

---

## 3. Data Model

### 3.1 신규 상수 정의

```javascript
// ── 6단계 상태 색상 (backend status_6 매핑) ──
const STATUS_COLORS_6 = {
  safe:       "#4caf50",  // 안전 (Green)
  good:       "#8bc34a",  // 양호 (Light Green)
  caution:    "#ffc107",  // 주의 (Amber)
  marginCall: "#ff9800",  // 마진콜 (Orange)        ← key 유지 (backend: margin_call → frontend: marginCall)
  forcedLiq:  "#ff5252",  // 강제청산 (Red)          ← key 유지 (backend: forced_liq → frontend: forcedLiq)
  debtExceed: "#ff1744",  // 채무초과 (Deep Red)     ← key 유지 (backend: debt_exceed → frontend: debtExceed)
};

const STATUS_LABELS_6 = {
  safe:       "안전",
  good:       "양호",
  caution:    "주의",
  marginCall: "마진콜",
  forcedLiq:  "강제청산",
  debtExceed: "채무초과",
};

// 6단계 순서 (위험도 내림차순 = 렌더링 순서)
const STATUS_ORDER_6 = ["debtExceed", "forcedLiq", "marginCall", "caution", "good", "safe"];

// ── VLPI 변수별 색상 (Component Breakdown) ──
const VLPI_VAR_COLORS = {
  caution_zone:      "#5c6bc0",  // Indigo
  credit_momentum:   "#26a69a",  // Teal
  policy_shock:      "#ff7043",  // Deep Orange
  overnight_gap:     "#ab47bc",  // Purple
  cumulative_decline:"#ef5350",  // Red
  individual_flow:   "#42a5f5",  // Blue
};
```

### 3.2 Backend → Frontend 키 매핑

backend `status_6` 필드값은 snake_case (`margin_call`, `forced_liq`, `debt_exceed`)이고, frontend는 camelCase.
`export_web.py`의 `_remap_cohorts()`가 이미 camelCase로 변환:

| Backend (status_6) | Frontend (status_6) | 색상 |
|---------------------|---------------------|------|
| `debt_exceed` | `debtExceed` | `#ff1744` |
| `forced_liq` | `forcedLiq` | `#ff5252` |
| `margin_call` | `marginCall` | `#ff9800` |
| `caution` | `caution` | `#ffc107` |
| `good` | `good` | `#8bc34a` |
| `safe` | `safe` | `#4caf50` |

**확인 필요**: `export_web.py`의 `_remap_cohorts()`에서 `status_6` 값을 camelCase로 변환하는지 확인. 현재 코드에서 `status`는 그대로 전달하므로, `status_6`도 backend 원본값 그대로일 수 있음. → **구현 시 매핑 함수 필요**.

```javascript
// status_6 키 정규화 함수
function normalizeStatus6(s) {
  const MAP = { debt_exceed: "debtExceed", forced_liq: "forcedLiq", margin_call: "marginCall" };
  return MAP[s] || s;
}
```

### 3.3 VLPI_DATA 실제 구조 (kospi_data.js line 38043)

```javascript
VLPI_DATA = {
  history: [{ date, pre_vlpi, level, components: {caution_zone, credit_momentum, ...}, raw_variables: {v1~v6}, impact }],
  latest: { date: "2026-03-04", pre_vlpi: 39.0, level: "caution", components: {...}, raw_variables: {...}, impact: null },
  scenario_matrix: [
    { label: "낙관적", ewy_change_pct: 2.5, policy_shock: false, pre_vlpi: 34.0, sell_volume_억: 9548902, sell_ratio_pct: 3.26, price_impact_pct: 0, absorption_ratio: 0 },
    { label: "기본",   ewy_change_pct: -1.0, ..., pre_vlpi: 41.0, ... },
    { label: "비관적", ewy_change_pct: -4.0, ..., pre_vlpi: 47.0, ... },
  ]
}
```

### 3.4 VLPI_CONFIG 실제 구조 (kospi_data.js line 38124)

```javascript
VLPI_CONFIG = {
  weights: { w1: 0.25, w2: 0.1, w3: 0.2, w4: 0.2, w5: 0.15, w6: 0.1 },
  status_thresholds: { debt_exceed: 100, forced_liq: 120, margin_call: 140, caution: 155, good: 170 },
  variables: [
    { key: "v1", label: "주의구간 비중", desc: "담보비율 140~170% 코호트 비중", range: "0~1", weight_key: "w1" },
    // ... v2~v6
  ],
  levels: [
    { min: 0, max: 30, label: "정상", color: "#4caf50" },
    { min: 30, max: 50, label: "주의", color: "#ffc107" },
    { min: 50, max: 70, label: "경고", color: "#ff9800" },
    { min: 70, max: 100, label: "위험", color: "#f44336" },
  ],
  impact_params: { sensitivity: 0.15, sigmoid_k: 0.08, sigmoid_mid: 50, samsung_credit_weight: 0.5 }
}
```

---

## 4. UI/UX Design

### 4.1 Screen Layout

```
┌─────────────────────────────────────────────────┐
│ Section 1: 코호트 분포 (6단계)                    │
│ ┌─────────────────────────────────────────┐      │
│ │ [LIFO ▪ FIFO]  날짜선택                 │      │
│ │ ──────────────────────────────────      │      │
│ │ 6색 Stacked Horizontal Bar              │      │
│ │ (진입가 내림차순, 현재 KOSPI 기준선)     │      │
│ │ ──────────────────────────────────      │      │
│ │ [총잔고 ○.○조] [주의구간 ○○%] [위험 ○○%]│      │
│ │ 범례: ■안전 ■양호 ■주의 ■마진콜 ■강제청산 ■채무초과│
│ └─────────────────────────────────────────┘      │
│                                                  │
│ Section 1.5: StockCreditBreakdown (6단계 색상)    │
│                                                  │
│ Section 2: VLPI 대시보드                          │
│ ┌──────────────────┬──────────────────────┐      │
│ │  A. VLPI Gauge   │  B. Component        │      │
│ │  ╭─────────╮     │  Breakdown           │      │
│ │ ╱   39.0    ╲    │  V1 ░░░░░░░░ 0.0    │      │
│ │╱    주의     ╲   │  V2 ██░░░░░░ 3.0    │      │
│ │▔▔▔▔▔▔▔▔▔▔▔▔    │  V3 ████████ 20.0   │      │
│ │                  │  V4 █████░░░ 10.0   │      │
│ │                  │  V5 ░░░░░░░░ 0.0    │      │
│ │                  │  V6 ███░░░░░ 6.0    │      │
│ ├──────────────────┴──────────────────────┤      │
│ │  C. Impact Table (시나리오 매트릭스)      │      │
│ │  ┌────────┬────────┬────────┬──────────┐│      │
│ │  │시나리오 │EWY변동 │VLPI   │매도추정  ││      │
│ │  ├────────┼────────┼────────┼──────────┤│      │
│ │  │낙관적  │+2.5%  │34     │955만억   ││      │
│ │  │기본 ← │-1.0%  │41     │1,437만억 ││ hl   │
│ │  │비관적  │-4.0%  │47     │2,899만억 ││      │
│ │  └────────┴────────┴────────┴──────────┘│      │
│ ├─────────────────────────────────────────┤      │
│ │  D. Cohort Risk Map (담보비율 분포)      │      │
│ │  200% ─ ─ ─ ─ ─ ─ ─ ─ ─ ─            │      │
│ │  170% ═══════════════════ (양호)        │      │
│ │  155% ═══════════════════ (주의)        │      │
│ │  140% ═══════════════════ (마진콜)      │      │
│ │  120% ═══════════════════ (강제청산)    │      │
│ │  100% ─ ─ ─ ─ ─ ─ ─ ─ ─ ─            │      │
│ │       ● ●   ●  ●  ●  ● (코호트들)     │      │
│ └─────────────────────────────────────────┘      │
│                                                  │
│ Section 3: 시뮬레이터 (기존 유지)                 │
└──────────────────────────────────────────────────┘
```

### 4.2 Component Specification

#### A. VLPIGauge (순수 SVG)

- **치수**: width=240, height=140 (반원)
- **구현**: `<svg>` + `<path>` arc segments, 4색 구간
- **색상 구간**: VLPI_CONFIG.levels 배열 참조
  - 0~30: `#4caf50` (정상)
  - 30~50: `#ffc107` (주의)
  - 50~70: `#ff9800` (경고)
  - 70~100: `#f44336` (위험)
- **중앙 텍스트**: Pre-VLPI 스코어 (fontSize 32, bold) + 등급 라벨 (fontSize 14)
- **바늘**: 현재 스코어 위치를 가리키는 얇은 삼각형 또는 선
- **SVG Arc 공식**:
  ```
  startAngle = Math.PI (180°, 왼쪽)
  endAngle = 0 (0°, 오른쪽)
  radius = 90, cx = 120, cy = 120
  각 구간: proportion = (max - min) / 100
           segmentAngle = proportion * Math.PI
  ```

#### B. ComponentBreakdown (recharts BarChart)

- **타입**: Horizontal BarChart (layout="vertical")
- **데이터**: `VLPI_DATA.latest.components` 객체를 배열로 변환
  ```javascript
  const breakdownData = VLPI_CONFIG.variables.map(v => ({
    name: v.label,                                    // "주의구간 비중"
    value: VLPI_DATA.latest.components[varKeyMap[v.key]], // 기여분 수치
    raw: VLPI_DATA.latest.raw_variables[v.key],       // 원시값
    weight: VLPI_CONFIG.weights[v.weight_key],        // 가중치
    color: VLPI_VAR_COLORS[varKeyMap[v.key]],         // 색상
    desc: v.desc,                                      // 설명
  }));
  ```
- **varKeyMap**: `{ v1: "caution_zone", v2: "credit_momentum", v3: "policy_shock", v4: "overnight_gap", v5: "cumulative_decline", v6: "individual_flow" }`
- **바**: 각 변수별 고유색, max domain = Pre-VLPI 값 (39.0) 또는 고정 100
- **라벨**: 바 오른쪽에 기여분 숫자 표시
- **Tooltip**: 변수 설명 + raw 값 + 가중치(×100)

#### C. ImpactTable (HTML table)

- **행**: `VLPI_DATA.scenario_matrix` (3행: 낙관/기본/비관)
- **컬럼**: 시나리오 | EWY변동% | 정책쇼크 | Pre-VLPI | 매도추정(억) | 매도비율%
- **하이라이트**: 현재 VLPI에 가장 가까운 행 (`Math.abs(row.pre_vlpi - latest.pre_vlpi)` 최소)
- **매도추정 포맷**: fmtBillion() 호출 (sell_volume_억 / 10 → 십억원 단위로 변환 후)
- **sell_volume_억 값**: 현재 데이터가 매우 큼 (9,548,902억 = 약 955조원) → 원본 단위 확인 필요
  - 실제로 `sell_volume_억` 이 억원 단위이면 → 표시: `{(val / 10000).toFixed(0)}조원`

#### D. CohortRiskMap (recharts ScatterChart)

- **X축**: 코호트 인덱스 (또는 진입가)
- **Y축**: 담보비율 (%) — domain [90, 210]
- **점**: 각 코호트 = 1개 Scatter 점
  - 크기: amount (정규화 → minSize=40, maxSize=200)
  - 색상: STATUS_COLORS_6[status_6]
- **기준선** (ReferenceLine y):
  - 170%: 양호 기준 (green dashed)
  - 155%: 주의 기준 (amber dashed)
  - 140%: 마진콜 기준 (orange dashed)
  - 120%: 강제청산 기준 (red dashed)
  - 100%: 채무초과 기준 (deep red dashed)
- **Tooltip**: 코호트 진입일 + 진입가 + 현재 담보비율 + 잔액 + status_6

---

## 5. Component Specification

### 5.1 신규 컴포넌트

| Component | Type | 위치 | 예상 줄수 | 설명 |
|-----------|------|------|----------|------|
| `VLPIGauge` | Function | CohortAnalysis.jsx 내부 | ~60줄 | SVG 반원 게이지 |
| `ComponentBreakdown` | Function | CohortAnalysis.jsx 내부 | ~50줄 | V1~V6 기여분 바 차트 |
| `ImpactTable` | Function | CohortAnalysis.jsx 내부 | ~60줄 | 시나리오 매트릭스 테이블 |
| `CohortRiskMap` | Function | CohortAnalysis.jsx 내부 | ~50줄 | 담보비율 분포 산점도 |
| `normalizeStatus6` | Utility | CohortAnalysis.jsx 상단 | ~4줄 | snake_case → camelCase 변환 |

### 5.2 수정 컴포넌트

| Component | 변경 내용 |
|-----------|----------|
| `CohortBarLabel` → `CohortBarLabel6` | STATUS_COLORS → STATUS_COLORS_6, STATUS_LABELS → STATUS_LABELS_6, 코호트의 status_6 참조 |
| `CohortTooltip` → `CohortTooltip6` | 6단계 색상 + 담보비율 기준선 표시 |
| `MiniCohortChart` | STATUS_COLORS → STATUS_COLORS_6 참조 (단, Section 3 backtest에서만 사용 → status_6 없으면 status fallback) |
| `StockCreditBreakdown` > `StatusBar` | 4색 → 6색 (safe/good/caution/marginCall/forcedLiq/debtExceed) |
| Summary Cards | safePct → cautionZonePct (caution + good 합산), dangerPct → riskPct (marginCall + forcedLiq + debtExceed) |
| Guide Box 범례 | 4색 → 6색 |
| Section 1 `cohortChartData` | `c.status` → `normalizeStatus6(c.status_6) || c.status` (fallback) |

### 5.3 삭제 컴포넌트

| Component | Line Range (현재) | 이유 |
|-----------|-------------------|------|
| `ReliabilityDashboard` | 508~678 (~170줄) | v1.8.0 Model Learning Tab 대체 |
| `BacktestComparison` | 361~505 (~145줄) | v1.7.0 시뮬레이터 대체 |
| `TriggerMapTable` | 849~956 (~107줄) | VLPI 대시보드 대체 |
| `computeImpliedAbsorption` | 270~278 (~9줄) | BacktestComparison 전용 |
| `BACKTEST_DATES` import | line 22 | ReliabilityDashboard 삭제 |

### 5.4 유지 컴포넌트 (변경 없음)

| Component | 이유 |
|-----------|------|
| `SectionTitle` | 공통 |
| `PanelBox` | 공통 |
| `SummaryCard` | 공통 |
| `ToggleGroup` | 공통 |
| `SliderControl` | Section 3 |
| `SimTooltip` | Section 3 |
| `runSimulation()` | Section 3 (v1.7.0까지 유지) |
| `computeBacktestBeta()` | Section 3 backtest |
| `reconstructCohorts()` | Section 3 backtest — 단, Section 1 히스토리 선택에서도 사용 (4단계 classifyStatus 유지, status_6 없으므로) |
| `classifyStatus()` | Section 3 + reconstructCohorts에서 계속 필요 (히스토리 코호트에는 status_6 없음) |

---

## 6. File Change Specification

### 6.1 `web/src/simulators/kospi/colors.js`

```diff
 export const C = {
   ...existing...

+  // 6-stage cohort status
+  safeStatus: "#4caf50",
+  goodStatus: "#8bc34a",
+  cautionStatus: "#ffc107",
+  marginCallStatus: "#ff9800",
+  forcedLiqStatus: "#ff5252",
+  debtExceedStatus: "#ff1744",
+
+  // VLPI variable colors
+  vlpiV1: "#5c6bc0",
+  vlpiV2: "#26a69a",
+  vlpiV3: "#ff7043",
+  vlpiV4: "#ab47bc",
+  vlpiV5: "#ef5350",
+  vlpiV6: "#42a5f5",
 };
```

### 6.2 `web/src/simulators/kospi/shared/terms.jsx`

신규 TERM 추가 (~15개):

```javascript
// 6단계 상태
status_6_safe:       { label: "안전 (Safe)", desc: "담보비율 ≥ 170%. 충분한 여유" },
status_6_good:       { label: "양호 (Good)", desc: "담보비율 155%~170%. 양호한 상태" },
status_6_caution:    { label: "주의 (Caution)", desc: "담보비율 140%~155%. 추가 하락 시 마진콜 가능" },
status_6_marginCall: { label: "마진콜 (Margin Call)", desc: "담보비율 120%~140%. D+2 추가담보 요구" },
status_6_forcedLiq:  { label: "강제청산 (Forced Liq)", desc: "담보비율 100%~120%. 반대매매 실행 중" },
status_6_debtExceed: { label: "채무초과 (Debt Exceed)", desc: "담보비율 < 100%. 원금 초과 손실" },

// VLPI
pre_vlpi:       { label: "Pre-VLPI", desc: "자발적 투매 압력 지수 (0~100). 6개 변수 가중합. 높을수록 투매 압력 큼" },
vlpi_gauge:     { label: "VLPI 게이지", desc: "Pre-VLPI 스코어를 시각적으로 표시. 정상(0~30)/주의(30~50)/경고(50~70)/위험(70~100)" },
vlpi_component: { label: "VLPI 구성요소", desc: "Pre-VLPI를 구성하는 6개 변수의 가중 기여분" },
vlpi_impact:    { label: "VLPI 시나리오", desc: "낙관/기본/비관 시나리오별 VLPI 예측과 예상 매도압력" },
risk_map:       { label: "위험 분포도", desc: "각 코호트의 담보비율을 산점도로 표시. 기준선 아래일수록 위험" },
caution_zone:   { label: "주의구간 비중 (V1)", desc: "담보비율 140~170% 코호트 비중. VLPI의 핵심 선행 입력" },
```

### 6.3 `web/src/simulators/kospi/CohortAnalysis.jsx`

#### Import 변경

```diff
 import {
   COHORT_DATA, INVESTOR_FLOWS, MARKET_DATA, SHORT_SELLING,
-  COHORT_HISTORY, BACKTEST_DATES, STOCK_CREDIT,
+  COHORT_HISTORY, STOCK_CREDIT, VLPI_DATA, VLPI_CONFIG,
 } from "./data/kospi_data";
```

#### 상수 변경 (기존 유지 + 신규 추가)

- `STATUS_COLORS`, `STATUS_LABELS`: **유지** (Section 3 시뮬레이터 + reconstructCohorts에서 사용)
- `STATUS_COLORS_6`, `STATUS_LABELS_6`, `STATUS_ORDER_6`: **추가** (Section 1 + Section 2)
- `VLPI_VAR_COLORS`: **추가** (Section 2 ComponentBreakdown)
- `normalizeStatus6()`: **추가** (status_6 키 정규화)

#### Section 1 변경

1. `cohortSummary` 계산:
   - `safePct` → 삭제
   - `cautionZonePct`: caution + good 합산 / total
   - `riskPct`: marginCall + forcedLiq + debtExceed 합산 / total
2. `cohortChartData`: `c.status` → `normalizeStatus6(c.status_6) || c.status`
3. `CohortBarLabel`: STATUS_COLORS_6, STATUS_LABELS_6 사용
4. `CohortTooltip`: STATUS_COLORS_6, STATUS_LABELS_6 사용
5. Summary Cards: [총잔고] [주의구간 ○○%] [위험 ○○%] [Portfolio Beta]
6. 범례: 6색

#### Section 2 변경 (트리거맵 → VLPI 대시보드)

기존 `<PanelBox>` 트리거맵 전체를 VLPI 대시보드로 교체:

```jsx
{/* Section 2: VLPI 대시보드 */}
<PanelBox>
  <SectionTitle termKey="pre_vlpi">VLPI 대시보드</SectionTitle>
  {/* Guide Box */}
  <div>...VLPI 설명...</div>

  {/* A + B: Gauge + Breakdown (2-column) */}
  <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: 20 }}>
    <VLPIGauge score={VLPI_DATA.latest.pre_vlpi} level={VLPI_DATA.latest.level} levels={VLPI_CONFIG.levels} />
    <ComponentBreakdown components={VLPI_DATA.latest.components} variables={VLPI_CONFIG.variables} weights={VLPI_CONFIG.weights} />
  </div>

  {/* C: Impact Table */}
  <ImpactTable scenarios={VLPI_DATA.scenario_matrix} currentVlpi={VLPI_DATA.latest.pre_vlpi} />

  {/* D: Risk Map */}
  <CohortRiskMap cohorts={activeCohorts} thresholds={VLPI_CONFIG.status_thresholds} />
</PanelBox>
```

#### Section 3 변경

- BacktestComparison 호출 **삭제** (line 1679~1687)
- 나머지 시뮬레이터 로직 **유지**

#### Section 4 삭제

- ReliabilityDashboard 호출 **삭제** (line 1704~1712)

---

## 7. Implementation Order

```
Step 1:  colors.js — 6단계 상태 + VLPI 변수 색상 추가
Step 2:  terms.jsx — 6단계 상태 + VLPI 용어 15개 추가
Step 3:  CohortAnalysis.jsx — import 변경 (BACKTEST_DATES 삭제, VLPI_DATA/CONFIG 추가)
Step 4:  CohortAnalysis.jsx — STATUS_COLORS_6, STATUS_LABELS_6, normalizeStatus6() 추가
Step 5:  CohortAnalysis.jsx — Section 1 6단계 전환 (chartData, labels, tooltip, summary, legend)
Step 6:  CohortAnalysis.jsx — VLPIGauge 컴포넌트 구현 (SVG arc)
Step 7:  CohortAnalysis.jsx — ComponentBreakdown 컴포넌트 구현 (recharts horizontal bar)
Step 8:  CohortAnalysis.jsx — ImpactTable 컴포넌트 구현 (HTML table)
Step 9:  CohortAnalysis.jsx — CohortRiskMap 컴포넌트 구현 (recharts scatter)
Step 10: CohortAnalysis.jsx — Section 2 트리거맵 → VLPI 대시보드 교체
Step 11: CohortAnalysis.jsx — 삭제 (ReliabilityDashboard, BacktestComparison, TriggerMapTable, computeImpliedAbsorption)
Step 12: CohortAnalysis.jsx — StockCreditBreakdown StatusBar 6색 적용
Step 13: CohortAnalysis.jsx — MiniCohortChart 6단계 색상 (fallback 처리)
Step 14: npm run build + dev 서버 검증
```

---

## 8. Test Plan

### 8.1 Visual Verification

- [ ] Section 1: 6색 Stacked Bar 정상 렌더, 각 status_6별 올바른 색상
- [ ] Section 1: Summary 카드 — 주의구간%, 위험% 정확
- [ ] Section 1: 범례 6색 + 한글 라벨
- [ ] Section 1: 히스토리 날짜 선택 시 reconstructCohorts fallback 정상 (4단계)
- [ ] VLPI Gauge: 스코어 39.0, level "주의", 바늘 위치 정확
- [ ] Component Breakdown: V1~V6 기여분 합 ≈ Pre-VLPI (39.0)
- [ ] Impact Table: 3행 (낙관/기본/비관) 렌더, 기본 행 하이라이트
- [ ] Cohort Risk Map: 코호트 점 + 기준선 5개 (100%/120%/140%/155%/170%)
- [ ] StockCreditBreakdown: StatusBar 6색 표시
- [ ] Section 3 시뮬레이터: What-if + Backtest 모두 정상 작동
- [ ] 삭제 확인: ReliabilityDashboard, BacktestComparison, TriggerMapTable 없음
- [ ] `npm run build` 성공, 에러/경고 없음

### 8.2 Edge Cases

- [ ] VLPI_DATA.latest.impact = null → Impact Table에서 graceful 처리
- [ ] 코호트에 status_6 없는 경우 (히스토리 복원) → status fallback
- [ ] VLPI_DATA.history 1건만 → 히스토리 차트 미표시 (v1.8.0)
- [ ] 모든 코호트 safe → Risk Map 기준선 위에 모두 표시

---

## 9. Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| status_6 키 매핑 불일치 | Section 1 색상 깨짐 | normalizeStatus6() + fallback |
| SVG Gauge 반응형 깨짐 | 모바일 레이아웃 | viewBox 고정 + width 100% |
| sell_volume_억 단위 혼동 | Impact Table 수치 오류 | 원본 데이터 단위 확인 후 포맷 결정 |
| Section 3 regression | 시뮬레이터 동작 불능 | classifyStatus + STATUS_COLORS 유지 (독립) |
| CohortAnalysis.jsx 크기 | 리팩토링 regression | 단계별 검증 (Step별 build 확인) |

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 0.1 | 2026-03-05 | Initial design draft |
