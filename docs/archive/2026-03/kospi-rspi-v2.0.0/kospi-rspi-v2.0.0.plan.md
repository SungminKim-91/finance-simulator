# KOSPI RSPI v2.0.0 Planning Document

> **Summary**: VLPI(단방향 매도 압력) → RSPI(양방향 가속/감쇠) 전면 재설계
>
> **Project**: KOSPI Crisis Detector
> **Version**: v2.0.0
> **Author**: Claude + sungmin
> **Date**: 2026-03-05
> **Status**: Draft

---

## 1. Overview

### 1.1 Purpose

기존 VLPI(Voluntary Liquidation Pressure Index, 0~100)를 RSPI(Retail Selling Pressure Index, -100~+100)로 전면 교체.
매도 압력만 측정하던 단방향 모델에서 **가속력(CF) - 감쇠력(DF)** 양방향 모델로 전환하여 반등 시그널까지 포착.

### 1.2 Background — 피벗 근거

2026.03.04~05 실데이터 검증 결과:

1. **VLPI(매도 압력만)로는 반등 설명 불가**
   - 3/4→3/5: CF=53.6(상승)이지만 실제 +11% 반등 — 야간선물 상한가, 외국인 순매수 전환, 신용유입 등 **감쇠력이 압도**
   - 매도 압력만 보는 모델 = 매번 파국으로 수렴하는 과대추정

2. **정책 쇼크(V3) 변수 무의미**
   - 한투/NH 신용 중단했는데 잔고 +4,531억 증가 (다른 증권사 대체)
   - 이진 변수(0/1)의 과민 반응, 실제 효과는 V2/V6에 이미 흡수

3. **캐스케이드 시뮬레이션 현실 불일치**
   - 주의구간 비중 3.7%에서는 캐스케이드 구조적 불가
   - 매도 시 동시에 저가매수 유입 → 순압력(Net Pressure)을 봐야 현실적

### 1.3 검증 결과 (NCP 모델 백테스트)

```
            │  가속력(CF) │  감쇠력(DF) │   RSPI   │  실제
────────────┼────────────┼────────────┼──────────┼────────
→3/4 예측   │    48.9    │    31.0    │  +17.9   │ -11.74% (하락 맞음)
→3/5 예측   │    53.6    │    88.6    │  -35.0   │ +11.09% (반등 맞음)
```

기존 VLPI로는 3/5를 "추가 하락"으로 오판했을 것.

### 1.4 Related Documents

- 참조: `rspi_v2_pivot_plan.md` (외부 피벗 플랜)
- 참조: `samsung_credit_cohort_data.md` (삼성 신용 코호트 실데이터)
- 아카이브: `docs/archive/2026-03/kospi-vlpi-v1.6.0/` (이전 VLPI 버전)

---

## 2. Scope

### 2.1 In Scope

- [x] VLPI → RSPI 명칭 전환 (constants, engine, export, frontend)
- [ ] 양방향 모델: CF(4변수) - DF(4변수) = RSPI (-100~+100)
- [ ] 정책 쇼크(V3) 완전 삭제
- [ ] 신규 감쇠력 4변수: D1(야간반등), D2(신용유입), D3(외국인소진), D4(안전버퍼)
- [ ] D1: 4개 야간시장 소스 (EWY, KORU, 야간선물, US market) + coherence bonus
- [ ] D2: 신용잔고 D+1 시차 처리 (T일 RSPI = T-1일 잔고 사용)
- [ ] Backend: rspi_engine.py 신규 생성, constants.py RSPI 상수, compute_models.py 연결
- [ ] Frontend: RSPIGauge(수평바, -100~+100), DualBreakdown(CF/DF 대칭), ImpactTable 변경
- [ ] Section 3: RSPI 시뮬레이터 (8개 슬라이더, 프리셋 3종+커스텀)
- [ ] 삼성 코호트 데이터 기반 검증 (3/4, 3/5 방향 일치)

### 2.2 Out of Scope

- Phase 5 배포 (GitHub Actions cron + Vercel)
- KOSPI200 야간선물 데이터 자동 수집 (초기 None 처리, 수동 입력)
- 히스토리 RSPI 일별 타임시리즈 (초기 latest only)
- 기존 Section 1(코호트 바), Section 1.5(종목별 신용잔고) 변경

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | RSPI = CF - DF 양방향 계산 엔진 (rspi_engine.py) | High | Pending |
| FR-02 | CF 4변수: V1(주의구간), V2(연속하락), V3(개인수급), V4(신용가속) | High | Pending |
| FR-03 | DF 4변수: D1(야간반등), D2(신용유입), D3(외국인소진), D4(안전버퍼) | High | Pending |
| FR-04 | D1: EWY+KORU+야간선물+US market 4소스, coherence bonus | High | Pending |
| FR-05 | D2: 신용잔고 D+1 시차 처리 (credit_data date = 잔고 기준일) | High | Pending |
| FR-06 | RSPI 5단계 판정: 반등압력/균형/약한하락/하락우세/캐스케이드 | High | Pending |
| FR-07 | RSPIGauge: 수평 바 게이지, -100~+100, 5색상 | High | Pending |
| FR-08 | DualBreakdown: CF(빨간) / DF(초록) 대칭 2컬럼 레이아웃 | High | Pending |
| FR-09 | ImpactTable: RSPI 음수 시 "반등 예상" 표시 | Medium | Pending |
| FR-10 | Section 3 RSPI 시뮬레이터: 8슬라이더 + 프리셋 3종 + 커스텀 | Medium | Pending |
| FR-11 | 삼성 코호트 기반 검증 (RSPI +17.9/3/4, -35.0/3/5) | High | Pending |
| FR-12 | fetch_daily.py: KORU ticker 수집 추가 | Medium | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement Method |
|----------|----------|-------------------|
| Performance | kospi_data.js < 1MB | 빌드 후 파일 크기 확인 |
| UX | 8슬라이더 복잡도 → 프리셋으로 진입 | 사용 흐름 검증 |
| Accuracy | 3/4, 3/5 방향 일치 | rspi_engine 단위 테스트 |

---

## 4. Variable Structure

### 4.1 CF — Cascade Force (가속력, 4변수)

| Key | Label | Weight | Description | Range | Source |
|-----|-------|--------|-------------|-------|--------|
| V1 | 주의구간 비중 | 0.30 | 담보비율 140~170% 코호트 비중 | 0~1 | 코호트 데이터 |
| V2 | 연속 하락 | 0.25 | 연속 하락일수 + 누적 하락률 | 0~1 | KOSPI 일간 |
| V3 | 개인 수급 | 0.25 | 전일 개인 순매수 패턴 | 0~1 | KRX 투자자 |
| V4 | 신용 가속 | 0.20 | 신용잔고 감소 시 가속 모멘텀 | 0~0.7 | KOFIA 잔고 |

### 4.2 DF — Damping Force (감쇠력, 4변수)

| Key | Label | Weight | Description | Range | Source |
|-----|-------|--------|-------------|-------|--------|
| D1 | 야간 반등 | 0.30 | EWY/KORU/야간선물/US market 반등 + coherence | 0~1 | yfinance |
| D2 | 신용 유입 | 0.20 | 하락일 신용잔고 증가 = 저가매수 (D+1 시차) | 0~1 | KOFIA 잔고 |
| D3 | 외국인 소진 | 0.25 | 외국인 매도 규모 감소/전환 | 0~1 | KRX 외국인 |
| D4 | 안전 버퍼 | 0.25 | 안전구간 코호트 비중 (방화벽) | 0.05~1 | 코호트 데이터 |

### 4.3 RSPI 계산

```
CF_raw = cf1×V1 + cf2×V2 + cf3×V3 + cf4×V4
DF_raw = df1×D1 + df2×D2 + df3×D3 + df4×D4

CF_normalized = CF_raw × 100  (0~100)
DF_normalized = DF_raw × 100  (0~100)

RSPI = CF_normalized - DF_normalized  (-100 ~ +100)
```

### 4.4 RSPI 5단계 판정

| Range | Label | Color | 해석 |
|-------|-------|-------|------|
| -100 ~ -20 | 반등 압력 | #4caf50 (Green) | 감쇠력 압도, 반등 예상 |
| -20 ~ 0 | 균형 | #8bc34a (LGreen) | 약한 반등~균형 |
| 0 ~ +20 | 약한 하락 | #ffc107 (Amber) | 약한 매도 압력 |
| +20 ~ +40 | 하락 우세 | #ff9800 (Orange) | 추가 하락 압력 우세 |
| +40 ~ +100 | 캐스케이드 | #f44336 (Red) | 캐스케이드 위험 |

### 4.5 D1 야간시장 4소스 상세

| Source | Ticker | Weight | Divisor | Notes |
|--------|--------|--------|---------|-------|
| EWY | EWY | 0.30 | 5.0 | iShares MSCI Korea ETF, 가장 유동성 높음 |
| KORU | KORU | 0.25 | 15.0 | 3x Korea Bull, 개인 센티먼트 직접 반영 |
| 야간선물 | (수동) | 0.25 | 8.0 | KOSPI200 야간선물, 초기 None → fallback |
| US Market | ^GSPC | 0.20 | 3.0 | S&P500, 글로벌 센티먼트 |

- **Coherence bonus**: 4개 다 반등 → 1.3x, 방향 혼재 → 0.7x, 4개 다 하락 → 감쇠 0
- **Graceful degradation**: 소스 미확보 시 확보된 소스에 가중치 재배분

### 4.6 변수 매핑 (기존 VLPI → 신규 RSPI)

```
기존 V1 (주의구간 비중)     → V1 (동일, w 0.25→0.30)
기존 V2 (신용잔고 모멘텀)   → V4 (가속 부분) + D2 (감쇠 부분) 분리
기존 V3 (정책 쇼크)        → 삭제
기존 V4 (야간 갭)          → D1 (감쇠력으로 이동, 4소스 확장)
기존 V5 (연속 하락)        → V2 (번호 변경)
기존 V6 (개인 수급)        → V3 (번호 변경)
(신규)                    → D3 (외국인 매도 소진도)
(신규)                    → D4 (안전 코호트 버퍼)
```

---

## 5. Implementation Plan (14단계)

### Phase A: Backend 피벗 (Step 1~5)

| Step | Task | Files | Description |
|------|------|-------|-------------|
| 1 | constants.py 업데이트 | `kospi/config/constants.py` | VLPI_* → RSPI_* 상수, POLICY_SHOCK 삭제, CF/DF weights, OVERNIGHT params, RSPI_LEVELS |
| 2 | rspi_engine.py 생성 | `kospi/scripts/rspi_engine.py` | vlpi_engine.py 복사→리네임, 정책쇼크 삭제, 신규 4함수(D1~D4), calc_rspi(), RSPIEngine 클래스 |
| 3 | rspi_engine 검증 | (테스트) | samsung_cohorts 데이터로 3/4 RSPI=+17.9, 3/5 RSPI=-35.0 방향 일치 확인 |
| 4 | compute_models.py 변경 | `kospi/scripts/compute_models.py` | VLPIEngine → RSPIEngine 교체, model_output["rspi"] |
| 5 | export_web.py 변경 | `kospi/scripts/export_web.py` | VLPI_DATA → RSPI_DATA, VLPI_CONFIG → RSPI_CONFIG, cf/df 분리 구조 |

### Phase B: Frontend 피벗 (Step 6~12)

| Step | Task | Files | Description |
|------|------|-------|-------------|
| 6 | colors.js 업데이트 | `web/src/simulators/kospi/colors.js` | vlpiV1~V6 → rspiV1~V4 + rspiD1~D4, 5단계 레벨 색상 |
| 7 | terms.jsx 업데이트 | `web/src/simulators/kospi/shared/terms.jsx` | VLPI 용어 삭제 → RSPI/CF/DF/D1~D4 용어 추가 |
| 8 | CohortAnalysis.jsx import 변경 | `web/src/simulators/kospi/CohortAnalysis.jsx` | VLPI_DATA → RSPI_DATA, VLPI_CONFIG → RSPI_CONFIG |
| 9 | RSPIGauge 구현 | `web/src/simulators/kospi/CohortAnalysis.jsx` | 수평바 게이지 -100~+100, 5색상, 중앙(0) 균형점, 마커 |
| 10 | DualBreakdown 구현 | `web/src/simulators/kospi/CohortAnalysis.jsx` | CF 4개(빨간) + DF 4개(초록) 대칭 2컬럼 레이아웃 |
| 11 | ImpactTable 변경 | `web/src/simulators/kospi/CohortAnalysis.jsx` | RSPI 음수 → "반등 예상", 시나리오 매트릭스 RSPI 기반 |
| 12 | Section 3 RSPI 시뮬레이터 | `web/src/simulators/kospi/CohortAnalysis.jsx` | 8슬라이더(CF4+DF4), 프리셋 3종+커스텀, 실시간 게이지, Impact 카드 |

### Phase C: 검증 (Step 13~14)

| Step | Task | Description |
|------|------|-------------|
| 13 | 전체 파이프라인 검증 | compute_models → export_web → kospi_data.js → CohortAnalysis.jsx 정합성 |
| 14 | npm run build + 배포 | 빌드 에러 없음, 모바일 반응형 확인 |

---

## 6. Backend Architecture

### 6.1 신규/변경 상수 (constants.py)

```python
# 삭제: VLPI_DEFAULT_WEIGHTS, POLICY_SHOCK_MAP, VLPI_POLICY_MULTIPLIER
# 신규:
RSPI_CF_WEIGHTS = {"cf1": 0.30, "cf2": 0.25, "cf3": 0.25, "cf4": 0.20}
RSPI_DF_WEIGHTS = {"df1": 0.30, "df2": 0.20, "df3": 0.25, "df4": 0.25}
OVERNIGHT_WEIGHTS = {"ewy": 0.30, "koru": 0.25, "futures": 0.25, "us_market": 0.20}
OVERNIGHT_EWY_DIVISOR = 5.0
OVERNIGHT_KORU_DIVISOR = 15.0  # 3x 레버리지 → EWY×3
OVERNIGHT_FUTURES_DIVISOR = 8.0
OVERNIGHT_US_DIVISOR = 3.0
RSPI_SENSITIVITY = 0.15
RSPI_SIGMOID_K = 0.08
RSPI_SIGMOID_MID = 50
RSPI_LIQUIDITY_FACTOR = 0.5
RSPI_LEVELS = {"critical": 40, "high": 20, "medium": 0, "low": -20}
```

### 6.2 rspi_engine.py 구조

```
재사용 (vlpi_engine.py에서):
  calc_collateral_ratio(), classify_status_6(),
  calc_caution_zone_pct() → V1
  calc_cumulative_decline() → V2 (기존 V5)
  calc_individual_flow_direction() → V3 (기존 V6)

수정:
  calc_credit_momentum() → calc_credit_accel_momentum() (V4, 가속부분만)
  calc_overnight_gap() → calc_overnight_recovery() (D1, 4소스+coherence)

삭제:
  calc_policy_shock()

신규:
  calc_overnight_recovery() — D1
  calc_credit_inflow_damping() — D2 (D+1 시차 처리)
  calc_foreign_exhaustion() — D3
  calc_safe_buffer() — D4
  calc_rspi() — 종합
  RSPIEngine 클래스
```

### 6.3 RSPI_DATA export 구조

```json
{
  "latest": {
    "date": "2026-03-05",
    "rspi": -35.0,
    "cascade_force": 53.6,
    "damping_force": 88.6,
    "cascade_risk": "none",
    "cf_components": {"caution_zone": 2.1, "cumulative_decline": 19.0, "individual_flow": 20.0, "credit_accel": 12.5},
    "df_components": {"overnight_recovery": 28.5, "credit_inflow": 12.6, "foreign_exhaustion": 22.5, "safe_buffer": 25.0},
    "raw_variables": {"v1": 0.07, "v2": 0.76, "v3": 1.0, "v4": 0.30, "d1": 0.95, "d2": 0.63, "d3": 0.90, "d4": 1.0},
    "impact": {...}
  },
  "scenario_matrix": [
    {"label": "낙관적", "ewy_pct": 2.5, "rspi": -42},
    {"label": "기본",   "ewy_pct": -1.0, "rspi": 5},
    {"label": "비관적", "ewy_pct": -4.0, "rspi": 38}
  ]
}
```

---

## 7. Frontend Architecture

### 7.1 RSPIGauge (수평 바, -100~+100)

```
[-100 ────── -20 ──── 0 ──── +20 ────── +100]
 반등 압력    균형    약한하락   하락우세   캐스케이드
 (Green)   (LGreen) (Amber)  (Orange)   (Red)
                       ▲ 마커 위치
```

마커 위치: `(rspi + 100) / 200 * 100` (%)

### 7.2 DualBreakdown (CF/DF 대칭)

```
가속력 (CF: 53.6)          │  감쇠력 (DF: 88.6)
─────────────────          │  ─────────────────
V1 주의구간  ██░░ 2.1     │  D1 야간반등  ████████ 28.5
V2 연속하락  █████ 19.0   │  D2 신용유입  ████░░░ 12.6
V3 개인수급  █████ 20.0   │  D3 외국인    ██████░ 22.5
V4 신용가속  ███░░ 12.5   │  D4 안전버퍼  ███████ 25.0
```

### 7.3 Section 3 RSPI 시뮬레이터 레이아웃

```
┌─────────────────────────────────────────────────────┐
│ Section 3: RSPI 시뮬레이터                            │
│                                                      │
│ [프리셋: 낙관 | 기본 | 비관 | 커스텀]                  │
│                                                      │
│ ┌──────────────────┬────────────────────────────┐    │
│ │ 가속력 (CF)       │        RSPI 게이지         │    │
│ │ V1 주의구간 ──○── │ [-100 ──── 0 ──── +100]   │    │
│ │ V2 연속하락 ──○── │         ▲ -35             │    │
│ │ V3 개인수급 ──○── │       "반등 압력"          │    │
│ │ V4 신용가속 ──○── │                            │    │
│ │                  ├────────────────────────────┤    │
│ │ 감쇠력 (DF)       │   CF: 53.6 │ DF: 88.6    │    │
│ │ D1 야간반등 ──○── │                            │    │
│ │ D2 신용유입 ──○── │ ┌────────┐ ┌────────────┐│    │
│ │ D3 외국인   ──○── │ │매도추정 │ │가격영향     ││    │
│ │ D4 안전버퍼 ──○── │ │ —      │ │반등 예상    ││    │
│ └──────────────────┴────────────────────────────┘    │
│                                                      │
│ 시나리오 비교:                                        │
│ ┌──────────┬───────┬───────┬──────────┬────────────┐ │
│ │ 시나리오  │ RSPI  │ CF    │ DF       │ 가격영향   │ │
│ │ 낙관적   │  -42  │ 53.6  │ 95.6     │ 반등 예상  │ │
│ │ 기본     │   +5  │ 53.6  │ 48.6     │ -1~2%     │ │
│ │ 비관적   │  +38  │ 53.6  │ 15.6     │ -8~12%    │ │
│ │ ★커스텀  │  -35  │ 53.6  │ 88.6     │ 반등 예상  │ │
│ └──────────┴───────┴───────┴──────────┴────────────┘ │
└─────────────────────────────────────────────────────┘
```

---

## 8. Data Sources

### 8.1 신규 데이터 소스

| Source | Ticker/API | 용도 | 수집 방법 |
|--------|-----------|------|----------|
| KORU | yfinance "KORU" | D1 야간반등 | fetch_daily.py 추가 |
| S&P500 | yfinance "^GSPC" | D1 야간반등 | fetch_daily.py 추가 |
| 야간선물 | (수동/향후 자동) | D1 야간반등 | 초기 None, graceful degradation |

### 8.2 D+1 신용잔고 시차 처리

```
T일 RSPI 계산 시:
- credit_data[latest]의 date = T-1일 (잔고 기준일, T일 공시)
- price_data[latest] = T-1일 종가
- "어제 주가 -11.74%인데, 어제 기준 신용잔고 +2.08% = 어제 저가매수"
- T일 잔고는 T+1에야 확보 → 구조적 한계, D2는 "어제의 감쇠력"
```

---

## 9. Backward Compatibility

### 9.1 vlpi_engine.py

- 삭제하지 않음 (deprecated 마킹)
- rspi_engine.py는 독립 파일 (vlpi import 없음)
- compute_models.py에서 vlpi_engine import 제거

### 9.2 Frontend VLPI 잔재

- VLPI_DATA, VLPI_CONFIG: export_web.py에서 제거 (RSPI 대체)
- kospi_data.js에서 VLPI_* export 제거
- VLPIGauge, ComponentBreakdown: 삭제 (RSPIGauge, DualBreakdown 대체)
- Section 3 기존 시뮬레이터 코드(commented): RSPI 시뮬레이터로 완전 교체

---

## 10. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| 야간선물 데이터 확보 어려움 | D1 정확도 저하 | High | EWY+KORU+US 3개로 fallback, futures=None 시 가중치 재배분 |
| KORU 유동성 낮음 | D1 노이즈 | Medium | 종가 기준만 사용, EWY 방향 불일치 시 가중치 하향 |
| 신용잔고 D+1 공시 시차 | D2+V4 지연 | High | 잔고 기준일=date, 당일 신용 변화 반영 구조적 불가 인정 |
| RSPI 음수 영역 해석 혼란 | UX 문제 | Medium | "음수=반등 압력" 가이드 박스 상시 표시 |
| 8개 슬라이더 UI 복잡도 | 사용성 저하 | Medium | 프리셋으로 진입 → 커스텀은 고급 모드 |
| 기존 VLPI 히스토리 단절 | 비교 불가 | Low | RSPI 히스토리 별도 시작, VLPI는 아카이브 |
| Backend+Frontend 동시 변경 | 통합 리스크 | Medium | Phase A(backend) 완료 후 Phase B 시작 |

---

## 11. Success Criteria

### 11.1 Definition of Done

- [ ] rspi_engine.py: 3/4 RSPI ≈ +17.9, 3/5 RSPI ≈ -35.0 (방향 일치)
- [ ] compute_models.py: model_output["rspi"] 정상 출력
- [ ] export_web.py: RSPI_DATA, RSPI_CONFIG 정상 export
- [ ] RSPIGauge: -100~+100 수평바 정상 렌더링
- [ ] DualBreakdown: CF/DF 대칭 표시
- [ ] Section 3 시뮬레이터: 8슬라이더 + 프리셋 정상 동작
- [ ] npm run build 에러 없음
- [ ] VLPI 잔재 완전 제거 (import, export, 컴포넌트)

### 11.2 Quality Criteria

- [ ] 빌드 성공
- [ ] kospi_data.js < 1MB
- [ ] 모바일 반응형 레이아웃

---

## 12. Next Steps

1. [ ] Write design document (`kospi-rspi-v2.0.0.design.md`)
2. [ ] Phase A: Backend 피벗 (Step 1~5)
3. [ ] Phase B: Frontend 피벗 (Step 6~12)
4. [ ] Phase C: 검증 (Step 13~14)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-03-05 | Initial draft — VLPI→RSPI 전면 재설계 피벗 플랜 | Claude + sungmin |
