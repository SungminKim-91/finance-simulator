# KOSPI VLPI (Voluntary Liquidation Pressure Index) — v1.5.0~v1.8.0

> 자발적 청산 압력 지수 기반 코호트 분석 전면 재설계
> 기간: v1.5.0 ~ v1.8.0 (4-phase incremental)
> 참조: `vlpi_architecture_v2.md`, `samsung_credit_cohort_data.md`

---

## 0. 핵심 철학 변경

### v1.4.0 (기존): 반대매매 중심
- 담보비율 < 140% → 마진콜, 손실 ≥ 39% → 강제청산
- 시뮬레이터가 "반대매매 연쇄" 모델링
- **한계**: 2026.03.04 삼성전자 -11.74% 폭락에서 마진콜 코호트 0개 — 반대매매 모델로 설명 불가

### v1.5.0+ (신규): 자발적 투매 중심 (VLPI)
- **핵심 발견**: 실제 급락의 대부분은 반대매매가 아닌 **자발적 투매** (공포 매도)
- 6개 선행변수로 "내일의 투매 압력"을 예측하는 **Pre-VLPI** 모델
- Impact Function으로 VLPI → 예상 매도물량 → 예상 가격영향 변환
- Bayesian 가중치 학습으로 데이터 축적에 따른 모델 자동 개선

---

## 1. Phase 로드맵

| Version | Phase | 범위 | 핵심 산출물 |
|---------|-------|------|------------|
| **v1.5.0** | Backend VLPI Engine | Python 모델 + 데이터 파이프라인 | `vlpi_engine.py`, EWY 수집, 6단계 분류, export 확장 |
| **v1.6.0** | Frontend Cohort Redesign | 코호트 탭 UI 전면 재설계 | 6단계 차트, VLPI 게이지, 트리거맵 재설계 |
| **v1.7.0** | VLPI Simulator + Overnight | 시뮬레이터 + 밤사이 시나리오 | Pre-VLPI 시뮬레이터, What-If, Impact 시각화 |
| **v1.8.0** | Model Learning Tab | Bayesian 학습 + 성과 대시보드 | 가중치 학습 UI, 예측 성과, 이벤트 추가 |

---

## 2. v1.5.0 — Backend VLPI Engine

### 2.1 신규 파일: `kospi/scripts/vlpi_engine.py`

Pre-VLPI 6개 변수 계산 + Impact Function 구현.

**V1: 주의구간 코호트 비중** (`calc_caution_zone_pct`)
- T-1 종가 기준 각 코호트 담보비율 계산
- 140% ≤ 담보비율 < 170% 코호트의 가중 비중 합산
- 입력: T-1 종가, 코호트 목록 / 출력: 0~1

**V2: 신용잔고 모멘텀** (`calc_credit_momentum`)
- 최근 3일 KOSPI 유가증권 신용잔고 변화율
- 잔고 증가(물타기) → 음수, 잔고 감소(청산) → 양수
- 출력: -0.3 ~ 0.7

**V3: 정책 쇼크** (`calc_policy_shock`)
- 증권사 신용 중단, 서킷브레이커 등 이벤트 심각도
- shock_map 기반 (최대값 + 나머지 30%)
- 출력: 0 ~ 1

**V4: 야간 갭 시그널** (`calc_overnight_gap`)
- EWY 변동률 (0.6) + KOSPI 야간선물 (0.3) + USD/KRW NDF (0.1)
- 갭다운 예상 시 양수, 갭업 시 음수
- 출력: -1 ~ 1

**V5: 연속 하락 심각도** (`calc_cumulative_decline`)
- 연속 하락일수(비선형 점수) + 누적 하락률(15%=1.0) 결합
- 출력: 0 ~ 1

**V6: 전일 개인 수급 방향** (`calc_individual_flow_direction`)
- 5개 패턴 매칭: 대량순매수→항복 패턴이 가장 위험
- 출력: 0 ~ 1

**Pre-VLPI 종합** (`calc_pre_vlpi`)
- 6변수 가중합산 (w1=0.25, w2=0.10, w3=0.20, w4=0.20, w5=0.15, w6=0.10)
- 정규화 후 0~100 스코어
- 컴포넌트별 기여분 분해 반환

**Impact Function**
- `estimate_selling_volume`: Pre-VLPI → sigmoid → 매도비율 → 매도금액
- `estimate_price_impact`: Kyle's Lambda 기반, 비선형 가격영향
- `run_scenario`: 전체 파이프라인 (VLPI → 매도 → 가격)

### 2.2 상태 분류 6단계 전환

`compute_models.py` Cohort.classify_status() 변경:

```
담보비율 < 100%  → "debt_exceed"  (채무초과)
담보비율 < 120%  → "forced_liq"   (강제청산)
담보비율 < 140%  → "margin_call"  (마진콜)
담보비율 < 155%  → "caution"      (주의)
담보비율 < 170%  → "good"         (양호)
담보비율 ≥ 170%  → "safe"         (안전)
```

**담보비율 공식** (samsung_credit_cohort_data 기준):
```
담보비율(%) = (현재가 / (매수가 × LOAN_RATE)) × 100
LOAN_RATE = 0.55  (= 1 - MARGIN_RATE)
```

### 2.3 데이터 수집 확장

#### 2.3a EWY 야간 갭 데이터
`fetch_daily.py`에 EWY (iShares MSCI South Korea ETF) 추가:
- yfinance로 EWY 일봉 수집
- `ewy_change_pct` 계산 (한국장 마감 이후 미국장 변동)
- `timeseries.json`에 `ewy_close`, `ewy_change_pct` 필드 추가

#### 2.3b 금투협(KOFIA) 신용잔고 데이터 소스 개선
현재 Naver Finance(sise_deposit) 스크래핑은 **D-2 지연**.
금투협은 **D-1 기준** 데이터를 더 빠르게 제공.

**소스 우선순위 (개선)**:
1. **공공데이터포털 API** (`data.go.kr/data/15094809`): 금융투자협회종합통계정보
   - 신용공여잔고 포함, REST API, 인증키 발급 필요
   - 엔드포인트: 8개 오퍼레이션 중 신용공여 관련 조회
   - 장점: 안정적, 공식 API
2. **FreeSIS 스크래핑** (`freesis.kofia.or.kr`): 종합통계포털
   - SPA 기반 동적 로딩 → XHR 엔드포인트 리버스 엔지니어링 필요
   - D-1 기준 데이터 확보 가능
3. **Naver Finance** (기존): D-2 지연, fallback으로 유지

**신규 파일**: `kospi/scripts/kofia_fetcher.py`
- 공공데이터포털 API 우선 시도
- FreeSIS XHR fallback
- Naver 최후 fallback
- `fetch_daily.py`에서 기존 naver_scraper 대신 kofia_fetcher 호출

### 2.4 Samsung 코호트 데이터 통합

`samsung_credit_cohort_data.md`의 실데이터를 시드 데이터로 활용:
- 6개 코호트 (F/A/B/C/D/E) 초기 데이터
- 일별 시세, 수급, 신용잔고 데이터
- `kospi/data/samsung_cohorts.json` 시드 파일 생성

### 2.5 export_web.py 확장

새 export 추가:
- **VLPI_DATA**: Pre-VLPI 히스토리 + 컴포넌트 분해 + Impact 결과
- **VLPI_CONFIG**: 가중치, 변수 설명, 시나리오 프리셋
- COHORT_DATA params에 6단계 분류 기준 추가

### 2.6 파일 변경 목록

| 파일 | 작업 |
|------|------|
| `kospi/scripts/vlpi_engine.py` | **신규** — VLPI 엔진 전체 |
| `kospi/scripts/compute_models.py` | 6단계 분류 전환, VLPI 연동 |
| `kospi/scripts/fetch_daily.py` | EWY 수집 추가 |
| `kospi/scripts/export_web.py` | VLPI_DATA, VLPI_CONFIG export |
| `kospi/config/constants.py` | VLPI 상수, 6단계 기준값 |
| `kospi/scripts/kofia_fetcher.py` | **신규** — 금투협 공공데이터포털 API + FreeSIS fallback |
| `kospi/data/samsung_cohorts.json` | **신규** — 시드 데이터 |

---

## 3. v1.6.0 — Frontend Cohort Redesign

### 3.1 Section 1: 코호트 분포 (6단계)

기존 4단계(safe/watch/marginCall/danger) → 6단계 전환:

| Status | 한글 | 색상 | 기준 |
|--------|------|------|------|
| debt_exceed | 채무초과 | #ff1744 (deep red) | 담보 < 100% |
| forced_liq | 강제청산 | #ff5252 (red) | 담보 < 120% |
| margin_call | 마진콜 | #ff9800 (orange) | 담보 < 140% |
| caution | 주의 | #ffc107 (amber) | 담보 < 155% |
| good | 양호 | #8bc34a (light green) | 담보 < 170% |
| safe | 안전 | #4caf50 (green) | 담보 ≥ 170% |

- Stacked horizontal bar chart 유지, 색상 6단계
- Summary 카드: 총 잔고, "주의구간 비중" (V1용), 위험비율
- 날짜 선택기 유지 (과거 코호트 재구성)

### 3.2 Section 2: VLPI 대시보드 (트리거맵 대체)

기존 트리거맵(하락% → 마진콜/반대매매 금액) → **VLPI 계기판** 전환:

**VLPI Gauge**: 큰 반원 게이지 (0~100)
- 0~30 녹색 (정상), 30~50 노란색 (주의), 50~70 주황색 (경고), 70~100 빨간색 (위험)
- 현재 Pre-VLPI 스코어 + 등급 텍스트

**Component Breakdown**: 수평 Stacked Bar
- V1~V6 각 변수의 기여분 시각화
- 호버 시 변수 설명 + 현재 값 + 가중치

**Impact Table**: 시나리오 매트릭스
- VLPI 20/30/40/50/60/70/80 각각에 대한 매도비율/매도추정/가격영향
- 현재 VLPI에 해당하는 행 하이라이트

**Cohort Risk Map**: 코호트별 담보비율 분포
- 각 코호트의 현재 위치를 170%~100% 축 위에 표시
- 마진콜 라인(140%) 레퍼런스

### 3.3 기존 Section 3 (시뮬레이터) → v1.7.0으로 이동

### 3.4 ReliabilityDashboard 삭제
- 기존 백테스트 40건 산점도/방향정확도 → 삭제
- v1.8.0 Model Learning Tab으로 대체

### 3.5 terms.jsx 업데이트
- 6단계 상태 용어 추가 (debt_exceed, good)
- VLPI 관련 용어 추가 (pre_vlpi, caution_zone, overnight_gap 등)

### 3.6 파일 변경 목록

| 파일 | 작업 |
|------|------|
| `CohortAnalysis.jsx` | **전면 재설계** — 6단계 + VLPI 대시보드 |
| `shared/terms.jsx` | 6단계 상태 + VLPI 용어 추가 |
| `colors.js` | 6단계 색상 추가 |
| `data/kospi_data.js` | VLPI_DATA, VLPI_CONFIG import |

---

## 4. v1.7.0 — VLPI Simulator + Overnight Scenario

### 4.1 Pre-VLPI 시뮬레이터

기존 "반대매매 연쇄 시뮬레이터" → **VLPI 시뮬레이터** 전환:

**입력 패널**:
- V4 (EWY 야간 갭): 슬라이더 -5%~+5% + 자동(실제 데이터)
- V3 (정책 쇼크): 체크박스 (신용 중단, 서킷브레이커, 규제 경고 등)
- 기타 V1/V2/V5/V6: 자동 계산 (T-1 데이터) + 오버라이드 토글

**출력 패널**:
- Pre-VLPI 게이지 (실시간 업데이트)
- Component 분해 바
- Impact 결과: 예상 매도금액, 예상 가격영향%
- 시나리오 비교 테이블 (밤사이 EWY -1%/-3%/-5% 각각)

### 4.2 밤사이 업뎃 시나리오

**"오늘 밤 이렇게 되면?"** 패널:

```
현재 상태 (T-1 장마감 기준):
- V1: 주의구간 7.0% │ V2: 신용 +0.49% │ V5: 2일 연속 -10.57%
- V6: 개인 +57,974억

밤사이 시나리오 선택:
┌─────────────────┬──────────┬──────────┬──────────┐
│                 │ 낙관적    │ 기본     │ 비관적    │
├─────────────────┼──────────┼──────────┼──────────┤
│ EWY 변동        │ +2.5%    │ -1.0%    │ -4.0%    │
│ 정책 쇼크       │ 없음      │ 없음     │ 증권사중단 │
│ Pre-VLPI        │ 22       │ 38      │ 68       │
│ 예상 매도       │ 2,376억   │ 5,940억  │ 26,136억  │
│ 예상 가격영향   │ -0.5%     │ -3%     │ -12%     │
└─────────────────┴──────────┴──────────┴──────────┘
```

- 3개 프리셋 (낙관/기본/비관) + 커스텀
- 각 시나리오별 코호트 상태 변화 프리뷰

### 4.3 파일 변경 목록

| 파일 | 작업 |
|------|------|
| `CohortAnalysis.jsx` | Section 3 시뮬레이터 → VLPI 시뮬레이터 교체 |
| `vlpi_engine.py` | 시나리오 프리셋 생성 함수 추가 |
| `export_web.py` | 시나리오 프리셋 데이터 export |

---

## 5. v1.8.0 — Model Learning Tab

### 5.1 Bayesian 가중치 학습 대시보드

**가중치 시각화**:
- 6개 가중치의 Beta posterior 분포 차트 (범프 차트)
- Prior(점선) vs Posterior(실선) 오버레이
- 95% CI 밴드
- 유효 데이터 수 (effective_n) 표시

**이벤트 히스토리**:
- 학습에 사용된 이벤트 목록 (날짜, 실제 하락률, VLPI 예측값)
- 각 이벤트 후 가중치 변화 추적 차트

**성과 지표**:
- 방향 적중률 (VLPI > 50 → 다음날 하락?)
- 규모 상관계수 (VLPI vs 실제 하락률)
- False Positive / False Negative Rate

### 5.2 이벤트 추가 기능

**"새 이벤트 학습" 버튼**:
1. 날짜 + 실제 하락률 입력
2. 해당 날짜의 V1~V6 자동 계산 (또는 수동 입력)
3. Bayesian update 실행
4. 가중치 변화 시각화
5. JSON 파일로 posterior 저장

### 5.3 민감도 분석

- 각 가중치 ±50% perturbation 결과
- 민감도 매트릭스 (fragile/robust 분류)
- 앙상블 불확실성 범위

### 5.4 파일 변경 목록

| 파일 | 작업 |
|------|------|
| `kospi/scripts/vlpi_engine.py` | BayesianWeightOptimizer 클래스, 민감도 분석 |
| `kospi/data/vlpi_posteriors.json` | **신규** — Bayesian posterior 저장 |
| `CohortAnalysis.jsx` | Section 4 Model Learning 탭 추가 |
| `export_web.py` | VLPI_LEARNING export 추가 |

---

## 6. 데이터 흐름

```
fetch_daily.py
  ├── KOSPI/삼성전자 시세 (ECOS/KRX)
  ├── 투자자 수급 (KRX)
  ├── 신용잔고 (Naver/금투협)
  └── EWY (yfinance) ← v1.5.0 신규
         │
         ▼
compute_models.py
  ├── Cohort 생성 (6단계 분류) ← v1.5.0 변경
  └── vlpi_engine.py 호출 ← v1.5.0 신규
         │
         ▼
export_web.py
  ├── COHORT_DATA (6단계)
  ├── VLPI_DATA (Pre-VLPI + Impact)
  ├── VLPI_CONFIG (가중치 + 설명)
  └── VLPI_LEARNING (Bayesian posteriors)
         │
         ▼
kospi_data.js → CohortAnalysis.jsx
```

---

## 7. 삭제 대상

- `ReliabilityDashboard` 컴포넌트 (CohortAnalysis.jsx 내)
- `BacktestComparison` 컴포넌트
- `BACKTEST_DATES` export (export_web.py + kospi_data.js)
- 기존 `ForcedLiqSimulator.run()` → VLPI 시뮬레이터로 대체
- 기존 트리거맵 (`get_trigger_map`) → VLPI 대시보드로 대체
- `MARGIN_DISTRIBUTION` 관련 잔여 코드 (이미 v1.4.0에서 대부분 제거)

---

## 8. 리스크 및 제약

1. **EWY 데이터 시차**: 미국장 마감(한국 06:00) 이후에만 확보 가능 → 한국 개장(09:00) 전 3시간 윈도우
2. **신용잔고 지연**: Naver=D-2, 금투협=D-1. 공공데이터포털 API 키 발급 필요 (data.go.kr). V2는 최선 T-1 데이터 사용
3. **삼성전자 50% 가정**: 실제 종목별 비중 데이터 없음 → constants에서 조정 가능하게
4. **Bayesian N < 5**: 초기에는 가중치 변화가 미미 → UI에 "학습 초기" 경고 표시
5. **정책 쇼크 수동 입력**: 뉴스 크롤링 자동화는 범위 밖 → 수동 입력 UI 필요

---

## 9. 검증 기준

### v1.5.0 (Backend)
- [ ] `vlpi_engine.py` — 2026.02.27~03.04 시뮬레이션 → Pre-VLPI ≈ 46 (3/3→3/4)
- [ ] 6단계 분류 — 3/4 종가 172,200 기준: D코호트 = "주의" (144.6%), 마진콜 0개
- [ ] EWY fetch — yfinance로 EWY 일봉 수집 성공
- [ ] export — VLPI_DATA, VLPI_CONFIG 정상 export

### v1.6.0 (Frontend)
- [ ] 6단계 바 차트 정상 렌더링
- [ ] VLPI 게이지 + 컴포넌트 분해 표시
- [ ] 트리거맵 → VLPI Impact 테이블 전환
- [ ] ReliabilityDashboard 삭제 확인

### v1.7.0 (Simulator)
- [ ] EWY 슬라이더 조작 → Pre-VLPI 실시간 변경
- [ ] 3개 시나리오 프리셋 동작
- [ ] 코호트 상태 변화 프리뷰

### v1.8.0 (Learning)
- [ ] Bayesian update 후 가중치 시각화
- [ ] 이벤트 추가 → posterior 변화
- [ ] 성과 지표 (방향 적중률 등) 표시
