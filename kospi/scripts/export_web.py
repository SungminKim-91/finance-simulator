#!/usr/bin/env python3
"""
Python 모델 결과 → React 데이터 파일 내보내기.
kospi/data/ → web/src/simulators/kospi/data/kospi_data.js

Exports (18):
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
 14. COHORT_HISTORY    — 코호트 히스토리 (레지스트리 + 일별 스냅샷)
 15. BACKTEST_DATES    — 급변동일 목록 + D+1~D+5 실제 데이터
 16. STOCK_CREDIT      — 종목별 신용잔고 배분 + 가중 트리거맵
 17. VLPI_DATA         — 자발적 청산 압력 지수 (히스토리 + 시나리오 매트릭스)
 18. VLPI_CONFIG       — VLPI 가중치, 상태기준, 변수 설명, 영향 파라미터

Usage:
    python kospi/scripts/export_web.py
"""
import json
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
WEB_DATA_DIR = PROJECT_ROOT.parent / "web" / "src" / "simulators" / "kospi" / "data"

import sys as _sys
if str(PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import (
    MARGIN_RATE, LOAN_RATE, STATUS_THRESHOLDS, LEVERAGE,
    SAMSUNG_CREDIT_WEIGHT,
    RSPI_CF_WEIGHTS, RSPI_DF_WEIGHTS,
    RSPI_SENSITIVITY, RSPI_SIGMOID_K, RSPI_SIGMOID_MID,
)


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
    # Merge: timeseries 값으로 snapshot 빈 값 보완
    ts_map = {r["date"]: r for r in ts} if ts else {}
    for cd in credit_data:
        tr = ts_map.get(cd["date"], {})
        if cd["credit_balance_billion"] is None:
            cd["credit_balance_billion"] = tr.get("credit_balance_billion")
        if cd["deposit_billion"] is None:
            cd["deposit_billion"] = tr.get("deposit_billion")
        if cd["forced_liq_billion"] is None:
            cd["forced_liq_billion"] = tr.get("forced_liq_billion")

    # === 3. INVESTOR_FLOWS ===
    investor_flows = []
    for r in ts:
        indiv = r.get("individual_billion")
        foreign = r.get("foreign_billion")
        institution = r.get("institution_billion")
        fin_invest = r.get("financial_invest_billion")
        # retail = 개인 + 금융투자 (둘 다 있을 때)
        if indiv is not None and fin_invest is not None:
            retail = round(indiv + fin_invest, 1)
        elif indiv is not None:
            retail = indiv
        else:
            retail = None
        investor_flows.append({
            "date": r["date"],
            "individual_billion": indiv,
            "financial_invest_billion": fin_invest,
            "retail_billion": retail,
            "foreign_billion": foreign,
            "institution_billion": institution,
        })

    # === 4. GLOBAL_DATA (+ 야간 데이터) ===
    global_data = [
        {
            "date": r["date"],
            "usd_krw": r.get("usd_krw"),
            "wti": r.get("wti"),
            "vix": r.get("vix"),
            "sp500": r.get("sp500"),
            "ewy_close": r.get("ewy_close"),
            "ewy_change_pct": r.get("ewy_change_pct"),
            "koru_close": r.get("koru_close"),
            "koru_change_pct": r.get("koru_change_pct"),
            "sp500_change_pct": r.get("sp500_change_pct"),
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

    # Pre-load stock_credit for use in COHORT_DATA params
    stock_credit_raw = model_output.get("stock_credit", {})

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
        "portfolio_beta": cohorts.get("portfolio_beta", 1.0),
        "params": {
            "margin_rate": MARGIN_RATE,
            "loan_rate": LOAN_RATE,
            "status_thresholds": STATUS_THRESHOLDS,
            "leverage": LEVERAGE,
            "stock_weighted": stock_credit_raw.get("stock_weighted", False),
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

    # === 14. COHORT_HISTORY ===
    cohort_history = model_output.get("cohort_history", {"registry": {}, "snapshots": []})

    # === 15. BACKTEST_DATES ===
    backtest_dates = model_output.get("backtest_dates", [])

    # === 16. STOCK_CREDIT ===
    stock_credit = {
        "stocks": stock_credit_raw.get("stocks", []),
        "weighted_trigger_map": stock_credit_raw.get("weighted_trigger_map", []),
        "betas": stock_credit_raw.get("betas", {}),
        "stock_weighted": stock_credit_raw.get("stock_weighted", False),
    }

    # 종목별 파라미터 추가 (from constants)
    try:
        from config.constants import TOP_10_TICKERS, STOCK_GROUP_PARAMS
        tickers_info = {}
        for ticker, info in TOP_10_TICKERS.items():
            group = info["group"]
            params = STOCK_GROUP_PARAMS.get(group, {})
            tickers_info[ticker] = {
                "name": info["name"],
                "group": group,
                **params,
            }
        stock_credit["tickers"] = tickers_info
        stock_credit["stock_params"] = STOCK_GROUP_PARAMS
    except ImportError:
        pass

    # === 17. RSPI_DATA (v2.0.0, VLPI 대체) ===
    rspi_raw = model_output.get("rspi", {})
    rspi_data = {
        "history": rspi_raw.get("history", []),
        "latest": rspi_raw.get("latest"),
        "scenario_matrix": rspi_raw.get("scenario_matrix", []),
    }

    # === 18. RSPI_CONFIG ===
    rspi_config = {
        "weights": rspi_raw.get("weights", {"cf": RSPI_CF_WEIGHTS, "df": RSPI_DF_WEIGHTS}),
        "status_thresholds": STATUS_THRESHOLDS,
        "cf_variables": [
            {"key": "v1", "label": "주의구간 비중", "desc": "담보비율 140~170% 코호트 비중", "range": "0~1"},
            {"key": "v2", "label": "연속 하락", "desc": "연속 하락일수 + 누적 하락률", "range": "0~1"},
            {"key": "v3", "label": "개인 수급", "desc": "전일 개인 순매수 패턴", "range": "0~1"},
            {"key": "v4", "label": "신용 가속", "desc": "신용잔고 감소 가속 모멘텀", "range": "0~0.7"},
        ],
        "df_variables": [
            {"key": "d1", "label": "야간 반등", "desc": "EWY/KORU/야간선물/US 반등 + coherence", "range": "0~1"},
            {"key": "d2", "label": "신용 유입", "desc": "하락일 신용증가 = 저가매수 (D+1 시차)", "range": "0~1"},
            {"key": "d3", "label": "외국인 소진", "desc": "외국인 매도 규모 감소/전환", "range": "0~1"},
            {"key": "d4", "label": "안전 버퍼", "desc": "안전구간 코호트 비중 (방화벽)", "range": "0~1"},
        ],
        "levels": [
            {"min": -100, "max": -20, "label": "반등 압력", "color": "#4caf50"},
            {"min": -20,  "max": 0,   "label": "균형",      "color": "#8bc34a"},
            {"min": 0,    "max": 20,  "label": "약한 하락",  "color": "#ffc107"},
            {"min": 20,   "max": 40,  "label": "하락 우세",  "color": "#ff9800"},
            {"min": 40,   "max": 100, "label": "캐스케이드", "color": "#f44336"},
        ],
        "impact_params": {
            "sensitivity": RSPI_SENSITIVITY,
            "sigmoid_k": RSPI_SIGMOID_K,
            "sigmoid_mid": RSPI_SIGMOID_MID,
            "samsung_credit_weight": SAMSUNG_CREDIT_WEIGHT,
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
        f.write(f" * Exports: 18\n")
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
        f.write(to_js_export("COHORT_HISTORY", cohort_history))
        f.write(to_js_export("BACKTEST_DATES", backtest_dates))
        f.write(to_js_export("STOCK_CREDIT", stock_credit))
        f.write(to_js_export("RSPI_DATA", rspi_data))
        f.write(to_js_export("RSPI_CONFIG", rspi_config))

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
    print(f"  CohortHist:{len(cohort_history.get('registry', {}))} cohorts, {len(cohort_history.get('snapshots', []))} days")
    print(f"  Backtest:  {len(backtest_dates)} events")
    sc_stocks = stock_credit.get("stocks", [])
    print(f"  StockCred: {len(sc_stocks)} stocks, weighted={stock_credit.get('stock_weighted', False)}")
    rspi_latest = rspi_data.get("latest")
    rspi_score = rspi_latest.get("rspi", "N/A") if rspi_latest else "N/A"
    print(f"  RSPI:      score={rspi_score}, history={len(rspi_data.get('history', []))}, scenarios={len(rspi_data.get('scenario_matrix', []))}")


def _remap_cohorts(cohorts: list[dict]) -> list[dict]:
    """Python cohort output → frontend 호환 형식 변환.

    Python: remaining_amount_billion, status=forced_liq/margin_call
    Frontend: amount, status=danger/marginCall

    v1.5.0: 6단계 status_map + 4단계 호환 (legacy_status)
    """
    # v1.5.0 6단계 매핑
    status_map_6 = {
        "debt_exceed": "debtExceed",
        "forced_liq": "forcedLiq",
        "margin_call": "marginCall",
        "caution": "caution",
        "good": "good",
        "safe": "safe",
    }
    # v1.4 호환 4단계 매핑
    legacy_map = {
        "debt_exceed": "danger",
        "forced_liq": "danger",
        "margin_call": "marginCall",
        "caution": "watch",
        "good": "watch",
        "watch": "watch",
        "safe": "safe",
    }
    result = []
    for c in cohorts:
        raw_status = c.get("status", "safe")
        entry = {
            "entry_date": c.get("entry_date", ""),
            "entry_kospi": c.get("entry_kospi", 0),
            "entry_stock_price": c.get("entry_stock_price", 0),
            "amount": c.get("remaining_amount_billion", 0),
            "pnl_pct": c.get("pnl_pct", 0),
            "collateral_ratio": c.get("collateral_ratio", 0),
            "collateral_ratio_pct": c.get("collateral_ratio_pct", 0),
            "status": legacy_map.get(raw_status, "safe"),
            "status_6": status_map_6.get(raw_status, raw_status),
        }
        liq_pct = c.get("liquidated_pct", 0)
        if liq_pct > 0:
            entry["liquidated_pct"] = liq_pct
        result.append(entry)
    return result


def _avg_trading_value(ts: list[dict]) -> int:
    """최근 20일 평균 거래대금."""
    recent = ts[-20:] if len(ts) >= 20 else ts
    vals = [r.get("kospi_trading_value_billion", 0) or 0 for r in recent]
    return round(sum(vals) / len(vals)) if vals else 10000


if __name__ == "__main__":
    export_all()
