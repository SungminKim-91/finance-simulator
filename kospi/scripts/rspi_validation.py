#!/usr/bin/env python3
"""
RSPI v3.1 검증 + 3단계 순차 최적화.

Phase A: 기본값으로 v3.0 vs v3.1 비교
Phase B: 3단계 순차 최적화 (감도→증폭기→시그널 가중치)
Phase C: 최종 검증 (최적 파라미터)
Phase D: 리포트

Usage:
    cd kospi
    python -m scripts.rspi_validation
    python -m scripts.rspi_validation --round1-only
    python -m scripts.rspi_validation --skip-optimization
"""
import json
import math
import statistics
import argparse
import itertools
from pathlib import Path
from collections import defaultdict

import sys as _sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import (
    RSPI_WEIGHTS, RSPI_SIGNAL_WEIGHTS,
    V1_PROXIMITY_POWER, V1_MARGIN_CALL_RATIO, V1_SAFE_RANGE,
    V2_LOOKBACK, V2_DIVISOR,
    V5_DIVISOR,
    VA_FLOOR, VA_CEILING, VA_LOG_SCALE,
    SAMSUNG_CREDIT_WEIGHT,
    STRUCTURAL_AMP_ALPHA, STRUCTURAL_AMP_BETA, STRUCTURAL_AMP_GAMMA,
    STRUCTURAL_AMP_MAX,
    INDIV_CUM_SUM_WINDOW,
    OVERNIGHT_EWY_DIVISOR,
)
from scripts.rspi_engine import RSPIEngine

DATA_DIR = PROJECT_ROOT / "data"


def load_timeseries():
    with open(DATA_DIR / "timeseries.json", encoding="utf-8") as f:
        return json.load(f)


def load_cohort_data():
    with open(DATA_DIR / "model_output.json", encoding="utf-8") as f:
        data = json.load(f)
    ch = data.get("cohort_history", {})
    registry = ch.get("registry", {})
    snapshots = ch.get("snapshots", [])
    d2c = {}
    for snap in snapshots:
        cohorts = []
        for ed, amt in snap.get("amounts", {}).items():
            if ed in registry and amt > 0:
                cohorts.append({
                    "entry_kospi": registry[ed]["entry_kospi"],
                    "remaining_amount_billion": amt,
                })
        d2c[snap["date"]] = cohorts
    return d2c


def run_pipeline(ts, d2c, power=V1_PROXIMITY_POWER,
                 signal_weights=None, amp_params=None,
                 sensitivity_params=None):
    """RSPI 전체 히스토리 계산."""
    engine = RSPIEngine(
        proximity_power=power,
        signal_weights=signal_weights,
        amp_params=amp_params,
        sensitivity_params=sensitivity_params,
    )
    total_credit = 0
    for rec in ts:
        c = rec.get("credit_balance_billion")
        if c and c > 0:
            total_credit = c
    sam_credit = total_credit * SAMSUNG_CREDIT_WEIGHT if total_credit > 0 else 0

    for idx in range(max(20, 0), len(ts)):
        rec = ts[idx]
        sam_price = rec.get("samsung", 0) or 0
        if sam_price <= 0:
            continue
        cohorts = d2c.get(rec["date"], [])
        on_data = {}
        is_latest = (idx == len(ts) - 1)
        lb_range = 1 if is_latest else min(4, idx + 1)
        for lb in range(0, lb_range):
            cand = ts[idx - lb]
            if cand.get("ewy_change_pct") is not None:
                on_data = {
                    "ewy_pct": cand.get("ewy_change_pct"),
                    "koru_pct": cand.get("koru_change_pct"),
                    "kospi_futures_pct": cand.get("kospi_futures_pct"),
                    "us_market_pct": cand.get("sp500_change_pct"),
                }
                break
        vols = [ts[j].get("samsung_volume", 0) or 0 for j in range(max(0, idx - 19), idx + 1)]
        adv = sum(vols) / len(vols) / 1000 if vols else 30000
        rc = rec.get("credit_balance_billion")
        dc = (rc * SAMSUNG_CREDIT_WEIGHT) if rc else sam_credit
        engine.calculate_for_date(
            date=rec["date"], ts=ts, cohorts=cohorts,
            overnight_data=on_data, samsung_credit_bn=dc,
            current_price=int(sam_price), adv_shares_k=adv,
        )
    return engine.history


def _next_day_returns(ts):
    ret = {}
    for i, rec in enumerate(ts):
        if i + 1 < len(ts):
            k0 = rec.get("kospi", 0) or 0
            k1 = ts[i + 1].get("kospi", 0) or 0
            if k0 > 0 and k1 > 0:
                ret[rec["date"]] = (k1 / k0 - 1) * 100
    return ret


def _eval_metrics(history, ts_returns, min_idx=80):
    """중립 비율, strong 방향 일치율, moderate 일치율."""
    valid = [h for h in history if h.get("rspi") is not None]
    # Skip first min_idx entries (개인누적 z-score warmup)
    if min_idx > 0:
        dates_sorted = sorted(set(h["date"] for h in valid))
        if len(dates_sorted) > min_idx:
            cutoff_date = dates_sorted[min_idx]
            valid = [h for h in valid if h["date"] >= cutoff_date]

    total = len(valid)
    if total == 0:
        return {"neutral_pct": 0, "strong_match": 0, "moderate_match": 0, "count": 0}

    neutral = sum(1 for h in valid if abs(h["rspi"]) < 5)
    neutral_pct = neutral / total

    # strong (|RSPI| >= 20)
    strong = [(h["rspi"], ts_returns.get(h["date"], 0))
              for h in valid if abs(h["rspi"]) >= 20 and h["date"] in ts_returns]
    if strong:
        strong_dir = [(r, ret) for r, ret in strong if abs(r) >= 1]
        strong_match = (sum(1 for r, ret in strong_dir
                            if (r < 0 and ret < 0) or (r > 0 and ret > 0))
                        / len(strong_dir)) if strong_dir else 0.5
    else:
        strong_match = 0

    # moderate (10 <= |RSPI| < 20)
    moderate = [(h["rspi"], ts_returns.get(h["date"], 0))
                for h in valid if 10 <= abs(h["rspi"]) < 20 and h["date"] in ts_returns]
    if moderate:
        mod_dir = [(r, ret) for r, ret in moderate if abs(r) >= 1]
        mod_match = (sum(1 for r, ret in mod_dir
                         if (r < 0 and ret < 0) or (r > 0 and ret > 0))
                     / len(mod_dir)) if mod_dir else 0.5
    else:
        mod_match = 0

    return {
        "neutral_pct": neutral_pct,
        "strong_match": strong_match,
        "strong_count": len(strong),
        "moderate_match": mod_match,
        "moderate_count": len(moderate),
        "count": total,
    }


def _false_alarm_count(history, ts_returns):
    """False alarm: |RSPI| > 20 and direction wrong."""
    cnt = 0
    for h in history:
        if h.get("rspi") is None or h["date"] not in ts_returns:
            continue
        r, ret = h["rspi"], ts_returns[h["date"]]
        if abs(r) > 20 and ((r < -20 and ret > 0) or (r > 20 and ret < 0)):
            cnt += 1
    return cnt


# ──────────────────────────────────────────────
# Phase A: v3.0 vs v3.1 비교
# ──────────────────────────────────────────────

def phase_a(ts, d2c, ts_returns):
    print("\n" + "=" * 60)
    print("Phase A: v3.0 vs v3.1 기본값 비교")
    print("=" * 60)

    # v3.1 기본값
    hist_v31 = run_pipeline(ts, d2c)
    m_v31 = _eval_metrics(hist_v31, ts_returns)
    fa_v31 = _false_alarm_count(hist_v31, ts_returns)

    # RSPI stats
    vals = [h["rspi"] for h in hist_v31 if h.get("rspi") is not None]

    print(f"\n  v3.1 기본값 결과 ({m_v31['count']}일):")
    print(f"    Q1 중립 비율:      {m_v31['neutral_pct']:.1%} (목표 65%+)")
    print(f"    Q3 strong 일치율:  {m_v31['strong_match']:.1%} ({m_v31['strong_count']}일, 목표 70%+)")
    print(f"    moderate 일치율:   {m_v31['moderate_match']:.1%} ({m_v31['moderate_count']}일)")
    print(f"    False alarm:       {fa_v31}건")
    print(f"    RSPI mean={statistics.mean(vals):.1f}, std={statistics.stdev(vals):.1f}")

    # 핵심 날짜
    print(f"\n  핵심 날짜 분해:")
    print(f"  {'날짜':<12} {'RSPI':>6} {'V1':>6} {'V1vel':>6} {'cum_z':>6} {'str_a':>6} {'V2':>6} {'V3':>6} {'V5':>6}")
    for target in ["2025-12-12", "2026-03-03", "2026-03-04", "2026-03-05"]:
        h = next((x for x in hist_v31 if x["date"] == target), None)
        if h and h.get("rspi") is not None:
            rv = h.get("raw_variables", {})
            sa = h.get("structural_amp", "?")
            print(f"  {target:<12} {h['rspi']:>+6.1f} {rv.get('v1', 0):>6.4f} "
                  f"{rv.get('v1_velocity', 0):>6.4f} {rv.get('indiv_cum_z', 0):>+6.2f} "
                  f"{sa:>6.3f} {rv.get('v2', 0):>+6.3f} {rv.get('v3', 0):>+6.3f} {rv.get('v5', 0):>+6.3f}")

    return hist_v31, m_v31


# ──────────────────────────────────────────────
# Phase B: 3단계 순차 최적화
# ──────────────────────────────────────────────

def round1_sensitivity(ts, d2c, ts_returns):
    """Round 1: 감도 파라미터 (V2 div, V3 EWY div, V5 div)."""
    print("\n" + "=" * 60)
    print("Round 1: 감도 파라미터 최적화 (64 조합)")
    print("=" * 60)

    v2_divs = [2.0, 2.5, 3.0, 3.5]
    v3_divs = [5.0, 6.0, 7.0, 8.0]
    v5_divs = [1.5, 2.0, 2.5, 3.0]

    results = []

    for v2d, v3d, v5d in itertools.product(v2_divs, v3_divs, v5_divs):
        sp = {"v2_divisor": v2d, "v3_ewy_divisor": v3d, "v5_divisor": v5d}
        hist = run_pipeline(ts, d2c, sensitivity_params=sp)
        m = _eval_metrics(hist, ts_returns)
        results.append({
            "v2d": v2d, "v3d": v3d, "v5d": v5d,
            "neutral": m["neutral_pct"], "strong": m["strong_match"],
            "strong_n": m["strong_count"], "moderate": m["moderate_match"],
        })

    # Sort: neutral DESC (primary), strong DESC (secondary)
    results.sort(key=lambda r: (-r["neutral"], -r["strong"]))

    print(f"\n  상위 10개:")
    print(f"  {'V2div':>5} {'V3div':>5} {'V5div':>5} {'중립%':>6} {'strong%':>8} {'strong#':>7} {'mod%':>6}")
    for r in results[:10]:
        print(f"  {r['v2d']:>5.1f} {r['v3d']:>5.1f} {r['v5d']:>5.1f} "
              f"{r['neutral']:>6.1%} {r['strong']:>8.1%} {r['strong_n']:>7} {r['moderate']:>6.1%}")

    # 선택: 중립 60%+ AND strong 65%+ 중 중립 최대
    best = None
    for threshold_n, threshold_s in [(0.65, 0.70), (0.60, 0.65), (0.55, 0.60), (0.50, 0.55), (0.40, 0.50)]:
        candidates = [r for r in results if r["neutral"] >= threshold_n and r["strong"] >= threshold_s]
        if candidates:
            best = candidates[0]
            print(f"\n  선택 (중립≥{threshold_n:.0%}, strong≥{threshold_s:.0%}): "
                  f"V2={best['v2d']}, V3={best['v3d']}, V5={best['v5d']}")
            break

    if best is None:
        best = results[0]
        print(f"\n  기준 미달 — 중립 최대 선택: V2={best['v2d']}, V3={best['v3d']}, V5={best['v5d']}")

    return best


def round2_amplifier(ts, d2c, ts_returns, r1_best):
    """Round 2: 증폭기 파라미터 (1600 조합)."""
    print("\n" + "=" * 60)
    print("Round 2: 증폭기 파라미터 최적화 (1600 조합)")
    print("=" * 60)

    sp = {"v2_divisor": r1_best["v2d"], "v3_ewy_divisor": r1_best["v3d"],
          "v5_divisor": r1_best["v5d"]}

    powers = [1.5, 2.0, 2.5, 3.0]
    alphas = [1.0, 1.5, 2.0, 2.5, 3.0]
    betas = [1.5, 2.0, 3.0, 4.0, 5.0]
    gammas = [0.3, 0.5, 0.7, 1.0]
    windows = [20, 40, 60, 80]

    results = []
    total = len(powers) * len(alphas) * len(betas) * len(gammas) * len(windows)
    done = 0

    for pwr, alpha, beta, gamma, win in itertools.product(powers, alphas, betas, gammas, windows):
        done += 1
        if done % 200 == 0:
            print(f"  ... {done}/{total}")

        amp_params = {
            "alpha": alpha, "beta": beta, "gamma": gamma,
            "max_amp": STRUCTURAL_AMP_MAX, "sum_window": win,
        }
        hist = run_pipeline(ts, d2c, power=pwr, amp_params=amp_params,
                           sensitivity_params=sp)
        m = _eval_metrics(hist, ts_returns)
        results.append({
            "power": pwr, "alpha": alpha, "beta": beta, "gamma": gamma, "window": win,
            "neutral": m["neutral_pct"], "strong": m["strong_match"],
            "strong_n": m["strong_count"], "moderate": m["moderate_match"],
        })

    # Sort: strong DESC (primary), neutral filter
    # Filter: neutral >= 55%
    filtered = [r for r in results if r["neutral"] >= 0.55]
    if not filtered:
        filtered = results
    filtered.sort(key=lambda r: (-r["strong"], -r["neutral"]))

    print(f"\n  상위 10개:")
    print(f"  {'pwr':>4} {'α':>4} {'β':>4} {'γ':>4} {'win':>4} {'중립%':>6} {'strong%':>8} {'#':>3} {'mod%':>6}")
    for r in filtered[:10]:
        print(f"  {r['power']:>4.1f} {r['alpha']:>4.1f} {r['beta']:>4.1f} "
              f"{r['gamma']:>4.1f} {r['window']:>4} "
              f"{r['neutral']:>6.1%} {r['strong']:>8.1%} {r['strong_n']:>3} {r['moderate']:>6.1%}")

    best = filtered[0]
    print(f"\n  선택: power={best['power']}, α={best['alpha']}, β={best['beta']}, "
          f"γ={best['gamma']}, window={best['window']}")
    return best


def round3_signal_weights(ts, d2c, ts_returns, r1_best, r2_best):
    """Round 3: 시그널 가중치 (합=1 조합)."""
    print("\n" + "=" * 60)
    print("Round 3: 시그널 가중치 최적화")
    print("=" * 60)

    sp = {"v2_divisor": r1_best["v2d"], "v3_ewy_divisor": r1_best["v3d"],
          "v5_divisor": r1_best["v5d"]}

    ws2_opts = [0.25, 0.30, 0.35, 0.40]
    ws3_opts = [0.35, 0.40, 0.45, 0.50]
    ws5_opts = [0.10, 0.15, 0.20, 0.25]

    valid_combos = [(w2, w3, w5) for w2 in ws2_opts for w3 in ws3_opts for w5 in ws5_opts
                    if abs(w2 + w3 + w5 - 1.0) < 0.01]

    print(f"  유효 조합: {len(valid_combos)}개")

    amp_params = {
        "alpha": r2_best["alpha"], "beta": r2_best["beta"],
        "gamma": r2_best["gamma"], "max_amp": STRUCTURAL_AMP_MAX,
        "sum_window": r2_best["window"],
    }

    results = []
    for ws2, ws3, ws5 in valid_combos:
        sw = {"ws2": ws2, "ws3": ws3, "ws5": ws5}
        hist = run_pipeline(ts, d2c, power=r2_best["power"],
                           signal_weights=sw, amp_params=amp_params,
                           sensitivity_params=sp)
        m = _eval_metrics(hist, ts_returns)
        results.append({
            "ws2": ws2, "ws3": ws3, "ws5": ws5,
            "neutral": m["neutral_pct"], "strong": m["strong_match"],
            "strong_n": m["strong_count"], "moderate": m["moderate_match"],
        })

    results.sort(key=lambda r: (-r["strong"], -r["moderate"]))

    print(f"\n  전체 결과:")
    print(f"  {'ws2':>5} {'ws3':>5} {'ws5':>5} {'중립%':>6} {'strong%':>8} {'#':>3} {'mod%':>6}")
    for r in results:
        print(f"  {r['ws2']:>5.2f} {r['ws3']:>5.2f} {r['ws5']:>5.2f} "
              f"{r['neutral']:>6.1%} {r['strong']:>8.1%} {r['strong_n']:>3} {r['moderate']:>6.1%}")

    best = results[0]
    print(f"\n  선택: ws2={best['ws2']}, ws3={best['ws3']}, ws5={best['ws5']}")
    return best


# ──────────────────────────────────────────────
# Phase C: 최종 검증
# ──────────────────────────────────────────────

def phase_c(ts, d2c, ts_returns, r1, r2, r3):
    print("\n" + "=" * 60)
    print("Phase C: 최종 검증 (최적 파라미터)")
    print("=" * 60)

    sp = {"v2_divisor": r1["v2d"], "v3_ewy_divisor": r1["v3d"],
          "v5_divisor": r1["v5d"]}

    amp_params = {
        "alpha": r2["alpha"], "beta": r2["beta"],
        "gamma": r2["gamma"], "max_amp": STRUCTURAL_AMP_MAX,
        "sum_window": r2["window"],
    }
    sw = {"ws2": r3["ws2"], "ws3": r3["ws3"], "ws5": r3["ws5"]}

    hist = run_pipeline(ts, d2c, power=r2["power"], signal_weights=sw,
                       amp_params=amp_params, sensitivity_params=sp)
    m = _eval_metrics(hist, ts_returns)
    fa = _false_alarm_count(hist, ts_returns)

    vals = [h["rspi"] for h in hist if h.get("rspi") is not None]

    print(f"\n  C1. 전체 재검증:")
    print(f"    Q1 중립 비율:      {m['neutral_pct']:.1%}")
    print(f"    Q3 strong 일치율:  {m['strong_match']:.1%} ({m['strong_count']}일)")
    print(f"    moderate 일치율:   {m['moderate_match']:.1%} ({m['moderate_count']}일)")
    print(f"    False alarm:       {fa}건")
    print(f"    RSPI mean={statistics.mean(vals):.1f}, std={statistics.stdev(vals):.1f}")

    # C2. 음전환 추적
    daily_rets = {}
    for i, rec in enumerate(ts):
        if i > 0:
            p = ts[i - 1].get("kospi", 0) or 0
            c = rec.get("kospi", 0) or 0
            if p > 0 and c > 0:
                daily_rets[rec["date"]] = (c / p - 1) * 100
    rspi_map = {h["date"]: h["rspi"] for h in hist if h.get("rspi") is not None}

    events = []
    for i in range(5, len(ts) - 10):
        date = ts[i]["date"]
        if date not in daily_rets:
            continue
        prev_5 = [ts[j]["date"] for j in range(i - 5, i)]
        up_days = sum(1 for d in prev_5 if daily_rets.get(d, 0) > 0)
        if up_days >= 4 and daily_rets[date] < 0:
            cum = sum(daily_rets.get(ts[j]["date"], 0) for j in range(i + 1, min(i + 6, len(ts))))
            rspi_10d = [rspi_map[ts[j]["date"]] for j in range(i, min(i + 10, len(ts)))
                        if ts[j]["date"] in rspi_map]
            avg_r = statistics.mean(rspi_10d) if rspi_10d else 0
            etype = "deep" if cum < -5 else "mild" if cum < -2 else "quick"
            events.append({"type": etype, "avg_rspi": avg_r})

    print(f"\n  C2. 음전환 추적:")
    for et in ["deep", "mild", "quick"]:
        grp = [e for e in events if e["type"] == et]
        avg = statistics.mean([e["avg_rspi"] for e in grp]) if grp else 0
        print(f"    {et:<6}: {len(grp)}건, 평균 RSPI={avg:+.1f}")

    # C3. amp A/B
    no_amp_vals = [(h["date"], h["rspi"] / h["volume_amp"] if h.get("volume_amp") and h["volume_amp"] > 0 else h["rspi"])
                   for h in hist if h.get("rspi") is not None and h.get("volume_amp") is not None]
    with_amp_vals = [(h["date"], h["rspi"]) for h in hist if h.get("rspi") is not None]

    def _strong_match(pairs):
        s = [(r, ts_returns.get(d, 0)) for d, r in pairs if abs(r) >= 20 and d in ts_returns]
        if not s:
            return 0, 0
        sd = [(r, ret) for r, ret in s if abs(r) >= 1]
        return (sum(1 for r, ret in sd if (r < 0 and ret < 0) or (r > 0 and ret > 0)) / len(sd) if sd else 0.5), len(s)

    na_m, na_n = _strong_match(no_amp_vals)
    wa_m, wa_n = _strong_match(with_amp_vals)
    print(f"\n  C3. 거래량 증폭기:")
    print(f"    amp 없이: strong 일치율={na_m:.1%} ({na_n}일)")
    print(f"    amp 적용: strong 일치율={wa_m:.1%} ({wa_n}일)")

    # C4. False alarm 상세
    print(f"\n  C4. False alarm 상세:")
    fa_list = []
    for h in hist:
        if h.get("rspi") is None or h["date"] not in ts_returns:
            continue
        r, ret = h["rspi"], ts_returns[h["date"]]
        if abs(r) > 20 and ((r < -20 and ret > 0) or (r > 20 and ret < 0)):
            rv = h.get("raw_variables", {})
            vc = h.get("variable_contributions", {})
            culprit = max(vc, key=lambda k: abs(vc.get(k, 0) or 0)) if vc else "?"
            fa_list.append((h["date"], r, ret, culprit, h.get("structural_amp", 0)))
    for d, r, ret, c, sa in fa_list[:10]:
        print(f"    {d}: RSPI={r:+.1f}, 다음날={ret:+.2f}%, 범인={c}, str_amp={sa:.2f}")

    # C5. 핵심 날짜
    print(f"\n  C5. 핵심 날짜:")
    print(f"  {'날짜':<12} {'RSPI':>6} {'V1':>6} {'V1vel':>6} {'cum_z':>6} {'str_a':>6} {'V2':>6} {'V3':>6} {'V5':>6}")
    for target in ["2025-12-12", "2026-03-03", "2026-03-04", "2026-03-05"]:
        h = next((x for x in hist if x["date"] == target), None)
        if h and h.get("rspi") is not None:
            rv = h.get("raw_variables", {})
            sa = h.get("structural_amp", "?")
            print(f"  {target:<12} {h['rspi']:>+6.1f} {rv.get('v1', 0):>6.4f} "
                  f"{rv.get('v1_velocity', 0):>6.4f} {rv.get('indiv_cum_z', 0):>+6.2f} "
                  f"{sa:>6.3f} {rv.get('v2', 0):>+6.3f} {rv.get('v3', 0):>+6.3f} {rv.get('v5', 0):>+6.3f}")

    # C6. 과적합 체크
    print(f"\n  C6. 과적합 체크:")
    noise_pairs = [(h["rspi"], ts_returns.get(h["date"], 0))
                   for h in hist if h.get("rspi") is not None and abs(h["rspi"]) < 5 and h["date"] in ts_returns]
    if noise_pairs:
        noise_dir = [(r, ret) for r, ret in noise_pairs if abs(r) >= 0.5]
        noise_match = sum(1 for r, ret in noise_dir if (r < 0 and ret < 0) or (r > 0 and ret > 0)) / len(noise_dir) if noise_dir else 0.5
        print(f"    noise 방향 일치율: {noise_match:.1%} (58% 이하 정상)")

    return hist, m, fa


# ──────────────────────────────────────────────
# Phase D: 최종 리포트
# ──────────────────────────────────────────────

def phase_d(m_v30, m_v31_default, m_v31_opt, fa_opt, r1, r2, r3):
    print("\n" + "=" * 60)
    print("Phase D: RSPI v3.1 최종 검증 리포트")
    print("=" * 60)

    print(f"""
  1. 구조 변경: 덧셈 → 곱셈 모델
     V4(개인수급 패턴) 삭제 → 개인누적 z-score (증폭기 편입)
     V1을 시그널→증폭기로 이동

  2. 최적 파라미터:
     감도: V2_div={r1['v2d']}, V3_EWY_div={r1['v3d']}, V5_div={r1['v5d']}
     증폭기: power={r2['power']}, α={r2['alpha']}, β={r2['beta']}, γ={r2['gamma']}, window={r2['window']}
     시그널: ws2={r3['ws2']}, ws3={r3['ws3']}, ws5={r3['ws5']}

  3. 검증 비교:
     ┌───────────────┬──────────┬──────────┬──────────┐
     │ 지표          │ v3.0     │ v3.1기본 │ v3.1최적 │
     ├───────────────┼──────────┼──────────┼──────────┤
     │ Q1: 중립 비율 │ 25.7%    │ {m_v31_default['neutral_pct']:.1%}    │ {m_v31_opt['neutral_pct']:.1%}    │
     │ Q3: strong 일치│ 83.3%   │ {m_v31_default['strong_match']:.1%}    │ {m_v31_opt['strong_match']:.1%}    │
     │ moderate 일치 │ 71.4%    │ {m_v31_default['moderate_match']:.1%}    │ {m_v31_opt['moderate_match']:.1%}    │
     │ false alarm   │ 9        │ —        │ {fa_opt}        │
     └───────────────┴──────────┴──────────┴──────────┘
""")

    q1 = m_v31_opt["neutral_pct"] >= 0.65
    q3 = m_v31_opt["strong_match"] >= 0.70
    overall = "유효" if (q1 and q3) else "부분유효" if (q1 or q3) else "무효"
    print(f"  Q1: {'PASS' if q1 else 'FAIL'}, Q3: {'PASS' if q3 else 'FAIL'}")
    print(f"  전체 판정: {overall}")

    return overall


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RSPI v3.1 Validation + Optimization")
    parser.add_argument("--skip-optimization", action="store_true")
    parser.add_argument("--round1-only", action="store_true")
    args = parser.parse_args()

    print("RSPI v3.1 검증 + 3단계 순차 최적화")
    print("─" * 60)

    ts = load_timeseries()
    d2c = load_cohort_data()
    ts_returns = _next_day_returns(ts)
    print(f"  데이터: {len(ts)}일, 코호트: {len(d2c)}일")

    # Phase A
    hist_default, m_default = phase_a(ts, d2c, ts_returns)

    if args.skip_optimization:
        print("\n최적화 건너뜀.")
        return

    # Phase B
    r1 = round1_sensitivity(ts, d2c, ts_returns)

    if args.round1_only:
        print("\nRound 1만 실행.")
        return

    r2 = round2_amplifier(ts, d2c, ts_returns, r1)
    r3 = round3_signal_weights(ts, d2c, ts_returns, r1, r2)

    # Phase C
    hist_opt, m_opt, fa_opt = phase_c(ts, d2c, ts_returns, r1, r2, r3)

    # Phase D
    m_v30 = {"neutral_pct": 0.257, "strong_match": 0.833, "moderate_match": 0.714}
    overall = phase_d(m_v30, m_default, m_opt, fa_opt, r1, r2, r3)

    print(f"\n{'=' * 60}")
    print(f"검증 완료. 전체 판정: {overall}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
