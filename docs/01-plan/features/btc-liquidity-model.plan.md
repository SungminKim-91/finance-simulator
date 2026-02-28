# Plan: BTC Liquidity Prediction Model v1.0.0

> Feature: btc-liquidity-model
> Created: 2026-03-01
> Status: Final (v1.0.0)
> PDCA Phase: Completed
> Updated: 2026-03-01

---

## 1. Feature Overview

### 1.1 목적
글로벌 유동성 지표를 기반으로 BTC 가격의 **큰 흐름(방향성)**을 **5-6개월 선행 예측**하는 분석 시뮬레이터 구축.
실제 데이터 크롤링 파이프라인을 포함하여 주간 자동 Score 산출까지 지원.

### 1.2 핵심 철학
- BTC를 target으로 직접 최적화하지 않음 — 유동성 지수를 먼저 독립 구성 → 사후 검증
- 파형 매칭이 목적 — 월간 수익률(hit rate)이 아닌 `corr(score, log₁₀(BTC))` 최적화
- `log₁₀(BTC)` 스케일 비교
- 12m MA detrend 통일
- 과적합 방지: 변수 수 × 15 ≤ 데이터 포인트

### 1.3 현재 상태
- Phase 2 최적화 완료 (3개 확정 변수: NL, GM2_resid, SOFR)
- OOS corr: 0.407 (lag=5m)
- **다음 단계**: HY Spread + CME Basis 추가 → v4.0 완성 + 데이터 파이프라인

---

## 2. Scope (v1.0.0)

### 2.1 In-Scope

#### A. 데이터 수집 레이어 (Data Fetchers)
| 변수 | 소스 | API | 시리즈/방법 |
|------|------|-----|------------|
| WALCL | FRED | fredapi | `WALCL` (주간) |
| TGA | Treasury Fiscal Data | REST (키 불필요) | `/v1/accounting/dts/operating_cash_balance` |
| RRP | FRED | fredapi | `RRPONTSYD` (일간) |
| SOFR | FRED | fredapi | `SOFR` (일간) |
| IORB | FRED | fredapi | `IORB` (일간) |
| US M2 | FRED | fredapi | `M2SL` (월간) |
| EU M2 | FRED | fredapi | FRED 대체 시리즈 (ECB SDW 대신) |
| CN M2 | FRED | fredapi | `MYAGM2CNM189N` (월간) |
| JP M2 | FRED | fredapi | `MABMM2JPM189N` (월간) |
| DXY | Yahoo Finance | yfinance | `DX-Y.NYB` |
| HY Spread | FRED | fredapi | `BAMLH0A0HYM2` (월간) |
| BTC 현물 | Yahoo Finance | yfinance | `BTC-USD` |
| CME BTC 선물 | Yahoo Finance | yfinance | `BTC=F` (CME 근월물) |
| BTC 현물 보조 | CoinGecko/Binance | REST | Fallback/교차 검증 |

#### B. 계산 레이어 (Calculators)
- NL = WALCL - TGA - RRP
- GM2 = US_M2 + EU_M2 + CN_M2 + JP_M2
- GM2 직교화: `GM2_resid = GM2_level - (β × NL_level + α)`
- SOFR Binary: `(SOFR - IORB) > 20bps → 1, else → 0`
- HY Spread Level: 12m MA detrend
- CME Basis: `(선물 - 현물) / 현물 × (365/잔존일수) × 100` → 12m MA detrend
- 모든 수준 변수: 12m MA detrend → z-score

#### C. 최적화 레이어 (Optimizer)
- Grid Search: 5개 변수 가중치 + lag(0-9m) 동시 탐색
- 목적함수: `maximize corr(score(t), log₁₀(BTC)(t+k))`
- Walk-Forward: 60m expanding train / 6m rolling test / 8 windows
- 직교화 필요성 자동 판단 (상관 > 0.5)

#### D. 파이프라인 (Pipeline)
- 주간 자동 실행 (cron 지원)
- 실시간 Score 산출 및 히스토리 저장
- 터미널/JSON 출력

#### E. 시각화 (Visualization)
- Score vs log₁₀(BTC) 오버레이 차트
- 교차상관 히트맵
- Walk-Forward 결과 시각화

### 2.2 Out-of-Scope (v1.1+)
- Slack/Discord 알림 시스템
- 웹 대시보드 (Streamlit/Dash)
- 포트폴리오 시뮬레이션
- 실시간 트레이딩 시그널

---

## 3. 변수 명세 (v4.0 — 5개 변수)

### [1] NL Level — 미국 유동성 수준 (메인)
```
원천: NL = WALCL - TGA - RRP
변환: NL_level = (NL - NL_12mMA) / NL_12mMA × 100
가중치: ~1.5 (Grid Search 재확정)
역할: 미국 유동성 환경, 주간 업데이트
```

### [2] GM2 Residual — 미국 외 글로벌 유동성 (보조)
```
원천: GM2 = US_M2 + EU_M2 + CN_M2 + JP_M2
직교화: GM2_resid = GM2_level - (β × NL_level + α)  # OLS로 β,α 결정
가중치: ~2.0 (Grid Search 재확정)
역할: EU/CN/JP 고유 유동성
래그: 2-3개월
```

### [3] SOFR Binary — 위기 감지
```
원천: SOFR - IORB
변환: spread > 20bps → 1, else → 0
가중치: ~-2.5 (Grid Search 재확정)
역할: 비상 브레이크
```

### [4] HY Spread Level — 신용 스프레드 (위험선호) ★NEW
```
원천: ICE BofA US High Yield OAS
FRED: BAMLH0A0HYM2
변환: HY_level = (HY - HY_12mMA) / HY_12mMA × 100
역할: 유동성의 "질" — 위험선호/회피
참고: BTC와 역상관 → 가중치 음수 예상
가용: 2016-01 ~ 현재
```

### [5] CME Basis — 기관 포지셔닝 ★NEW
```
원천: (CME BTC 근월물 - BTC 현물) / 현물 × (365/잔존일수) × 100
변환: Basis_level = (Basis - Basis_12mMA) / |Basis_12mMA| × 100
역할: 기관 캐리 트레이드 수급 압력
참고: 높음→캐리유입→강세, 급락→캐리청산→약세
가용: 2017-12 ~ (앞쪽 NaN 처리)
데이터: Yahoo Finance(CME BTC=F) + Yahoo/CoinGecko(현물) 복합
```

---

## 4. 기술 스택

| 구분 | 기술 | 이유 |
|------|------|------|
| Language | Python 3.11+ | 금융 데이터 분석 생태계 최강 |
| Data | pandas, numpy | 시계열 처리 표준 |
| FRED API | fredapi | 공식 Python 패키지 |
| Market Data | yfinance | Yahoo Finance 무료 접근 |
| HTTP | requests | Treasury API, CoinGecko, Binance |
| Optimization | scipy, numpy | Grid Search, 상관 계산 |
| Visualization | matplotlib, seaborn | 차트 생성 |
| Storage | JSON + SQLite | 경량 로컬 저장 |
| Testing | pytest | 표준 테스트 프레임워크 |
| Config | python-dotenv | API 키 관리 (.env) |

---

## 5. 구현 순서 (Implementation Phases)

### Phase 1: 프로젝트 셋업 + FRED 기본 데이터 수집
- [ ] Python 프로젝트 초기화 (pyproject.toml / requirements.txt)
- [ ] config 모듈 (.env, API 키, 상수)
- [ ] FRED fetcher (WALCL, RRP, SOFR, IORB, M2 시리즈)
- [ ] Treasury fetcher (TGA)
- [ ] FRED API 키 발급 가이드 포함

### Phase 2: 시장 데이터 + 신규 변수 수집
- [ ] Market fetcher (DXY, BTC 현물/선물 - yfinance)
- [ ] HY Spread fetcher (FRED BAMLH0A0HYM2)
- [ ] CME Basis 계산기 (선물-현물 연율화)
- [ ] CoinGecko/Binance fallback fetcher

### Phase 3: 계산 엔진
- [ ] NL 계산 (WALCL - TGA - RRP)
- [ ] GM2 합산 (US + EU + CN + JP, 월간 캐리포워드)
- [ ] 12m MA detrend (모든 수준 변수)
- [ ] GM2 직교화 (OLS residual)
- [ ] SOFR Binary 변환
- [ ] z-score 표준화

### Phase 4: 최적화 엔진
- [ ] Grid Search (5변수 가중치 + lag 탐색)
- [ ] 목적함수: corr(score, log₁₀(BTC))
- [ ] Walk-Forward 검증 (expanding window)
- [ ] 직교화 자동 판단 (상관 > 0.5)
- [ ] 최적 가중치 출력 및 저장

### Phase 5: 파이프라인 + 시각화
- [ ] 주간 실행 main.py (전체 파이프라인)
- [ ] Score 히스토리 JSON/SQLite 저장
- [ ] Score vs log₁₀(BTC) 오버레이 차트
- [ ] 교차상관 히트맵
- [ ] Walk-Forward 결과 시각화
- [ ] 터미널 요약 출력

### Phase 6: 테스트 + 문서화
- [ ] 단위 테스트 (fetcher, calculator, optimizer)
- [ ] 통합 테스트 (전체 파이프라인)
- [ ] README.md (설치, 사용법, API 키 설정)
- [ ] CLAUDE.md (프로젝트 컨텍스트)

---

## 6. 파일 구조 (설계)

```
finance-simulator/
├── CLAUDE.md                    # 프로젝트 컨텍스트 (AI 작업용)
├── README.md                    # 설치/사용 가이드
├── pyproject.toml               # Python 프로젝트 설정
├── requirements.txt             # 의존성
├── .env.example                 # API 키 템플릿
├── .gitignore
├── config/
│   ├── __init__.py
│   ├── settings.py              # 환경변수, API 키 로드
│   └── constants.py             # z-score params, weights, 데이터 범위
├── src/
│   ├── __init__.py
│   ├── fetchers/
│   │   ├── __init__.py
│   │   ├── fred_fetcher.py      # FRED API (WALCL, RRP, SOFR, IORB, M2, HY)
│   │   ├── treasury_fetcher.py  # Treasury Fiscal Data API (TGA)
│   │   ├── market_fetcher.py    # yfinance (DXY, BTC, CME futures)
│   │   └── fallback_fetcher.py  # CoinGecko/Binance (CME Basis 보조)
│   ├── calculators/
│   │   ├── __init__.py
│   │   ├── net_liquidity.py     # NL = WALCL - TGA - RRP
│   │   ├── global_m2.py         # GM2 합산 + 직교화
│   │   ├── sofr_binary.py       # SOFR - IORB binary
│   │   ├── hy_spread.py         # HY Spread detrend
│   │   ├── cme_basis.py         # CME Basis 연율화 + detrend
│   │   └── detrend.py           # 공통 12m MA detrend + z-score
│   ├── optimizers/
│   │   ├── __init__.py
│   │   ├── grid_search.py       # 5변수 파형 매칭 Grid Search
│   │   ├── walk_forward.py      # Walk-Forward 검증
│   │   └── orthogonalize.py     # 직교화 (OLS residual)
│   ├── pipeline/
│   │   ├── __init__.py
│   │   ├── runner.py            # 주간 파이프라인 실행
│   │   └── storage.py           # JSON/SQLite 저장
│   ├── visualization/
│   │   ├── __init__.py
│   │   ├── overlay_chart.py     # Score vs log₁₀(BTC)
│   │   ├── correlation_heatmap.py
│   │   └── walkforward_plot.py
│   └── utils/
│       ├── __init__.py
│       ├── date_utils.py        # 날짜/기간 유틸
│       └── logger.py            # 로깅 설정
├── data/
│   ├── raw/                     # API 원본 응답
│   ├── processed/               # 계산된 시계열
│   └── scores/                  # 최종 Score 히스토리
├── tests/
│   ├── test_fetchers.py
│   ├── test_calculators.py
│   └── test_optimizers.py
├── docs/
│   ├── 01-plan/features/
│   │   └── btc-liquidity-model.plan.md
│   ├── 02-design/features/
│   ├── 03-analysis/
│   └── 04-report/
└── main.py                      # 진입점
```

---

## 7. 리스크 & 대응

| 리스크 | 영향 | 대응 |
|--------|------|------|
| FRED API Rate Limit | 데이터 수집 지연 | 캐싱 + 배치 요청 (120/분) |
| CME 선물 데이터 부재 (2017.12 이전) | Basis 변수 NaN | NaN forward-fill 또는 해당 기간 제외 |
| ECB SDW 접근 불가 | GM2 계산 불가 | FRED 대체 시리즈 사용 (확정) |
| yfinance API 변경/차단 | 시장 데이터 수집 실패 | CoinGecko/Binance fallback |
| 5변수 Grid Search 시간 | 최적화 느림 | 탐색 범위 분할, 조기 종료 |
| GM2 래그 (2-3개월) | 최신 데이터 부재 | 직전값 캐리포워드 |

---

## 8. 성공 기준

| 지표 | 목표 |
|------|------|
| 5개 변수 데이터 수집 | 2016-01 ~ 현재 전체 기간 커버 |
| 파형 매칭 corr | > 0.40 (현재 3변수 0.407, 5변수로 개선 기대) |
| 최적 lag | 4-7개월 범위 (일관성) |
| Walk-Forward OOS | 양의 상관 유지 |
| 주간 파이프라인 | 1회 실행 < 5분, 에러율 < 1% |
| 과적합 안전 | 데이터÷변수 ≥ 15:1 (108÷5 = 21.6:1 ✓) |

---

## 9. FRED API 키 발급 가이드

### 발급 절차
1. https://fred.stlouisfed.org 접속
2. 우측 상단 "My Account" → 회원가입 (무료)
3. 로그인 후 "My Account" → "API Keys" 탭
4. "Request API Key" 클릭
5. Description 입력 (예: "BTC Liquidity Model") → 즉시 발급
6. `.env` 파일에 저장: `FRED_API_KEY=your_key_here`

### 참고
- 무료, Rate Limit: 120 requests/min
- 개인 학술/연구 용도 무제한

---

## 10. 의사결정 로그

| 결정 | 이유 |
|------|------|
| finance-simulator 별도 프로젝트 | clean-house와 완전히 독립적인 도메인 |
| Python | 금융 데이터 분석 생태계 (pandas, fredapi, yfinance) |
| ECB SDW → FRED 대체 | 구현 간편, ECB API 파싱 복잡도 회피 |
| CME Basis 복합 소스 | Yahoo Finance(선물) + CoinGecko/Binance(현물) 정확도 극대화 |
| Full scope v1.0.0 | 모델+파이프라인 일체형으로 즉시 활용 가능 |
| SQLite + JSON | 경량 로컬 환경, 외부 DB 불필요 |

---

## References
- `CLAUDE_PROJECT_CONTEXT.md` — 전체 프로젝트 컨텍스트 및 모델 진화 히스토리
- `v3_data_pipeline_plan.md` — 데이터 파이프라인 설계 원본
