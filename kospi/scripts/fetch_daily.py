#!/usr/bin/env python3
"""
KOSPI 일간 데이터 수집 스크립트 (yfinance + ECOS + Naver + pykrx hybrid).

yfinance: 삼전/하닉 가격, 글로벌 (USD/KRW, WTI, VIX, SPY)
ECOS: KOSPI/KOSDAQ 지수, 외국인 순매수, 거래량/대금, 시가총액
Naver: 고객예탁금, 신용잔고
pykrx: 투자자 수급 (매매동향), 공매도

Usage:
    python -m scripts.fetch_daily                              # 오늘 데이터
    python -m scripts.fetch_daily --date 2026-03-03            # 특정 날짜
    python -m scripts.fetch_daily --range 2026-01-01 2026-03-03  # 범위
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    from pykrx import stock as krx
except ImportError:
    krx = None

from scripts.ecos_fetcher import fetch_ecos_daily
from scripts.naver_scraper import fetch_naver_deposit_credit, fetch_naver_investor_flows, fetch_stock_market_caps, fetch_stock_daily_prices
from scripts.krx_auth import create_krx_session, inject_pykrx_session
from scripts.kofia_fetcher import fetch_all as fetch_kofia_all
from config.constants import TOP_10_TICKERS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DAILY_DIR = DATA_DIR / "daily"

TICKERS = {"005930": "삼성전자", "000660": "SK하이닉스"}
DATE_FMT = "%Y%m%d"
ISO_FMT = "%Y-%m-%d"

# yfinance 심볼 매핑
YF_SYMBOLS = {
    "kospi": "^KS11",
    "kosdaq": "^KQ11",
    "samsung": "005930.KS",
    "hynix": "000660.KS",
    "usd_krw": "USDKRW=X",
    "wti": "CL=F",
    "vix": "^VIX",
    "sp500": "SPY",
    "ewy": "EWY",
    "koru": "KORU",
}


def _fmt(date_str: str) -> str:
    """ISO → pykrx format (YYYYMMDD)"""
    return date_str.replace("-", "")


def fetch_yfinance_batch(start: str, end: str) -> pd.DataFrame:
    """yfinance로 모든 심볼 일괄 다운로드.
    change_pct 계산을 위해 시작일 7일 전부터 다운로드."""
    if yf is None:
        print("  [WARN] yfinance not installed")
        return pd.DataFrame()

    symbols = list(YF_SYMBOLS.values())
    start_dt = datetime.strptime(start, ISO_FMT) - timedelta(days=7)
    start_ext = start_dt.strftime(ISO_FMT)
    end_dt = datetime.strptime(end, ISO_FMT) + timedelta(days=1)
    end_plus = end_dt.strftime(ISO_FMT)

    try:
        df = yf.download(symbols, start=start_ext, end=end_plus, progress=False)
        return df
    except Exception as e:
        print(f"  [WARN] yfinance batch download failed: {e}")
        return pd.DataFrame()


def extract_date_data(yf_data: pd.DataFrame, date: str) -> dict:
    """yfinance DataFrame에서 특정 날짜 데이터 추출."""
    result = {
        "kospi": None, "kosdaq": None, "samsung": None, "hynix": None,
        "kospi_volume": None, "kospi_trading_value_billion": None,
        "samsung_volume": None, "hynix_volume": None,
        "usd_krw": None, "wti": None, "vix": None, "sp500": None,
        "ewy_close": None, "ewy_change_pct": None,
        "koru_close": None, "koru_change_pct": None,
        "sp500_change_pct": None,
    }

    if yf_data.empty:
        return result

    try:
        dt = pd.Timestamp(date)
        if dt not in yf_data.index:
            return result

        row = yf_data.loc[dt]

        # 지수/종목 종가
        for key, symbol in YF_SYMBOLS.items():
            try:
                val = row[("Close", symbol)]
                if pd.notna(val):
                    if key in ("kospi", "kosdaq"):
                        result[key] = round(float(val), 2)
                    elif key in ("samsung", "hynix"):
                        result[key] = int(float(val))
                    elif key == "usd_krw":
                        result[key] = round(float(val), 1)
                    elif key == "sp500":
                        result[key] = round(float(val), 1)
                    elif key == "ewy":
                        result["ewy_close"] = round(float(val), 2)
                    elif key == "koru":
                        result["koru_close"] = round(float(val), 2)
                    else:
                        result[key] = round(float(val), 2)
            except (KeyError, TypeError):
                pass

        # EWY 변동률 계산 (전일 대비)
        if result["ewy_close"] is not None:
            try:
                for offset in range(1, 6):
                    check_dt = dt - pd.Timedelta(days=offset)
                    if check_dt in yf_data.index:
                        prev_ewy = yf_data.loc[check_dt][("Close", YF_SYMBOLS["ewy"])]
                        if pd.notna(prev_ewy) and float(prev_ewy) > 0:
                            result["ewy_change_pct"] = round(
                                (result["ewy_close"] / float(prev_ewy) - 1) * 100, 2
                            )
                            break
            except (KeyError, TypeError):
                pass

        # KORU 변동률 계산 (전일 대비)
        if result["koru_close"] is not None:
            try:
                for offset in range(1, 6):
                    check_dt = dt - pd.Timedelta(days=offset)
                    if check_dt in yf_data.index:
                        prev_koru = yf_data.loc[check_dt][("Close", YF_SYMBOLS["koru"])]
                        if pd.notna(prev_koru) and float(prev_koru) > 0:
                            result["koru_change_pct"] = round(
                                (result["koru_close"] / float(prev_koru) - 1) * 100, 2
                            )
                            break
            except (KeyError, TypeError):
                pass

        # SP500 변동률 계산 (전일 대비)
        if result["sp500"] is not None:
            try:
                for offset in range(1, 6):
                    check_dt = dt - pd.Timedelta(days=offset)
                    if check_dt in yf_data.index:
                        prev_sp = yf_data.loc[check_dt][("Close", YF_SYMBOLS["sp500"])]
                        if pd.notna(prev_sp) and float(prev_sp) > 0:
                            result["sp500_change_pct"] = round(
                                (result["sp500"] / float(prev_sp) - 1) * 100, 2
                            )
                            break
            except (KeyError, TypeError):
                pass

        # 거래량
        for key, symbol in YF_SYMBOLS.items():
            try:
                vol = row[("Volume", symbol)]
                if pd.notna(vol):
                    if key == "kospi":
                        result["kospi_volume"] = int(vol)
                    elif key == "samsung":
                        result["samsung_volume"] = int(vol)
                    elif key == "hynix":
                        result["hynix_volume"] = int(vol)
            except (KeyError, TypeError):
                pass

    except Exception as e:
        print(f"  [WARN] extract_date_data error for {date}: {e}")

    return result


def fetch_investor_flows(date: str) -> dict:
    """pykrx로 투자자 수급 데이터 수집."""
    result = {
        "individual_billion": None,
        "foreign_billion": None,
        "institution_billion": None,
    }

    if krx is None:
        return result

    d = _fmt(date)
    try:
        df = krx.get_market_trading_value_by_date(d, d, "KOSPI")
        if not df.empty:
            row = df.iloc[0]
            result["individual_billion"] = round(float(row.get("개인", 0)) / 1e8, 1)
            result["foreign_billion"] = round(float(row.get("외국인합계", 0)) / 1e8, 1)
            result["institution_billion"] = round(float(row.get("기관합계", 0)) / 1e8, 1)
    except Exception as e:
        print(f"  [WARN] Investor flows failed for {date}: {e}")

    return result


def fetch_short_selling(date: str) -> dict:
    """pykrx로 공매도 데이터 수집."""
    result = {
        "market_total_shares": None,
        "market_total_billion": None,
        "government_ban_active": False,
    }

    if krx is None:
        return result

    d = _fmt(date)
    try:
        df = krx.get_shorting_volume_by_date(d, d, "KOSPI")
        if not df.empty:
            total = df.sum()
            result["market_total_shares"] = int(total.get("공매도거래량", 0))
            result["market_total_billion"] = round(float(total.get("공매도거래대금", 0)) / 1e8, 2)
    except Exception as e:
        pass  # 공매도 실패는 무시 (비필수)

    return result


def build_snapshot(
    date: str,
    yf_data: pd.DataFrame,
    ecos_data: dict | None = None,
    naver_data: dict | None = None,
    naver_investor_data: dict | None = None,
    stock_caps: dict | None = None,
    stock_daily_prices: dict | None = None,
) -> dict:
    """모든 데이터를 하나의 일간 스냅샷으로 조합.

    데이터 우선순위: ECOS > yfinance (지수), Naver (예탁금/신용잔고/투자자수급)
    """
    data = extract_date_data(yf_data, date)
    ecos_day = (ecos_data or {}).get(date, {})
    naver_day = (naver_data or {}).get(date, {})
    naver_inv_day = (naver_investor_data or {}).get(date, {})

    # ECOS 데이터로 보강 (우선순위: ECOS > yfinance)
    kospi_close = ecos_day.get("kospi") or data["kospi"]
    kosdaq_close = ecos_day.get("kosdaq") or data["kosdaq"]
    trading_value_b = ecos_day.get("trading_value_billion")
    volume_k = ecos_day.get("volume_thousand")
    market_cap_b = ecos_day.get("market_cap_billion")
    foreign_net_b = ecos_day.get("foreign_net_billion")

    # 투자자 수급: Naver > pykrx > ECOS(foreign only)
    flows = {
        "individual_billion": naver_inv_day.get("individual_billion"),
        "foreign_billion": naver_inv_day.get("foreign_billion"),
        "institution_billion": naver_inv_day.get("institution_billion"),
        "financial_invest_billion": naver_inv_day.get("financial_invest_billion"),
    }

    # Naver 없으면 ECOS 외국인 fallback
    if flows["foreign_billion"] is None and foreign_net_b is not None:
        flows["foreign_billion"] = round(foreign_net_b, 1)

    # pykrx 공매도
    shorts = fetch_short_selling(date)

    # Naver 예탁금/신용잔고 (fallback)
    deposit_b = naver_day.get("deposit_billion")
    credit_b = naver_day.get("credit_balance_billion")
    forced_liq_b = None
    unsettled_b = None
    credit_kospi_b = None
    credit_source = "naver"

    # KOFIA API (data.go.kr) > Naver fallback
    kofia = fetch_kofia_all(date)
    if kofia:
        credit_source = kofia["source"]
        if kofia.get("credit_balance_billion") is not None:
            credit_b = kofia["credit_balance_billion"]
        if kofia.get("credit_kospi_billion") is not None:
            credit_kospi_b = kofia["credit_kospi_billion"]
        if kofia.get("deposit_billion") is not None:
            deposit_b = kofia["deposit_billion"]
        if kofia.get("forced_liq_billion") is not None:
            forced_liq_b = kofia["forced_liq_billion"]
        if kofia.get("unsettled_billion") is not None:
            unsettled_b = kofia["unsettled_billion"]
        print(f"  [KOFIA] {credit_source}: credit={credit_b}, deposit={deposit_b}, forced_liq={forced_liq_b}")

    snapshot = {
        "date": date,
        "fetched_at": datetime.now().isoformat(),
        "market": {
            "kospi": {
                "close": kospi_close,
                "volume": int(volume_k * 1000) if volume_k else data["kospi_volume"],
                "trading_value_billion": trading_value_b,
            } if kospi_close else None,
            "kosdaq": {
                "close": kosdaq_close,
            } if kosdaq_close else None,
            "kospi_market_cap_trillion": round(market_cap_b / 1000, 2) if market_cap_b else None,
        },
        "stocks": {
            "005930": {
                "name": "삼성전자",
                "close": data["samsung"],
                "volume": data.get("samsung_volume"),
            },
            "000660": {
                "name": "SK하이닉스",
                "close": data["hynix"],
                "volume": data.get("hynix_volume"),
            },
        },
        "investor_flows": {
            "market_total": flows,
        },
        "credit": {
            "total_balance_billion": credit_b,
            "kospi_balance_billion": credit_kospi_b,
            "source": credit_source,
            "estimated": False,
        },
        "deposit": {
            "customer_deposit_billion": deposit_b,
            "estimated": False,
        },
        "settlement": {
            "unsettled_margin_billion": unsettled_b,
            "forced_liquidation_billion": forced_liq_b,
            "estimated": False,
        },
        "short_selling": shorts,
        "global": {
            "usd_krw": data["usd_krw"],
            "wti": data["wti"],
            "vix": data["vix"],
            "sp500": data["sp500"],
            "ewy_close": data.get("ewy_close"),
            "ewy_change_pct": data.get("ewy_change_pct"),
            "koru_close": data.get("koru_close"),
            "koru_change_pct": data.get("koru_change_pct"),
            "sp500_change_pct": data.get("sp500_change_pct"),
        },
        "stock_credit": _build_stock_credit(credit_b, stock_caps),
        "stock_prices": _build_stock_prices(date, stock_daily_prices),
        "manual_inputs": {
            "events": [],
        },
    }
    return snapshot


def _build_stock_prices(date: str, stock_daily_prices: dict | None) -> dict | None:
    """종목별 일간 종가 추출."""
    if not stock_daily_prices:
        return None
    prices = {}
    for ticker, daily in stock_daily_prices.items():
        if isinstance(daily, dict):
            price = daily.get(date, 0)
            if price > 0:
                prices[ticker] = price
    return prices if prices else None


def _build_stock_credit(total_credit_billion: float | None, stock_caps: dict | None) -> dict | None:
    """시가총액 비중으로 종목별 신용잔고 배분."""
    if not stock_caps or not total_credit_billion:
        return None
    weights = stock_caps.get("_weights", {})
    if not weights:
        return None
    stocks = {}
    for ticker, w in weights.items():
        info = stock_caps.get(ticker, {})
        stocks[ticker] = {
            "name": info.get("name", ticker),
            "credit_billion": round(total_credit_billion * w, 2),
            "weight_pct": round(w * 100, 2),
            "close": info.get("close", 0),
            "market_cap_billion": info.get("market_cap_billion", 0),
        }
    return {
        "method": "market_cap_proxy",
        "stocks": stocks,
        "top10_total_billion": round(sum(s["credit_billion"] for s in stocks.values()), 2),
    }


def save_daily_snapshot(date: str, snapshot: dict) -> Path:
    """kospi/data/daily/{date}.json 저장."""
    DAILY_DIR.mkdir(parents=True, exist_ok=True)
    path = DAILY_DIR / f"{date}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)
    return path


def append_timeseries(date: str, snapshot: dict) -> None:
    """kospi/data/timeseries.json 에 append."""
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

    kospi = snapshot.get("market", {}).get("kospi") or {}
    samsung = snapshot.get("stocks", {}).get("005930") or {}
    hynix = snapshot.get("stocks", {}).get("000660") or {}
    flows_mkt = snapshot.get("investor_flows", {}).get("market_total") or {}
    global_d = snapshot.get("global") or {}
    credit = snapshot.get("credit") or {}
    deposit = snapshot.get("deposit") or {}
    settlement = snapshot.get("settlement") or {}
    stock_credit = snapshot.get("stock_credit") or {}

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
        "financial_invest_billion": flows_mkt.get("financial_invest_billion"),
        "credit_balance_billion": credit.get("total_balance_billion"),
        "credit_source": credit.get("source", "naver"),
        "credit_estimated": credit.get("estimated", False),
        "deposit_billion": deposit.get("customer_deposit_billion"),
        "forced_liq_billion": settlement.get("forced_liquidation_billion"),
        "unsettled_billion": settlement.get("unsettled_margin_billion"),
        "usd_krw": global_d.get("usd_krw"),
        "wti": global_d.get("wti"),
        "vix": global_d.get("vix"),
        "sp500": global_d.get("sp500"),
        "ewy_close": global_d.get("ewy_close"),
        "ewy_change_pct": global_d.get("ewy_change_pct"),
        "koru_close": global_d.get("koru_close"),
        "koru_change_pct": global_d.get("koru_change_pct"),
        "sp500_change_pct": global_d.get("sp500_change_pct"),
    }

    # 종목별 신용잔고 (stock_credit)
    if stock_credit and stock_credit.get("stocks"):
        record["stock_credit"] = {
            t: s["credit_billion"]
            for t, s in stock_credit["stocks"].items()
        }

    # 종목별 종가 (stock_prices)
    sp = snapshot.get("stock_prices") or {}
    if sp:
        record["stock_prices"] = sp

    # 데이터가 있는 날만 추가 (kospi 또는 samsung 존재)
    if record["kospi"] or record["samsung"]:
        ts.append(record)
        ts.sort(key=lambda r: r["date"])

        with open(ts_path, "w", encoding="utf-8") as f:
            json.dump(ts, f, ensure_ascii=False, indent=2, default=str)
        return True
    return False


def update_metadata(date: str) -> None:
    """kospi/data/metadata.json 업데이트."""
    meta_path = DATA_DIR / "metadata.json"
    meta = {
        "last_updated": datetime.now().isoformat(),
        "last_date": date,
        "data_dir": str(DATA_DIR),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def _init_env():
    """dotenv 로드."""
    if load_dotenv:
        env_path = PROJECT_ROOT.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
            print(f"  [ENV] {env_path} 로드 완료")
        else:
            print(f"  [WARN] .env 파일 없음: {env_path}")
    else:
        print("  [WARN] python-dotenv 미설치 — 환경변수 직접 설정 필요")


def _init_krx():
    """KRX 로그인 + pykrx 세션 주입. 실패 시 None."""
    try:
        session = create_krx_session()
        inject_pykrx_session(session)
        return session
    except Exception as e:
        print(f"  [WARN] KRX 로그인 실패: {e} — pykrx fallback 사용")
        return None


def run_range(start: str, end: str):
    """날짜 범위 수집 — ECOS + Naver + yfinance + pykrx 통합."""
    print(f"\n{'='*60}")
    print(f"KOSPI 일간 데이터 수집: {start} ~ {end}")
    print(f"{'='*60}\n")

    # 0. 환경변수 로드
    _init_env()

    # 1. KRX 로그인 (1회)
    print("[1/5] KRX 로그인...")
    _init_krx()

    # 2. ECOS 배치 조회
    print("[2/5] ECOS 데이터 조회...")
    ecos_start = start.replace("-", "")
    ecos_end = end.replace("-", "")
    ecos_data = fetch_ecos_daily(ecos_start, ecos_end)

    # 3. Naver 배치 조회
    print("[3/6] Naver 예탁금/신용잔고 조회...")
    naver_data = fetch_naver_deposit_credit(start, end)

    # 4. Naver 투자자별 매매동향
    print("[4/6] Naver 투자자별 매매동향 조회...")
    naver_investor_data = fetch_naver_investor_flows(start, end)

    # 3.5. 종목별 시가총액 (신용잔고 배분용)
    print("[3.5/7] 종목별 시가총액 조회...")
    stock_caps = fetch_stock_market_caps(TOP_10_TICKERS)

    # 4.5. 종목별 일간 종가 조회
    print("[4.5/8] 종목별 일간 종가 조회...")
    stock_daily_prices = fetch_stock_daily_prices(TOP_10_TICKERS, start, end)

    # 5. yfinance 배치 다운로드
    print("[5/8] yfinance 배치 다운로드...")
    yf_data = fetch_yfinance_batch(start, end)
    if yf_data.empty:
        print("  [WARN] yfinance 데이터 없음 — ECOS 단독 진행")

    yf_days = len(yf_data) if not yf_data.empty else 0
    n_stocks = sum(1 for k in stock_caps if not k.startswith("_") and stock_caps[k].get("market_cap_billion", 0) > 0)
    n_stock_days = max((len(v) for v in stock_daily_prices.values()), default=0) if stock_daily_prices else 0
    print(f"  yfinance: {yf_days}일, ECOS: {len(ecos_data)}일, Naver: {len(naver_data)}일, Investor: {len(naver_investor_data)}일, Stocks: {n_stocks}, StockPrices: {n_stock_days}일")

    # 6. 각 날짜별 스냅샷 생성
    print("[6/8] 스냅샷 생성 + 저장...")
    current = datetime.strptime(start, ISO_FMT)
    end_dt = datetime.strptime(end, ISO_FMT)
    count = 0
    skipped = 0

    while current <= end_dt:
        if current.weekday() < 5:  # 평일만
            date = current.strftime(ISO_FMT)
            snapshot = build_snapshot(date, yf_data, ecos_data, naver_data, naver_investor_data, stock_caps, stock_daily_prices)
            save_daily_snapshot(date, snapshot)
            added = append_timeseries(date, snapshot)
            if added:
                count += 1
            else:
                skipped += 1

        current += timedelta(days=1)

    update_metadata(end)
    print(f"\n{'='*60}")
    print(f"완료: {count}일 저장, {skipped}일 건너뜀 (데이터 없음)")
    print(f"  ECOS: {len(ecos_data)}일 | Naver: {len(naver_data)}일 | yfinance: {yf_days}일")
    print(f"{'='*60}")


def run_single(date: str):
    """단일 날짜 수집."""
    _init_env()
    _init_krx()

    ecos_d = date.replace("-", "")
    ecos_data = fetch_ecos_daily(ecos_d, ecos_d)
    naver_data = fetch_naver_deposit_credit(date, date)
    naver_investor_data = fetch_naver_investor_flows(date, date)
    stock_caps = fetch_stock_market_caps(TOP_10_TICKERS)
    stock_daily_prices = fetch_stock_daily_prices(TOP_10_TICKERS, date, date)
    yf_data = fetch_yfinance_batch(date, date)

    snapshot = build_snapshot(date, yf_data, ecos_data, naver_data, naver_investor_data, stock_caps, stock_daily_prices)
    save_daily_snapshot(date, snapshot)
    append_timeseries(date, snapshot)
    update_metadata(date)
    print(f"[{date}] 완료.")


def backfill_change_pct():
    """기존 timeseries.json에서 change_pct가 None인 레코드만 yfinance로 패치.

    ECOS/Naver/KRX API 호출 없이 yfinance 1회 배치 다운로드만 수행.
    기존 데이터(kospi, credit 등)는 그대로 보존.
    """
    ts_path = DATA_DIR / "timeseries.json"
    if not ts_path.exists():
        print("[ERROR] timeseries.json 없음")
        return

    with open(ts_path, "r", encoding="utf-8") as f:
        ts = json.load(f)

    if not ts:
        print("[ERROR] timeseries.json 비어있음")
        return

    # change_pct가 없는 레코드 찾기
    missing = [r for r in ts if r.get("ewy_change_pct") is None]
    print(f"\n총 {len(ts)}일 중 change_pct 누락: {len(missing)}일")

    if not missing:
        print("패치할 데이터 없음 — 모든 레코드에 change_pct 존재")
        return

    # yfinance 1회 배치 다운로드 (전체 기간)
    start_date = ts[0]["date"]
    end_date = ts[-1]["date"]
    print(f"yfinance 배치 다운로드: {start_date} ~ {end_date}")
    yf_data = fetch_yfinance_batch(start_date, end_date)

    if yf_data.empty:
        print("[ERROR] yfinance 다운로드 실패")
        return

    print(f"  yfinance: {len(yf_data)}일 다운로드 완료")

    # 누락 레코드 패치
    patched = 0
    for rec in ts:
        if rec.get("ewy_change_pct") is not None:
            continue

        date = rec["date"]
        extracted = extract_date_data(yf_data, date)

        if extracted.get("ewy_change_pct") is not None:
            rec["ewy_close"] = extracted["ewy_close"]
            rec["ewy_change_pct"] = extracted["ewy_change_pct"]
            patched += 1

        if extracted.get("koru_change_pct") is not None:
            rec["koru_close"] = extracted["koru_close"]
            rec["koru_change_pct"] = extracted["koru_change_pct"]

        if extracted.get("sp500_change_pct") is not None:
            rec["sp500_change_pct"] = extracted["sp500_change_pct"]

    # 저장
    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump(ts, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n완료: {patched}/{len(missing)}일 패치 (yfinance only, API 호출 없음)")


from scripts.kofia_fetcher import backfill_credit as kofia_backfill

OVERRIDES_PATH = DATA_DIR / "manual_overrides.json"


def _load_overrides() -> dict:
    """manual_overrides.json 로드."""
    if not OVERRIDES_PATH.exists():
        return {}
    with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("overrides", {})


def _save_overrides(overrides: dict) -> None:
    """manual_overrides.json 저장."""
    if OVERRIDES_PATH.exists():
        with open(OVERRIDES_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data["overrides"] = overrides
    with open(OVERRIDES_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def backfill_credit_data():
    """timeseries.json에서 credit/deposit/forced_liq이 None인 날짜를 KOFIA API로 패치."""
    _init_env()

    ts_path = DATA_DIR / "timeseries.json"
    if not ts_path.exists():
        print("[ERROR] timeseries.json 없음")
        return

    with open(ts_path, "r", encoding="utf-8") as f:
        ts = json.load(f)

    if not ts:
        print("[ERROR] timeseries.json 비어있음")
        return

    # None인 날짜 찾기
    missing = [r for r in ts if r.get("credit_balance_billion") is None
               or r.get("forced_liq_billion") is None]
    print(f"\n총 {len(ts)}일 중 credit/forced_liq 누락: {len(missing)}일")

    if not missing:
        print("패치할 데이터 없음")
        return

    # KOFIA API 일괄 조회
    start = ts[0]["date"]
    end = ts[-1]["date"]
    print(f"KOFIA API 일괄 조회: {start} ~ {end}")

    api_data = kofia_backfill(start, end)
    print(f"  API 응답: {len(api_data)}일")

    if not api_data:
        print("[WARN] API 데이터 없음")
        return

    # date → data 매핑 (API는 YYYYMMDD, timeseries는 YYYY-MM-DD)
    api_map = {}
    for d in api_data:
        raw_date = d["date"]
        iso_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}" if len(raw_date) == 8 else raw_date
        api_map[iso_date] = d

    # 머지
    patched = 0
    for rec in ts:
        date = rec["date"]
        if date not in api_map:
            continue
        api = api_map[date]
        for field in ["credit_balance_billion", "deposit_billion", "forced_liq_billion", "unsettled_billion"]:
            if rec.get(field) is None and api.get(field) is not None:
                rec[field] = api[field]
                patched += 1

    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump(ts, f, ensure_ascii=False, indent=2, default=str)

    print(f"\n완료: {patched}개 필드 패치 (KOFIA API)")


def apply_overrides():
    """manual_overrides.json의 값을 timeseries.json에 머지.

    - 해당 날짜 레코드가 있으면: None인 필드만 오버라이드 (API 데이터 보존)
    - 해당 날짜 레코드가 없으면: 새 레코드 생성
    - force=True 필드는 기존 값도 덮어씀
    """
    overrides = _load_overrides()
    if not overrides:
        print("[override] 오버라이드 데이터 없음")
        return

    ts_path = DATA_DIR / "timeseries.json"
    with open(ts_path, "r", encoding="utf-8") as f:
        ts = json.load(f)

    ts_map = {r["date"]: r for r in ts}
    applied = 0

    for date, fields in overrides.items():
        if not isinstance(fields, dict):
            continue

        force = fields.pop("_force", False)

        if date in ts_map:
            rec = ts_map[date]
            for k, v in fields.items():
                if k.startswith("_"):
                    continue
                if force or rec.get(k) is None:
                    rec[k] = v
                    applied += 1
        else:
            rec = {"date": date}
            for k, v in fields.items():
                if not k.startswith("_"):
                    rec[k] = v
                    applied += 1
            ts.append(rec)

    ts.sort(key=lambda r: r["date"])
    with open(ts_path, "w", encoding="utf-8") as f:
        json.dump(ts, f, ensure_ascii=False, indent=2, default=str)

    print(f"[override] {len(overrides)}일, {applied}개 필드 적용 완료")


def manual_input(date: str):
    """대화형 수동 입력 — 날짜의 주요 필드를 프롬프트로 입력받아 overrides에 저장."""
    FIELDS = [
        ("kospi",                    "KOSPI 종가",           float),
        ("credit_balance_billion",   "신용잔고 (십억원)",      float),
        ("deposit_billion",          "투자자예탁금 (십억원)",   float),
        ("forced_liq_billion",       "반대매매금액 (십억원)",   float),
        ("individual_billion",       "개인 순매수 (십억원)",    float),
        ("foreign_billion",          "외국인 순매수 (십억원)",   float),
        ("institution_billion",      "기관 순매수 (십억원)",    float),
        ("samsung",                  "삼성전자 종가 (원)",      int),
        ("hynix",                    "SK하이닉스 종가 (원)",    int),
        ("usd_krw",                  "USD/KRW",              float),
        ("vix",                      "VIX",                  float),
    ]

    print(f"\n{'='*50}")
    print(f"  수동 입력: {date}")
    print(f"  (빈 엔터 = 건너뛰기, q = 종료)")
    print(f"{'='*50}\n")

    overrides = _load_overrides()
    entry = overrides.get(date, {})
    count = 0

    for field, label, typ in FIELDS:
        existing = entry.get(field)
        prompt = f"  {label} [{field}]"
        if existing is not None:
            prompt += f" (현재: {existing})"
        prompt += ": "

        val = input(prompt).strip()
        if val.lower() == "q":
            break
        if val == "":
            continue
        try:
            entry[field] = typ(val.replace(",", ""))
            count += 1
        except ValueError:
            print(f"    → 무시 (숫자 아님)")

    # 추가 자유 필드
    print(f"\n  추가 필드 입력 (key=value, 빈 엔터=완료):")
    while True:
        val = input("  > ").strip()
        if not val:
            break
        if "=" in val:
            k, v = val.split("=", 1)
            k = k.strip()
            v = v.strip()
            try:
                entry[k] = float(v.replace(",", ""))
                count += 1
            except ValueError:
                entry[k] = v
                count += 1

    if count > 0:
        overrides[date] = entry
        _save_overrides(overrides)
        print(f"\n  → {count}개 필드 저장 (manual_overrides.json)")

        # 바로 적용할지 물어봄
        yn = input("\n  timeseries.json에 바로 적용? (y/n): ").strip().lower()
        if yn == "y":
            apply_overrides()
    else:
        print("\n  → 입력 없음, 저장하지 않음")


def main():
    parser = argparse.ArgumentParser(description="KOSPI daily data fetcher")
    parser.add_argument("--date", type=str, help="Specific date (YYYY-MM-DD)")
    parser.add_argument("--range", nargs=2, metavar=("START", "END"),
                        help="Date range (YYYY-MM-DD YYYY-MM-DD)")
    parser.add_argument("--backfill", action="store_true",
                        help="Backfill change_pct only (yfinance, no ECOS/Naver/KRX)")
    parser.add_argument("--backfill-credit", action="store_true",
                        help="Backfill credit/deposit/forced_liq via KOFIA API")
    parser.add_argument("--manual", type=str, metavar="DATE",
                        help="Interactive manual input for DATE (YYYY-MM-DD)")
    parser.add_argument("--apply-overrides", action="store_true",
                        help="Apply manual_overrides.json to timeseries.json")
    args = parser.parse_args()

    if args.manual:
        manual_input(args.manual)
    elif args.apply_overrides:
        apply_overrides()
    elif args.backfill_credit:
        backfill_credit_data()
    elif args.backfill:
        backfill_change_pct()
    elif args.range:
        run_range(args.range[0], args.range[1])
    elif args.date:
        run_single(args.date)
    else:
        today = datetime.now()
        if today.weekday() >= 5:
            today -= timedelta(days=today.weekday() - 4)
        run_single(today.strftime(ISO_FMT))


if __name__ == "__main__":
    main()
