# PDCA Completion Report: kospi-v2.1.1-kofia-credit-pipeline

> **Feature**: KOFIA API로 신용잔고/예탁금/반대매매 소스 전환
> **Version**: v2.1.1
> **Match Rate**: 95.8% → 100% (4 gaps fixed)
> **Iterations**: 0 (single pass)
> **Date**: 2026-03-06

---

## 1. Summary

Naver Finance 스크래핑(D-2, 불안정) → 공공데이터포털 KOFIA API(D-2, 안정적 JSON)로 신용잔고/예탁금/반대매매 데이터 소스 전환. 추가로 수동 오버라이드 시스템과 backfill CLI 구현.

### Key Achievements

| 항목 | Before | After |
|------|--------|-------|
| 신용잔고 소스 | Naver 스크래핑 (HTML) | data.go.kr API (JSON) |
| 예탁금 소스 | Naver 스크래핑 | data.go.kr API |
| 반대매매 | OLS 추정 (None) | **실제 금액** (API 직접 제공) |
| 안정성 | HTML 변경 시 중단 | REST JSON |
| 속도 | ~90초 (294페이지) | ~2초 (2 API calls) |
| 과거 데이터 | 대부분 None | 282일 반대매매 실데이터 backfill 완료 |
| 수동 보완 | 불가 | JSON + CLI 오버라이드 |

---

## 2. Implementation Details

### 2.1 Modified Files

| File | Changes |
|------|---------|
| `scripts/kofia_fetcher.py` | 전면 재작성: 2-operation API, lazy API key, backfill 지원 |
| `scripts/fetch_daily.py` | KOFIA 통합, --backfill-credit, --manual, --apply-overrides |
| `data/manual_overrides.json` | 신규: 관리자 수동 입력 파일 |

### 2.2 New CLI Commands

```bash
python -m scripts.fetch_daily --backfill-credit    # KOFIA API로 과거 갭 일괄 패치
python -m scripts.fetch_daily --manual 2026-03-04   # 대화형 수동 입력
python -m scripts.fetch_daily --apply-overrides      # JSON 오버라이드 적용
python -m scripts.kofia_fetcher --test 2026-03-03   # API 단독 테스트
```

### 2.3 Data Pipeline

```
KOFIA API (data.go.kr)
  ├─ getGrantingOfCreditBalanceInfo → credit_balance_billion
  └─ getSecuritiesMarketTotalCapitalInfo → deposit_billion + forced_liq_billion
       │
       ▼ (실패 시)
Naver Scraper (fallback)
       │
       ▼
manual_overrides.json (admin override)
       │
       ▼
timeseries.json → export_web → kospi_data.js → Web Dashboard
```

---

## 3. Gap Analysis Results

| # | Gap | Impact | Resolution |
|---|-----|--------|-----------|
| 1 | unsettled_billion 미포함 (timeseries) | Low | append_timeseries에 추가 |
| 2 | credit_source 미포함 (timeseries) | Low | append_timeseries에 추가 |
| 3 | kospi_balance_billion 미포함 (snapshot) | Low | build_snapshot에 추가 |
| 4 | --test CLI 없음 (kofia_fetcher) | Low | __main__ 블록 추가 |

**All 4 gaps resolved in same session.**

---

## 4. Verification

| Check | Status |
|-------|--------|
| API 호출 성공 (2026-02-27, 3/3) | PASS |
| Naver 교차 검증 (예탁금 100%, 신용 ~98%) | PASS |
| backfill 282일 완료 | PASS |
| compute_models 성공 | PASS |
| export_web 성공 | PASS |
| npm run build 성공 | PASS |

---

## 5. Known Limitations

- **D-2 lag**: API도 Naver와 동일하게 D-2 지연 (FreeSIS 웹은 D-1일 수 있으나 SPA 보호)
- **신용잔고 차이 ~2%**: API `crdTrFingWhl` (융자 전체) vs Naver (융자+대주 합산 방식 상이)
- **3/4~3/5 데이터 없음**: API 미제공, 수동 오버라이드로 보완 가능

---

## 6. Lessons Learned

1. **모듈 로드 시점 vs 환경변수**: `os.getenv()`가 모듈 import 시 평가되면 dotenv 로드 전에 빈 값. → lazy 함수(`_api_key()`)로 해결
2. **Naver 호환성**: KOSPI-only vs 전체 신용잔고 — 기존 데이터와 일관성 유지가 중요
3. **공공데이터포털 단위**: 원(Won) 단위로 통일, /1e9로 십억원 변환
