# KOSPI RSPI v2.2.2 — V1 Look-Ahead Bias Fix

> **Summary**: V1 코호트 proximity의 look-ahead bias 제거 — 날짜별 코호트 스냅샷으로 전환
>
> **Feature**: kospi-rspi-v2.2.2
> **Version**: v2.2.1 → v2.2.2
> **Author**: Sungmin Kim
> **Created**: 2026-03-06
> **Status**: Completed

---

## 1. Overview

### 1.1 문제 (Look-Ahead Bias)

RSPI V1 (코호트 proximity) 계산에서 **최신일 기준 133개 코호트를 전체 262일에 동일 적용** — 미래에 생성된 코호트가 과거 날짜의 V1에 반영되는 심각한 look-ahead bias 존재.

**구체적 예시**: 2025-12-12 V1 계산 시
- 2026년 2~3월에 형성된 고점 코호트 (KOSPI 5,500~6,300) 포함
- 12/12 KOSPI=4,167에서 이 코호트들의 담보비율 120~138% → 마진콜 구간 잡힘
- **그 코호트는 12/12에 존재하지 않았음** — 미래 정보를 과거에 적용

### 1.2 수정

각 날짜 기준으로 **그때까지 존재하는 코호트만** 사용하여 V1 계산.

기존 `cohort_snapshots` (코호트 빌드 루프에서 날짜별 캡처) 활용 → RSPI 루프에서 해당 날짜의 스냅샷만 전달.

---

## 2. 변경 사항

### 2.1 compute_models.py

**Before (v2.2.1)**: 최신일 `lifo_adjusted` → 고정 `rspi_cohorts` → 전체 날짜 동일 적용
```python
rspi_cohorts = []  # 최신일 기준 133개 고정
for c in lifo_adjusted:
    rspi_cohorts.append({"entry_price": ..., "weight": ...})

for idx in range(start_idx, len(ts)):
    rspi_engine.calculate_for_date(cohorts=rspi_cohorts, ...)  # 동일 코호트
```

**After (v2.2.2)**: `cohort_snapshots` → `date_to_cohorts` dict → 날짜별 코호트 전달
```python
date_to_cohorts = {}
for snap in cohort_snapshots:
    cohorts_for_date = []
    for entry_date, amount in snap["amounts"].items():
        if entry_date in cohort_registry and amount > 0:
            cohorts_for_date.append({
                "entry_kospi": cohort_registry[entry_date]["entry_kospi"],
                "remaining_amount_billion": amount,
            })
    date_to_cohorts[snap["date"]] = cohorts_for_date

for idx in range(start_idx, len(ts)):
    date_cohorts = date_to_cohorts.get(rec["date"], [])  # 해당 날짜 코호트
    rspi_engine.calculate_for_date(cohorts=date_cohorts, ...)
```

---

## 3. 검증 결과

### 3.1 V1 변화 비교

| 날짜 | KOSPI | 코호트 수 (Before) | 코호트 수 (After) | V1 Before | V1 After |
|------|-------|:--:|:--:|---:|---:|
| 2025-12-12 | 4,167 | 133 | 99 | 0.1749 | **0.0243** |
| 2026-03-04 | 5,094 | 133 | 133 | 0.0702 | 0.0702 |
| 2026-03-05 | 5,584 | 133 | 133 | 0.0328 | 0.0328 |

### 3.2 12/12 분석

- **Before**: 133개 코호트 (max entry=6,307), danger(prox>0.5) 8개 → V1=0.1749
- **After**: 99개 코호트 (max entry=4,171), danger 0개 → V1=0.0243
- 2026년 1~3월 코호트 34개가 제거됨
- 12/12 시점에는 KOSPI 4,171 이하 코호트만 존재 → 담보비율 모두 안전

### 3.3 3/4 분석

- 3/4는 timeseries 끝에서 1일 전 → 코호트 구성이 거의 최신과 동일 (133개)
- V1 값 변화 없음 (정상)

### 3.4 Pipeline

- `compute_models.py`: 정상 실행, RSPI history=262 days
- `export_web.py`: 정상
- `npm run build`: 성공

---

## 4. Modified Files

| File | Changes |
|------|---------|
| `kospi/scripts/compute_models.py` | 고정 `rspi_cohorts` → `date_to_cohorts` 날짜별 매핑 |
| `kospi/data/model_output.json` | V1 값 전면 재계산 |
| `web/src/simulators/kospi/data/kospi_data.js` | 재빌드 |

---

## 5. Lessons Learned

1. **Look-ahead bias는 모델링의 가장 흔하고 치명적인 오류** — 코드 리뷰에서 "이 데이터가 이 시점에 존재했는가?"를 항상 질문
2. **기존 인프라 활용**: `cohort_snapshots`가 이미 날짜별 코호트를 캡처하고 있었음 — 새 코드 불필요, 기존 데이터를 RSPI 루프에 연결만 하면 됨
3. **근접 날짜에서는 보이지 않는 버그**: 3/4 (최신-1일)에서는 V1 차이가 없어 발견 불가 — 과거 날짜 검증 필수
