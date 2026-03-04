# Plan: KOSPI Crisis Detector v1.1.1 — Bugfix & UX Improvement

> Feature: `kospi-crisis-v1.1.1-bugfix` | Version: 1.1.1 | Created: 2026-03-04
> Parent: `kospi-crisis` Phase 4.1 후속

---

## 1. Overview

### 1.1 Purpose
v4.1 실데이터 통합 후 대시보드 검증 과정에서 발견된 5개 이슈를 수정하고 UX를 개선한다.

### 1.2 Problem Statement

| # | 이슈 | 심각도 | 분류 |
|---|------|--------|------|
| 1 | 신용잔고/예탁금 개별 토글 없음, 기본 기간 ALL | UX | Frontend |
| 2 | 비거래일 X축 갭 (null 값 라인 끊김) | UX | Frontend |
| 3 | 반대매매 섹션 불필요, 투자자 수급이 더 중요 | UX | Frontend |
| 4 | 투자자 수급: 개인/기관 0%, 외국인만 표시 | Critical | Data Pipeline |
| 5 | 코호트 분석 탭 데이터 없음 (LIFO 0, FIFO 0) | Critical | Data Pipeline |

### 1.3 Root Cause Analysis

**Issue 4 — 투자자 수급 데이터 누락**
- pykrx API 파손 (KRX 포맷 변경 2025-02-27) → individual/institution 항상 null
- ECOS 802Y001에 개인/기관 항목코드 없음 (외국인 순매수만 제공)
- **해결**: Naver Finance `investorDealTrendDay.naver` 스크래핑 (억원, 일간)

**Issue 5 — 코호트 데이터 빈 결과**
- Naver 예탁금/신용잔고 데이터가 2026-02-27까지만 존재
- 2026-03-03의 credit = null → `compute_models.py`에서 `or 0` = 0
- delta = 0 - 32188.1 = -32188.1 → 전체 32조원 코호트 일괄 "상환"
- **해결**: null credit → carry-forward (직전 유효값 유지)

### 1.4 Scope
- **In Scope**: Naver 투자자 스크래퍼, compute_models 코호트 버그, MarketPulse UI 개선
- **Out of Scope**: pykrx 대체 (여전히 broken), CohortAnalysis.jsx 수정, 신규 기능

---

## 2. Implementation Plan

### 2.1 Data Pipeline Fixes

| 파일 | 작업 | 설명 |
|------|------|------|
| `kospi/scripts/naver_scraper.py` | 추가 | `fetch_naver_investor_flows()` — 투자자별 매매동향 스크래핑 |
| `kospi/scripts/fetch_daily.py` | 수정 | 6-step pipeline (Naver investor 추가), build_snapshot 통합 |
| `kospi/scripts/compute_models.py` | 수정 | null credit carry-forward 로직 |
| `kospi/scripts/export_web.py` | 수정 | financial_invest_billion 직접 사용 (추정 제거) |

### 2.2 Frontend Fixes

| 파일 | 작업 | 설명 |
|------|------|------|
| `web/src/simulators/kospi/MarketPulse.jsx` | 수정 | 토글, 3M 기본, 반대매매 삭제, 섹션 재배치, connectNulls |

---

## 3. Acceptance Criteria

- [ ] 투자자 수급 282일 (개인/외국인/기관/금투 전부 non-null)
- [ ] 코호트 LIFO/FIFO > 100개
- [ ] 반대매매 섹션 제거
- [ ] 투자자 수급 → 신용잔고 순서
- [ ] 신용/예탁 토글 동작
- [ ] 기본 기간 3M
- [ ] vite build 성공

---

**Status**: Completed
