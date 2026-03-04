# Design: KOSPI Crisis Detector v1.1.1 — Bugfix & UX Improvement

> Feature: `kospi-crisis-v1.1.1-bugfix` | Version: 1.1.1 | Created: 2026-03-04
> Plan Reference: `docs/01-plan/features/kospi-crisis-v1.1.1-bugfix.plan.md`

---

## 1. Naver Investor Flow Scraper

### 1.1 `fetch_naver_investor_flows(start, end)`

**URL**: `https://finance.naver.com/sise/investorDealTrendDay.naver`
**Parameters**: `bizdate={end_date}&sosok=01&page={n}`
**Encoding**: euc-kr
**Unit**: 억원 → 십억원 (/10)

**Table Structure** (11 columns):

| Col | CSS Class | Field |
|-----|-----------|-------|
| 0 | `date2` | Date (YY.MM.DD) |
| 1 | `rate_up3/rate_down3` | 개인 (individual) |
| 2 | | 외국인 (foreign) |
| 3 | | 기관계 (institution) |
| 4 | | 금융투자 (financial_invest) |
| 5-9 | | 보험, 투신, 은행, 기타금융, 연기금 |
| 10 | | 기타법인 |

**Pagination**: ~10 rows/page, 역순(최신→과거), date < start 시 중단.
**Rate limit**: 0.3s between pages.
**Max pages**: 100 (~1000 trading days)

```python
def fetch_naver_investor_flows(start: str, end: str) -> dict[str, dict]:
    # Returns {
    #   "2026-03-04": {
    #     "individual_billion": 79.6,
    #     "foreign_billion": 230.3,
    #     "institution_billion": -597.8,
    #     "financial_invest_billion": -583.0,
    #   }, ...
    # }
```

### 1.2 Pipeline Integration

**fetch_daily.py 변경**:
- 6-step pipeline: env → KRX → ECOS → Naver deposit → **Naver investor** → yfinance → merge
- `build_snapshot()`: Naver investor 데이터를 primary source로 사용
- Data priority: **Naver investor > ECOS(foreign only)**

**timeseries.json 신규 필드**: `financial_invest_billion`

---

## 2. Cohort Null Credit Fix

### 2.1 Problem

```
Day 2026-02-27: credit = 32188.1 (Naver 마지막 데이터)
Day 2026-03-03: credit = null → `or 0` = 0
Delta = 0 - 32188.1 = -32188.1 → 모든 코호트 청산
```

### 2.2 Solution

```python
# compute_models.py run_all_models()
last_known_credit = 0
for i in range(1, len(ts)):
    cur_credit = cur.get("credit_balance_billion")
    # null이면 직전 유효값 유지 (carry-forward)
    if cur_credit is not None and cur_credit > 0:
        last_known_credit = cur_credit
    cur_credit_safe = cur_credit if (cur_credit and cur_credit > 0) else last_known_credit
```

---

## 3. MarketPulse UI Changes

### 3.1 Section Reorder

**Before**: KOSPI Chart → Credit → 반대매매 → Investor Flows → ...
**After**: KOSPI Chart → **Investor Flows** → **Credit** → 공매도 → ...

### 3.2 Credit/Deposit Toggle

```jsx
const [showCredit, setShowCredit] = useState(true);
const [showDeposit, setShowDeposit] = useState(true);
// Toggle buttons + conditional Line rendering
```

### 3.3 Default Period

```jsx
// Before: allDates[0] (ALL)
// After: allDates[Math.max(0, allDates.length - 66)] (3M)
```

### 3.4 Removed

- `FORCED_LIQ_THRESHOLD` constant
- `fmtHundM()` function
- `forcedLiqZoom` / `forcedLiqAxis` state
- 반대매매 section (entire PanelBox)

### 3.5 connectNulls

모든 Line 컴포넌트에 `connectNulls` 추가 → null 값으로 인한 라인 끊김 방지.

---

## 4. export_web.py Changes

```python
# Before: fin_invest 추정 (개인의 ~20%)
fin_invest = round(indiv * 0.2, 1) if indiv is not None else None

# After: timeseries에서 직접 읽기
fin_invest = r.get("financial_invest_billion")
```

---

**Status**: Implemented
