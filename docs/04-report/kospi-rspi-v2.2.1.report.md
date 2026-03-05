# KOSPI RSPI v2.2.1 — Minor Fix Completion Report

> **Summary**: KOFIA 거래대금 단위 버그, yfinance 거래량 단위 불일치, RSPI pending 상태 도입, V1 코호트 proximity 수정, 코호트 경로 통합
>
> **Feature**: kospi-rspi-v2.2.1
> **Version**: v2.2.0 → v2.2.1
> **Author**: Sungmin Kim
> **Created**: 2026-03-06
> **Status**: Completed

---

## 1. Overview

### 1.1 Feature Summary

RSPI v2.2.0 배포 후 UI 검증 과정에서 발견된 6건의 데이터/로직 버그를 수정하는 마이너 패치입니다.

**핵심 수정 사항**:
1. **KOFIA 거래대금 100x 과대 계산** — divisor 10 → 1000 (백만원 단위)
2. **yfinance 거래량 단위 불일치** — ECOS only 정책으로 전환
3. **RSPI pending 상태 도입** — 야간 데이터 미확보 시 계산 보류
4. **V1 코호트 proximity 항상 0** — 필드명 + 가격 소스 3중 버그 수정
5. **"오늘" vs 기준일 코호트 불일치** — reconstructCohorts() 경로 통합
6. **V3 overnight lookback** — 최신일은 당일만 확인 (stale 데이터 방지)

### 1.2 PDCA Cycle

| Phase | Status | Outcome |
|-------|--------|---------|
| **Plan** | ✅ | UI 검증 중 6건 버그 식별 |
| **Do** | ✅ | 9개 파일 수정 |
| **Check** | ✅ | Pipeline + Build 통과, UI 검증 완료 |
| **Report** | ✅ | 본 보고서 |

---

## 2. Bug Fixes

### 2.1 KOFIA 거래대금 단위 (100x 과대)

**파일**: `kospi/scripts/kofia_excel_parser.py`

**원인**: KOFIA FreeSIS 엑셀의 거래대금 단위가 **백만원**인데, divisor를 10으로 설정하여 억원으로 잘못 변환.

**수정**:
```python
# Before: divisor=10 (억원 가정 → 45,309 십억원)
"주식시장>거래대금>KOSPI": ("kospi_trading_value_billion", 10),

# After: divisor=1000 (백만원 → 453.09 십억원)
"주식시장>거래대금>KOSPI": ("kospi_trading_value_billion", 1e3),
```

**검증**: 2026-03-05 거래대금 453,090백만원 / 1000 = 453.09십억원 (정상)

### 2.2 yfinance 거래량 단위 불일치

**파일**: `kospi/scripts/fetch_daily.py`

**원인**: ECOS는 `천주 × 1000`으로 주단위 변환, yfinance `^KS11` volume은 다른 단위계. fallback으로 사용 시 162.2M vs 1.66M 100배 차이.

**수정**: yfinance volume fallback 제거, ECOS only 정책.

```python
"volume": None,  # yfinance ^KS11 volume 단위 불일치 - ECOS only
```

### 2.3 RSPI Pending 상태

**파일**: `kospi/scripts/rspi_engine.py`, `compute_models.py`, `export_web.py`, `CohortAnalysis.jsx`

**원인**: 최신일에 야간 데이터(EWY, KORU, S&P500, 선물)가 아직 확보되지 않은 경우, V3=0으로 계산하여 RSPI가 부정확하게 산출됨.

**수정**: 최신일 + overnight 데이터 없음 → `rspi=None, level="pending"` 반환.

```python
if is_latest and not has_overnight:
    pending_result = {
        "rspi": None, "level": "pending", "pending": True,
        "raw_variables": {"v1": v1, "v2": v2, "v3": None, "v4": None, "v5": None},
        ...
    }
```

**프론트엔드**: pending 시 게이지/분해 숨기고 "RSPI 계산 대기중 (야간 데이터 미확보)" 메시지 표시.

### 2.4 V1 코호트 Proximity 항상 0

**파일**: `kospi/scripts/rspi_engine.py`

**원인 (3중 버그)**:
1. `entry_price` 필드명 → 실제 데이터는 `entry_kospi`
2. `weight` 필드명 → 실제 데이터는 `remaining_amount_billion`
3. 삼성전자 가격(190,000원)으로 KOSPI 코호트 비교 → KOSPI 지수(~2,500) 사용해야 함

**수정**:
```python
# 필드명 수정
entry_price = cohort.get("entry_kospi") or cohort.get("entry_price", 0)
w = cohort.get("remaining_amount_billion") or cohort.get("weight", 0)

# KOSPI 지수 사용
kospi_price = ts[idx].get("kospi", 0) or 0
v1 = calc_cohort_proximity(kospi_price, cohorts)
```

### 2.5 "오늘" vs 기준일 코호트 불일치

**파일**: `web/src/simulators/kospi/CohortAnalysis.jsx`

**원인**: "오늘" 선택 시 정적 `COHORT_DATA.lifo`, 날짜 선택 시 `reconstructCohorts()` — 서로 다른 코드 경로.

**수정**: 모든 경우 `COHORT_HISTORY.snapshots`에서 해당 날짜 스냅샷 검색 → `reconstructCohorts()` 통합.

```jsx
const snaps = COHORT_HISTORY?.snapshots;
const targetDate = cohortDate || snaps?.[snaps.length - 1]?.date;
const snap = targetDate ? snaps?.find(s => s.date === targetDate) : null;
```

### 2.6 V3 Overnight Lookback (Stale 데이터)

**파일**: `kospi/scripts/compute_models.py`

**원인**: 최신일에 야간 데이터가 None이어도, D-1~D-3 lookback으로 3일 전 데이터를 채워서 마치 데이터가 있는 것처럼 처리.

**수정**: 최신일은 당일만 확인 (lookback_range=1).

```python
is_latest = (idx == len(ts) - 1)
lookback_range = 1 if is_latest else min(4, idx + 1)
```

---

## 3. Modified Files

| File | Changes |
|------|---------|
| `kospi/scripts/kofia_excel_parser.py` | 거래대금 divisor 10→1000 |
| `kospi/scripts/fetch_daily.py` | yfinance volume fallback 제거 |
| `kospi/scripts/rspi_engine.py` | pending 상태, V1 필드명/가격 수정, trading_value 필드 호환 |
| `kospi/scripts/compute_models.py` | V3 lookback 최신일 제한, pending 시 scenario_matrix skip |
| `kospi/scripts/export_web.py` | pending 상태 pass-through, VLPI→RSPI docstring |
| `web/src/simulators/kospi/CohortAnalysis.jsx` | pending UI, 코호트 경로 통합 |
| `kospi/data/timeseries.json` | 3/5 거래대금+거래량 데이터 보정 |
| `kospi/data/daily/2026-03-05.json` | 동일 보정 |
| `kospi/data/model_output.json` | 재계산된 RSPI 결과 |
| `web/src/simulators/kospi/data/kospi_data.js` | 재빌드된 웹 데이터 |

---

## 4. Verification

- Pipeline: `compute_models.py` + `export_web.py` 정상 실행
- Build: `npm run build` 성공 (warnings only)
- 3/5 거래대금: 45,309 → 453.09 십억원 (정상)
- 3/5 RSPI: pending 상태 (야간 데이터 미확보)
- 3/4 V1 코호트 proximity: 정상 값 반환 (KOSPI 지수 기준)
- "오늘" = "3/5" 동일 결과 확인

---

## 5. Lessons Learned

1. **단위 검증 필수**: 외부 소스(KOFIA, yfinance) 데이터는 반드시 실제 값과 교차 검증
2. **Pending > 0**: 데이터 미확보 시 0으로 채우기보다 명시적 pending 상태가 더 정확
3. **코드 경로 통합**: 같은 데이터를 표시하는 UI는 반드시 동일 코드 경로 사용
4. **필드명 일관성**: Python 백엔드와 JS 프론트엔드 간 필드명 불일치 주의
