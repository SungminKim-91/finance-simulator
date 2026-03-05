# KOSPI VLPI v1.6.0 — Frontend Cohort Redesign

> 코호트 탭 UI 전면 재설계: 6단계 상태 + VLPI 대시보드
> 선행 버전: v1.5.0 (Backend VLPI Engine, Match Rate 99.1%)
> 참조: `docs/archive/2026-03/kospi-vlpi-v1.5.0/kospi-vlpi-v1.5.0.plan.md` Section 3

---

## 0. 배경

### v1.5.0 완료 사항 (Backend)
- `vlpi_engine.py`: 6변수 Pre-VLPI (0~100) + Impact Function
- 6단계 상태 분류 (`STATUS_THRESHOLDS`): debt_exceed/forced_liq/margin_call/caution/good/safe
- `kospi_data.js`: `VLPI_DATA` (#17) + `VLPI_CONFIG` (#18) export 완료
- `_remap_cohorts()`: `status` = legacy 4단계, `status_6` = 신규 6단계 이중 export

### 현재 Frontend 상태
- `CohortAnalysis.jsx` (1715줄): 4단계 `STATUS_COLORS` (safe/watch/marginCall/danger)
- `classifyStatus()` JS 함수: 4단계 로직 (v1.4.1 기준)
- `ReliabilityDashboard`: 40건 백테스트 산점도 (삭제 대상)
- `BacktestComparison`: 듀얼 라인 차트 (삭제 대상)
- Section 1: 코호트 분포 (4색 stacked bar)
- Section 2: 트리거맵 (하락% → 마진콜/반대매매 금액)
- Section 3: 반대매매 연쇄 시뮬레이터 (v1.7.0에서 VLPI 시뮬레이터로 대체)

---

## 1. 변경 범위

### 1.1 Section 1: 코호트 분포 → 6단계

| 항목 | Before (v1.4) | After (v1.6) |
|------|--------------|--------------|
| 상태 분류 | 4단계 (safe/watch/marginCall/danger) | 6단계 (safe/good/caution/marginCall/forcedLiq/debtExceed) |
| 색상 | 4색 | 6색 (green → light green → amber → orange → red → deep red) |
| STATUS_COLORS | `{safe, watch, marginCall, danger}` | `{safe, good, caution, marginCall, forcedLiq, debtExceed}` |
| classifyStatus() | JS 함수 (4단계) | backend `status_6` 필드 직접 사용 |
| 요약 카드 | 총잔고, 안전비율, 위험비율 | 총잔고, 주의구간(V1용), 위험비율 |
| reconstructCohorts() | 4단계 classify | `status_6` 필드 소비 |

**구체적 변경:**
- `STATUS_COLORS_6`: 6단계 색상 맵 (VLPI_CONFIG.levels + status_thresholds 색상)
- `STATUS_LABELS_6`: 6단계 한글 라벨 (채무초과/강제청산/마진콜/주의/양호/안전)
- Stacked horizontal bar: 6색 segment
- Summary 카드 "주의구간 비중": caution + good 구간 비율 (V1 입력값)

### 1.2 Section 2: 트리거맵 → VLPI 대시보드

기존 트리거맵 (하락% → 마진콜/반대매매 금액 테이블) **삭제** → **VLPI 대시보드** 신규:

**A. VLPI Gauge** (핵심 비주얼)
- 반원 게이지 (0~100), SVG arc 기반
- 4색 구간: 0~30 녹색(정상) / 30~50 노란색(주의) / 50~70 주황색(경고) / 70~100 빨간색(위험)
- 중앙: 현재 Pre-VLPI 스코어 (큰 숫자) + 등급 텍스트
- 데이터: `VLPI_DATA.latest.pre_vlpi` + `VLPI_DATA.latest.level`

**B. Component Breakdown** (변수별 기여분)
- 수평 Stacked Bar (recharts BarChart horizontal)
- V1~V6 각 변수의 기여분 (VLPI_DATA.latest.components)
- 호버: 변수 설명 + 현재 원시값 + 가중치 (VLPI_CONFIG.variables)
- 색상: 각 변수별 고유색 (6색)

**C. Impact Table** (시나리오 매트릭스)
- 3행 테이블 (낙관/기본/비관)
- 컬럼: 시나리오, EWY변동, Pre-VLPI, 매도추정(억), 가격영향(%)
- 현재 VLPI에 해당하는 행 하이라이트
- 데이터: `VLPI_DATA.scenario_matrix`

**D. Cohort Risk Map** (코호트 담보비율 분포)
- 수직 축: 담보비율 (100% ~ 200%)
- 각 코호트를 점(dot)으로 표시, 크기 = weight
- 수평 라인: 140%(마진콜), 155%(주의), 170%(양호) 기준선
- 호버: 코호트 라벨 + 진입가 + 현재 담보비율 + 상태

### 1.3 Section 3: 시뮬레이터 유지 (v1.7.0으로 이관)

- 기존 반대매매 연쇄 시뮬레이터 **그대로 유지** (v1.7.0에서 VLPI 시뮬레이터로 교체)
- 단, `classifyStatus()` → backend `status_6` 사용으로 통일

### 1.4 삭제 대상

| 컴포넌트 | 이유 |
|----------|------|
| `ReliabilityDashboard` (~170줄) | v1.8.0 Model Learning Tab으로 대체 |
| `BacktestComparison` (~150줄) | v1.7.0 시뮬레이터에서 더 나은 비교 제공 |
| `BACKTEST_DATES` import | ReliabilityDashboard 삭제에 따른 미사용 |
| `TriggerMapTable` (~110줄) | VLPI 대시보드로 대체 |

### 1.5 유지/수정 대상

| 컴포넌트 | 변경 |
|----------|------|
| `StockCreditBreakdown` (~170줄) | 6단계 색상 적용, 나머지 유지 |
| `MiniCohortChart` (~60줄) | 6단계 색상 적용 |
| `runSimulation()` (~80줄) | v1.7.0까지 유지 |

---

## 2. 데이터 소스

### kospi_data.js에서 소비할 데이터

```javascript
// 기존 (유지)
import { COHORT_DATA, INVESTOR_FLOWS, MARKET_DATA, SHORT_SELLING,
         COHORT_HISTORY, STOCK_CREDIT } from "./data/kospi_data";

// 신규 (v1.5.0에서 추가된 export)
import { VLPI_DATA, VLPI_CONFIG } from "./data/kospi_data";

// 삭제
// import { BACKTEST_DATES } from "./data/kospi_data";  // ReliabilityDashboard 삭제
```

### VLPI_DATA 구조
```json
{
  "history": [{ "date", "pre_vlpi", "level", "components": {v1~v6}, "raw_variables", "impact" }],
  "latest": { "pre_vlpi": 39.0, "level": "caution", "components": {...}, "impact": {...} },
  "scenario_matrix": [{ "label", "ewy_change_pct", "pre_vlpi", "sell_volume_억", "price_impact_pct" }]
}
```

### VLPI_CONFIG 구조
```json
{
  "weights": { "w1"~"w6" },
  "status_thresholds": { "debt_exceed": 100, ..., "good": 170 },
  "variables": [{ "key", "label", "desc", "range", "weight_key" }],
  "levels": [{ "min", "max", "label", "color" }],
  "impact_params": { "sensitivity", "sigmoid_k", "sigmoid_mid", "samsung_credit_weight" }
}
```

### COHORT_DATA 코호트 필드 (v1.5.0 갱신)
```json
{
  "entry_kospi": 5200,
  "entry_stock_price": 190000,
  "amount": 2.34,
  "pnl_pct": -8.5,
  "collateral_ratio_pct": 164.8,
  "status": "watch",           // legacy 4단계 (기존 코드 호환)
  "status_6": "good",          // 신규 6단계
  "liquidated_pct": 0
}
```

---

## 3. 색상 체계

### 6단계 상태 색상

| Status | 한글 | 색상 | Hex |
|--------|------|------|-----|
| debtExceed | 채무초과 | Deep Red | `#ff1744` |
| forcedLiq | 강제청산 | Red | `#ff5252` |
| marginCall | 마진콜 | Orange | `#ff9800` |
| caution | 주의 | Amber | `#ffc107` |
| good | 양호 | Light Green | `#8bc34a` |
| safe | 안전 | Green | `#4caf50` |

### VLPI 레벨 색상 (게이지용)

| Level | 범위 | 색상 | Hex |
|-------|------|------|-----|
| normal | 0~30 | Green | `#4caf50` |
| caution | 30~50 | Yellow | `#ffc107` |
| warning | 50~70 | Orange | `#ff9800` |
| danger | 70~100 | Red | `#f44336` |

### 변수 색상 (Component Breakdown)

| Variable | 색상 | Hex |
|----------|------|-----|
| V1 주의구간 | Indigo | `#5c6bc0` |
| V2 신용모멘텀 | Teal | `#26a69a` |
| V3 정책쇼크 | Deep Orange | `#ff7043` |
| V4 야간갭 | Purple | `#ab47bc` |
| V5 연속하락 | Red | `#ef5350` |
| V6 개인수급 | Blue | `#42a5f5` |

---

## 4. UI 레이아웃

```
┌─────────────────────────────────────────────┐
│ Section 1: 코호트 분포 (6단계)                │
│ ┌─────────────────────────────────────┐      │
│ │ [LIFO ▪ FIFO]  날짜선택             │      │
│ │ ══════════════════════════════      │      │
│ │ 6색 Stacked Horizontal Bar          │      │
│ │ (가격대별 코호트, 높은→낮은)          │      │
│ │ ══════════════════════════════      │      │
│ │ [총 잔고 ○.○조] [주의구간 ○○%] [위험 ○○%]│
│ └─────────────────────────────────────┘      │
│                                              │
│ Section 2: VLPI 대시보드                      │
│ ┌──────────────┬──────────────────────┐      │
│ │  VLPI Gauge  │  Component Breakdown │      │
│ │   ╭───╮      │  V1 ████░░ 7.3      │      │
│ │  ╱  39 ╲     │  V2 ██░░░░ 3.0      │      │
│ │ ╱ 주의  ╲    │  V3 ████████ 20.0   │      │
│ │ ▔▔▔▔▔▔▔▔    │  V4 █████░░ 10.0    │      │
│ ├──────────────┴──────────────────────┤      │
│ │  Impact Table (시나리오 매트릭스)     │      │
│ │  낙관적 │ EWY+2.5% │ VLPI 22 │ ...  │      │
│ │  기본   │ EWY-1.0% │ VLPI 38 │ ...  │ ← hl│
│ │  비관적 │ EWY-4.0% │ VLPI 64 │ ...  │      │
│ ├─────────────────────────────────────┤      │
│ │  Cohort Risk Map (담보비율 분포)      │      │
│ │  200% ─ ─ ─ ─ ─ ─ ─ ─ ─ ─        │      │
│ │  170% ═══════════════════ (양호)    │      │
│ │  155% ═══════════════════ (주의)    │      │
│ │  140% ═══════════════════ (마진콜)   │      │
│ │  120% ═══════════════════ (강제청산)  │      │
│ │  100% ─ ─ ─ ─ ─ ─ ─ ─ ─ ─        │      │
│ │       ● ●   ●  ●  ●  ● (코호트들)  │      │
│ └─────────────────────────────────────┘      │
│                                              │
│ Section 3: 시뮬레이터 (기존 유지, v1.7.0 교체) │
│ ┌─────────────────────────────────────┐      │
│ │ (기존 반대매매 시뮬레이터 그대로)       │      │
│ └─────────────────────────────────────┘      │
│                                              │
│ StockCreditBreakdown (종목별 가중) — 6단계 색상 │
└─────────────────────────────────────────────┘
```

---

## 5. 파일 변경 목록

| 파일 | 작업 | 예상 줄수 변경 |
|------|------|---------------|
| `CohortAnalysis.jsx` | 전면 재설계 (6단계 + VLPI 대시보드, 삭제 3개 컴포넌트) | -430줄 삭제 + 400줄 신규 ≈ 1685줄 |
| `shared/terms.jsx` | 6단계 상태 + VLPI 용어 추가 (~15 TERM) | +60줄 |
| `colors.js` | 6단계 색상 + VLPI 변수 색상 추가 | +20줄 |

---

## 6. 구현 순서

```
Step 1: colors.js — 6단계 상태 색상 + VLPI 변수 색상 추가
Step 2: terms.jsx — 6단계 상태 + VLPI 용어 (debt_exceed, good, pre_vlpi, caution_zone 등)
Step 3: CohortAnalysis.jsx — STATUS_COLORS_6, STATUS_LABELS_6, VLPI import
Step 4: Section 1 6단계 전환 — stacked bar 6색, summary 카드, reconstructCohorts → status_6
Step 5: Section 2 VLPI Gauge — SVG arc 반원 게이지 (0~100)
Step 6: Section 2 Component Breakdown — V1~V6 수평 stacked bar
Step 7: Section 2 Impact Table — 시나리오 매트릭스 3행 테이블
Step 8: Section 2 Cohort Risk Map — 담보비율 분포 dot chart
Step 9: 삭제 — ReliabilityDashboard, BacktestComparison, TriggerMapTable, BACKTEST_DATES import
Step 10: StockCreditBreakdown + MiniCohortChart — 6단계 색상 적용
Step 11: 검증 — npm run build + dev 서버 확인
```

---

## 7. 검증 기준

- [ ] 6단계 stacked bar: 6색 표시, 각 status_6별 올바른 색상/라벨
- [ ] VLPI Gauge: 반원 표시, 현재 스코어 39.0, level "caution"
- [ ] Component Breakdown: V1~V6 기여분 합 = Pre-VLPI 스코어
- [ ] Impact Table: 3 시나리오 (낙관/기본/비관) 정상 렌더링
- [ ] Cohort Risk Map: 코호트 점 + 기준선 4개 (100%/140%/155%/170%)
- [ ] 삭제 확인: ReliabilityDashboard, BacktestComparison, TriggerMapTable 없음
- [ ] StockCreditBreakdown: 6단계 색상 적용
- [ ] `npm run build` 성공, 에러 없음
- [ ] Dev 서버에서 모든 섹션 정상 표시

---

## 8. 리스크

1. **VLPI_DATA가 단일 날짜**: 현재 latest만 있음 (history는 1건). 히스토리 차트는 v1.8.0에서.
2. **SVG Gauge 커스텀**: recharts에 반원 게이지 없음 → 순수 SVG로 직접 구현 필요
3. **CohortAnalysis.jsx 1715줄**: 큰 파일 리팩토링 시 regression 위험 → 단계별 검증 필수
4. **시뮬레이터 하위호환**: Section 3의 `classifyStatus()` JS 함수를 `status_6`로 전환 시 기존 로직 영향 확인
