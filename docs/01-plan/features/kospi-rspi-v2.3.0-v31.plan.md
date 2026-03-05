# RSPI v2.3.0 Phase 2 Plan — v3.1 곱셈 모델 + 3단계 순차 최적화

> **Feature**: kospi-rspi-v2.3.0-v31
> **Version**: v2.3.0 → v2.3.0 (Phase 2)
> **Created**: 2026-03-07
> **Status**: Plan

---

## 1. 배경

v2.3.0 1차 검증에서 발견된 구조적 문제:
- Q1 FAIL: 중립 25.7% (목표 70%+) — 덧셈 모델에서 V1이 단독 점수 생성
- V4 무효: 개인 수급 패턴 예측력 없음 (corr=0.03, p=0.645)
- V1 상관계수 낮음: 0.12 (V3의 0.42 대비)

## 2. 목표

### 2.1 덧셈→곱셈 모델 전환
- `RSPI = -1 × base_signal × structural_amp × volume_amp × 100`
- 시그널(방향): V2, V3, V5 → base_signal ≈ -1~+1
- 증폭기(강도): V1 level + V1 velocity + 개인누적 z-score → structural_amp ≈ 1~3.5
- 트리거 없으면 base≈0 → RSPI≈0 (Q1 해결)

### 2.2 V4 삭제 → 개인누적 z-score
- 패턴 기반 V4 제거
- 60일 누적 개인매수의 rolling z-score → 증폭기에 편입

### 2.3 3단계 순차 최적화
- Round 1: 감도 (V2/V3/V5 divisor) — 64 조합
- Round 2: 증폭기 (power/alpha/beta/gamma/sum_window) — 1600 조합
- Round 3: 시그널 가중치 (ws2/ws3/ws5, 합=1) — ~15 조합

## 3. 범위

### In Scope
- rspi_engine.py: v3.1 곱셈 모델, V4→개인누적, V1 velocity, structural_amp
- rspi_validation.py: 3단계 순차 최적화 + 최종 검증
- compute_models.py: 개인 순매수 데이터 전달
- constants.py: v3.1 파라미터 상수

### Out of Scope
- 프론트엔드 변경 (기존 RSPI 컴포넌트 호환)
- 위기지표(Crisis Gauge) 구현
