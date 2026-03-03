#!/usr/bin/env python3
"""
과거 데이터 1회성 수집 (pykrx).
2008, 2011, 2020, 2021 한국 시장 데이터.

Usage:
    python kospi/scripts/fetch_historical.py           # 전체 수집
    python kospi/scripts/fetch_historical.py --case 2008  # 특정 사례만
"""
import argparse
import json
from pathlib import Path

from pykrx import stock as krx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HISTORICAL_DIR = PROJECT_ROOT / "data" / "historical"

HISTORICAL_PERIODS = {
    "korea_2008": ("2007-01-01", "2009-12-31"),
    "korea_2011": ("2011-01-01", "2012-06-30"),
    "korea_2020": ("2019-06-01", "2020-12-31"),
    "korea_2021": ("2020-06-01", "2022-12-31"),
}


def fetch_historical_case(case_name: str, start: str, end: str) -> dict | None:
    """단일 과거 사례 데이터 수집."""
    print(f"\n[{case_name}] Fetching {start} ~ {end}...")

    d_start = start.replace("-", "")
    d_end = end.replace("-", "")

    # KOSPI 지수 OHLCV
    try:
        df = krx.get_index_ohlcv_by_date(d_start, d_end, "1001")
        if df.empty:
            print(f"  [WARN] No KOSPI data for {case_name}")
            return None
    except Exception as e:
        print(f"  [ERROR] Failed to fetch KOSPI: {e}")
        return None

    # 고점 탐색
    peak_idx = df["종가"].idxmax()
    peak_date = (
        peak_idx.strftime("%Y-%m-%d") if hasattr(peak_idx, "strftime") else str(peak_idx)
    )
    peak_kospi = float(df.loc[peak_idx, "종가"])
    print(f"  Peak: {peak_date} @ {peak_kospi:,.0f}")

    # 시계열 구성
    timeseries = []
    prev_close = None
    for date_idx, row in df.iterrows():
        date_str = (
            date_idx.strftime("%Y-%m-%d")
            if hasattr(date_idx, "strftime")
            else str(date_idx)
        )
        close = float(row.get("종가", 0))
        change_pct = (
            round((close / prev_close - 1) * 100, 2) if prev_close and prev_close > 0 else 0
        )
        timeseries.append({
            "date": date_str,
            "kospi": close,
            "kospi_change_pct": change_pct,
            "volume": int(row.get("거래량", 0)),
            "trading_value_billion": round(float(row.get("거래대금", 0)) / 1e8, 1),
        })
        prev_close = close

    # 주체별 매매동향 (시장 전체)
    print(f"  Fetching investor flows...")
    try:
        flow_df = krx.get_market_trading_value_by_date(d_start, d_end, "KOSPI")
        for ts_row in timeseries:
            d = ts_row["date"].replace("-", "")
            try:
                if d in flow_df.index.strftime("%Y%m%d"):
                    frow = flow_df.loc[flow_df.index.strftime("%Y%m%d") == d].iloc[0]
                    ts_row["individual_billion"] = round(float(frow.get("개인", 0)) / 1e8, 1)
                    ts_row["foreign_billion"] = round(float(frow.get("외국인합계", 0)) / 1e8, 1)
                    ts_row["institution_billion"] = round(float(frow.get("기관합계", 0)) / 1e8, 1)
            except Exception:
                pass
    except Exception as e:
        print(f"  [WARN] Investor flows failed: {e}")

    result = {
        "case_name": case_name,
        "period": {"start": start, "end": end},
        "peak": {"date": peak_date, "kospi": peak_kospi},
        "data_points": len(timeseries),
        "timeseries": timeseries,
    }

    # 저장
    HISTORICAL_DIR.mkdir(parents=True, exist_ok=True)
    path = HISTORICAL_DIR / f"{case_name}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2, default=str)
    print(f"  Saved: {path} ({len(timeseries)} data points)")
    return result


def main():
    parser = argparse.ArgumentParser(description="KOSPI historical data fetcher")
    parser.add_argument("--case", type=str, help="Specific case year (e.g., 2008)")
    args = parser.parse_args()

    if args.case:
        key = f"korea_{args.case}"
        if key in HISTORICAL_PERIODS:
            start, end = HISTORICAL_PERIODS[key]
            fetch_historical_case(key, start, end)
        else:
            print(f"Unknown case: {args.case}")
            print(f"Available: {', '.join(HISTORICAL_PERIODS.keys())}")
    else:
        for case_name, (start, end) in HISTORICAL_PERIODS.items():
            fetch_historical_case(case_name, start, end)
        print("\nAll historical cases fetched.")


if __name__ == "__main__":
    main()
