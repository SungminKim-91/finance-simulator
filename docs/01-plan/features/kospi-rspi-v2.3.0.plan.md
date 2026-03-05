# RSPI v2.3.0 Plan — 비선형 Proximity + 검증 프레임워크

> **Feature**: kospi-rspi-v2.3.0
> **Version**: v2.2.2 → v2.3.0
> **Created**: 2026-03-07
> **Status**: Plan

---

## 1. 배경

RSPI v2.2.x에서 V1 look-ahead bias를 수정했으나, 두 가지 구조적 문제 남음:

1. **V1 선형 proximity** — 담보비율 180%→179% 와 146%→145%를 동일 취급. 마진콜 근처에서 급가속하는 비선형(power) 필요.
2. **모델 검증 부재** — 262일 백데이터로 변수별 유효성, 시그널 강도, false alarm 분석 미실시.

## 2. 목표

### 2.1 V1 비선형 Proximity (power=2.5)
- `calc_cohort_proximity(price, cohorts, power=2.5)` — power 파라미터 추가
- `linear_proximity ^ power` 지수 변환
- power=2.5 효과: ratio 170% → proximity 0.18, ratio 145% → proximity 0.78

### 2.2 9단계 검증 프레임워크
- Step 1: 변수별 분포 진단 (V1~V5, VA)
- Step 2: RSPI 분포 진단 (레벨 분포, false alarm 후보)
- Step 3: 변수별 예측력 (상관계수, quintile spread, hit rate)
- Step 4: RSPI 시그널 강도 (4 버킷 방향 일치율)
- Step 5: 음전환 후 전개 추적
- Step 6: 거래량 증폭기 A/B 비교
- Step 7: False alarm 상세 분석
- Step 8: 가중치 민감도
- Step 9: V1 power 파라미터 최적화 (1.0, 1.5, 2.0, 2.5, 3.0)

### 2.3 핵심 검증 질문 (3대)
- Q1: RSPI 평상시 |RSPI|<5가 70%+인가?
- Q2: 급락 이벤트에서 RSPI -30 이하, 반등에서 +15 이상인가?
- Q3: |RSPI|>20인 날의 방향 일치율 65%+인가?

## 3. 범위

### In Scope
- rspi_engine.py: V1 power 파라미터 추가
- rspi_validation.py: 9단계 검증 스크립트 (신규)
- compute_models.py: power 파라미터 전달
- constants.py: V1_PROXIMITY_POWER 상수
- 검증 리포트 생성

### Out of Scope
- 프론트엔드 변경 (검증 결과에 따라 후속)
- 가중치 전면 재조정 (검증이 민감 변수만 미세 조정)
- 위기지표(Crisis Gauge) 구현

## 4. 참조 문서
- `rspi_v3_final.md` — RSPI v3.0 설계서 (V1 power, 검증 Phase 1~5)
- `rspi_validation_plan.md` — 9단계 검증 계획서 (실행 지시문, 판단 기준)
