#!/usr/bin/env python3
"""
금투협(KOFIA) 데이터 스크래핑.
D12~D15: 신용거래융자 잔고, 고객예탁금, 위탁매매 미수금, 반대매매 금액.
T+2 지연 — date 파라미터는 실제 데이터 기준일 (2영업일 전).

Usage:
    python kospi/scripts/kofia_scraper.py --date 2026-03-01

Note:
    KOFIA FREESIS 포탈 POST API 리버스 엔지니어링 기반.
    금투협 통계 포탈: https://freesis.kofia.or.kr
"""
import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
except ImportError:
    requests = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

KOFIA_BASE_URL = "https://freesis.kofia.or.kr"

# KOFIA FREESIS API endpoints (reverse-engineered)
CREDIT_URL = f"{KOFIA_BASE_URL}/api/statistics/credit-trading"
DEPOSIT_URL = f"{KOFIA_BASE_URL}/api/statistics/customer-deposit"
SETTLEMENT_URL = f"{KOFIA_BASE_URL}/api/statistics/settlement"

# Retry / rate-limit
MAX_RETRIES = 3
RETRY_DELAY = 2.0
REQUEST_TIMEOUT = 15


class KofiaScrapingError(Exception):
    pass


def _session() -> "requests.Session":
    """공용 세션 — 헤더 + 쿠키 유지."""
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9",
        "Referer": f"{KOFIA_BASE_URL}/",
        "Origin": KOFIA_BASE_URL,
        "Content-Type": "application/json;charset=UTF-8",
    })
    return s


def _post_with_retry(session, url, payload, retries=MAX_RETRIES):
    """POST with retry + exponential backoff."""
    for attempt in range(retries):
        try:
            resp = session.post(url, json=payload, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                return resp.json()
            print(f"  [WARN] KOFIA returned {resp.status_code} for {url}")
        except requests.exceptions.RequestException as e:
            print(f"  [WARN] KOFIA request error (attempt {attempt + 1}): {e}")
        if attempt < retries - 1:
            time.sleep(RETRY_DELAY * (attempt + 1))
    return None


def fetch_kofia_data(date: str) -> dict:
    """
    금투협 데이터 수집 (T+2 지연 반영).

    Args:
        date: 데이터 기준일 (YYYY-MM-DD). 실제로 2영업일 전 데이터.

    Returns:
        {
            "credit": {"total_balance_billion": float, "date": str},
            "deposit": {"customer_deposit_billion": float, "date": str},
            "settlement": {
                "unsettled_margin_billion": float | None,
                "forced_liquidation_billion": float | None,
                "date": str
            }
        }
    """
    if requests is None:
        print("  [WARN] requests not installed")
        return _empty_result(date)

    print(f"  [KOFIA] Fetching data for {date}...")

    result = {
        "credit": {"total_balance_billion": None, "date": date},
        "deposit": {"customer_deposit_billion": None, "date": date},
        "settlement": {
            "unsettled_margin_billion": None,
            "forced_liquidation_billion": None,
            "date": date,
        },
    }

    session = _session()

    try:
        credit_val = _scrape_credit_balance(session, date)
        result["credit"]["total_balance_billion"] = credit_val
    except Exception as e:
        print(f"  [WARN] Credit scraping failed: {e}")

    try:
        deposit_val = _scrape_customer_deposit(session, date)
        result["deposit"]["customer_deposit_billion"] = deposit_val
    except Exception as e:
        print(f"  [WARN] Deposit scraping failed: {e}")

    try:
        settlement = _scrape_settlement(session, date)
        result["settlement"].update(settlement)
    except Exception as e:
        print(f"  [WARN] Settlement scraping failed: {e}")

    return result


def _scrape_credit_balance(session, date: str) -> float | None:
    """신용거래융자 잔고 (십억원).

    KOFIA FREESIS → 투자자별 거래실적 → 신용거래 잔고 현황
    POST payload: 기간, 시장구분(KOSPI+KOSDAQ)
    """
    date_compact = date.replace("-", "")
    payload = {
        "selectType": "1",
        "marketType": "0",  # 전체
        "startDate": date_compact,
        "endDate": date_compact,
    }

    data = _post_with_retry(session, CREDIT_URL, payload)
    if not data:
        return None

    try:
        # KOFIA 응답 구조: { "result": [...], "total": {...} }
        rows = data.get("result") or data.get("data") or data.get("body", {}).get("result", [])
        if isinstance(rows, list) and rows:
            # 마지막 행이 합계 (전체 시장)
            total_row = rows[-1] if len(rows) > 1 else rows[0]
            # 잔고 필드: credit_balance, balance, 등
            balance = (
                total_row.get("credit_balance")
                or total_row.get("balance")
                or total_row.get("잔고")
                or total_row.get("creditBalance")
            )
            if balance is not None:
                # 억원 → 십억원 변환
                return round(float(balance) / 10, 1)
    except (KeyError, ValueError, IndexError, TypeError) as e:
        print(f"  [WARN] Credit parse error: {e}")

    return None


def _scrape_customer_deposit(session, date: str) -> float | None:
    """고객예탁금 (십억원).

    KOFIA → 시장현황 → 고객예탁금 추이
    """
    date_compact = date.replace("-", "")
    payload = {
        "selectType": "1",
        "startDate": date_compact,
        "endDate": date_compact,
    }

    data = _post_with_retry(session, DEPOSIT_URL, payload)
    if not data:
        return None

    try:
        rows = data.get("result") or data.get("data") or data.get("body", {}).get("result", [])
        if isinstance(rows, list) and rows:
            row = rows[-1] if len(rows) > 1 else rows[0]
            deposit = (
                row.get("customer_deposit")
                or row.get("deposit")
                or row.get("예탁금")
                or row.get("customerDeposit")
            )
            if deposit is not None:
                return round(float(deposit) / 10, 1)
    except (KeyError, ValueError, IndexError, TypeError) as e:
        print(f"  [WARN] Deposit parse error: {e}")

    return None


def _scrape_settlement(session, date: str) -> dict:
    """위탁매매 미수금 + 반대매매 금액 (십억원).

    KOFIA → 반대매매/미수금 현황
    """
    date_compact = date.replace("-", "")
    payload = {
        "selectType": "1",
        "startDate": date_compact,
        "endDate": date_compact,
    }

    result = {
        "unsettled_margin_billion": None,
        "forced_liquidation_billion": None,
    }

    data = _post_with_retry(session, SETTLEMENT_URL, payload)
    if not data:
        return result

    try:
        rows = data.get("result") or data.get("data") or data.get("body", {}).get("result", [])
        if isinstance(rows, list) and rows:
            row = rows[-1] if len(rows) > 1 else rows[0]
            unsettled = (
                row.get("unsettled_margin")
                or row.get("미수금")
                or row.get("unsettledMargin")
            )
            forced = (
                row.get("forced_liquidation")
                or row.get("반대매매")
                or row.get("forcedLiquidation")
            )
            if unsettled is not None:
                result["unsettled_margin_billion"] = round(float(unsettled) / 10, 1)
            if forced is not None:
                result["forced_liquidation_billion"] = round(float(forced) / 10, 1)
    except (KeyError, ValueError, IndexError, TypeError) as e:
        print(f"  [WARN] Settlement parse error: {e}")

    return result


def _empty_result(date: str) -> dict:
    return {
        "credit": {"total_balance_billion": None, "date": date},
        "deposit": {"customer_deposit_billion": None, "date": date},
        "settlement": {
            "unsettled_margin_billion": None,
            "forced_liquidation_billion": None,
            "date": date,
        },
    }


def save_kofia_data(date: str, data: dict) -> Path:
    """kospi/data/kofia/{date}.json 저장."""
    kofia_dir = DATA_DIR / "kofia"
    kofia_dir.mkdir(parents=True, exist_ok=True)
    path = kofia_dir / f"{date}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"  Saved: {path}")
    return path


def main():
    parser = argparse.ArgumentParser(description="KOFIA data scraper")
    parser.add_argument("--date", type=str, required=True, help="Date (YYYY-MM-DD)")
    args = parser.parse_args()

    data = fetch_kofia_data(args.date)
    save_kofia_data(args.date, data)

    # Summary
    credit = data["credit"]["total_balance_billion"]
    deposit = data["deposit"]["customer_deposit_billion"]
    forced = data["settlement"]["forced_liquidation_billion"]
    print(f"\n  Credit:  {credit or 'N/A'} B")
    print(f"  Deposit: {deposit or 'N/A'} B")
    print(f"  Forced:  {forced or 'N/A'} B")


if __name__ == "__main__":
    main()
