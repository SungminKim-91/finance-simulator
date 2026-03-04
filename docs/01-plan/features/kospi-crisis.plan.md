# Plan: KOSPI Crisis Detector

> Feature: `kospi-crisis` | Version: 1.0.0 | Created: 2026-03-03
> Spec Source: `KOSPI_CRISIS_DETECTOR_SPEC v1.0`

---

## 1. Overview

### 1.1 목적
한국 주식시장의 신용잔고 기반 코호트 분석, 반대매매 연쇄 시뮬레이션, 과거 사례 비교, 시나리오 확률 추적을 하나의 대시보드에서 수행하는 모델. 기존 BTC 유동성 모델과 동일 React 웹앱 내 별도 탭으로 통합.

### 1.2 핵심 가치
- 신용잔고 코호트 분석으로 "어느 가격대에 얼마나 물렸는지" 시각화
- 반대매매 연쇄 피드백 루프 시뮬레이션 (초기 충격 → 강제청산 → 추가 하락 → ...)
- Bayesian 시나리오 확률 추적 (일간 업데이트)
- 과거 위기 사례(2008, 2015 중국, 2020, 2021)와 현재 비교

### 1.3 Scope
- **In Scope**: 데이터 수집 파이프라인, 4개 모델 엔진, 4탭 대시보드, 기존 BTC 대시보드와 탭 통합
- **Out of Scope**: 실시간 알림(Slack/Push), 모바일 네이티브 앱, 자동 매매 연동, Vercel 배포 자동화 (Phase 5 별도)

---

## 2. Architecture

### 2.1 시스템 구조

```
┌──────────────────────────────────────────────────────────────┐
│                   React Web App (localhost / Vercel)          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ BTC 유동성│  │ Market   │  │ Cohort & │  │ Scenario │    │
│  │ (기존)    │  │ Pulse    │  │ Forced   │  │ & History│    │
│  │ App/AppV2 │  │ Tab A    │  │ Liq. B   │  │ Tab C/D  │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│         ▲              ▲            ▲             ▲          │
│         └──────────────┴────────────┴─────────────┘          │
│                    JSON Data (static import or fetch)         │
└──────────────────────────────────────────────────────────────┘
                              │
                   ┌──────────┴──────────┐
                   │  Python Pipelines    │
                   │  scripts/            │
                   │  (local or GH Actions)│
                   └─────────────────────┘
```

### 2.2 기술 스택

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + Recharts 2.15 + Vite 6.0 (기존 공유) |
| Data Fetcher | Python 3.12 + pykrx + FinanceDataReader + BeautifulSoup4 |
| Scheduling | GitHub Actions cron (KST 16:30) — Phase 5 |
| Data Format | JSON (daily snapshots + timeseries + model output) |
| Hosting | localhost (dev) → Vercel (prod, Phase 5) |

### 2.3 폴더 구조 (시뮬레이터별 최상위 분리)

```
finance-simulator/
│
├── btc/                            # === BTC 유동성 시뮬레이터 ===
│   ├── src/                        # 기존 src/ 이동 (Phase 5)
│   │   ├── fetchers/
│   │   ├── calculators/
│   │   ├── index_builders/
│   │   ├── validators/
│   │   ├── robustness/
│   │   └── pipeline/
│   ├── data/                       # 기존 data/ 이동 (Phase 5)
│   ├── config/                     # 기존 config/ 이동 (Phase 5)
│   ├── export_v2_web.py
│   └── main.py
│
├── kospi/                          # === KOSPI 위기감지 시뮬레이터 ===
│   ├── scripts/                    # Python 데이터 수집 & 모델
│   │   ├── fetch_daily.py          # 일간 자동 수집 (pykrx + FDR + KOFIA)
│   │   ├── fetch_historical.py     # 과거 데이터 1회성 수집
│   │   ├── kofia_scraper.py        # 금투협 스크래핑
│   │   ├── compute_models.py       # 코호트/반대매매/스코어/시나리오 연산
│   │   ├── estimate_missing.py     # T+2 추정 (rolling OLS)
│   │   └── export_web.py           # JSON → web data 내보내기
│   ├── data/                       # KOSPI 데이터
│   │   ├── daily/                  # 일간 스냅샷 {YYYY-MM-DD}.json
│   │   ├── timeseries.json         # 전체 시계열
│   │   ├── model_output.json       # 모델 연산 결과
│   │   ├── scenarios.json          # 시나리오 정의 + 확률 히스토리
│   │   ├── metadata.json           # last_updated
│   │   └── historical/             # 과거 사례 비교
│   │       ├── korea_2008.json
│   │       ├── korea_2020.json
│   │       ├── korea_2021.json
│   │       └── china_2015.json
│   └── config/                     # KOSPI 전용 설정
│       └── constants.py
│
├── us-market/                      # === 미장 시뮬레이터 (미래) ===
│   └── (TBD)
│
├── web/                            # === 통합 프론트엔드 ===
│   ├── src/
│   │   ├── main.jsx                # 시뮬레이터 선택기 (BTC/KOSPI/미장/...)
│   │   ├── simulators/
│   │   │   ├── btc/                # BTC 시뮬레이터 UI
│   │   │   │   ├── App.jsx         # v1 (기존)
│   │   │   │   ├── AppV2.jsx       # v2 Dual-Band (기존)
│   │   │   │   ├── data.js
│   │   │   │   └── data_v2.js
│   │   │   ├── kospi/              # KOSPI 시뮬레이터 UI
│   │   │   │   ├── KospiApp.jsx    # KOSPI 메인 (4탭 라우팅)
│   │   │   │   ├── MarketPulse.jsx # Tab A: 시장 현황
│   │   │   │   ├── CohortAnalysis.jsx  # Tab B: 코호트 & 반대매매
│   │   │   │   ├── ScenarioTracker.jsx # Tab C: 시나리오 확률
│   │   │   │   ├── HistoricalComp.jsx  # Tab D: 과거 비교
│   │   │   │   ├── shared/         # KOSPI 공유 컴포넌트
│   │   │   │   │   ├── CrisisGauge.jsx
│   │   │   │   │   ├── EstimatedBadge.jsx
│   │   │   │   │   └── KospiHeader.jsx
│   │   │   │   └── data/
│   │   │   │       └── kospi_data.js
│   │   │   └── us-market/          # 미장 시뮬레이터 UI (미래)
│   │   └── shared/                 # 전체 시뮬레이터 공유
│   │       ├── colors.js           # 통합 색상 팔레트
│   │       └── components/         # 공유 UI 컴포넌트
│   ├── package.json
│   └── vite.config.js
│
├── docs/                           # PDCA 문서
├── .github/workflows/              # GitHub Actions (Phase 5)
│   └── daily-fetch.yml
└── CLAUDE.md
```

**핵심 원칙:**
- 시뮬레이터별 최상위 폴더 분리 (`btc/`, `kospi/`, `us-market/`)
- 각 시뮬레이터는 자체 `scripts/`, `data/`, `config/` 보유 (독립적)
- `web/`은 통합 프론트엔드 — `simulators/{name}/`으로 UI 분리
- BTC 기존 코드는 **당장 이동하지 않음** — Phase 5 통합 시 `btc/`로 이동

**Phase 1 시작 시 실제 생성 폴더:**
```
kospi/scripts/          # KOSPI Python 코드
kospi/data/             # KOSPI 데이터
kospi/data/historical/  # 과거 사례
web/src/simulators/kospi/  # KOSPI React 컴포넌트
```
```

---

## 3. Data Layer

### 3.1 데이터 소스 (22개 자동 + 5개 수동)

**자동 수집 (pykrx + FDR + KOFIA):**

| ID | 데이터 | 소스 | 지연 |
|----|--------|------|------|
| D01 | KOSPI/KOSDAQ OHLCV | KRX (pykrx) | T+0 |
| D02-D03 | 삼성전자/SK하이닉스 OHLCV | KRX (pykrx) | T+0 |
| D04-D06 | 주체별 매매동향 (시장+삼전+하닉) | KRX (pykrx) | T+0 |
| D07-D08 | USD/KRW, WTI | Yahoo (FDR) | T+0 |
| D09-D11 | 공매도 (시장+삼전+하닉) | KRX (pykrx) | T+0 |
| D12-D15 | 신용잔고, 예탁금, 미수금, 반대매매 | 금투협 KOFIA | **T+2** |
| D16-D17 | 종목별 신용잔고 (삼전, 하닉) | KRX | T+1~2 |
| D18 | KOSPI 200일 MA | 계산 (D01) | - |
| D19 | KOSPI 시가총액 | KRX (pykrx) | T+0 |
| D20-D21 | VIX, S&P 500 | Yahoo (FDR) | T+0 |
| D22 | KOSPI 거래대금 | KRX (pykrx) | T+0 |

**수동 입력:**

| ID | 데이터 | 주기 |
|----|--------|------|
| M01 | DRAM 계약가 전망 (QoQ %) | 분기 |
| M02 | DRAM 스팟 가격 (DDR5 8Gb) | 주간 |
| M03 | 증권사 신용한도 변경 뉴스 | 비정기 |
| M04 | 정부 조치 이벤트 | 비정기 |
| M05 | 2015 중국 사례 데이터 | 1회 하드코딩 |

### 3.2 T+2 추정 로직
- 신용잔고/예탁금: `rolling OLS 10일` (개인순매수, KOSPI수익률, 전일변화)
- 추정치에 `estimated: true` 플래그 + confidence interval
- 반대매매는 추정하지 않음 (이산적 이벤트)
- 실측 도착 시 보정 + 오차 로그

---

## 4. Model Layer (4개 엔진)

### 4.1 Module A: 코호트 모델 (Cohort Builder)
- **입력**: 일간 신용잔고 변화량, KOSPI 종가
- **로직**: ΔCredit > 0 → 새 코호트 생성, ΔCredit < 0 → LIFO/FIFO 상환
- **출력**: 활성 코호트 목록 (진입가, 잔고, PnL%, 담보비율, 상태)
- **가격대 분포**: 500pt 단위 히스토그램

### 4.2 Module B: 반대매매 시뮬레이터 (Forced Liquidation)
- **증거금 분포**: A군 40%(35%) / A군 45%(35%) / B군 50%(25%) / 기타 60%(5%)
- **담보 기준**: 140% 마진콜, 130% 즉시 반대매매
- **연쇄 시뮬레이션**:
  - 초기 충격 → 담보비율 체크 → 강제청산 물량 → 흡수율 적용 → 시장 충격 → 반복
  - 라운드 1~10 (슬라이더), 수렴 시 중단 (강제청산 < 100억)
- **흡수율 모드**: 자동(수급기반) / 보수적(0.3) / 중립(0.5) / 낙관(0.7) / 커스텀

### 4.3 Module C: 위기 스코어 (Crisis Score)
- **14개 scored 지표 (v1.4)**: 레버리지 과열도, 수급 편중도, 가격 괴리도, 신용 가속도, 예탁금 유입, VIX, 거래대금 폭발도, 반대매매 강도, 신용/예탁금 비율, DRAM 사이클, **신용 중단(I16)**, **기관 순매도(I17)**, **개인 매수력 감소(I18)**, **불트랩(I19)**
- **제거 (v1.4)**: 외국인 매도 강도(I06, 관측만), 환율 스트레스(I07, 관측만), 공매도 이상(I08, 근거 부족)
- **처리**: Percentile rank 정규화(0~100) → PCA → 가중치 결정 → 위기 점수(0~100)
- **등급**: 0~50 보통 / 50~70 주의 / 70~85 위험 / 85~95 심각 / 95+ 극단

### 4.4 Module D: 시나리오 확률 (Bayesian Tracker)
- **5개 시나리오 (v1.4)**: 연착륙(S1, 소멸) / 방어(S2, 8%) / 캐스케이드(S3, 55%) / 전면위기(S4, 33%) / 펀더멘털 붕괴(S5, 4%)
- **Loop B 폐기 → Loop C 추가**: 외국인 매도 예측 실패 → 펀드 환매 캐스케이드(T+1~T+3 지연)
- **방어벽 5단계**: 개인매수(붕괴) / 연기금(약화) / 한은FX(작동) / US통화스왑(거절) / IMF(미발동)
- **업데이트**: 일간 Bayesian (6개 관측 지표 × 정규분포 likelihood)
- **Key Drivers**: 각 시나리오 확률 변동의 상위 3개 원인 지표
- **유연성**: 시나리오 추가/수정/제거 가능, 확률 <2% 시 자동 비활성화

### 4.5 Module E: 과거 사례 비교 (Historical Comparison)
- **데이터셋**: 한국 2008, 2020, 2021 (pykrx 자동) + 중국 2015 (하드코딩)
- **유사도**: DTW(60%) + Cosine Similarity(40%) 하이브리드
- **오버레이**: 고점 대비 경과일 기준 정렬 (D+0, D+1, ...)

---

## 5. Dashboard Layer (4탭)

### 5.1 Tab A: Market Pulse (시장 현황)
- 핵심 숫자 카드: KOSPI, 삼전, 하닉, USD/KRW, WTI, 위기점수 게이지
- 신용잔고 + 예탁금 시계열 (실측 solid / 추정 dashed)
- 주체별 수급 (개인/외국인/기관 stacked bar)
- 공매도 현황 + 정부 조치 이벤트 마커
- 글로벌 컨텍스트 (VIX, S&P500, WTI, USD/KRW 미니차트)
- DRAM 가격 추이, 이벤트 로그

### 5.2 Tab B: Cohort & Forced Liquidation
- 코호트 분포 히트맵 (가격대별 잔고, PnL%, 담보비율, 상태 색상)
- FIFO/LIFO 토글
- 반대매매 트리거 맵 (KOSPI 하락 시나리오별 마진콜/강제청산 금액)
- **인터랙티브 시뮬레이터**: 초기 충격 슬라이더, 라운드 슬라이더, 흡수율 모드, 증거금 분포 슬라이더, 실행 버튼, 라운드별 결과 step chart

### 5.3 Tab C: Scenario Tracker
- 현재 확률 바 차트 (4개 시나리오 + 변화율)
- 확률 변화 시계열 (stacked area chart)
- 오늘의 Key Drivers 패널
- 시나리오별 예상 경로 fan chart (30/60/90일)

### 5.4 Tab D: Historical Comparison
- 유사도 점수 바 차트
- 오버레이 시계열 (고점 대비 경과일, 체크박스 선택)
- 지표별 비교 테이블 (현재 vs 과거 사례)
- 사례 상세 이벤트 타임라인

### 5.5 공통 UI 요소
- 상단 고정: 위기점수 뱃지 + KOSPI 현재가 + 마지막 업데이트
- estimated 데이터: 점선 + [추정] 뱃지
- 다크모드 기본 (기존 BTC 팔레트 계승)

---

## 6. Implementation Phases

### Phase 1: Data Foundation + Tab A (MVP) — 2~3일
```
1.1 main.jsx 최소 리팩토링 (BTC/KOSPI 시뮬레이터 선택기)
1.2 Python 데이터 수집 (scripts/kospi/)
    - fetch_daily.py (pykrx + FDR + KOFIA)
    - fetch_historical.py (과거 데이터 1회성)
    - kofia_scraper.py (금투협 스크래핑)
1.3 데이터 JSON 스키마 구현
1.4 Tab A (Market Pulse) 기본 구현
    - 핵심 숫자 카드, 신용잔고 차트, 수급 바 차트
```

### Phase 2: Cohort + Forced Liquidation + Tab B — 3~4일
```
2.1 코호트 모델 엔진 (LIFO/FIFO)
2.2 반대매매 시뮬레이터 엔진 (피드백 루프)
2.3 T+2 추정 로직
2.4 Tab B 구현 (히트맵, 트리거 맵, 인터랙티브 시뮬레이터)
```

### Phase 3: Crisis Score + Scenario + Historical + Tab C/D — 4~5일
```
3.1 위기 지표 14개 산출 + PCA (v1.4: I06/I07/I08 제거, I16~I19 추가)
3.2 5개 시나리오 (v1.4: S5 펀더멘털 붕괴 추가, Loop C 반영)
3.3 과거 사례 유사도 (DTW + Cosine)
3.4 Tab C (Crisis Analysis: Score + Scenario + Loop + Defense) + Tab D (Historical)
```

### Phase 4: Scenario Engine + Integration — 3~4일
```
4.1 Bayesian 시나리오 엔진
4.2 시나리오 관리 UI
4.3 위기 점수 → 시나리오 연동
4.4 전체 통합 테스트
```

### Phase 5: Deploy + Polish — 2~3일 (별도 PDCA)
```
5.1 GitHub Actions 워크플로우
5.2 Vercel 배포
5.3 모바일 반응형
5.4 성능 최적화
```

---

## 7. Dependencies

### Python (신규)
```
pykrx
finance-datareader
beautifulsoup4
requests
scipy
numpy
pandas
```

### React (기존 공유)
```
react 18, recharts 2.15, vite 6.0
추가 예정: lodash (선택), mathjs (선택)
```

---

## 8. Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| pykrx API 변경/중단 | 데이터 수집 중단 | FDR 백업, 네이버금융 fallback |
| 금투협 페이지 구조 변경 | 신용잔고 수집 실패 | 에러 알림, 수동 입력 fallback |
| T+2 추정 정확도 | 모델 오류 | 추정 오차 로그 → 계수 개선 |
| 증거금 분포 추정 부정확 | 반대매매 규모 오차 | 슬라이더로 사용자 조절 |
| 시나리오 파라미터 주관적 | 확률 왜곡 | 백테스팅 검증 + 사용자 조절 |
| 과거 데이터 불완전 (2008) | 비교 정확도 저하 | ECOS API 보완, 가용 범위 명시 |

---

## 9. Success Criteria

| Metric | Target |
|--------|--------|
| 데이터 수집 성공률 | pykrx/FDR ≥ 95%, KOFIA ≥ 80% |
| Tab A~D 렌더링 | 4개 탭 모두 정상 렌더링, 인터랙티브 작동 |
| 반대매매 시뮬레이션 | 5라운드 내 수렴, 합리적 결과 |
| 위기 점수 백테스팅 | 과거 사례에서 score>70 시 실제 하락 발생 확인 |
| 시나리오 확률 | 4개 합산 = 100%, 일간 업데이트 정상 |
| BTC 대시보드 | 기존 기능 깨지지 않음 (regression 없음) |
| 과거 사례 유사도 | DTW+Cosine 정상 산출, 오버레이 차트 |

---

## 10. Reference

- **Spec Document**: `KOSPI_CRISIS_DETECTOR_SPEC v1.0` (1438줄)
- **기존 BTC 모델**: `web/src/AppV2.jsx` (색상 팔레트, 차트 패턴 참조)
- **BTC PCA 방법론**: `src/index_builders/pca_builder.py` (위기 스코어에 재사용)
