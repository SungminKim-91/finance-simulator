# KOSPI Crisis Detector v1.2.0 — Cohort Backtest Simulator + Margin Reform Report

> **Summary**: 코호트 백테스트 시뮬레이터, 담보비율 분포 개편, 신뢰도 대시보드 추가. 신용거래 실태 조사 반영.
>
> **Feature**: kospi-crisis-v1.2.0
> **Version**: v1.2.0
> **Author**: Sungmin Kim
> **Created**: 2026-03-04
> **Status**: Completed

---

## 1. Overview

### 1.1 Feature Summary

v1.1.1 코호트 bugfix 이후, 시뮬레이터의 실용성 강화를 위한 3대 개선:

1. **담보비율 분포 개편**: 단일 threshold (130%/140%) → 증권사/종목군별 실제 분포 반영
2. **백테스트 모드**: 과거 임의의 거래일 선택 → 충격% 입력 → 시뮬 vs 실제 D+1~D+5 비교
3. **신뢰도 대시보드**: 급변동일 40건에 대해 일괄 시뮬레이션 → 방향 정확도, RMSE, 산점도
4. **코호트 히스토리**: 281일 × 201코호트 일별 스냅샷 생성 (백테스트용)
5. **신용거래 실태 조사**: 한국 신용거래의 95%+ 가 개별주식임을 확인, 모델 한계 명시

### 1.2 PDCA Cycle

| Phase | Status | Outcome |
|-------|--------|---------|
| **Plan** | Completed | 10-step plan (담보비율 분포 + 코호트 히스토리 + 백테스트) |
| **Do** | Completed | compute_models + export_web + CohortAnalysis.jsx + terms.jsx |
| **Check** | Completed | 빌드 통과, 사용자 피드백 5라운드 반영 |
| **Report** | Completed | 본 보고서 |

---

## 2. Credit Trading Research Findings

### 2.1 신용거래 대상

- **~95% 이상 개별주식** (삼성전자, SK하이닉스 등 대형주 집중)
- ETF 신용거래: 사실상 없음 (레버리지/인버스 ETF는 규정상 제외)
- 전체 신용잔고 32.8조원 (2026-03, 사상최대): KOSPI 66% / KOSDAQ 34%
- 상위 20종목에 ~10.4조원 집중 (삼전 ~2조, 하닉 ~1.5조)

### 2.2 담보비율 실태

| 종목군 | 증거금률 | 유지비율 | 강제청산 시점 |
|--------|---------|---------|-------------|
| A군 (대형우량) | 45% | 140% | D+2 미납 → 하한가 동시호가 |
| B군 (중형) | 45% | 145% | 동일 |
| C군 (소형) | 50% | 150% | 동일 |
| D군 (고위험) | 55%+ | 155~160% | 동일 |

### 2.3 모델 타당성 평가

**KOSPI 지수 수준 모델링이 유효한 이유:**
- 신용잔고가 지수 편입 대형주에 집중 (삼전+하닉 = KOSPI 시총 ~35%)
- 피드백 루프가 지수 수준에서 작동 (주가↓ → 담보부족 → 강제매도 → 추가하락)
- 반대매매는 하한가 동시호가 → 시장 개시에 기계적 하락 압력

**한계 (UI에 명시):**
- KOSDAQ 34%는 KOSPI에 직접 영향 없음 (심리적 전염만)
- 종목별 신용비율 차이 미반영 (삼전 0.3% vs 소형주 5~10%)
- 외국인 매도 연쇄 미반영

---

## 3. Changes

### 3.1 Backend (Python)

| File | Change | Lines |
|------|--------|-------|
| `compute_models.py` | MAINTENANCE_DISTRIBUTION + FORCED_LIQ_DISTRIBUTION + MARGIN_DISTRIBUTION 분포 상수 | +15 |
| `compute_models.py` | Cohort.status() → 분포 기반 가중평균 상태 판정 | ~30줄 수정 |
| `compute_models.py` | get_trigger_map() → 이중 분포 루프 적용 | ~20줄 수정 |
| `compute_models.py` | ForcedLiqSimulator.run() → 삼중 분포 루프 적용 | ~25줄 수정 |
| `compute_models.py` | +cohort_history 캡처 (registry + daily snapshots) | +25 |
| `compute_models.py` | +_identify_backtest_dates() 급변동일 식별 | +40 |
| `export_web.py` | +COHORT_HISTORY, BACKTEST_DATES 신규 export (13→15) | +30 |
| `export_web.py` | params에 distribution 상수 포함 | +10 |

### 3.2 Frontend (React)

| File | Change | Lines |
|------|--------|-------|
| `CohortAnalysis.jsx` | +reconstructCohorts() 유틸리티 (히스토리→코호트 복원) | +48 |
| `CohortAnalysis.jsx` | +computeImpliedAbsorption() (역산 흡수율) | +12 |
| `CohortAnalysis.jsx` | +runSimulation() 분포 기반 삼중 루프 | ~80줄 수정 |
| `CohortAnalysis.jsx` | +백테스트 모드 UI (기준일 선택 + 비교뷰) | +320 |
| `CohortAnalysis.jsx` | +BacktestComparison 컴포넌트 (듀얼 라인 차트 + 비교 테이블) | +130 |
| `CohortAnalysis.jsx` | +ReliabilityDashboard (산점도 + 방향정확도 + RMSE) | +250 |
| `CohortAnalysis.jsx` | 코호트 접기/더보기 토글 (MAX_VISIBLE=20) | +20 |
| `CohortAnalysis.jsx` | 백테스트 시 위험 코호트 요약 표시 | +30 |
| `CohortAnalysis.jsx` | 모델 한계 명시 (가이드 박스 텍스트) | 텍스트 수정 |
| `terms.jsx` | +8개 신규 용어 (backtest, implied_absorption 등) | +40 |
| `terms.jsx` | 상태 용어 분포 반영 수정 (status_danger 등) | ~10줄 수정 |

### 3.3 Data

| Export | 규모 | 설명 |
|--------|------|------|
| COHORT_HISTORY | ~745 KB | registry (201 cohorts) + snapshots (281 days) |
| BACKTEST_DATES | ~20 KB | 40건 급변동일 + D+1~D+5 실제 데이터 |
| kospi_data.js 총 | ~899 KB | 기존 324KB + 신규 575KB |

---

## 4. Key Design Decisions

### 4.1 백테스트 모드: "기준일 + 충격 분리" 설계

초기 설계는 BACKTEST_DATES(급변동일)에서만 선택 가능했으나, 사용자 피드백으로 근본 재설계:

- **문제**: "급변동일=기준일+충격" 으로 혼동 → 실제 use case와 맞지 않음
- **예시**: 2/26(금) 선택 → -7.25% 입력(3/3 월요일 실제 하락) → D+1~D+5 비교
- **해결**: 모든 거래일(281일) 중 자유 선택 + 충격% 독립 입력
- Forward 데이터: MARKET_DATA에서 동적 조회 (pre-computed → runtime)

### 4.2 담보비율 분포 모델

단일 threshold 대신 3개 분포의 가중 곱:
```
MARGIN_DISTRIBUTION = {0.40: 0.30, 0.45: 0.30, 0.50: 0.25, 0.60: 0.15}
MAINTENANCE_DISTRIBUTION = {1.40: 0.45, 1.45: 0.25, 1.50: 0.20, 1.60: 0.10}
FORCED_LIQ_DISTRIBUTION = {1.20: 0.45, 1.25: 0.25, 1.30: 0.20, 1.40: 0.10}
```

금투협 종목군 분류 + 주요 증권사(키움/미래에셋/삼성/NH) 약관 기반.

---

## 5. Verification

| Test | Result |
|------|--------|
| compute_models 파이프라인 | PASS (201 cohorts, 281 days, 40 backtest events) |
| export_web 15 exports | PASS |
| vite build | PASS (2.10s, no errors) |
| 코호트 접기/더보기 토글 | PASS |
| 백테스트 기준일 전체 선택 | PASS |
| 위험 코호트 요약 표시 | PASS |
| 분포 텍스트 명시 | PASS |
| 모델 한계 가이드 | PASS |

---

## 6. Lessons Learned

### What Went Well
1. **신용거래 실태 조사**: 모델 가정이 현실과 대체로 부합함을 확인
2. **백테스트 재설계**: 사용자와 토의 후 근본적 use case 이해 → "기준일+충격 분리" 설계
3. **분포 기반 모델**: 현실 증권사 약관에 근거한 파라미터로 설득력 향상

### Areas for Improvement
1. **종목별 가중 모델 미구현**: 개별 종목 신용잔고 데이터가 없어 지수 수준 근사에 머무름
2. **KOSDAQ 미반영**: 신용잔고 34%를 차지하나 KOSPI 모델에서 제외
3. **kospi_data.js 899KB**: 용량 증가 → 코드 스플리팅 또는 lazy load 검토 필요

---

## 7. Next Steps

| Priority | Action | Phase |
|----------|--------|-------|
| 1 | 종목별 가중 모델 (상위 20종목 신용잔고 추적) | v1.3.0 |
| 2 | GitHub Actions cron 자동화 | Phase 5 |
| 3 | Vercel 배포 | Phase 5 |
| 4 | kospi_data.js 코드 스플리팅 | 성능 개선 |

---

**Report Generated**: 2026-03-04
