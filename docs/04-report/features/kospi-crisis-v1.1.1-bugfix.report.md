# KOSPI Crisis Detector v1.1.1 — Bugfix & UX Improvement Report

> **Summary**: v4.1 실데이터 통합 후 발견된 5개 이슈 수정 — 투자자 수급 Naver 스크래퍼, 코호트 null carry-forward, MarketPulse UI 개선
>
> **Feature**: kospi-crisis-v1.1.1-bugfix
> **Version**: v1.1.1
> **Author**: Sungmin Kim
> **Created**: 2026-03-04
> **Status**: Approved (Match Rate 100%)

---

## 1. Overview

### 1.1 Feature Summary

v4.1 실데이터 통합 후 대시보드 검증에서 발견된 5개 이슈:
1. **신용잔고/예탁금 토글**: 개별 on/off 토글 + 기본 기간 3M
2. **비거래일 갭**: null 값으로 인한 라인 끊김 → connectNulls
3. **섹션 재배치**: 반대매매 삭제, 투자자 수급 최상단 이동
4. **투자자 수급 데이터**: Naver investorDealTrendDay 스크래핑 (282일)
5. **코호트 빈 결과**: null credit carry-forward 버그 수정

### 1.2 PDCA Cycle

| Phase | Status | Outcome |
|-------|--------|---------|
| **Plan** | Completed | 5개 이슈 근본 원인 분석 + 수정 방안 |
| **Design** | Completed | Naver investor 스크래퍼, carry-forward, UI 변경 설계 |
| **Do** | Completed | 5개 파일 수정, 파이프라인 재실행 |
| **Check** | Completed | Match Rate 100% |
| **Report** | Completed | 본 보고서 |

---

## 2. Root Cause Analysis

### 2.1 Issue 4: 투자자 수급 데이터 누락

```
pykrx (KRX API 파손, 2025-02-27) → individual/institution = null
ECOS 802Y001 → 외국인 순매수만 제공 (개인/기관 항목코드 없음)
→ 해결: Naver Finance investorDealTrendDay.naver 스크래핑
  URL: ?bizdate={date}&sosok=01&page={n}
  단위: 억원, 11컬럼 (날짜/개인/외국인/기관계/금투/보험/투신/은행/기타금융/연기금/기타법인)
  결과: 282일 × 4필드 (individual, foreign, institution, financial_invest)
```

### 2.2 Issue 5: 코호트 빈 결과

```
Naver 데이터 끝: 2026-02-27 (credit = 32188.1)
2026-03-03: credit = null → or 0 = 0
delta = 0 - 32188.1 = -32188.1 → 모든 코호트 일괄 청산!
→ 해결: null credit → carry-forward (직전 유효값 유지)
  결과: LIFO 130, FIFO 127 코호트 정상 생성
```

---

## 3. Changes

### 3.1 Data Pipeline

| File | Change | Lines |
|------|--------|-------|
| `kospi/scripts/naver_scraper.py` | +`fetch_naver_investor_flows()` | +120 |
| `kospi/scripts/fetch_daily.py` | 6-step pipeline, Naver investor 통합 | +39 |
| `kospi/scripts/compute_models.py` | null credit carry-forward | +13 |
| `kospi/scripts/export_web.py` | financial_invest_billion 직접 사용 | +11/-6 |

### 3.2 Frontend

| File | Change |
|------|--------|
| `MarketPulse.jsx` | 반대매매 삭제 (-50줄), 투자자 수급 최상단, 신용/예탁 토글, 3M 기본, connectNulls |

### 3.3 Data Quality Improvement

| Metric | Before | After |
|--------|--------|-------|
| individual_billion | 0% (null) | **100%** (282/282) |
| institution_billion | 0% (null) | **100%** (282/282) |
| financial_invest_billion | N/A | **100%** (282/282) |
| foreign_billion | 99.6% | **100%** (282/282) |
| Cohort LIFO | 0 | **130** |
| Cohort FIFO | 0 | **127** |

---

## 4. Verification

| Test | Result |
|------|--------|
| Naver investor 282일 | PASS |
| compute_models cohort 생성 | PASS (LIFO 130, FIFO 127) |
| export_web 13 exports | PASS |
| vite build | PASS (2.05s, no errors) |
| 반대매매 섹션 제거 | PASS |
| 투자자 수급 최상단 | PASS |
| 신용/예탁 토글 | PASS |
| 기본 3M 기간 | PASS |
| connectNulls 적용 | PASS |

---

## 5. Lessons Learned

### What Went Well
1. **Naver investor 스크래핑**: 안정적 HTML 구조, `sosok=01&bizdate` 파라미터로 쉽게 페이지네이션
2. **근본 원인 분석**: 코호트 빈 결과의 원인을 데이터 흐름 추적으로 정확히 파악
3. **carry-forward 패턴**: null 데이터 처리의 표준 방법으로 재사용 가능

### Areas for Improvement
1. **Naver 데이터 지연**: 예탁금/신용잔고가 T-3~5 지연 → 최근 며칠 null 불가피
2. **pykrx 여전히 broken**: KRX API 자체 변경으로 복구 불가, Naver 대체 완료

---

## 6. Next Steps

| Priority | Action | Phase |
|----------|--------|-------|
| 1 | CohortAnalysis.jsx 데이터 연결 검증 | Phase 4.2 |
| 2 | GitHub Actions cron 자동화 | Phase 5 |
| 3 | Vercel 배포 | Phase 5 |

---

**Report Generated**: 2026-03-04
**Gap Analysis Reference**: `docs/03-analysis/kospi-crisis-v1.1.1-bugfix.analysis.md`
