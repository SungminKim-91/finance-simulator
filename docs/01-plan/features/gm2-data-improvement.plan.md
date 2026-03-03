# Plan: GM2 Data & 2025 Mismatch Improvement

> Status: **Backlog** | Priority: Medium | Created: 2026-03-03

## Background

v2.1 Dual-Band 모델(lag=6, tactical+combine)이 전체 추세에서 가장 잘 맞지만,
**2025년 구간에서 방향성 불일치**가 발생. 진단 결과 3가지 근본 원인 확인.

## Problem Analysis

### 1. GM2 데이터 고착 (Critical)

```
2024-03 ~ 2025-01: GM2_resid = -2.963 (11개월 연속 동일값)
2025-02:           GM2_resid = +0.354 (갑자기 +3.3σ 점프)
```

- EU/JP/CN M2 데이터가 11개월간 업데이트 안 됨 (FRED M3 시리즈 지연)
- Option H clip(±2.0)으로 일부 완화되었으나, 고착 기간 structural이 실제 유동성 미반영
- 정상화 시점에 인위적 절벽 발생 → structural 급락

### 2. HY 단기 충격 (2025-03~04)

```
2025-02: HY = -0.138 → 2025-03: +0.958 → 2025-04: +1.483 (관세 불확실성)
```

- PCA loading=0.587 (NL 다음 2위) → structural에 과도하게 반영
- 단기 정책 이벤트가 구조적 유동성 지표에 잡음 유입

### 3. 2025 H2 BTC 독자 요인

- Structural 회복(+0.03→+0.30) 구간에서 BTC는 $115K→$88K 하락
- ETF 자금흐름, 규제 변화 등 모델 외 요인 지배

## Lag=6 Direction Matching (2025)

| Chart Date | Source Date | Structural | BTC | Match |
|:---:|:---:|:---:|:---:|:---:|
| 2025-01~07 | 2024-07~2025-01 | +1.3~+1.5 | $64K→$115K | OK |
| 2025-08 | 2025-02 | +0.385 | $108K | OK |
| 2025-09 | 2025-03 | -0.233 | $114K | MISS |
| 2025-10 | 2025-04 | -0.543 | $109K | OK |
| 2025-11 | 2025-05 | +0.030 | $90K | MISS |
| 2025-12 | 2025-06 | +0.298 | $88K | MISS |

## Potential Improvements

### Option A: GM2 Interpolation
- 고착 구간에서 선형 보간 또는 carry-forward 대신 monthly decay 적용
- 장점: 절벽 현상 완화
- 단점: 실제 데이터 없는 구간을 추정하는 것이므로 과적합 위험

### Option B: Adaptive HY Weight
- HY가 2σ 이상 급등 시 PCA 대신 adaptive weight 적용 (HY 영향 축소)
- 장점: 단기 충격 필터링
- 단점: 모델 복잡도 증가, BTC 보고 조정하면 과적합

### Option C: Data Pipeline 개선
- FRED M3 시리즈 지연 감지 → 대체 소스 (ECB/BOJ 직접 API) fallback
- GM2 데이터 freshness 지표 추가 (dashboard에 경고 표시)
- 장점: 근본 원인 해결
- 단점: 추가 API 통합 필요

### Option D: Regime Detection
- 데이터 품질 저하 구간 자동 감지 → confidence band 확대 표시
- structural index에 "data quality" 가중치 적용
- 장점: 사용자에게 신뢰도 정보 제공

## Recommendation

**Phase 1**: Option C (데이터 파이프라인) — 근본 원인 해결이 최우선
**Phase 2**: Option D (Regime Detection) — 대시보드에 데이터 품질 표시
**Phase 3**: Option A/B는 과적합 위험 평가 후 결정

## Notes

- 현재 모델 목표는 "큰 흐름 5-9개월 선행 예측"이므로 단기 불일치는 허용 범위
- 2025년은 GM2 데이터 품질 이슈 + 관세 충격이 겹친 특수 구간
- GM2 데이터가 정상화되면 2024 H2 ~ 2025 H1 structural 재계산 시 개선 기대
