# Completion Report: kospi-data-infra-v2.4.0

> **Feature**: 25년 데이터 확장 + 파이프라인 단위 검증 + OOM 수정
> **Date**: 2026-03-06
> **Status**: Completed

---

## 1. 요약

| 지표 | Before | After |
|------|--------|-------|
| timeseries 기간 | 283일 (2025-01~2026-03) | **6,335일** (2000-12~2026-03) |
| RSPI 히스토리 | 262일 | **6,211일** |
| 코호트 히스토리 | ~300일 | **6,334일** (3,592 코호트) |
| 백테스트 이벤트 | ~40건 | **762건** |
| kospi_data.js | 61MB (OOM) | **11MB** (정상) |
| S&P 500 단위 | SPY ETF (~$680) | **^GSPC 인덱스** (~6800) |
| 단위 검증 | 없음 | **27개 필드, 3단계 파이프라인** |

## 2. 데이터 확장 결과

### 2.1 필드별 커버리지 (6,335일 기준)

| 필드 | 건수 | 커버리지 | 소스 |
|------|------|---------|------|
| kospi | 6,189 | 97.7% | KOFIA 엑셀 |
| samsung | 6,227 | 98.3% | yfinance |
| hynix | 5,719 | 90.3% | yfinance |
| kosdaq | 6,219 | 98.2% | yfinance |
| usd_krw | 5,485 | 86.6% | yfinance |
| vix | 6,057 | 95.6% | yfinance |
| sp500 | 6,057 | 95.6% | yfinance (^GSPC) |
| ewy_close | 6,057 | 95.6% | yfinance |
| koru_close | 3,080 | 48.6% | yfinance (2013~ ETF) |
| credit_balance | 6,335 | 100% | KOFIA 엑셀 |
| deposit | 6,335 | 100% | KOFIA 엑셀 |
| individual | 5,223 | 82.4% | Naver (2005~) |
| foreign | 5,223 | 82.4% | Naver (2005~) |
| institution | 5,223 | 82.4% | Naver (2005~) |
| forced_liq | 4,916 | 77.6% | KOFIA 엑셀 (2006-04~) |
| market_cap | 6,188 | 97.7% | KOFIA 엑셀 |

### 2.2 커버리지 공백 (채울 수 없는 기간)

| 필드 | 공백 기간 | 이유 |
|------|----------|------|
| koru_close | 2000~2013-04 | KORU ETF 미존재 |
| individual/foreign/institution | 2000~2004 | Naver 데이터 시작점 |
| forced_liq | 2000~2006-04 | KOFIA 통계 집계 시작 전 |
| usd_krw | 2000~2003 | yfinance KRW=X 히스토리 한계 |

## 3. 버그 수정

### 3.1 S&P 500 단위 오류 (Critical)
- **증상**: sp500 값이 ~680 (SPY ETF 가격)으로 표시, 실제 S&P 500은 ~6800
- **원인**: `fetch_daily.py` L62 `YF_SYMBOLS = {"sp500": "SPY"}` — ETF 심볼 사용
- **수정**: `"SPY"` → `"^GSPC"` + timeseries 5,522건 값 교체 + sp500_change_pct 재계산

### 3.2 Vite OOM (Critical)
- **증상**: `FATAL ERROR: Ineffective mark-compacts near heap limit` — 개발서버 시작 불가
- **원인**: kospi_data.js 61MB (COHORT_HISTORY 51MB = 84%)
- **수정**: COHORT_HISTORY → `public/data/cohort_history.json` 분리, `fetch()` lazy load
- **결과**: kospi_data.js 11MB, Vite 159ms 정상 시작

### 3.3 CREDIT_DATA 누락 (Major)
- **증상**: Raw Data 테이블에서 신용잔고/예탁금이 788일만 표시
- **원인**: `export_web.py`가 daily snapshots(788일)에서만 CREDIT_DATA 빌드
- **수정**: timeseries 전체(6,335일) 기반으로 변경

### 3.4 Naver Investor 페이지 제한 (Enhancement)
- **증상**: 투자자 수급 데이터가 ~4년(1,000일)으로 제한
- **원인**: `naver_scraper.py` `max_pages = 100` 하드코딩
- **수정**: 동적 max page 감지 (`pgRR` 파싱) → 519페이지 = 5,182일(21년)

## 4. 단위 검증 파이프라인

### 4.1 validate_data.py (신규)
- 27개 필드의 기대 범위 정의 (`FIELD_RANGES`)
- `validate_record()`: 단일 레코드 검증, `fix=True`로 범위 밖 값 자동 None 처리
- `validate_timeseries()`: 전체 timeseries 일괄 검증 + 요약 리포트

### 4.2 적용 지점

| 파이프라인 | 함수 | 동작 |
|-----------|------|------|
| fetch_daily.py | `append_timeseries()` | 매일 수집 시 자동 검증 |
| kofia_excel_parser.py | `parse_kofia_excel()` | 엑셀 파싱 후 검증 |
| export_web.py | `export_all()` | 웹 내보내기 전 최종 검증 |

## 5. 수정 파일 목록

| 파일 | 변경 사항 |
|------|---------|
| `scripts/validate_data.py` | **신규** — 27개 필드 단위 검증 모듈 |
| `scripts/fetch_daily.py` | SPY→^GSPC, validate_record 통합 |
| `scripts/naver_scraper.py` | investor max_pages 동적 감지 |
| `scripts/kofia_excel_parser.py` | validate_record 통합 |
| `scripts/export_web.py` | CREDIT_DATA 전체 기간, COHORT_HISTORY 분리, validate_timeseries 통합 |
| `data/timeseries.json` | 283→6,335일, sp500 5,522건 수정 |
| `web/src/simulators/kospi/CohortAnalysis.jsx` | COHORT_HISTORY lazy load (fetch) |
| `web/src/simulators/kospi/data/kospi_data.js` | 61MB→11MB |
| `web/public/data/cohort_history.json` | **신규** — COHORT_HISTORY 별도 JSON (33MB) |
