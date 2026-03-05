# kospi-v2.1.1-kofia-credit-pipeline Planning Document

> **Summary**: Naver 스크래핑(D-2) → KOFIA 공공데이터포털 API(D-1)로 신용잔고/예탁금/반대매매 데이터 소스 전환
>
> **Project**: KOSPI Crisis Detector
> **Version**: v2.1.1
> **Author**: sungmin
> **Date**: 2026-03-05
> **Status**: Draft

---

## 1. Overview

### 1.1 Purpose

현재 신용잔고/예탁금 데이터는 Naver Finance 스크래핑(`sise_deposit.naver`)에 의존하며 D-2 지연이 발생한다.
금융투자협회(KOFIA)가 공공데이터포털에 제공하는 **GetKofiaStatisticsInfoService** API를 통해 D-1 데이터를 직접 확보하고, 추가로 **반대매매 실제 금액**까지 획득한다.

### 1.2 Background

| 항목 | 현재 (Naver) | 목표 (KOFIA API) |
|------|-------------|-----------------|
| **신용잔고** | D-2, 스크래핑 | D-1, 공식 API |
| **예탁금** | D-2, 스크래핑 | D-1, 공식 API (투자자예탁금) |
| **반대매매** | OLS 추정 (estimate_missing.py) | **실제 금액** (API 직접 제공) |
| **안정성** | HTML 구조 변경 시 중단 | REST API (JSON) |
| **속도** | 294페이지 스크래핑 ~90초 | 단일 API 호출 ~1초 |

### 1.3 API Discovery 결과

**Base URL**: `https://apis.data.go.kr/1160100/service/GetKofiaStatisticsInfoService`
**데이터셋**: [금융위원회_금융투자협회종합통계정보](https://www.data.go.kr/data/15094809/openapi.do)
**인증**: data.go.kr serviceKey (무료 발급, 즉시 활성화)

#### Operation 1: `getGrantingOfCreditBalanceInfo` (신용공여잔고추이)

| Field | Type | Description |
|-------|------|-------------|
| `basDt` | string | YYYYMMDD 기준일자 |
| `crdTrFingScrs` | number | **신용거래융자 유가증권** (= KOSPI 신용잔고) |
| `crdTrFingKosdaq` | number | 신용거래융자 코스닥 |
| `crdTrFingWhl` | number | 신용거래융자 전체 (유가+코스닥) |
| `crdTrLndrScrs` | number | 신용거래대주 유가증권 |
| `crdTrLndrKosdaq` | number | 신용거래대주 코스닥 |
| `crdTrLndrWhl` | number | 신용거래대주 전체 |
| `sbscCapLn` | number | 청약자금 대출 |
| `dpsgScrtMogFing` | number | 예탁증권 담보융자 |

**Parameters**: `serviceKey`, `numOfRows`, `pageNo`, `basDt` (YYYYMMDD), `resultType` (json/xml)

#### Operation 2: `getSecuritiesMarketTotalCapitalInfo` (증시자금추이)

| Field | Type | Description |
|-------|------|-------------|
| `basDt` | string | YYYYMMDD 기준일자 |
| `invrDpsgAmt` | number | **투자자예탁금** (파생 예수금 제외) |
| `brkTrdUcolMny` | number | **위탁매매 미수금** |
| `brkTrdUcolMnyVsOppsTrdAmt` | number | **실제 반대매매금액** |
| `ucolMnyVsOppsTrdRlImpt` | number | 미수금 대비 반대매매비중(%) |
| `onbdDrvPrdTrRcAdvAmt` | number | 장내파생상품 거래 예수금 |
| `toCstRpchCndBndSlgBal` | number | RP 매도잔고 |

**Parameters**: `serviceKey`, `numOfRows`, `pageNo`, `basDt` (YYYYMMDD), `resultType` (json/xml)

### 1.4 Related Documents

- Design: `docs/02-design/features/kospi-v2.1.1-kofia-credit-pipeline.design.md` (TBD)
- Current pipeline: `kospi/scripts/fetch_daily.py`, `kospi/scripts/kofia_fetcher.py`

---

## 2. Scope

### 2.1 In Scope

- [x] KOFIA API 연동 (`kofia_fetcher.py` Tier 1 구현)
- [x] 신용잔고: `crdTrFingScrs` (유가증권) → `credit_balance_billion`
- [x] 예탁금: `invrDpsgAmt` → `deposit_billion`
- [x] 반대매매: `brkTrdUcolMnyVsOppsTrdAmt` → `forced_liq_billion` (실제값!)
- [x] Naver fallback 유지 (API 장애 시)
- [x] `--backfill-credit` 명령: 과거 데이터 KOFIA API로 일괄 패치
- [x] Raw Data 탭에서 RSPI 계산치 제거 (완료)
- [x] 환경변수: `DATA_GO_KR_API_KEY` (`.env`)

### 2.2 Out of Scope

- FreeSIS SPA 리버스엔지니어링 (Tier 2) — SPA 보호 강력, 불필요
- KOFIA OpenAPI (openapi.kofia.or.kr) — 별도 서비스, 학습진도 등 무관 데이터
- 코스닥 신용잔고 분리 표시 (향후 v2.2.0)
- API key 자동 발급/갱신

---

## 3. Requirements

### 3.1 Functional Requirements

| ID | Requirement | Priority | Status |
|----|-------------|----------|--------|
| FR-01 | KOFIA API로 일별 신용잔고(유가증권) 조회 | High | Pending |
| FR-02 | KOFIA API로 일별 투자자예탁금 조회 | High | Pending |
| FR-03 | KOFIA API로 일별 반대매매 실제금액 조회 | High | Pending |
| FR-04 | API 실패 시 Naver 스크래핑 fallback | Medium | Pending |
| FR-05 | `--backfill-credit` CLI로 과거 데이터 패치 | Medium | Pending |
| FR-06 | 단위 변환: API 원단위(백만원?) → 십억원(billion) | High | Pending |
| FR-07 | timeseries.json에 `credit_source` 필드 추가 | Low | Pending |

### 3.2 Non-Functional Requirements

| Category | Criteria | Measurement |
|----------|----------|-------------|
| Performance | API 1회 호출 < 3초 | requests timeout |
| Reliability | Naver fallback 100% | 단위 테스트 |
| Data Freshness | D-1 (전일 데이터) | 날짜 비교 |

---

## 4. Success Criteria

### 4.1 Definition of Done

- [ ] KOFIA API로 3/4 날짜 신용잔고 조회 성공
- [ ] 투자자예탁금 + 반대매매금액 동시 확보
- [ ] `fetch_daily` 실행 시 KOFIA → Naver fallback 체인 작동
- [ ] 3/3~3/5 데이터 갭 해소
- [ ] `npm run build` 성공
- [ ] Raw Data 탭에서 RSPI 계산치 미표시 (완료)

### 4.2 Quality Criteria

- [ ] API 응답 파싱 정확성 (Naver 값과 교차 검증)
- [ ] timeseries.json 기존 데이터 보존
- [ ] 빌드 성공

---

## 5. Risks and Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| data.go.kr API key 필요 | High | High | 사용자가 직접 발급 (즉시, 무료) |
| API 응답 단위 불명확 (백만원? 억원?) | Medium | Medium | 첫 호출로 Naver 값과 교차 검증 |
| API 일일 호출 한도 | Low | Low | 배치 페이지네이션 (numOfRows=100) |
| D-1 아닌 D-2일 수 있음 | Medium | Low | 실측으로 확인 |

---

## 6. Implementation Plan

### 6.1 Step 1: `kofia_fetcher.py` Tier 1 구현

```python
BASE_URL = "https://apis.data.go.kr/1160100/service/GetKofiaStatisticsInfoService"

def _fetch_credit_from_data_go_kr(date: str) -> dict | None:
    """Operation: getGrantingOfCreditBalanceInfo"""
    resp = requests.get(f"{BASE_URL}/getGrantingOfCreditBalanceInfo", params={
        "serviceKey": API_KEY,
        "numOfRows": 1,
        "pageNo": 1,
        "resultType": "json",
        "basDt": date.replace("-", ""),
    })
    item = resp.json()["response"]["body"]["items"]["item"][0]
    return {
        "credit_kospi_mm": item["crdTrFingScrs"],    # 유가증권 신용융자
        "credit_kosdaq_mm": item["crdTrFingKosdaq"],  # 코스닥 신용융자
        "credit_total_mm": item["crdTrFingWhl"],      # 전체
    }

def _fetch_market_fund_from_data_go_kr(date: str) -> dict | None:
    """Operation: getSecuritiesMarketTotalCapitalInfo"""
    resp = requests.get(f"{BASE_URL}/getSecuritiesMarketTotalCapitalInfo", params={...})
    item = resp.json()["response"]["body"]["items"]["item"][0]
    return {
        "deposit_mm": item["invrDpsgAmt"],              # 투자자예탁금
        "forced_liq_mm": item["brkTrdUcolMnyVsOppsTrdAmt"],  # 반대매매금액
        "unsettled_mm": item["brkTrdUcolMny"],           # 미수금
    }
```

### 6.2 Step 2: `fetch_daily.py` 통합

`build_snapshot()`에서:
1. KOFIA API 호출 (2개 operation)
2. 성공: credit, deposit, forced_liq 모두 API 값 사용
3. 실패: Naver fallback (기존 로직 유지)

### 6.3 Step 3: `--backfill-credit` CLI

기존 timeseries.json에서 `credit_balance_billion`이 None인 날짜만 KOFIA API로 패치.
페이지네이션으로 일괄 조회 (numOfRows=365).

### 6.4 Step 4: 검증

1. KOFIA API 값 vs Naver 값 교차 검증 (동일 날짜)
2. 단위 확인 (백만원 vs 억원)
3. 3/3~3/5 데이터 갭 해소 확인

---

## 7. Environment Variables

| Variable | Purpose | Scope |
|----------|---------|-------|
| `DATA_GO_KR_API_KEY` | 공공데이터포털 인증키 | Server (.env) |

**발급 방법**: https://www.data.go.kr → 회원가입 → 활용신청 (자동 승인, 즉시 사용)

---

## 8. Next Steps

1. [ ] 사용자: data.go.kr API key 발급 + `.env`에 추가
2. [ ] Design 문서 작성 (`/pdca design kospi-v2.1.1-kofia-credit-pipeline`)
3. [ ] 구현 + 테스트
4. [ ] Gap analysis

---

## Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 0.1 | 2026-03-05 | Initial draft — API discovery 완료 | sungmin |
