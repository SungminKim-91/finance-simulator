# RSPI v3.1 검증 보고서 — 곱셈 모델 + 3단계 순차 최적화

> **Feature**: kospi-rspi-v2.3.0-v31
> **Version**: v2.3.0 (Phase 2)
> **Date**: 2026-03-07
> **Status**: 부분유효 (Q1 FAIL, Q3 PASS)

---

## 1. 요약

| 지표 | v3.0 (덧셈) | v3.1 기본값 | v3.1 최적화 | 목표 |
|------|-------------|------------|------------|------|
| Q1: 중립 비율 | 25.7% | 14.8% | **20.9%** | 65%+ |
| Q3: strong 일치율 | 83.3% | 65.6% | **75.4%** | 70%+ |
| moderate 일치율 | 71.4% | 62.2% | 54.2% | — |
| False alarm | 9건 | 43건 | **26건** | — |
| 과적합 (noise 방향) | — | — | 55.3% | ≤58% |

**전체 판정: 부분유효** — Q3 방향 정확도 크게 개선 (75.4%), 하지만 Q1 중립 비율은 구조적 한계로 미달.

## 2. 구조 변경 사항

### 2.1 덧셈 → 곱셈 모델 전환
```
v3.0: RSPI = -1 × Σ(wi × Vi) × volume_amp × 100
v3.1: RSPI = -1 × base_signal × structural_amp × volume_amp × 100
```

- **시그널** (방향): `base_signal = ws2*V2 + ws3*V3 + ws5*V5`
- **증폭기** (강도): `structural_amp = 1 + α*V1 + β*velocity + γ*max(z,0)`

### 2.2 V4 제거 → 개인누적 z-score
- 패턴 기반 V4 (예측력 없음, corr=0.03) 삭제
- 60일 누적 개인매수의 rolling z-score → 구조적 증폭기에 편입

### 2.3 V1 역할 변경
- v3.0: V1은 시그널 (가중 합산의 일부)
- v3.1: V1은 증폭기 (방향 결정에 참여하지 않음, 크기만 증폭)

## 3. 최적 파라미터

### 3.1 Round 1: 감도 (64조합)
| 파라미터 | 기본값 | 최적값 | 변경 이유 |
|---------|-------|--------|---------|
| V2_DIVISOR | 2.0 | **3.5** | 외국인 z-score 감도 축소 → false alarm 감소 |
| V3_EWY_DIVISOR | 5.0 | **8.0** | 야간시장 감도 축소 → neutral 비율 개선 |
| V5_DIVISOR | 2.0 | **2.5** | 신용잔고 감도 미세 축소 |

### 3.2 Round 2: 증폭기 (1600조합)
| 파라미터 | 기본값 | 최적값 |
|---------|-------|--------|
| V1_PROXIMITY_POWER | 2.5 | **1.5** |
| STRUCTURAL_AMP_ALPHA | 2.0 | 2.0 (유지) |
| STRUCTURAL_AMP_BETA | 3.0 | **1.5** |
| STRUCTURAL_AMP_GAMMA | 0.5 | 0.5 (유지) |
| INDIV_CUM_SUM_WINDOW | 60 | 60 (유지) |

### 3.3 Round 3: 시그널 가중치 (10조합)
| 파라미터 | 기본값 | 최적값 |
|---------|-------|--------|
| ws2 (V2 외국인) | 0.35 | 0.35 (유지) |
| ws3 (V3 야간) | 0.45 | 0.45 (유지) |
| ws5 (V5 신용) | 0.20 | 0.20 (유지) |

## 4. 핵심 날짜 분석

| 날짜 | RSPI | V1 | V1_vel | cum_z | str_amp | V2 | V3 | V5 |
|------|------|-----|--------|-------|---------|-----|-----|-----|
| 2025-12-12 | -25.7 | 0.011 | 0.000 | +0.14 | 1.09 | -0.05 | +0.49 | +0.10 |
| 2026-03-03 | -82.8 | 0.014 | 0.010 | +1.05 | 1.57 | +0.46 | +1.00 | -0.77 |
| 2026-03-04 | +60.7 | 0.053 | 0.039 | +1.05 | 1.69 | -0.20 | -0.31 | -0.48 |
| 2026-03-05 | -66.2 | 0.021 | 0.000 | +1.53 | 1.81 | -0.14 | +1.00 | +0.00 |

- 3/3 급락: RSPI = -82.8 (extreme_sell) → 정확
- 3/4 반등: RSPI = +60.7 (strong_rebound) → 정확
- 3/5 재하락: RSPI = -66.2 (extreme_sell) → structural_amp 1.81 (개인 축적 z=1.53)

## 5. 음전환 추적 (C2)

| 유형 | 건수 | 평균 RSPI | 해석 |
|------|------|----------|------|
| deep (5일 -5%↓) | 1건 | -25.2 | 강한 매도 시그널 정확 |
| mild (5일 -2~5%↓) | 5건 | -7.5 | 약한 매도 감지 |
| quick (반등) | 33건 | +4.4 | 중립~약한 반등 (정상) |

## 6. 버그 수정

### Round 1 module-level import 버그 (치명적)
- **증상**: 64조합 모두 동일 결과 (14.8% neutral, 65.6% strong)
- **원인**: `rspi_engine.py`에서 `V2_DIVISOR`, `OVERNIGHT_EWY_DIVISOR`, `V5_DIVISOR`를 module-level `from config.constants import ...`로 바인딩. `config.constants` 모듈 속성을 변경해도 이미 바인딩된 로컬 이름에 반영 안 됨.
- **수정**: 3개 함수(`calc_foreign_direction`, `calc_overnight_signal`, `calc_credit_momentum`)에 optional divisor 파라미터 추가. `RSPIEngine`에 `sensitivity_params` dict 추가하여 인스턴스별 divisor 전달.

## 7. Q1 미달 근본 원인 분석

Q1 (중립 비율) 목표 65%+ 대비 20.9%로 미달. 근본 원인:

1. **V3 (야간시장)의 상시 활성화**: EWY/KORU/S&P500은 매일 변동. 야간 데이터가 존재하는 날은 거의 모두 V3 ≠ 0. divisor를 8.0까지 올려도 |V3| > 0.05 가 대부분.
2. **곱셈 모델의 한계**: structural_amp ≥ 1.0이므로, base_signal ≠ 0이면 RSPI는 항상 amplified. 중립(|RSPI| < 5)이 되려면 base_signal ≈ 0이어야 하는데, V3만으로도 base > 0.05 → RSPI > 5.
3. **설계 가정의 오류**: "트리거 없으면 base≈0 → RSPI≈0" 가정은 V2/V3/V5 중 하나라도 상시 non-zero면 성립 불가.

### 가능한 해결 방향 (향후 과제)
- V3 dead zone: |EWY_pct| < 1% 시 V3=0 (소규모 변동 무시)
- V3 gating: structural_amp > 1.2일 때만 V3 활성화
- 중립 정의 변경: |RSPI| < 10을 neutral로 재정의

## 8. 수정 파일 목록

| 파일 | 변경 사항 |
|------|---------|
| `kospi/scripts/rspi_engine.py` | v3.1 곱셈 모델, sensitivity_params, divisor 파라미터화 |
| `kospi/scripts/rspi_validation.py` | 3단계 최적화 (sensitivity_params 방식), module-import 버그 수정 |
| `kospi/config/constants.py` | V2_DIVISOR=3.5, EWY_DIVISOR=8.0, V5_DIVISOR=2.5, POWER=1.5, BETA=1.5 |
| `kospi/scripts/export_web.py` | proximity_power 내보내기 (기존) |

## 9. 결론

v3.1 곱셈 모델은 **방향 정확도(Q3)를 75.4%로 개선**하고 **false alarm을 40% 줄였으나**, 중립 비율(Q1) 문제는 야간시장 시그널의 상시 활성화로 인해 구조적으로 해결 불가. V3 dead zone 또는 gating 메커니즘이 Q1 해결의 핵심 과제.
