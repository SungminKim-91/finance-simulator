#!/usr/bin/env python3
"""
Python 모델 결과 → React 데이터 파일 내보내기.
kospi/data/ → web/src/simulators/kospi/data/kospi_data.js

Usage:
    python kospi/scripts/export_web.py
"""
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
WEB_DATA_DIR = PROJECT_ROOT.parent / "web" / "src" / "simulators" / "kospi" / "data"


def load_json(path: Path):
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def load_daily_snapshots() -> list[dict]:
    daily_dir = DATA_DIR / "daily"
    if not daily_dir.exists():
        return []
    snapshots = []
    for p in sorted(daily_dir.glob("*.json")):
        data = load_json(p)
        if data:
            snapshots.append(data)
    return snapshots


def to_js_export(name: str, data) -> str:
    serialized = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    return f"export const {name} = {serialized};\n\n"


def export_all() -> None:
    ts = load_json(DATA_DIR / "timeseries.json") or []
    snapshots = load_daily_snapshots()

    if not ts and not snapshots:
        print("No data found. Run fetch_daily.py first.")
        return

    # --- MARKET_DATA ---
    market_data = []
    for r in ts:
        market_data.append({
            "date": r["date"],
            "kospi": r.get("kospi"),
            "kosdaq": None,
            "samsung": r.get("samsung"),
            "hynix": r.get("hynix"),
            "kospi_change_pct": None,
            "samsung_change_pct": None,
            "hynix_change_pct": None,
            "volume": r.get("kospi_volume"),
            "trading_value_billion": r.get("kospi_trading_value_billion"),
        })
    # Compute change %
    for i in range(1, len(market_data)):
        prev, curr = market_data[i - 1], market_data[i]
        for key in ("kospi", "samsung", "hynix"):
            if curr[key] and prev[key] and prev[key] > 0:
                curr[f"{key}_change_pct"] = round(
                    (curr[key] / prev[key] - 1) * 100, 2
                )

    # --- CREDIT_DATA ---
    credit_data = []
    for s in snapshots:
        credit = s.get("credit", {})
        deposit = s.get("deposit", {})
        settlement = s.get("settlement", {})
        credit_data.append({
            "date": s["date"],
            "credit_balance_billion": credit.get("total_balance_billion"),
            "deposit_billion": deposit.get("customer_deposit_billion"),
            "forced_liq_billion": settlement.get("forced_liquidation_billion"),
            "estimated": credit.get("estimated", False),
        })

    # --- INVESTOR_FLOWS ---
    investor_flows = [
        {
            "date": r["date"],
            "individual_billion": r.get("individual_billion"),
            "foreign_billion": r.get("foreign_billion"),
            "institution_billion": r.get("institution_billion"),
        }
        for r in ts
    ]

    # --- GLOBAL_DATA ---
    global_data = [
        {
            "date": r["date"],
            "usd_krw": r.get("usd_krw"),
            "wti": r.get("wti"),
            "vix": r.get("vix"),
            "sp500": r.get("sp500"),
        }
        for r in ts
    ]

    # --- SHORT_SELLING ---
    short_selling = []
    for s in snapshots:
        ss = s.get("short_selling", {})
        short_selling.append({
            "date": s["date"],
            "market_total_billion": ss.get("market_total_billion"),
            "gov_ban": ss.get("government_ban_active", False),
        })

    # --- EVENTS ---
    events = []
    for s in snapshots:
        for evt in s.get("manual_inputs", {}).get("events", []):
            events.append(evt)
    events.sort(key=lambda e: e.get("date", ""), reverse=True)
    events = events[:20]

    # --- META ---
    meta = {
        "last_updated": datetime.now().isoformat(),
        "last_date": ts[-1]["date"] if ts else None,
        "data_source": "pipeline",
        "data_quality": {
            "total_days": len(ts),
            "credit_estimated_days": sum(1 for c in credit_data if c.get("estimated")),
        },
    }

    # --- Write JS ---
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = WEB_DATA_DIR / "kospi_data.js"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("/**\n")
        f.write(f" * KOSPI Crisis Detector Data (auto-generated)\n")
        f.write(f" * Generated: {datetime.now().isoformat()}\n")
        f.write(f" * Source: kospi/data/\n")
        f.write(f" */\n\n")
        f.write(to_js_export("MARKET_DATA", market_data))
        f.write(to_js_export("CREDIT_DATA", credit_data))
        f.write(to_js_export("INVESTOR_FLOWS", investor_flows))
        f.write(to_js_export("GLOBAL_DATA", global_data))
        f.write(to_js_export("SHORT_SELLING", short_selling))
        f.write(to_js_export("EVENTS", events))
        f.write(to_js_export("META", meta))

    print(f"Exported to {output_path}")
    print(f"  Market:  {len(market_data)} days")
    print(f"  Credit:  {len(credit_data)} days")
    print(f"  Flows:   {len(investor_flows)} days")
    print(f"  Global:  {len(global_data)} days")
    print(f"  Shorts:  {len(short_selling)} days")
    print(f"  Events:  {len(events)}")


if __name__ == "__main__":
    export_all()
