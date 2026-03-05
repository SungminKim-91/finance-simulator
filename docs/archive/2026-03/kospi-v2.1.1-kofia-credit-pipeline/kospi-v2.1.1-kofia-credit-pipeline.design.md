# kospi-v2.1.1-kofia-credit-pipeline Design Document

> **Summary**: data.go.kr KOFIA API로 신용잔고/예탁금/반대매매 데이터 소스 전환 + 수동 오버라이드 + backfill
>
> **Plan**: `docs/01-plan/features/kospi-v2.1.1-kofia-credit-pipeline.plan.md`
> **Author**: sungmin
> **Date**: 2026-03-06
> **Status**: Draft

---

## 1. Architecture

### 1.1 Data Flow

```
data.go.kr API ──┐
  (Tier 1)       │
                 ├──→ kofia_fetcher.py ──→ fetch_daily.py ──→ timeseries.json ──→ export_web.py
Naver Scraper ───┘       (3-field)           build_snapshot      append_ts           kospi_data.js
  (Tier 2 fallback)
                                                  ↑
                                       manual_overrides.json
                                         (admin override)
```

### 1.2 API Endpoints (검증 완료)

| # | Operation | URL Suffix | 주요 필드 |
|---|-----------|-----------|----------|
| 1 | 신용공여잔고 | `/getGrantingOfCreditBalanceInfo` | `crdTrFingScrs` (KOSPI 신용융자) |
| 2 | 증시자금추이 | `/getSecuritiesMarketTotalCapitalInfo` | `invrDpsgAmt` (예탁금), `brkTrdUcolMnyVsOppsTrdAmt` (반대매매) |

**Base URL**: `https://apis.data.go.kr/1160100/service/GetKofiaStatisticsInfoService`
**인증**: `DATA_GO_KR_API_KEY` (`.env`)
**단위**: 원(Won) → `/1e9` = 십억원(billion)

### 1.3 교차 검증 결과 (2026-02-27 기준)

| 항목 | API (원) | API (십억원) | Naver (십억원) | 일치율 |
|------|---------|-------------|--------------|-------|
| 신용잔고 (KOSPI) | 21,778,077,000,000 | 21,778.1 | — | — |
| 신용잔고 (전체) | 32,804,073,000,000 | 32,804.1 | 32,188.1 | ~98.1% |
| 예탁금 | 118,748,800,000,000 | 118,748.8 | 118,748.8 | 100% |
| 반대매매 | 16,455,000,000 | 16.5 | — | NEW |

**차이 원인**: API `crdTrFingWhl` = 신용거래융자 전체, Naver = 신용거래잔고(융자+대주 합산 방식 상이)

---

## 2. Module Design

### 2.1 `kofia_fetcher.py` — 전면 재작성

```python
# 현재: 3-tier stub (모두 None 반환)
# 변경: Tier 1 완전 구현 + Tier 2 제거 (FreeSIS 불필요)

BASE_URL = "https://apis.data.go.kr/1160100/service/GetKofiaStatisticsInfoService"
API_KEY = os.getenv("DATA_GO_KR_API_KEY", "")  # 환경변수명 변경

def fetch_credit_balance(date: str) -> dict | None:
    """KOFIA API로 신용잔고 조회. 실패 시 None → Naver fallback."""

def fetch_market_fund(date: str) -> dict | None:
    """KOFIA API로 예탁금 + 반대매매 조회. 실패 시 None."""

def fetch_all(date: str) -> dict | None:
    """2개 API 통합 호출. 하나라도 성공하면 결과 반환."""
    return {
        "date": date,
        "credit_balance_billion": ...,    # crdTrFingScrs / 1e9
        "credit_total_billion": ...,      # crdTrFingWhl / 1e9
        "deposit_billion": ...,           # invrDpsgAmt / 1e9
        "forced_liq_billion": ...,        # brkTrdUcolMnyVsOppsTrdAmt / 1e9
        "unsettled_billion": ...,         # brkTrdUcolMny / 1e9
        "source": "data.go.kr",
    }

def backfill_credit(start: str, end: str) -> list[dict]:
    """날짜 범위의 신용잔고를 일괄 조회 (numOfRows=365)."""
```

**반환값 변경**: 기존 `kospi_stock_credit_mm` (백만원) → `credit_balance_billion` (십억원)으로 통일.

### 2.2 `fetch_daily.py` — `build_snapshot()` 변경

```python
# 현재 (line 297-303):
kofia_credit = fetch_kofia_credit(date)
if kofia_credit:
    credit_b = kofia_credit["kospi_stock_credit_mm"] / 1e3

# 변경:
from scripts.kofia_fetcher import fetch_all as fetch_kofia_all

kofia = fetch_kofia_all(date)
if kofia:
    credit_b = kofia["credit_balance_billion"]
    deposit_b = kofia["deposit_billion"] or deposit_b   # Naver fallback 유지
    forced_liq_b = kofia["forced_liq_billion"]
    credit_source = kofia["source"]
```

### 2.3 `fetch_daily.py` — `--backfill-credit` CLI 추가

```python
def backfill_credit_data():
    """timeseries.json에서 credit=None인 날짜만 KOFIA API로 패치."""
    # 1. timeseries.json 로드
    # 2. credit_balance_billion이 None인 날짜 수집
    # 3. kofia_fetcher.backfill_credit(start, end) 일괄 호출
    # 4. 결과 머지 (기존 값 보존, None만 채움)
    # 5. 저장
```

### 2.4 `append_timeseries()` — 새 필드 추가

| 필드 | 타입 | 설명 |
|------|------|------|
| `credit_source` | string | `"data.go.kr"` / `"naver"` / `"manual"` |
| `forced_liq_billion` | float | 반대매매 실제금액 (기존 None → API값) |
| `unsettled_billion` | float | 미수금 (신규) |

### 2.5 수동 오버라이드 (이미 구현)

- `kospi/data/manual_overrides.json` — 자유 필드 JSON
- `--manual DATE` — 대화형 CLI
- `--apply-overrides` — JSON → timeseries.json 머지

---

## 3. Implementation Order

| # | Task | File | Deps |
|---|------|------|------|
| 1 | `kofia_fetcher.py` 전면 재작성 | `scripts/kofia_fetcher.py` | — |
| 2 | `fetch_daily.py` build_snapshot 통합 | `scripts/fetch_daily.py` | #1 |
| 3 | `--backfill-credit` CLI 추가 | `scripts/fetch_daily.py` | #1 |
| 4 | `append_timeseries` 새 필드 추가 | `scripts/fetch_daily.py` | #2 |
| 5 | API 호출 테스트 (3/3 교차검증) | — | #1 |
| 6 | backfill 실행 (2/27까지 갭 해소) | — | #3 |
| 7 | `export_web.py` forced_liq 전달 확인 | `scripts/export_web.py` | #4 |
| 8 | `npm run build` 검증 | — | #7 |

---

## 4. Error Handling

### 4.1 API 실패 시나리오

| 시나리오 | 처리 |
|---------|------|
| API key 미설정 | Skip, Naver fallback |
| 네트워크 타임아웃 (10s) | Skip, Naver fallback |
| 해당 날짜 데이터 없음 (totalCount=0) | None 반환, Naver fallback |
| JSON 파싱 오류 | Warn + None 반환 |
| 일일 호출 한도 초과 | Warn + None 반환, 다음 실행에서 재시도 |

### 4.2 Fallback Chain

```
fetch_all(date)
  ├─ API 성공 → credit + deposit + forced_liq 모두 반환
  ├─ API 부분 성공 → 성공한 필드만 반환, 나머지 None
  └─ API 전체 실패 → None → build_snapshot에서 Naver fallback
```

---

## 5. Data Model Changes

### 5.1 timeseries.json 레코드 변경

```diff
 {
   "date": "2026-03-03",
   "credit_balance_billion": 32188.1,
+  "credit_source": "data.go.kr",
   "deposit_billion": 118748.8,
-  "forced_liq_billion": null,
+  "forced_liq_billion": 16.5,
+  "unsettled_billion": 893.2,
   ...
 }
```

### 5.2 daily/{date}.json snapshot 변경

```diff
 "credit": {
-  "total_balance_billion": 32188.1,
+  "total_balance_billion": 32188.1,    // Naver 전체 or API KOSPI
+  "kospi_balance_billion": 21778.1,    // API only: 유가증권
+  "source": "data.go.kr",
 },
 "settlement": {
-  "forced_liquidation_billion": null,
+  "forced_liquidation_billion": 16.5,  // API 실제값
+  "unsettled_margin_billion": 893.2,   // API 미수금
 }
```

---

## 6. Testing Strategy

### 6.1 교차 검증

```bash
# 단일 날짜 비교 (API vs Naver)
python -m scripts.kofia_fetcher --test 2026-02-27

# 결과:
# credit: API 21778.1B (KOSPI) vs Naver 32188.1B (전체) → 차이는 코스닥 포함 여부
# deposit: 100% 일치
# forced_liq: NEW (Naver에 없음)
```

### 6.2 backfill 검증

```bash
# 과거 갭 패치
python -m scripts.fetch_daily --backfill-credit

# 확인: timeseries.json에서 credit=None 레코드 수 → 0
```

### 6.3 빌드 검증

```bash
python -m scripts.compute_models && python -m scripts.export_web
cd ../web && npm run build
```

---

## 7. Environment

| Variable | Value | Note |
|----------|-------|------|
| `DATA_GO_KR_API_KEY` | `.env` (보안) | 공공데이터포털 일반인증키 |

**기존 `KOFIA_API_KEY`** → **`DATA_GO_KR_API_KEY`**로 변경 (`.env`에 이미 존재)

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-03-06 | Initial design — API 검증 완료 기반 | sungmin |
