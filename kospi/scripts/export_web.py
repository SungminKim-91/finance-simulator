#!/usr/bin/env python3
"""
Python 모델 결과 → React 데이터 파일 내보내기.
kospi/data/ → web/src/simulators/kospi/data/kospi_data.js

Exports (13):
  1. MARKET_DATA       — KOSPI/KOSDAQ/삼전/하닉 일간
  2. CREDIT_DATA       — 신용잔고, 예탁금, 반대매매
  3. INVESTOR_FLOWS    — 주체별 수급
  4. GLOBAL_DATA       — USD/KRW, WTI, VIX, S&P500
  5. SHORT_SELLING     — 공매도
  6. COHORT_DATA       — 코호트 분포 + 트리거맵
  7. CRISIS_SCORE      — 위기 점수 + 14개 지표
  8. SCENARIOS         — 5개 시나리오 + 확률 히스토리
  9. HISTORICAL        — 과거 사례 비교
 10. DEFENSE_WALLS     — 방어벽 상태
 11. LOOP_STATUS       — Loop A/C 상태
 12. EVENTS            — 이벤트 로그
 13. META              — 메타데이터

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
    model_output = load_json(DATA_DIR / "model_output.json") or {}

    if not ts and not snapshots:
        print("No data found. Run fetch_daily.py first.")
        return

    # === 1. MARKET_DATA ===
    market_data = []
    for r in ts:
        market_data.append({
            "date": r["date"],
            "kospi": r.get("kospi"),
            "kosdaq": r.get("kosdaq"),
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

    # === 2. CREDIT_DATA ===
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
    # Fallback: ts 기반 credit data (daily snapshot 없을 때)
    if not credit_data and ts:
        for r in ts:
            credit_data.append({
                "date": r["date"],
                "credit_balance_billion": r.get("credit_balance_billion"),
                "deposit_billion": r.get("deposit_billion"),
                "forced_liq_billion": r.get("forced_liq_billion"),
                "estimated": r.get("credit_estimated", False),
            })

    # === 3. INVESTOR_FLOWS ===
    investor_flows = []
    for r in ts:
        indiv = r.get("individual_billion")
        foreign = r.get("foreign_billion")
        institution = r.get("institution_billion")
        # financial_invest_billion 추정: 개인의 ~20%
        fin_invest = round(indiv * 0.2, 1) if indiv is not None else None
        retail = round(indiv + fin_invest, 1) if indiv is not None and fin_invest is not None else indiv
        investor_flows.append({
            "date": r["date"],
            "individual_billion": indiv,
            "financial_invest_billion": fin_invest,
            "retail_billion": retail,
            "foreign_billion": foreign,
            "institution_billion": institution,
        })

    # === 4. GLOBAL_DATA ===
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

    # === 5. SHORT_SELLING ===
    short_selling = []
    for s in snapshots:
        ss = s.get("short_selling", {})
        short_selling.append({
            "date": s["date"],
            "market_total_billion": ss.get("market_total_billion"),
            "gov_ban": ss.get("government_ban_active", False),
        })
    if not short_selling and ts:
        for r in ts:
            short_selling.append({
                "date": r["date"],
                "market_total_billion": None,
                "gov_ban": False,
            })

    # === 6. COHORT_DATA (from model_output) ===
    # Remap Python field names to frontend expectations
    cohorts = model_output.get("cohorts", {})
    lifo_fe = _remap_cohorts(cohorts.get("lifo", []))
    fifo_fe = _remap_cohorts(cohorts.get("fifo", []))
    cohort_data = {
        "lifo": lifo_fe,
        "fifo": fifo_fe,
        "price_distribution_lifo": cohorts.get("price_distribution_lifo", []),
        "price_distribution_fifo": cohorts.get("price_distribution_fifo", []),
        "trigger_map": cohorts.get("trigger_map", []),
        "current_kospi": cohorts.get("current_kospi", 0),
        "current_fx": cohorts.get("current_fx", 1400),
        "avg_daily_trading_value_billion": _avg_trading_value(ts),
        "params": {
            "margin_distribution": {"0.40": 0.35, "0.45": 0.35, "0.50": 0.25, "0.60": 0.05},
            "maintenance_ratio": 1.40,
            "forced_liq_ratio": 1.30,
            "impact_coefficient": 1.5,
            "fx_sensitivity": {
                "low": {"threshold": 1, "multiplier": 0.5},
                "mid": {"threshold": 2, "multiplier": 1.0},
                "high": {"threshold": 3, "multiplier": 1.5},
                "extreme": {"threshold": float("inf"), "multiplier": 2.0},
            },
        },
    }

    # === 7. CRISIS_SCORE ===
    crisis_score = model_output.get("crisis_score", {
        "current": 50, "classification": "normal",
        "weights": {}, "indicators": {}, "history": [],
    })

    # === 8. SCENARIOS ===
    scenarios = model_output.get("scenarios", {
        "scenarios": [], "probability_history": [], "key_drivers": [],
    })

    # === 9. HISTORICAL ===
    historical = model_output.get("historical", {
        "cases": [], "similarities": {}, "overlay": [],
    })
    # indicator_comparison 추가 (crisis_score indicators에서 추출)
    if "indicator_comparison" not in historical and crisis_score.get("indicators"):
        historical["indicator_comparison"] = [
            {
                "indicator": key,
                "label": val.get("desc", key),
                "current": val.get("raw", 0),
            }
            for key, val in crisis_score.get("indicators", {}).items()
        ]

    # === 10. DEFENSE_WALLS ===
    defense_walls = model_output.get("defense_walls", [])

    # === 11. LOOP_STATUS ===
    loop_status = model_output.get("loop_status", {})

    # === 12. EVENTS ===
    events = []
    for s in snapshots:
        for evt in s.get("manual_inputs", {}).get("events", []):
            events.append(evt)
    events.sort(key=lambda e: e.get("date", ""), reverse=True)
    events = events[:20]

    # === 13. META ===
    meta = {
        "last_updated": datetime.now().isoformat(),
        "last_date": ts[-1]["date"] if ts else None,
        "data_source": "pipeline",
        "data_quality": {
            "total_days": len(ts),
            "credit_estimated_days": sum(1 for c in credit_data if c.get("estimated")),
            "missing_fields": [],
        },
    }

    # === Write JS ===
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    output_path = WEB_DATA_DIR / "kospi_data.js"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("/**\n")
        f.write(f" * KOSPI Crisis Detector Data (auto-generated)\n")
        f.write(f" * Generated: {datetime.now().isoformat()}\n")
        f.write(f" * Source: kospi/data/ (pipeline)\n")
        f.write(f" * Exports: 13\n")
        f.write(f" */\n\n")

        f.write(to_js_export("MARKET_DATA", market_data))
        f.write(to_js_export("CREDIT_DATA", credit_data))
        f.write(to_js_export("INVESTOR_FLOWS", investor_flows))
        f.write(to_js_export("GLOBAL_DATA", global_data))
        f.write(to_js_export("SHORT_SELLING", short_selling))
        f.write(to_js_export("COHORT_DATA", cohort_data))
        f.write(to_js_export("CRISIS_SCORE", crisis_score))
        f.write(to_js_export("SCENARIOS", scenarios))
        f.write(to_js_export("HISTORICAL", historical))
        f.write(to_js_export("DEFENSE_WALLS", defense_walls))
        f.write(to_js_export("LOOP_STATUS", loop_status))
        f.write(to_js_export("EVENTS", events))
        f.write(to_js_export("META", meta))

    print(f"Exported to {output_path}")
    print(f"  Market:    {len(market_data)} days")
    print(f"  Credit:    {len(credit_data)} days")
    print(f"  Flows:     {len(investor_flows)} days")
    print(f"  Global:    {len(global_data)} days")
    print(f"  Shorts:    {len(short_selling)} days")
    print(f"  Cohorts:   LIFO {len(cohort_data['lifo'])}, FIFO {len(cohort_data['fifo'])}")
    print(f"  Crisis:    score={crisis_score.get('current', 'N/A')}")
    print(f"  Scenarios: {len(scenarios.get('scenarios', []))}")
    print(f"  Historical:{len(historical.get('cases', []))} cases")
    print(f"  Defense:   {len(defense_walls)} walls")
    print(f"  Events:    {len(events)}")


def _remap_cohorts(cohorts: list[dict]) -> list[dict]:
    """Python cohort output → frontend 호환 형식 변환.

    Python: remaining_amount_billion, status=forced_liq/margin_call
    Frontend: amount, status=danger/marginCall
    """
    status_map = {"forced_liq": "danger", "margin_call": "marginCall", "watch": "watch", "safe": "safe"}
    result = []
    for c in cohorts:
        result.append({
            "entry_date": c.get("entry_date", ""),
            "entry_kospi": c.get("entry_kospi", 0),
            "amount": c.get("remaining_amount_billion", 0),
            "pnl_pct": c.get("pnl_pct", 0),
            "collateral_ratio": c.get("collateral_ratio", 0),
            "status": status_map.get(c.get("status", "safe"), "safe"),
        })
    return result


def _avg_trading_value(ts: list[dict]) -> int:
    """최근 20일 평균 거래대금."""
    recent = ts[-20:] if len(ts) >= 20 else ts
    vals = [r.get("kospi_trading_value_billion", 0) or 0 for r in recent]
    return round(sum(vals) / len(vals)) if vals else 10000


if __name__ == "__main__":
    export_all()
