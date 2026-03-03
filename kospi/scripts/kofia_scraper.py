#!/usr/bin/env python3
"""
금투협(KOFIA) 데이터 스크래핑.
D12~D15: 신용거래융자 잔고, 고객예탁금, 위탁매매 미수금, 반대매매 금액.
T+2 지연 — date 파라미터는 실제 데이터 기준일 (2영업일 전).

Usage:
    python kospi/scripts/kofia_scraper.py --date 2026-03-01

Note:
    Phase 1에서는 stub 구현. 실제 KOFIA 웹사이트 구조 확인 후 완성 필요.
    금투협 통계 포탈: https://freesis.kofia.or.kr
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    requests = None
    BeautifulSoup = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

KOFIA_BASE_URL = "https://freesis.kofia.or.kr"


class KofiaScrapingError(Exception):
    pass


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
        print("  [WARN] requests/beautifulsoup4 not installed")
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

    # --- Stub: 실제 KOFIA API 엔드포인트 확인 후 구현 ---
    # 아래는 인터페이스만 정의. Phase 2에서 실제 스크래핑 구현.
    try:
        result["credit"]["total_balance_billion"] = _scrape_credit_balance(date)
    except Exception as e:
        print(f"  [WARN] Credit scraping failed: {e}")

    try:
        result["deposit"]["customer_deposit_billion"] = _scrape_customer_deposit(date)
    except Exception as e:
        print(f"  [WARN] Deposit scraping failed: {e}")

    try:
        settlement = _scrape_settlement(date)
        result["settlement"].update(settlement)
    except Exception as e:
        print(f"  [WARN] Settlement scraping failed: {e}")

    return result


def _scrape_credit_balance(date: str) -> float | None:
    """신용거래융자 잔고 (억원).

    TODO: KOFIA 통계 포탈 → 투자자별 거래실적 → 신용거래융자 잔고
    실제 URL/파라미터 확인 후 구현.
    """
    # Stub - return None until actual scraping is implemented
    return None


def _scrape_customer_deposit(date: str) -> float | None:
    """고객예탁금 (억원).

    TODO: KOFIA → 시장현황 → 고객예탁금 추이
    """
    return None


def _scrape_settlement(date: str) -> dict:
    """위탁매매 미수금 + 반대매매 금액 (억원).

    TODO: KOFIA → 반대매매/미수금 현황
    """
    return {
        "unsettled_margin_billion": None,
        "forced_liquidation_billion": None,
    }


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
