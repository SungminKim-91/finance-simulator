# KOSPI RSPI v2.2.0 -- 5변수 + 거래량 증폭기 전면 재설계

> Feature: `kospi-rspi-v2.2.0`
> Created: 2026-03-06
> Status: Plan
> Reference: `rspi_v3_final.md`, `rspi_v2_pivot_plan.md`

## 1. 배경 및 동기

### 1.1 현재 문제 (v2.0.0 CF/DF 모델)

v2.0.0은 CF(가속력 4변수) - DF(감쇠력 4변수) 양방향 모델로 설계되었으나, **8개 변수 중 사실상 1개만 작동**:

| 변수 | 가중치 | 262일 활성화율 | 문제 |
|------|--------|-------------|------|
| **V1** (주의구간) | CF 30% | ~0% | 140~170% 이진 범위 너무 좁음 |
| **V2** (연속 하락) | CF 25% | 0일 | `break`문으로 1일 상승 시 즉시 중단 |
| **V3** (개인 수급) | CF 25% | 100% | 유일하게 정상 작동 |
| **V4** (신용 가속) | CF 20% | 낮음 | 0.3/0.7 이진값, 낮은 기여 |
| **D1** (야간 반등) | DF 30% | 69.5% | 데이터 부재 (30.5% 결측) |
| **D2** (신용 유입) | DF 20% | 낮음 | 신호 약함 |
| **D3** (외국인 소진) | DF 25% | ~0% | -10000억 절대값 임계 (현실 불가) |
| **D4** (안전 버퍼) | DF 25% | 100% | V1=0 -> 항상 1.0 고정 |

**결과**: RSPI 범위 -63.5 ~ +6.0. Critical(40+) 0일, High(20+) 0일. DF 최소값 항상 25+ (D4=1.0 고정) -> RSPI > 20 구조적 불가.

### 1.2 근본 원인 -- CF/DF 분리 구조의 한계

1. **변수 간 의존성 문제**: D4(안전 버퍼)가 V1(주의구간)의 역수 -> V1=0이면 D4=1.0 -> DF가 항상 25+
2. **단방향 변수의 비활성**: V1, V2, V4는 0~1 단방향 -> 대부분 0에 고정
3. **양방향 시그널 분리 오류**: 야간시장(D1), 외국인(D3)이 감쇠력에만 있어 하락 시그널 반영 불가
4. **이진값 과다**: V4(0.3/0.7), V2(break), V1(이진 범위) -> 연속적 변화 추적 불가

### 1.3 해결 방향 -- v3 설계 (rspi_v3_final.md)

CF/DF 분리를 폐기하고, **5개 양방향 변수 + 거래량 증폭기** 단일 수식으로 전환:

```
RSPI = -1 x (w1*V1 + w2*V2 + w3*V3 + w4*V4 + w5*V5) x VolumeAmp x 100

부호: 변수 내부 양수 = 매도 방향, 최종 부호 반전 -> 음수 = 매도 압력(빨간)
범위: -100 ~ +100
```

핵심 차이:
- 변수가 **양방향(-1~+1)** -> 평상시 ~0, 급변시 극단값으로 자동 이동
- 별도 트리거/활성화 없음: |RSPI| < 5이면 자연스럽게 중립
- 거래량 증폭기: 시그널의 확신도를 독립적으로 조절

## 2. 목표

### 2.1 핵심 목표

1. **CF/DF 8변수 -> 5변수+VA 단일 수식 전환**: rspi_engine.py 전면 재작성
2. **모든 변수 연속값 + 자동 활성화**: 이진값, break문, 절대 임계값 제거
3. **5단계 검증 프레임워크**: 변수 유효성 -> 시그널 강도 -> 음전환 추적 -> VA 검증 -> 민감도
4. **3/3~3/5 실제 데이터 방향 100% 일치**: 기존 v3_final.md 시뮬레이션 확인

### 2.2 성공 기준

| 지표 | 현재 (v2.0.0) | 목표 (v2.2.0) |
|------|------|------|
| 활성 변수 수 | 1/8 (V3만) | **5/5 + VA** |
| RSPI 범위 | -63.5 ~ +6.0 | **-80 ~ +60 이상** |
| 3/3 RSPI | ~0 (비활성) | **~-50** (강한 매도 압력) |
| 3/4->3/5 RSPI | ~0 | **~+19** (반등 압력) |
| noise 버킷 방향 일치율 | N/A | **~50%** (랜덤, 과적합 아님) |
| strong 버킷 방향 일치율 | N/A | **65%+** |
| 부호 규칙 | 양수=매도 | **음수=매도(빨간), 양수=반등(초록)** |

### 2.3 비목표 (Out of Scope)

- Bayesian 가중치 자동 학습 (v2.3.0)
- KRX 야간선물 자동 수집 (별도 feature)
- 위기지표 (Crisis Gauge) 구현 (별도 설계, RSPI와 역할 분담)
- Impact Function 재설계 (기존 sigmoid 유지, v3에서 분리 예정)

## 3. 변수 설계 (v3 기준)

### 3.1 변수 요약

```
ID | 이름              | 범위      | 가중치 | 성격
V1 | 코호트 proximity  | 0 ~ +1   |  0.25  | 단방향. 구조적 취약성
V2 | 외국인 수급 방향  | -1 ~ +1  |  0.20  | 양방향. z-score 기반
V3 | 야간시장 시그널   | -1 ~ +1  |  0.25  | 양방향. 4소스+coherence
V4 | 개인 수급 방향    | -1 ~ +1  |  0.20  | 양방향. 패턴 기반
V5 | 신용잔고 모멘텀   | -1 ~ +1  |  0.10  | 양방향. D+1 시차. 확인용
VA | 거래량 증폭기     | 0.3~2.0  | (배율) | 적응형 기준선. 확신도
```

### 3.2 v2.0.0 -> v2.2.0 변수 매핑

```
v2.0.0 (CF/DF)          ->  v2.2.0 (5변수)
───────────────────         ───────────────
V1 주의구간 (이진)      ->  V1 코호트 proximity (연속, 140~200% 거리함수)
V2 연속하락 (break)     ->  (삭제 -- 독립 변수로서 무의미)
V3 개인수급 (단방향)    ->  V4 개인수급 (양방향 패턴)
V4 신용가속 (이진)      ->  V5 신용잔고 모멘텀 (양방향 연속)
D1 야간반등 (감쇠만)    ->  V3 야간시장 시그널 (양방향)
D2 신용유입 (감쇠만)    ->  V5에 흡수 (신용 증가 = 음수값)
D3 외국인소진 (절대값)  ->  V2 외국인 수급 (z-score 상대값)
D4 안전버퍼 (V1 역수)   ->  (삭제 -- V1 자체가 연속이므로 불필요)
(없음)                  ->  VA 거래량 증폭기 (신규)
```

### 3.3 각 변수 상세

#### V1: 코호트 proximity (0~1, 단방향)

현재: 담보비율 140~170% 이진 판정 -> 거의 항상 0
변경: 연속 거리 함수, 140% 중심에서 200%까지 60%p 범위

```python
proximity = max(0, min(1.0, 1 - (ratio - 140) / 60))
# ratio 200% -> proximity 0.00
# ratio 170% -> proximity 0.50
# ratio 140% -> proximity 1.00 (cap)
V1 = weighted_avg(proximity, cohort.weight)
```

#### V2: 외국인 수급 방향 (-1~+1, 양방향)

현재: D3에서 -10000억 절대값 임계 -> 거의 항상 0
변경: z-score 기반 상대값, 시장 규모에 자동 적응

```python
z = (today_foreign - avg_20d) / std_20d
V2 = clamp(-1, 1, -z / 2.0)
# 극단 매도 (z=-3) -> V2 = +1.0
# 극단 매수 (z=+3) -> V2 = -1.0
```

#### V3: 야간시장 시그널 (-1~+1, 양방향)

현재: D1에서 반등(양수)만 감쇠로 인정
변경: 양방향 (갭다운=매도 시그널, 갭업=반등 시그널) + coherence

```python
signal = -(pct / divisor)  # 하락이면 양수(매도), 상승이면 음수(반등)
# 4소스 가중평균 + 방향일치 보너스(1.3x) 또는 혼재 감쇠(0.7x)
```

#### V4: 개인 수급 방향 (-1~+1, 양방향)

현재: V3에서 단방향 (0~1, 매도 방향만)
변경: 양방향 패턴 (-0.4=대량매수, +1.0=항복)

```python
# 대량매수->급감 = +1.0 (항복)
# 대량매수 유지 = -0.4 (매도 흡수)
# 순매도 전환 = +0.5
```

#### V5: 신용잔고 모멘텀 (-1~+1, 양방향)

현재: V4에서 0/0.3/0.7 이진값, 감소만 반영
변경: 연속 양방향 함수 (증가=유입=-1, 감소=투매=+1)

```python
V5 = clamp(-1, 1, -change_pct / 2.0)
# +2% 증가 -> V5 = -1.0 (강한 유입)
# -2% 감소 -> V5 = +1.0 (대규모 투매)
```

#### VA: 거래량 증폭기 (0.3~2.0, 배율)

현재: 없음
신규: 적응형 기준선 + log2 스케일링

```python
baseline = max(adv_20, avg_5d)  # 위기 시 자동으로 기준선 상승
ratio = volume_today / baseline
amp = 1 + 0.5 * log2(ratio)
# ratio 0.5 -> amp 0.50 (확신 낮음)
# ratio 1.0 -> amp 1.00 (중립)
# ratio 2.0 -> amp 1.50 (확신 높음)
```

### 3.4 부호 규칙

```
변수 내부 (V1~V5): 양수 = 매도 방향
  V1 높음 = 코호트 취약
  V2 양수 = 외국인 매도
  V3 양수 = 야간 갭다운
  V4 양수 = 개인 항복
  V5 양수 = 신용 유출

최종 출력 (부호 반전):
  RSPI 음수 = 매도 압력 (빨간)
  RSPI 양수 = 반등 압력 (초록)
  RSPI ~0  = 중립 (회색)

거래량 증폭기: amp > 1.0 = 확신 높음, amp < 1.0 = 확신 낮음
```

### 3.5 검증 시뮬레이션 (v3_final.md 기준)

```
날짜        | V1    | V2    | V3    | V4    | V5    | amp  | RSPI | 실제
3/3 트리거  | 0.083 | +1.00 | +0.99 | -0.40 | -0.25 | 1.37 | -50  | -7.3%
3/4 폭락    | 0.083 | +1.00 | +0.30 | -0.40 | -0.25 | 1.41 | -27  | -11.7%
3/4->5 예측 | 0.412 | -0.47 | -0.98 | +1.00 | -1.00 | 1.41 | +19  | +11.1%
3/5->6 예측 | 0.120 | +0.16 | +0.48 | -0.40 | -1.00 | 0.87 |  ~0  | ???

방향 일치: 3/3 O  3/4 O  3/5 O  = 100% (3건)
```

## 4. 검증 프레임워크 (5단계)

### Phase 1: 개별 변수 유효성 (262일 전체)

각 변수 vs 다음날 수익률: 상관계수, spread(상위/하위 20%), hit rate

판단 기준:
- |상관계수| > 0.10: 유효
- spread 부호 반대: 로직 수정 필요

### Phase 2: RSPI 시그널 강도 (|RSPI| 크기별 버킷)

| 버킷 | 기대 날수 | 기대 방향 일치율 |
|------|----------|-----------------|
| noise (|RSPI|<5) | ~200일 | ~50% (랜덤) |
| mild (5~15) | ~40일 | 55~60% |
| moderate (15~30) | ~15일 | 60~70% |
| strong (30+) | ~7일 | 70~85% |

### Phase 3: 음전환 후 전개 추적

음전환 이벤트(5일 중 4일+ 상승 후 첫 하락) -> 이후 10일 RSPI vs 실제 방향

### Phase 4: 거래량 증폭기 검증

amp 적용 전/후 Phase 2 비교 -> strong 버킷 개선 여부

### Phase 5: 가중치 민감도 (Phase 2 성공 시에만)

5개 가중치 각 +/-50% -> strong 버킷 일치율 변화. 민감 변수 1~2개만 3단계 조정.

## 5. 레벨 판정 + UI

```
RSPI       | 판정            | 색상
-100~-40   | 극단 매도 압력   | Deep Red
-40~-20    | 강한 매도 압력   | Red
-20~-5     | 약한 매도 압력   | Amber
-5~+5      | 중립             | Gray
+5~+20     | 약한 반등 압력   | L.Green
+20~+40    | 강한 반등 압력   | Green
+40~+100   | 극단 반등 (투매소진) | D.Green
```

v2.0.0 대비 변경: 5단계(양수=매도) -> 7단계(음수=매도, 양수=반등). 사용자 직관에 맞게 빨간=매도.

## 6. 변경 범위

### 6.1 Phase A -- Backend 엔진 전면 재작성

| 파일 | 변경 | 중요도 |
|------|------|--------|
| `kospi/scripts/rspi_engine.py` | **전면 재작성**: 5변수 + VA + calc_rspi | 핵심 |
| `kospi/config/constants.py` | CF/DF 가중치 -> 5변수 가중치 + VA 상수 | 핵심 |
| `kospi/scripts/rspi_backtest.py` | **신규** -- 5단계 검증 프레임워크 | 핵심 |

#### A-1. rspi_engine.py 전면 재작성

삭제:
- calc_caution_zone_pct() (이진 판정)
- calc_cumulative_decline() (break문)
- calc_individual_flow_direction() (단방향)
- calc_credit_accel_momentum() (이진값)
- calc_overnight_recovery() (감쇠만)
- calc_credit_inflow_damping() (감쇠만)
- calc_foreign_exhaustion() (절대값)
- calc_safe_buffer() (V1 역수)
- calc_rspi() (CF-DF 구조)

신규:
- calc_cohort_proximity(price, cohorts) -> V1 (0~1, 연속 거리함수)
- calc_foreign_direction(flows, idx, lookback=20) -> V2 (-1~+1, z-score)
- calc_overnight_signal(ewy, koru, futures, us) -> V3 (-1~+1, 4소스+coherence)
- calc_individual_direction(flows, idx) -> V4 (-1~+1, 패턴)
- calc_credit_momentum(credit, idx) -> V5 (-1~+1, 변화율)
- calc_volume_amplifier(vol, adv20, recent5d) -> VA (0.3~2.0)
- calc_rspi(v1,v2,v3,v4,v5,amp) -> RSPI (-100~+100)

유지:
- calc_collateral_ratio() (담보비율 계산)
- classify_status_6() (6단계 분류)
- estimate_selling_volume() (Impact Function)
- estimate_price_impact() (Kyle's Lambda)
- RSPIEngine 클래스 (인터페이스 변경)

#### A-2. constants.py 업데이트

삭제:
- RSPI_CF_WEIGHTS, RSPI_DF_WEIGHTS (CF/DF 구조)
- RSPI_LEVELS (5단계 양수=매도)
- VLPI_* deprecated 상수들

신규:
- RSPI_WEIGHTS = {v1: 0.25, v2: 0.20, v3: 0.25, v4: 0.20, v5: 0.10}
- RSPI_LEVELS (7단계 음수=매도)
- VA_FLOOR = 0.3, VA_CEILING = 2.0
- V2_LOOKBACK = 20, V2_DIVISOR = 2.0
- V4_THRESHOLD = 300 (억원)
- V5_DIVISOR = 2.0

유지:
- OVERNIGHT_WEIGHTS, OVERNIGHT_*_DIVISOR (V3용)
- RSPI_SENSITIVITY, RSPI_SIGMOID_* (Impact Function)

#### A-3. rspi_backtest.py 신규

- validate_variable(): Phase 1 개별 변수 유효성
- validate_signal_strength(): Phase 2 시그널 강도
- validate_post_decline_tracking(): Phase 3 음전환 추적
- validate_volume_amplifier(): Phase 4 VA 검증
- sensitivity_analysis(): Phase 5 가중치 민감도

### 6.2 Phase B -- 파이프라인 연동

| 파일 | 변경 | 중요도 |
|------|------|--------|
| `kospi/scripts/compute_models.py` | RSPI 히스토리 재계산 (262일) | 연동 |
| `kospi/scripts/export_web.py` | RSPI_DATA/RSPI_CONFIG 구조 변경 | 연동 |

#### B-1. compute_models.py

- RSPIEngine.calculate_for_date() 호출 변경
- trading_value 데이터 VA용으로 파이프라인 연결
- foreign flow 데이터 V2용으로 파이프라인 연결

#### B-2. export_web.py

- RSPI_DATA: history에 v1~v5 + amp + rspi 포함
- RSPI_CONFIG: 5변수 + VA 정보, 7단계 레벨
- CF/DF 구조 제거

### 6.3 Phase C -- Frontend 적용

| 파일 | 변경 | 중요도 |
|------|------|--------|
| `web/src/simulators/kospi/data/kospi_data.js` | 자동 재생성 | 자동 |
| `web/src/simulators/kospi/CohortAnalysis.jsx` | 게이지 + 변수분해 UI 변경 | UI |
| `web/src/simulators/kospi/colors.js` | RSPI 7단계 색상 | UI |
| `web/src/simulators/kospi/shared/terms.jsx` | 5변수 + VA 용어 | UI |

#### C-1. RSPIGauge 변경

v2.0.0: 수평바, 양수=매도, 5단계
v2.2.0: 수평바, **음수=매도(빨간), 양수=반등(초록)**, 7단계

#### C-2. DualBreakdown -> VariableBreakdown

v2.0.0: CF(4변수) | DF(4변수) 대칭 2컬럼
v2.2.0: V1~V5 단일 수평바 5개 + VA 표시

## 7. 리스크

| 리스크 | 대응 |
|--------|------|
| V1 연속화로 false positive | 거리함수 60%p 범위로 자연 감쇠 |
| V2 z-score 극단값 | lookback 20일 + clamp(-1,1) |
| V4 패턴 기반 이산적 | 임계값 300억은 향후 ADV 비율로 전환 가능 |
| V5 D+1 시차 | 가중치 0.10 (최저)으로 영향 제한 |
| VA 과증폭 | ceiling 2.0 + log2 스케일로 완만 |
| 부호 반전 혼란 | 코드 내 주석 명확화 + 프론트 가이드박스 |
| 기존 RSPI 히스토리 단절 | v2.2.0 히스토리 새로 시작, v2.0.0은 deprecated |

## 8. 구현 순서

```
Phase A (Backend)  ->  Phase B (파이프라인)  ->  Phase C (Frontend)
    A-1: rspi_engine.py 전면 재작성
    A-2: constants.py 업데이트
    A-3: rspi_backtest.py 5단계 검증
                          B-1: compute_models.py 연동
                          B-2: export_web.py 구조 변경
                                                 C-1: kospi_data.js 재생성
                                                 C-2: CohortAnalysis.jsx UI
                                                 C-3: colors.js + terms.jsx
```

## 9. export 구조 (Frontend용)

```javascript
RSPI_DATA = {
  history: [{date, rspi, raw, amp, v1, v2, v3, v4, v5}],
  latest: {
    date, rspi, level,
    raw_variables: {v1, v2, v3, v4, v5},
    volume_amp,
    variable_contributions: {v1_contrib, v2_contrib, ...},
  },
  scenario_matrix: [
    {label: "낙관적", ewy_pct: +3, rspi: +25, ...},
    {label: "기본",   ewy_pct: -1, rspi: -5, ...},
    {label: "비관적", ewy_pct: -4, rspi: -30, ...},
  ],
}

RSPI_CONFIG = {
  weights: {v1: 0.25, v2: 0.20, v3: 0.25, v4: 0.20, v5: 0.10},
  variables: [
    {key: "v1", label: "코호트 proximity", range: "0~1", direction: "단방향"},
    {key: "v2", label: "외국인 수급",      range: "-1~1", direction: "양방향"},
    {key: "v3", label: "야간시장",         range: "-1~1", direction: "양방향"},
    {key: "v4", label: "개인 수급",        range: "-1~1", direction: "양방향"},
    {key: "v5", label: "신용잔고",         range: "-1~1", direction: "양방향"},
  ],
  levels: [
    {min: -100, max: -40, label: "극단 매도",  color: "#b71c1c"},
    {min: -40,  max: -20, label: "강한 매도",  color: "#f44336"},
    {min: -20,  max: -5,  label: "약한 매도",  color: "#ffc107"},
    {min: -5,   max: 5,   label: "중립",       color: "#9e9e9e"},
    {min: 5,    max: 20,  label: "약한 반등",  color: "#8bc34a"},
    {min: 20,   max: 40,  label: "강한 반등",  color: "#4caf50"},
    {min: 40,   max: 100, label: "극단 반등",  color: "#1b5e20"},
  ],
}
```

## 10. 예상 결과

변수 전면 재설계 + 검증 프레임워크 후:
- RSPI 범위: -80 ~ +60 (현재 -63.5 ~ +6.0)
- 3/3 RSPI: ~-50 (강한 매도) -> 실제 -7.3% 방향 일치
- 3/4->3/5 RSPI: ~+19 (반등) -> 실제 +11.1% 방향 일치
- noise 버킷 ~50% (과적합 아님), strong 버킷 65%+ (유효)
- 5변수 모두 연속값으로 의미있는 신호 생성
