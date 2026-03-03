#!/usr/bin/env python3
"""
KOSPI 일간 데이터 수집 스크립트.

Usage:
    python kospi/scripts/fetch_daily.py                        # 오늘 데이터
    python kospi/scripts/fetch_daily.py --date 2026-03-03      # 특정 날짜
    python kospi/scripts/fetch_daily.py --range 2026-01-01 2026-03-03  # 범위
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

# pykrx / FDR imports
from pykrx import stock as krx
try:
    import FinanceDataReader as fdr
except ImportError:
    fdr = None

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DAILY_DIR = DATA_DIR / "daily"

TICKERS = {"005930": "삼성전자", "000660": "SK하이닉스"}
DATE_FMT = "%Y%m%d"     # pykrx format
ISO_FMT = "%Y-%m-%d"


def _fmt(date_str: str) -> str:
    """ISO → pykrx format (YYYYMMDD)"""
    return date_str.replace("-", "")


def fetch_market_data(date: str) -> dict:
    """D01, D19, D22 — KOSPI OHLCV, 시가총액, 거래대금"""
    d = _fmt(date)
    try:
        # KOSPI 지수 OHLCV
        df = krx.get_index_ohlcv_by_date(d, d, "1001")  # 1001 = KOSPI
        if df.empty:
            return {"kospi": None, "kosdaq": None, "kospi_market_cap_trillion": None}

        row = df.iloc[0]
        kospi = {
            "open": float(row.get("시가", 0)),
            "high": float(row.get("고가", 0)),
            "low": float(row.get("저가", 0)),
            "close": float(row.get("종가", 0)),
            "volume": int(row.get("거래량", 0)),
            "trading_value_billion": round(float(row.get("거래대금", 0)) / 1e8, 1),
        }
    except Exception as e:
        print(f"  [WARN] KOSPI OHLCV failed: {e}")
        kospi = None

    # KOSDAQ
    try:
        df2 = krx.get_index_ohlcv_by_date(d, d, "2001")  # 2001 = KOSDAQ
        if not df2.empty:
            row2 = df2.iloc[0]
            kosdaq = {
                "open": float(row2.get("시가", 0)),
                "high": float(row2.get("고가", 0)),
                "low": float(row2.get("저가", 0)),
                "close": float(row2.get("종가", 0)),
                "volume": int(row2.get("거래량", 0)),
            }
        else:
            kosdaq = None
    except Exception:
        kosdaq = None

    # 시가총액 — 전 종목 합계
    try:
        mcap_df = krx.get_market_cap_by_date(d, d, "005930")
        kospi_mcap = None  # 개별 종목 시총은 아래 stock_data에서 처리
    except Exception:
        pass

    kospi_mcap = None  # 시장 전체 시총은 별도 계산 필요 — 일단 None

    return {
        "kospi": kospi,
        "kosdaq": kosdaq,
        "kospi_market_cap_trillion": kospi_mcap,
    }


def fetch_stock_data(date: str) -> dict:
    """D02~D03 — 삼성전자/SK하이닉스 OHLCV"""
    d = _fmt(date)
    result = {}
    for ticker, name in TICKERS.items():
        try:
            df = krx.get_market_ohlcv_by_date(d, d, ticker)
            if df.empty:
                result[ticker] = {"name": name}
                continue
            row = df.iloc[0]
            result[ticker] = {
                "name": name,
                "open": int(row.get("시가", 0)),
                "high": int(row.get("고가", 0)),
                "low": int(row.get("저가", 0)),
                "close": int(row.get("종가", 0)),
                "volume": int(row.get("거래량", 0)),
            }
        except Exception as e:
            print(f"  [WARN] {name} OHLCV failed: {e}")
            result[ticker] = {"name": name}
    return result


def fetch_investor_flows(date: str) -> dict:
    """D04~D06 — 주체별 매매동향"""
    d = _fmt(date)
    result = {}

    # 시장 전체
    try:
        df = krx.get_market_trading_value_by_date(d, d, "KOSPI")
        if not df.empty:
            row = df.iloc[0]
            # 컬럼: 기관합계, 기타법인, 개인, 외국인합계, 전체
            result["market_total"] = {
                "individual_billion": round(float(row.get("개인", 0)) / 1e8, 1),
                "foreign_billion": round(float(row.get("외국인합계", 0)) / 1e8, 1),
                "institution_billion": round(float(row.get("기관합계", 0)) / 1e8, 1),
            }
        else:
            result["market_total"] = {
                "individual_billion": None,
                "foreign_billion": None,
                "institution_billion": None,
            }
    except Exception as e:
        print(f"  [WARN] Market flows failed: {e}")
        result["market_total"] = {
            "individual_billion": None,
            "foreign_billion": None,
            "institution_billion": None,
        }

    # 종목별 — pykrx로 가능한지 시도
    for ticker, name in TICKERS.items():
        try:
            df = krx.get_market_trading_value_by_date(d, d, ticker)
            if not df.empty:
                row = df.iloc[0]
                result[ticker] = {
                    "individual_billion": round(float(row.get("개인", 0)) / 1e8, 1),
                    "foreign_billion": round(float(row.get("외국인합계", 0)) / 1e8, 1),
                    "institution_billion": round(float(row.get("기관합계", 0)) / 1e8, 1),
                }
            else:
                result[ticker] = {"individual_billion": None, "foreign_billion": None, "institution_billion": None}
        except Exception:
            result[ticker] = {"individual_billion": None, "foreign_billion": None, "institution_billion": None}

    return result


def fetch_short_selling(date: str) -> dict:
    """D09~D11 — 공매도"""
    d = _fmt(date)
    result = {
        "market_total_shares": None,
        "market_total_billion": None,
        "government_ban_active": False,
    }
    try:
        df = krx.get_shorting_volume_by_date(d, d, "KOSPI")
        if not df.empty:
            total = df.sum()
            result["market_total_shares"] = int(total.get("공매도거래량", 0))
            result["market_total_billion"] = round(float(total.get("공매도거래대금", 0)) / 1e8, 2)
    except Exception as e:
        print(f"  [WARN] Short selling failed: {e}")

    for ticker in TICKERS:
        try:
            df = krx.get_shorting_volume_by_date(d, d, ticker)
            if not df.empty:
                row = df.iloc[0]
                result[f"{ticker}_shares"] = int(row.get("공매도거래량", 0))
            else:
                result[f"{ticker}_shares"] = None
        except Exception:
            result[f"{ticker}_shares"] = None

    return result


def fetch_global_data(date: str) -> dict:
    """D07, D08, D20, D21 — USD/KRW, WTI, VIX, S&P 500"""
    if fdr is None:
        print("  [WARN] FinanceDataReader not installed, skipping global data")
        return {"usd_krw": None, "wti": None, "vix": None, "sp500": None}

    result = {}
    mappings = {
        "usd_krw": "USD/KRW",
        "wti": "CL=F",
        "vix": "VIX",
        "sp500": "SPY",  # S&P 500 ETF as proxy
    }

    for key, symbol in mappings.items():
        try:
            df = fdr.DataReader(symbol, date, date)
            if not df.empty:
                result[key] = round(float(df.iloc[-1]["Close"]), 2)
            else:
                result[key] = None
        except Exception as e:
            print(f"  [WARN] {symbol} failed: {e}")
            result[key] = None

    return result


def build_snapshot(date: str) -> dict:
    """모든 데이터를 하나의 일간 스냅샷으로 조합"""
    print(f"[{date}] Fetching data...")

    market = fetch_market_data(date)
    print(f"  Market: {'OK' if market.get('kospi') else 'EMPTY'}")

    stocks = fetch_stock_data(date)
    print(f"  Stocks: {len([v for v in stocks.values() if v.get('close')])}/{len(TICKERS)}")

    flows = fetch_investor_flows(date)
    print(f"  Flows: {'OK' if flows.get('market_total', {}).get('individual_billion') is not None else 'EMPTY'}")

    shorts = fetch_short_selling(date)
    print(f"  Shorts: {'OK' if shorts.get('market_total_shares') else 'EMPTY'}")

    global_data = fetch_global_data(date)
    print(f"  Global: {sum(1 for v in global_data.values() if v is not None)}/4")

    snapshot = {
        "date": date,
        "fetched_at": datetime.now().isoformat(),
        "market": market,
        "stocks": stocks,
        "investor_flows": flows,
        "credit": {
            "total_balance_billion": None,
            "estimated": False,
        },
        "deposit": {
            "customer_deposit_billion": None,
            "estimated": False,
        },
        "settlement": {
            "unsettled_margin_billion": None,
            "forced_liquidation_billion": None,
            "estimated": False,
        },
        "short_selling": shorts,
        "global": global_data,
        "manual_inputs": {
            "events": [],
        },
    }
    return snapshot


def save_daily_snapshot(date: str, snapshot: dict) -> Path:
    """kospi/data/daily/{date}.json 저장"""
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    path = DAILY_DIR / f"{date}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Saved: {path}")
    return path


def append_timeseries(date: str, snapshot: dict) -> None:
    """kospi/data/timeseries.json 에 append"""
    ts_path = DATA_DIR / "timeseries.json"
    if ts_path.exists():
        with open(ts_path, "r", encoding="utf-8") as f:
            ts = json.load(f)
    else:
        ts = []

    # 중복 방지
    existing_dates = {r["date"] for r in ts}
    if date in existing_dates:
        ts = [r for r in ts if r["date"] != date]

    # 간결한 시계열 레코드
    kospi = snapshot.get("market", {}).get("kospi") or {}
    samsung = snapshot.get("stocks", {}).get("005930") or {}
    hynix = snapshot.get("stocks", {}).get("000660") or {}
    flows_mkt = snapshot.get("investor_flows", {}).get("market_total") or {}
    global_d = snapshot.get("global") or {}
    credit = snapshot.get("credit") or {}
    deposit = snapshot.get("deposit") or {}
    settlement = snapshot.get("settlement") or {}

    record = {
        "date": date,
        "kospi": kospi.get("close"),
        "kospi_volume": kospi.get("volume"),
        "kospi_trading_value_billion": kospi.get("trading_value_billion"),
        "samsung": samsung.get("close"),
        "hynix": hynix.get("close"),
        "individual_billion": flows_mkt.get("individual_billion"),
        "foreign_billion": flows_mkt.get("foreign_billion"),
        "institution_billion": flows_mkt.get("institution_billion"),
        "credit_balance_billion": credit.get("total_balance_billion"),
        "credit_estimated": credit.get("estimated", False),
        "deposit_billion": deposit.get("customer_deposit_billion"),
        "forced_liq_billion": settlement.get("forced_liquidation_billion"),
        "usd_krw": global_d.get("usd_krw"),
        "wti": global_d.get("wti"),
        "vix": global_d.get("vix"),
        "sp500": global_d.get("sp500"),
    }
    ts.append(record)
    ts.sort(key=lambda r: r["date"])

    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump(ts, f, ensure_ascii=False, indent=2, default=str)


def update_metadata(date: str) -> None:
    """kospi/data/metadata.json 업데이트"""
    meta_path = DATA_DIR / "metadata.json"
    meta = {
        "last_updated": datetime.now().isoformat(),
        "last_date": date,
        "data_dir": str(DATA_DIR),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def run_single(date: str):
    """단일 날짜 수집"""
    snapshot = build_snapshot(date)
    save_daily_snapshot(date, snapshot)
    append_timeseries(date, snapshot)
    update_metadata(date)
    print(f"[{date}] Done.\n")


def run_range(start: str, end: str):
    """날짜 범위 수집"""
    current = datetime.strptime(start, ISO_FMT)
    end_dt = datetime.strptime(end, ISO_FMT)
    while current <= end_dt:
        # 주말 건너뛰기
        if current.weekday() < 5:
            run_single(current.strftime(ISO_FMT))
        current += timedelta(days=1)


def main():
    parser = argparse.ArgumentParser(description="KOSPI daily data fetcher")
    parser.add_argument("--date", type=str, help="Specific date (YYYY-MM-DD)")
    parser.add_argument("--range", nargs=2, metavar=("START", "END"),
                        help="Date range (YYYY-MM-DD YYYY-MM-DD)")
    args = parser.parse_args()

    if args.range:
        run_range(args.range[0], args.range[1])
    elif args.date:
        run_single(args.date)
    else:
        # 가장 최근 영업일
        today = datetime.now()
        if today.weekday() >= 5:
            today -= timedelta(days=today.weekday() - 4)
        run_single(today.strftime(ISO_FMT))


if __name__ == "__main__":
    main()
