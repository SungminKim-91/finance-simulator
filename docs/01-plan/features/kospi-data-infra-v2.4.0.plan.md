# Plan: kospi-data-infra-v2.4.0

> 25년 데이터 확장 + 파이프라인 단위 검증 + OOM 수정

## 1. 배경

KOSPI Crisis Detector의 timeseries가 283일(~1년)로 제한되어 있어 장기 분석이 불가능.
KOFIA 엑셀 데이터(2000~2026)를 import하고, 나머지 필드를 yfinance/Naver로 채워 25년 히스토리를 구축.
데이터 확장 과정에서 단위 불일치(SPY vs ^GSPC), OOM(61MB JS 파일), 파이프라인 검증 부재 등 구조적 문제 발견 및 수정.

## 2. 목표

| 목표 | 기준 |
|------|------|
| timeseries 기간 | 283일 → 6,335일 (2000-12 ~ 2026-03) |
| 주요 필드 커버리지 | 80%+ |
| 단위 검증 | 파이프라인 전체 (fetch/parse/export) |
| Vite OOM | 해결 (COHORT_HISTORY 분리) |
| S&P 500 정확도 | ^GSPC 인덱스 (SPY ETF 아님) |

## 3. 범위

### In-Scope
- KOFIA 엑셀 3파일 import (예탁금, 신용잔고, 시장지표)
- yfinance 25년 backfill (samsung, hynix, kosdaq, usd_krw, vix, wti, sp500, ewy, koru)
- Naver investor 21년 확장 (개인/외국인/기관, max_pages 동적 감지)
- validate_data.py 모듈 (27개 필드 기대 범위)
- fetch_daily.py SPY→^GSPC 수정
- export_web.py CREDIT_DATA 전체 기간 빌드
- COHORT_HISTORY → public/data/cohort_history.json 분리 (lazy load)

### Out-of-Scope
- 모델(RSPI) 변경 없음
- 프론트엔드 UI 변경 없음 (COHORT_HISTORY lazy load 제외)

## 4. 데이터 소스

| 소스 | 필드 | 기간 | 비용 |
|------|------|------|------|
| KOFIA 엑셀 | credit, deposit, forced_liq, kospi, market_cap, trading_value | 2000-12 ~ 2026-03 | 무료 |
| yfinance | samsung, hynix, kosdaq, usd_krw, vix, wti, sp500, ewy, koru | 2000-12 ~ 2026-03 | 무료 |
| Naver investor | individual, foreign, institution | 2005-01 ~ 2025-12 | 무료 |
| ECOS | foreign (보조) | 2000 ~ 현재 | API 10만건/일 |
