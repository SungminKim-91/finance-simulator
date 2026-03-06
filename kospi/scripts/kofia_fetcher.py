#!/usr/bin/env python3
"""
금투협(KOFIA) 신용공여잔고/예탁금/반대매매 데이터 수집.

소스: 공공데이터포털 data.go.kr — GetKofiaStatisticsInfoService
  - Operation 1: getGrantingOfCreditBalanceInfo (신용공여잔고추이)
  - Operation 2: getSecuritiesMarketTotalCapitalInfo (증시자금추이)

환경변수: DATA_GO_KR_API_KEY (.env)
단위: API 원(Won) → /1e9 = 십억원(billion)
"""
import os

try:
    import requests
except ImportError:
    requests = None

BASE_URL = "https://apis.data.go.kr/1160100/service/GetKofiaStatisticsInfoService"
TIMEOUT = 10


def _api_key() -> str:
    """환경변수에서 API 키 조회 (lazy — dotenv 로드 후에도 작동)."""
    return os.getenv("DATA_GO_KR_API_KEY", "")


def _get(operation: str, params: dict) -> list[dict]:
    """공통 API 호출. items 리스트 반환, 실패 시 빈 리스트."""
    key = _api_key()
    if not requests or not key:
        return []

    params = {
        "serviceKey": key,
        "resultType": "json",
        **params,
    }
    try:
        resp = requests.get(f"{BASE_URL}/{operation}", params=params, timeout=TIMEOUT)
        if resp.status_code != 200:
            print(f"  [KOFIA] HTTP {resp.status_code} for {operation}")
            return []
        data = resp.json()
        body = data.get("response", {}).get("body", {})
        if body.get("totalCount", 0) == 0:
            return []
        items = body.get("items", {}).get("item", [])
        return items if isinstance(items, list) else [items]
    except Exception as e:
        print(f"  [KOFIA] {operation} error: {e}")
        return []


def _to_billion(value) -> float | None:
    """원(Won) → 십억원(billion). 문자열/숫자 모두 처리."""
    if value is None:
        return None
    try:
        return round(float(str(value).replace(",", "")) / 1e9, 1)
    except (ValueError, TypeError):
        return None


def fetch_credit_balance(date: str) -> dict | None:
    """신용공여잔고 조회 (Operation 1).

    Returns: {credit_balance_billion, credit_total_billion, ...} or None
    """
    items = _get("getGrantingOfCreditBalanceInfo", {
        "numOfRows": 1, "pageNo": 1,
        "basDt": date.replace("-", ""),
    })
    if not items:
        return None

    it = items[0]
    return {
        "date": it.get("basDt", date.replace("-", "")),
        "credit_balance_billion": _to_billion(it.get("crdTrFingScrs")),
        "credit_kosdaq_billion": _to_billion(it.get("crdTrFingKosdaq")),
        "credit_total_billion": _to_billion(it.get("crdTrFingWhl")),
    }


def fetch_market_fund(date: str) -> dict | None:
    """증시자금추이 조회 (Operation 2).

    Returns: {deposit_billion, forced_liq_billion, unsettled_billion, ...} or None
    """
    items = _get("getSecuritiesMarketTotalCapitalInfo", {
        "numOfRows": 1, "pageNo": 1,
        "basDt": date.replace("-", ""),
    })
    if not items:
        return None

    it = items[0]
    return {
        "date": it.get("basDt", date.replace("-", "")),
        "deposit_billion": _to_billion(it.get("invrDpsgAmt")),
        "forced_liq_billion": _to_billion(it.get("brkTrdUcolMnyVsOppsTrdAmt")),
        "unsettled_billion": _to_billion(it.get("brkTrdUcolMny")),
    }


def fetch_all(date: str) -> dict | None:
    """2개 API 통합 호출. 하나라도 성공하면 결과 반환."""
    credit = fetch_credit_balance(date)
    fund = fetch_market_fund(date)

    if not credit and not fund:
        return None

    result = {"date": date, "source": "data.go.kr"}

    if credit:
        result["credit_balance_billion"] = credit["credit_total_billion"]  # 전체 (Naver 호환)
        result["credit_kospi_billion"] = credit["credit_balance_billion"]  # KOSPI만 (참고용)

    if fund:
        result["deposit_billion"] = fund["deposit_billion"]
        result["forced_liq_billion"] = fund["forced_liq_billion"]
        result["unsettled_billion"] = fund["unsettled_billion"]

    return result


def backfill_credit(start: str, end: str) -> list[dict]:
    """날짜 범위의 데이터를 일괄 조회 (페이지네이션).

    Returns: [{date, credit_balance_billion, deposit_billion, forced_liq_billion, ...}, ...]
    """
    start_d = start.replace("-", "")
    end_d = end.replace("-", "")

    results = []
    page_size = 500

    # Operation 1: 신용잔고 일괄 (페이지네이션)
    credit_map = {}
    for page_no in range(1, 20):  # 최대 10000일 (약 40년)
        items = _get("getGrantingOfCreditBalanceInfo", {
            "numOfRows": page_size, "pageNo": page_no,
        })
        if not items:
            break
        for it in items:
            d = it.get("basDt", "")
            if start_d <= d <= end_d:
                credit_map[d] = {
                    "credit_balance_billion": _to_billion(it.get("crdTrFingWhl")),
                }
        # API가 최신→과거 순이면, 마지막 항목이 start보다 이전이면 중단
        last_d = items[-1].get("basDt", "")
        if last_d < start_d:
            break
        if len(items) < page_size:
            break

    # Operation 2: 증시자금 일괄 (페이지네이션)
    fund_map = {}
    for page_no in range(1, 20):
        items = _get("getSecuritiesMarketTotalCapitalInfo", {
            "numOfRows": page_size, "pageNo": page_no,
        })
        if not items:
            break
        for it in items:
            d = it.get("basDt", "")
            if start_d <= d <= end_d:
                fund_map[d] = {
                    "deposit_billion": _to_billion(it.get("invrDpsgAmt")),
                    "forced_liq_billion": _to_billion(it.get("brkTrdUcolMnyVsOppsTrdAmt")),
                    "unsettled_billion": _to_billion(it.get("brkTrdUcolMny")),
                }
        last_d = items[-1].get("basDt", "")
        if last_d < start_d:
            break
        if len(items) < page_size:
            break

    # Merge
    all_dates = sorted(set(list(credit_map.keys()) + list(fund_map.keys())))
    for d in all_dates:
        entry = {"date": d, "source": "data.go.kr"}
        entry.update(credit_map.get(d, {}))
        entry.update(fund_map.get(d, {}))
        results.append(entry)

    print(f"  [KOFIA backfill] credit={len(credit_map)}일, fund={len(fund_map)}일, merged={len(results)}일")
    return results


if __name__ == "__main__":
    import sys
    from dotenv import load_dotenv
    from pathlib import Path

    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

    date = sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--test" else "2026-03-03"
    print(f"Testing KOFIA API for {date}...")

    result = fetch_all(date)
    if result:
        for k, v in result.items():
            print(f"  {k}: {v}")
    else:
        print("  No data available")
