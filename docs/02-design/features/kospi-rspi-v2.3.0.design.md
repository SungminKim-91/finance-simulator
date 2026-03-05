# RSPI v2.3.0 Design — 비선형 Proximity + 검증 프레임워크

> **Feature**: kospi-rspi-v2.3.0
> **Created**: 2026-03-07

---

## 1. 코드 변경

### 1.1 rspi_engine.py — V1 비선형 proximity

```python
# constants.py에 추가
V1_PROXIMITY_POWER = 2.5

# calc_cohort_proximity 시그니처 변경
def calc_cohort_proximity(current_price, cohorts, power=V1_PROXIMITY_POWER):
    for cohort in cohorts:
        ratio = calc_collateral_ratio(current_price, entry_price)
        linear = max(0, min(1, 1 - (ratio - 140) / 60))
        proximity = linear ** power  # 핵심: 비선형 변환

        w = cohort.get("remaining_amount_billion") or cohort.get("weight", 0)
        weighted_proximity += proximity * w
        total_weight += w
    return weighted_proximity / total_weight
```

비선형 효과 (power=2.5):
```
ratio 200% → linear 0.00 → powered 0.00  (안전)
ratio 185% → linear 0.25 → powered 0.09  (여유)
ratio 170% → linear 0.50 → powered 0.18  (양호)
ratio 155% → linear 0.75 → powered 0.41  (주의)
ratio 145% → linear 0.92 → powered 0.78  (위험!)
ratio 140% → linear 1.00 → powered 1.00  (마진콜)
```

### 1.2 rspi_engine.py — RSPIEngine power 전달

```python
class RSPIEngine:
    def __init__(self, weights=None, proximity_power=V1_PROXIMITY_POWER):
        self.proximity_power = proximity_power

    def calculate_for_date(self, ...):
        v1 = calc_cohort_proximity(kospi_price, cohorts, power=self.proximity_power)
```

### 1.3 RSPI_CONFIG export 확장

```python
rspi_config = {
    "weights": RSPI_WEIGHTS,
    "proximity_power": V1_PROXIMITY_POWER,
    ...
}
```

## 2. 검증 스크립트 (rspi_validation.py)

### 2.1 구조

```python
class RSPIValidator:
    def __init__(self, ts, model_output):
        self.ts = ts
        self.rspi_history = model_output["rspi"]["history"]

    def step1_variable_distribution(self) -> dict
    def step2_rspi_distribution(self) -> dict
    def step3_variable_predictive_power(self) -> dict
    def step4_signal_strength(self) -> dict
    def step5_post_decline_tracking(self) -> dict
    def step6_volume_amplifier_comparison(self) -> dict
    def step7_false_alarm_analysis(self) -> dict
    def step8_weight_sensitivity(self) -> dict
    def step9_power_optimization(self) -> dict
    def generate_report(self) -> str
```

### 2.2 핵심 함수 명세

**Step 3 — 변수별 예측력:**
```python
def step3_variable_predictive_power(self):
    # 각 V에 대해:
    # 1. pearson_corr(V, next_day_return) + p-value
    # 2. quintile spread (상위20% - 하위20% 다음날 수익률)
    # 3. hit rate (V>0→다음날하락 비율)
    # 판단: |corr|>0.08, p<0.10, spread 부호 기대 일치 → 유효
```

**Step 4 — 시그널 강도:**
```python
def step4_signal_strength(self):
    # 4 버킷: noise(<5), mild(5-15), moderate(15-30), strong(30+)
    # 각 버킷: 날수, 평균|수익률|, 방향 일치율
    # 핵심: noise ~50%, strong 65%+ = 모델 유효
```

**Step 9 — power 최적화:**
```python
def step9_power_optimization(self, powers=[1.0, 1.5, 2.0, 2.5, 3.0]):
    # 각 power로 V1 262일 재계산 → RSPI 재계산 → Step 4 재실행
    # 선택: strong 버킷 일치율 최고 power
    # 제약: 기본값(2.5) 대비 5%+ 차이 있을 때만 변경
```

## 3. 실행 순서

1. constants.py에 V1_PROXIMITY_POWER 추가
2. rspi_engine.py에 power 파라미터 적용
3. compute_models.py에서 power 전달
4. rspi_validation.py 신규 작성
5. 파이프라인 실행 (compute_models + export_web)
6. 검증 실행 (rspi_validation.py)
7. 검증 결과 기반 파라미터 확정
8. 빌드 + 커밋

## 4. 수정 파일

| 파일 | 변경 |
|------|------|
| `kospi/config/constants.py` | V1_PROXIMITY_POWER = 2.5 |
| `kospi/scripts/rspi_engine.py` | power 파라미터, RSPIEngine 전달 |
| `kospi/scripts/compute_models.py` | RSPI_CONFIG에 power 포함 |
| `kospi/scripts/rspi_validation.py` | 9단계 검증 (신규) |
| `kospi/scripts/export_web.py` | RSPI_CONFIG에 proximity_power |
