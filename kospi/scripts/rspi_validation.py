#!/usr/bin/env python3
"""
RSPI v2.3.0 검증 프레임워크 — 9단계 변수별 유효성 + 시그널 강도 + power 최적화.

Usage:
    cd kospi
    python -m scripts.rspi_validation
    python -m scripts.rspi_validation --power-only   # Step 9만 실행
"""
import json
import math
import statistics
import argparse
from pathlib import Path
from collections import defaultdict

import sys as _sys
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(PROJECT_ROOT))

from config.constants import (
    RSPI_WEIGHTS, V1_PROXIMITY_POWER, V1_MARGIN_CALL_RATIO, V1_SAFE_RANGE,
    V2_LOOKBACK, V2_DIVISOR,
    OVERNIGHT_WEIGHTS,
    V4_CAPITULATION_PREV, V4_CAPITULATION_CURR, V4_LARGE_BUY, V4_DECLINE_RATIO,
    V5_DIVISOR,
    VA_FLOOR, VA_CEILING, VA_LOG_SCALE,
    SAMSUNG_CREDIT_WEIGHT,
)
from scripts.rspi_engine import (
    RSPIEngine, calc_cohort_proximity, calc_collateral_ratio,
)


DATA_DIR = PROJECT_ROOT / "data"
REPORT_DIR = PROJECT_ROOT.parent / "docs" / "04-report"


def load_timeseries():
    ts_path = DATA_DIR / "timeseries.json"
    with open(ts_path, encoding="utf-8") as f:
        return json.load(f)


def load_cohort_data():
    """model_output.json에서 cohort_history (registry + snapshots) 로드."""
    output_path = DATA_DIR / "model_output.json"
    with open(output_path, encoding="utf-8") as f:
        data = json.load(f)

    ch = data.get("cohort_history", {})
    cohort_registry = ch.get("registry", {})
    cohort_snapshots = ch.get("snapshots", [])

    # 날짜별 코호트 매핑 (look-ahead bias 제거 — v2.2.2)
    date_to_cohorts = {}
    for snap in cohort_snapshots:
        cohorts_for_date = []
        for entry_date, amount in snap.get("amounts", {}).items():
            if entry_date in cohort_registry and amount > 0:
                cohorts_for_date.append({
                    "entry_kospi": cohort_registry[entry_date]["entry_kospi"],
                    "remaining_amount_billion": amount,
                })
        date_to_cohorts[snap["date"]] = cohorts_for_date

    return date_to_cohorts


def run_rspi_pipeline(ts, date_to_cohorts, power=V1_PROXIMITY_POWER, weights=None):
    """RSPI 전체 히스토리 계산 (특정 power/weights로)."""
    engine = RSPIEngine(weights=weights, proximity_power=power)

    total_credit = 0
    for rec in ts:
        c = rec.get("credit_balance_billion")
        if c and c > 0:
            total_credit = c
    samsung_credit_bn = total_credit * SAMSUNG_CREDIT_WEIGHT if total_credit > 0 else 0

    start_idx = max(20, 0)
    for idx in range(start_idx, len(ts)):
        rec = ts[idx]
        sam_price = rec.get("samsung", 0) or 0
        if sam_price <= 0:
            continue

        date_cohorts = date_to_cohorts.get(rec["date"], [])

        # 야간 데이터
        on_data = {}
        is_latest = (idx == len(ts) - 1)
        lookback_range = 1 if is_latest else min(4, idx + 1)
        for lb in range(0, lookback_range):
            cand = ts[idx - lb]
            if cand.get("ewy_change_pct") is not None:
                on_data = {
                    "ewy_pct": cand.get("ewy_change_pct"),
                    "koru_pct": cand.get("koru_change_pct"),
                    "kospi_futures_pct": cand.get("kospi_futures_pct"),
                    "us_market_pct": cand.get("sp500_change_pct"),
                }
                break

        # ADV
        vols = [ts[j].get("samsung_volume", 0) or 0 for j in range(max(0, idx - 19), idx + 1)]
        adv = sum(vols) / len(vols) / 1000 if vols else 30000

        rec_credit = rec.get("credit_balance_billion")
        day_credit_bn = (rec_credit * SAMSUNG_CREDIT_WEIGHT) if rec_credit else samsung_credit_bn

        engine.calculate_for_date(
            date=rec["date"],
            ts=ts,
            cohorts=date_cohorts,
            overnight_data=on_data,
            samsung_credit_bn=day_credit_bn,
            current_price=int(sam_price),
            adv_shares_k=adv,
        )

    return engine.history


def _basic_stats(values):
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "mean": statistics.mean(values),
        "std": statistics.stdev(values) if len(values) > 1 else 0,
        "min": min(values),
        "max": max(values),
        "median": statistics.median(values),
    }


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return 0.0, 1.0
    mx, my = sum(xs) / n, sum(ys) / n
    sx = math.sqrt(sum((x - mx) ** 2 for x in xs) / (n - 1)) if n > 1 else 1
    sy = math.sqrt(sum((y - my) ** 2 for y in ys) / (n - 1)) if n > 1 else 1
    if sx == 0 or sy == 0:
        return 0.0, 1.0
    r = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / ((n - 1) * sx * sy)
    r = max(-1.0, min(1.0, r))
    # t-test for significance
    if abs(r) >= 1.0:
        p = 0.0
    else:
        t = r * math.sqrt((n - 2) / (1 - r * r))
        # approximate p-value using normal approximation for large n
        p = 2 * (1 - _norm_cdf(abs(t)))
    return r, p


def _norm_cdf(x):
    """Approximation of standard normal CDF."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ──────────────────────────────────────────────
# Step 1: 변수별 분포 진단
# ──────────────────────────────────────────────

def step1_variable_distribution(history):
    """각 변수(V1~V5, VA)의 분포 통계."""
    print("\n" + "=" * 60)
    print("Step 1: 변수별 분포 진단")
    print("=" * 60)

    var_keys = ["v1", "v2", "v3", "v4", "v5"]
    results = {}

    for vk in var_keys:
        vals = [h["raw_variables"][vk] for h in history
                if h.get("raw_variables") and h["raw_variables"].get(vk) is not None]
        stats = _basic_stats(vals)

        # 분포 버킷
        near_zero = sum(1 for v in vals if abs(v) < 0.01)
        weak = sum(1 for v in vals if 0.01 <= abs(v) < 0.2)
        medium = sum(1 for v in vals if 0.2 <= abs(v) < 0.5)
        strong = sum(1 for v in vals if abs(v) >= 0.5)

        results[vk] = {**stats, "near_zero": near_zero, "weak": weak, "medium": medium, "strong": strong}

        print(f"\n  {vk.upper()}: mean={stats.get('mean', 0):.4f}, std={stats.get('std', 0):.4f}, "
              f"min={stats.get('min', 0):.4f}, max={stats.get('max', 0):.4f}, median={stats.get('median', 0):.4f}")
        print(f"    |v|<0.01: {near_zero}일 ({near_zero / len(vals) * 100:.1f}%)" if vals else "    No data")
        print(f"    0.01~0.2: {weak}일, 0.2~0.5: {medium}일, 0.5+: {strong}일")

    # VA (volume amplifier)
    va_vals = [h.get("volume_amp", 1.0) for h in history if h.get("volume_amp") is not None]
    va_stats = _basic_stats(va_vals)
    over_15 = sum(1 for v in va_vals if v > 1.5)
    results["va"] = {**va_stats, "over_1.5": over_15}

    print(f"\n  VA: mean={va_stats.get('mean', 0):.4f}, std={va_stats.get('std', 0):.4f}, "
          f"min={va_stats.get('min', 0):.4f}, max={va_stats.get('max', 0):.4f}")
    print(f"    amp > 1.5: {over_15}일 ({over_15 / len(va_vals) * 100:.1f}%)" if va_vals else "    No data")

    return results


# ──────────────────────────────────────────────
# Step 2: RSPI 분포 진단
# ──────────────────────────────────────────────

def step2_rspi_distribution(history, ts):
    """RSPI 전체 분포 + 레벨 분포 + false alarm 후보."""
    print("\n" + "=" * 60)
    print("Step 2: RSPI 분포 진단")
    print("=" * 60)

    rspi_vals = [(h["date"], h["rspi"]) for h in history if h.get("rspi") is not None]
    vals = [v for _, v in rspi_vals]
    stats = _basic_stats(vals)

    print(f"\n  RSPI 기본통계: mean={stats.get('mean', 0):.2f}, std={stats.get('std', 0):.2f}, "
          f"min={stats.get('min', 0):.2f}, max={stats.get('max', 0):.2f}, median={stats.get('median', 0):.2f}")

    # 레벨 분포
    buckets = {
        "극단 매도 (< -40)": lambda v: v < -40,
        "강한 매도 (-40~-20)": lambda v: -40 <= v < -20,
        "약한 매도 (-20~-5)": lambda v: -20 <= v < -5,
        "중립 (-5~+5)": lambda v: -5 <= v <= 5,
        "약한 반등 (+5~+20)": lambda v: 5 < v <= 20,
        "강한 반등 (+20~+40)": lambda v: 20 < v <= 40,
        "극단 반등 (> +40)": lambda v: v > 40,
    }

    print(f"\n  레벨 분포 ({len(vals)}일):")
    level_counts = {}
    for label, fn in buckets.items():
        cnt = sum(1 for v in vals if fn(v))
        pct = cnt / len(vals) * 100 if vals else 0
        level_counts[label] = cnt
        print(f"    {label}: {cnt}일 ({pct:.1f}%)")

    # Q1 체크: |RSPI| < 5인 날 70%+
    neutral_count = level_counts.get("중립 (-5~+5)", 0)
    q1_pct = neutral_count / len(vals) * 100 if vals else 0
    q1_pass = q1_pct >= 70
    print(f"\n  Q1 체크: |RSPI|<5 = {neutral_count}일 ({q1_pct:.1f}%) → {'PASS' if q1_pass else 'FAIL'} (기준: 70%+)")

    # False alarm 후보: |RSPI| > 20 and 다음날 |수익률| < 1%
    ts_returns = {}
    for i, rec in enumerate(ts):
        if i + 1 < len(ts):
            today_kospi = rec.get("kospi", 0) or 0
            next_kospi = ts[i + 1].get("kospi", 0) or 0
            if today_kospi > 0 and next_kospi > 0:
                ts_returns[rec["date"]] = (next_kospi / today_kospi - 1) * 100

    false_alarms = []
    for date, rspi in rspi_vals:
        if abs(rspi) > 20 and date in ts_returns:
            next_ret = ts_returns[date]
            if abs(next_ret) < 1.0:
                false_alarms.append((date, rspi, next_ret))

    print(f"\n  False alarm 후보 (|RSPI|>20 & 다음날 |수익률|<1%): {len(false_alarms)}건")
    for date, rspi, ret in false_alarms[:10]:
        print(f"    {date}: RSPI={rspi:.1f}, 다음날={ret:+.2f}%")

    return {"stats": stats, "level_counts": level_counts, "q1_pass": q1_pass, "false_alarms": false_alarms}


# ──────────────────────────────────────────────
# Step 3: 변수별 예측력
# ──────────────────────────────────────────────

def step3_variable_predictive_power(history, ts):
    """각 변수의 다음날 수익률 예측력 (상관계수, quintile spread, hit rate)."""
    print("\n" + "=" * 60)
    print("Step 3: 변수별 예측력 검증")
    print("=" * 60)

    # 다음날 수익률 매핑
    ts_returns = {}
    for i, rec in enumerate(ts):
        if i + 1 < len(ts):
            today_kospi = rec.get("kospi", 0) or 0
            next_kospi = ts[i + 1].get("kospi", 0) or 0
            if today_kospi > 0 and next_kospi > 0:
                ts_returns[rec["date"]] = (next_kospi / today_kospi - 1) * 100

    var_keys = ["v1", "v2", "v3", "v4", "v5"]
    results = {}

    print(f"\n  {'ID':<4} {'상관계수':>8} {'p-value':>8} {'spread(%)':>10} {'hit rate':>8} {'판정':>6}")
    print(f"  {'─' * 4} {'─' * 8} {'─' * 8} {'─' * 10} {'─' * 8} {'─' * 6}")

    for vk in var_keys:
        pairs = []
        for h in history:
            if h.get("raw_variables") and h["raw_variables"].get(vk) is not None:
                if h["date"] in ts_returns:
                    pairs.append((h["raw_variables"][vk], ts_returns[h["date"]]))

        if len(pairs) < 10:
            print(f"  {vk.upper():<4} {'N/A':>8} {'N/A':>8} {'N/A':>10} {'N/A':>8} {'N/A':>6}")
            results[vk] = {"corr": 0, "p": 1, "spread": 0, "hit_rate": 0, "verdict": "N/A"}
            continue

        xs, ys = zip(*pairs)
        corr, p = _pearson(list(xs), list(ys))

        # Quintile spread
        sorted_pairs = sorted(pairs, key=lambda x: x[0])
        n = len(sorted_pairs)
        q = n // 5
        bottom_20 = [y for _, y in sorted_pairs[:q]]
        top_20 = [y for _, y in sorted_pairs[-q:]]
        spread = statistics.mean(top_20) - statistics.mean(bottom_20) if bottom_20 and top_20 else 0

        # Hit rate: V > 0 (매도) → 다음날 하락
        sell_signal = [(v, r) for v, r in pairs if v > 0.01]
        buy_signal = [(v, r) for v, r in pairs if v < -0.01]
        sell_hits = sum(1 for _, r in sell_signal if r < 0) if sell_signal else 0
        buy_hits = sum(1 for _, r in buy_signal if r > 0) if buy_signal else 0
        total_directional = len(sell_signal) + len(buy_signal)
        hit_rate = (sell_hits + buy_hits) / total_directional if total_directional > 0 else 0.5

        # 판정
        if abs(corr) > 0.08 and p < 0.10:
            verdict = "유효"
        elif abs(corr) > 0.03 or p < 0.20:
            verdict = "의심"
        else:
            verdict = "무효"

        results[vk] = {"corr": corr, "p": p, "spread": spread, "hit_rate": hit_rate, "verdict": verdict}
        print(f"  {vk.upper():<4} {corr:>+8.4f} {p:>8.4f} {spread:>+10.4f} {hit_rate:>8.1%} {verdict:>6}")

    return results


# ──────────────────────────────────────────────
# Step 4: 시그널 강도 검증
# ──────────────────────────────────────────────

def step4_signal_strength(history, ts):
    """RSPI 크기별 4 버킷의 예측력."""
    print("\n" + "=" * 60)
    print("Step 4: RSPI 시그널 강도 검증")
    print("=" * 60)

    ts_returns = {}
    for i, rec in enumerate(ts):
        if i + 1 < len(ts):
            today_kospi = rec.get("kospi", 0) or 0
            next_kospi = ts[i + 1].get("kospi", 0) or 0
            if today_kospi > 0 and next_kospi > 0:
                ts_returns[rec["date"]] = (next_kospi / today_kospi - 1) * 100

    bucket_defs = [
        ("noise", lambda r: abs(r) < 5),
        ("mild", lambda r: 5 <= abs(r) < 15),
        ("moderate", lambda r: 15 <= abs(r) < 30),
        ("strong", lambda r: abs(r) >= 30),
    ]

    results = {}
    print(f"\n  {'버킷':<10} {'날수':>5} {'평균|수익률|':>12} {'std':>8} {'방향 일치율':>10}")
    print(f"  {'─' * 10} {'─' * 5} {'─' * 12} {'─' * 8} {'─' * 10}")

    for bname, bfn in bucket_defs:
        entries = []
        for h in history:
            if h.get("rspi") is not None and h["date"] in ts_returns:
                if bfn(h["rspi"]):
                    entries.append((h["rspi"], ts_returns[h["date"]]))

        if not entries:
            results[bname] = {"count": 0, "mean_abs_ret": 0, "std": 0, "direction_match": 0}
            print(f"  {bname:<10} {0:>5} {'N/A':>12} {'N/A':>8} {'N/A':>10}")
            continue

        abs_rets = [abs(r) for _, r in entries]
        rets = [r for _, r in entries]
        mean_abs = statistics.mean(abs_rets)
        std_ret = statistics.stdev(rets) if len(rets) > 1 else 0

        # 방향 일치율 (|RSPI| < 1 제외)
        directional = [(rspi, ret) for rspi, ret in entries if abs(rspi) >= 1]
        if directional:
            matches = sum(1 for rspi, ret in directional
                          if (rspi < 0 and ret < 0) or (rspi > 0 and ret > 0))
            dir_match = matches / len(directional)
        else:
            dir_match = 0.5

        results[bname] = {
            "count": len(entries),
            "mean_abs_ret": mean_abs,
            "std": std_ret,
            "direction_match": dir_match,
        }
        print(f"  {bname:<10} {len(entries):>5} {mean_abs:>12.3f}% {std_ret:>8.3f} {dir_match:>10.1%}")

    # Q3 체크: strong에서 65%+
    strong_match = results.get("strong", {}).get("direction_match", 0)
    q3_pass = strong_match >= 0.65
    noise_match = results.get("noise", {}).get("direction_match", 0)
    print(f"\n  Q3 체크: strong 일치율 = {strong_match:.1%} → {'PASS' if q3_pass else 'FAIL'} (기준: 65%+)")
    print(f"  noise 일치율 = {noise_match:.1%} (기대: ~50%)")

    return results


# ──────────────────────────────────────────────
# Step 5: 음전환 후 전개 추적
# ──────────────────────────────────────────────

def step5_post_decline_tracking(history, ts):
    """상승세 → 음전환 이벤트 식별 + 이후 5일 추적."""
    print("\n" + "=" * 60)
    print("Step 5: 음전환 후 전개 추적")
    print("=" * 60)

    # 일별 수익률 계산
    daily_rets = {}
    for i, rec in enumerate(ts):
        if i > 0:
            prev = ts[i - 1].get("kospi", 0) or 0
            curr = rec.get("kospi", 0) or 0
            if prev > 0 and curr > 0:
                daily_rets[rec["date"]] = (curr / prev - 1) * 100

    # RSPI 매핑
    rspi_map = {h["date"]: h["rspi"] for h in history if h.get("rspi") is not None}

    # 음전환 이벤트: 최근 5일 중 4일+ 상승 후 첫 하락
    events = []
    for i in range(5, len(ts) - 10):
        rec = ts[i]
        date = rec["date"]
        if date not in daily_rets:
            continue

        # 최근 5일 (i-5 ~ i-1) 수익률
        prev_5_dates = [ts[j]["date"] for j in range(i - 5, i)]
        up_days = sum(1 for d in prev_5_dates if daily_rets.get(d, 0) > 0)
        today_ret = daily_rets[date]

        if up_days >= 4 and today_ret < 0:
            # 이후 5일 누적 수익률
            cum_ret = 0
            for j in range(i + 1, min(i + 6, len(ts))):
                if ts[j]["date"] in daily_rets:
                    cum_ret += daily_rets[ts[j]["date"]]

            # 이후 10일 RSPI 평균
            rspi_10d = []
            match_count = 0
            for j in range(i, min(i + 10, len(ts))):
                d = ts[j]["date"]
                if d in rspi_map and d in daily_rets:
                    rspi_10d.append(rspi_map[d])
                    r = daily_rets[d]
                    rsp = rspi_map[d]
                    if (rsp < 0 and r < 0) or (rsp > 0 and r > 0):
                        match_count += 1

            avg_rspi = statistics.mean(rspi_10d) if rspi_10d else 0
            dir_match = match_count / len(rspi_10d) if rspi_10d else 0

            # 분류
            if cum_ret < -5:
                etype = "deep_decline"
            elif cum_ret < -2:
                etype = "mild_decline"
            else:
                etype = "quick_recovery"

            events.append({
                "date": date, "type": etype, "cum_ret_5d": cum_ret,
                "avg_rspi_10d": avg_rspi, "dir_match_10d": dir_match,
            })

    # 집계
    type_agg = defaultdict(list)
    for e in events:
        type_agg[e["type"]].append(e)

    print(f"\n  {'이벤트 유형':<16} {'건수':>5} {'평균 RSPI':>10} {'방향 일치율':>10}")
    print(f"  {'─' * 16} {'─' * 5} {'─' * 10} {'─' * 10}")

    results = {}
    for etype in ["deep_decline", "mild_decline", "quick_recovery"]:
        group = type_agg.get(etype, [])
        if not group:
            print(f"  {etype:<16} {0:>5} {'N/A':>10} {'N/A':>10}")
            results[etype] = {"count": 0}
            continue

        avg_rspi = statistics.mean([e["avg_rspi_10d"] for e in group])
        avg_match = statistics.mean([e["dir_match_10d"] for e in group])

        results[etype] = {"count": len(group), "avg_rspi": avg_rspi, "avg_match": avg_match}
        print(f"  {etype:<16} {len(group):>5} {avg_rspi:>+10.2f} {avg_match:>10.1%}")

    # deep_decline RSPI < mild_decline RSPI?
    deep_rspi = results.get("deep_decline", {}).get("avg_rspi", 0)
    mild_rspi = results.get("mild_decline", {}).get("avg_rspi", 0)
    separation = deep_rspi < mild_rspi
    print(f"\n  Deep vs Mild 분리: deep={deep_rspi:+.2f}, mild={mild_rspi:+.2f} → {'PASS' if separation else 'FAIL'}")

    return results


# ──────────────────────────────────────────────
# Step 6: 거래량 증폭기 A/B 비교
# ──────────────────────────────────────────────

def step6_volume_amplifier_comparison(history, ts):
    """amp 적용 전/후 비교."""
    print("\n" + "=" * 60)
    print("Step 6: 거래량 증폭기 A/B 비교")
    print("=" * 60)

    ts_returns = {}
    for i, rec in enumerate(ts):
        if i + 1 < len(ts):
            today_kospi = rec.get("kospi", 0) or 0
            next_kospi = ts[i + 1].get("kospi", 0) or 0
            if today_kospi > 0 and next_kospi > 0:
                ts_returns[rec["date"]] = (next_kospi / today_kospi - 1) * 100

    # RSPI_no_amp 계산: raw / amp * amp=1.0 → raw * 100 * -1
    # Actually: RSPI = raw * va * 100 * -1, so RSPI_no_amp = (RSPI / va)
    bucket_defs = [
        ("noise", lambda r: abs(r) < 5),
        ("mild", lambda r: 5 <= abs(r) < 15),
        ("moderate", lambda r: 15 <= abs(r) < 30),
        ("strong", lambda r: abs(r) >= 30),
    ]

    def calc_bucket_stats(rspi_values):
        """rspi_values = [(date, rspi_val)]"""
        bucket_results = {}
        for bname, bfn in bucket_defs:
            entries = [(d, r) for d, r in rspi_values if bfn(r) and d in ts_returns]
            if not entries:
                bucket_results[bname] = {"count": 0, "dir_match": 0}
                continue
            directional = [(r, ts_returns[d]) for d, r in entries if abs(r) >= 1]
            if directional:
                matches = sum(1 for r, ret in directional
                              if (r < 0 and ret < 0) or (r > 0 and ret > 0))
                dm = matches / len(directional)
            else:
                dm = 0.5
            bucket_results[bname] = {"count": len(entries), "dir_match": dm}
        return bucket_results

    # Version A: no amp (RSPI / va)
    no_amp = []
    with_amp = []
    for h in history:
        if h.get("rspi") is not None and h.get("volume_amp") is not None:
            va = h["volume_amp"]
            rspi_no = h["rspi"] / va if va > 0 else h["rspi"]
            no_amp.append((h["date"], rspi_no))
            with_amp.append((h["date"], h["rspi"]))

    stats_no = calc_bucket_stats(no_amp)
    stats_with = calc_bucket_stats(with_amp)

    print(f"\n  {'버킷':<10} {'amp 없이':>20} {'amp 적용':>20}")
    print(f"  {'':>10} {'날수/일치율':>20} {'날수/일치율':>20}")
    print(f"  {'─' * 10} {'─' * 20} {'─' * 20}")

    for bname in ["noise", "mild", "moderate", "strong"]:
        sn = stats_no[bname]
        sw = stats_with[bname]
        print(f"  {bname:<10} {sn['count']:>5}/{sn['dir_match']:>6.1%}         "
              f"{sw['count']:>5}/{sw['dir_match']:>6.1%}")

    # amp > 1.5 분석
    high_amp = [(h["date"], h["rspi"], h["volume_amp"])
                for h in history
                if h.get("volume_amp") is not None and h["volume_amp"] > 1.5 and h.get("rspi") is not None]
    print(f"\n  amp > 1.5인 날: {len(high_amp)}일")
    false_in_high = sum(1 for d, r, _ in high_amp
                        if d in ts_returns and
                        ((r < -20 and ts_returns[d] > 0) or (r > 20 and ts_returns[d] < 0)))
    if high_amp:
        print(f"    이 중 false alarm (|RSPI|>20 & 방향 틀림): {false_in_high}건 ({false_in_high / len(high_amp) * 100:.1f}%)")

    return {"no_amp": stats_no, "with_amp": stats_with, "high_amp_count": len(high_amp)}


# ──────────────────────────────────────────────
# Step 7: False Alarm 상세 분석
# ──────────────────────────────────────────────

def step7_false_alarm_analysis(history, ts):
    """False alarm 패턴 분석."""
    print("\n" + "=" * 60)
    print("Step 7: False Alarm 상세 분석")
    print("=" * 60)

    ts_returns = {}
    for i, rec in enumerate(ts):
        if i + 1 < len(ts):
            today_kospi = rec.get("kospi", 0) or 0
            next_kospi = ts[i + 1].get("kospi", 0) or 0
            if today_kospi > 0 and next_kospi > 0:
                ts_returns[rec["date"]] = (next_kospi / today_kospi - 1) * 100

    # False alarm: |RSPI| > 20 and 방향 틀림
    false_alarms = []
    for h in history:
        if h.get("rspi") is None or h["date"] not in ts_returns:
            continue
        rspi = h["rspi"]
        ret = ts_returns[h["date"]]
        if abs(rspi) > 20:
            if (rspi < -20 and ret > 0) or (rspi > 20 and ret < 0):
                # 범인 변수 찾기: 가중 기여도 가장 큰 변수
                rv = h.get("raw_variables", {})
                vc = h.get("variable_contributions", {})
                culprit = max(vc, key=lambda k: abs(vc.get(k, 0) or 0)) if vc else "unknown"

                false_alarms.append({
                    "date": h["date"], "rspi": rspi, "next_ret": ret,
                    "type": "A_sell" if rspi < -20 else "B_rebound",
                    "culprit": culprit,
                    "raw_variables": rv,
                    "volume_amp": h.get("volume_amp", 1.0),
                })

    print(f"\n  False alarm 총: {len(false_alarms)}건")

    # 범인 분석
    culprit_counts = defaultdict(int)
    amp_over_15 = 0
    for fa in false_alarms:
        culprit_counts[fa["culprit"]] += 1
        if fa["volume_amp"] > 1.5:
            amp_over_15 += 1

    print(f"\n  {'범인 변수':<10} {'빈도':>5}")
    print(f"  {'─' * 10} {'─' * 5}")
    for var, cnt in sorted(culprit_counts.items(), key=lambda x: -x[1]):
        print(f"  {var:<10} {cnt:>5}건")

    if false_alarms:
        print(f"\n  amp > 1.5에 의한 과증폭: {amp_over_15}건 ({amp_over_15 / len(false_alarms) * 100:.1f}%)")

    print(f"\n  상세 (최대 10건):")
    for fa in false_alarms[:10]:
        rv = fa["raw_variables"]
        print(f"    {fa['date']}: RSPI={fa['rspi']:+.1f}, 다음날={fa['next_ret']:+.2f}%, "
              f"범인={fa['culprit']}, amp={fa['volume_amp']:.2f}")

    return {"count": len(false_alarms), "culprits": dict(culprit_counts), "amp_induced": amp_over_15}


# ──────────────────────────────────────────────
# Step 8: 가중치 민감도
# ──────────────────────────────────────────────

def step8_weight_sensitivity(ts, date_to_cohorts):
    """각 가중치를 ±50% 변동시켜 strong 버킷 일치율 변화."""
    print("\n" + "=" * 60)
    print("Step 8: 가중치 민감도 분석")
    print("=" * 60)

    ts_returns = {}
    for i, rec in enumerate(ts):
        if i + 1 < len(ts):
            today_kospi = rec.get("kospi", 0) or 0
            next_kospi = ts[i + 1].get("kospi", 0) or 0
            if today_kospi > 0 and next_kospi > 0:
                ts_returns[rec["date"]] = (next_kospi / today_kospi - 1) * 100

    base_weights = dict(RSPI_WEIGHTS)
    var_keys = ["v1", "v2", "v3", "v4", "v5"]
    multipliers = [0.5, 1.0, 1.5]

    def strong_dir_match(history_data):
        entries = [(h["rspi"], ts_returns.get(h["date"], 0))
                   for h in history_data
                   if h.get("rspi") is not None and abs(h["rspi"]) >= 30 and h["date"] in ts_returns]
        if not entries:
            return 0
        directional = [(r, ret) for r, ret in entries if abs(r) >= 1]
        if not directional:
            return 0.5
        matches = sum(1 for r, ret in directional if (r < 0 and ret < 0) or (r > 0 and ret > 0))
        return matches / len(directional)

    print(f"\n  {'ID':<4} {'0.5x':>8} {'1.0x':>8} {'1.5x':>8} {'민감도':>8}")
    print(f"  {'─' * 4} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8}")

    results = {}
    for vk in var_keys:
        rates = []
        for mult in multipliers:
            # 가중치 변동 + 재정규화
            new_w = dict(base_weights)
            orig = new_w[vk]
            new_w[vk] = orig * mult
            total = sum(new_w.values())
            new_w = {k: v / total for k, v in new_w.items()}

            hist = run_rspi_pipeline(ts, date_to_cohorts, weights=new_w)
            rate = strong_dir_match(hist)
            rates.append(rate)

        sensitivity = max(rates) - min(rates)
        results[vk] = {"rates": rates, "sensitivity": sensitivity}
        print(f"  {vk.upper():<4} {rates[0]:>8.1%} {rates[1]:>8.1%} {rates[2]:>8.1%} {sensitivity:>8.1%}")

    return results


# ──────────────────────────────────────────────
# Step 9: V1 power 최적화
# ──────────────────────────────────────────────

def step9_power_optimization(ts, date_to_cohorts):
    """power = [1.0, 1.5, 2.0, 2.5, 3.0] 비교."""
    print("\n" + "=" * 60)
    print("Step 9: V1 power 파라미터 최적화")
    print("=" * 60)

    powers = [1.0, 1.5, 2.0, 2.5, 3.0]

    ts_returns = {}
    for i, rec in enumerate(ts):
        if i + 1 < len(ts):
            today_kospi = rec.get("kospi", 0) or 0
            next_kospi = ts[i + 1].get("kospi", 0) or 0
            if today_kospi > 0 and next_kospi > 0:
                ts_returns[rec["date"]] = (next_kospi / today_kospi - 1) * 100

    results = []

    print(f"\n  Part A: V1 개별 예측력")
    print(f"  {'power':<8} {'상관계수':>8} {'p-value':>8} {'spread':>8} {'mean(V1)':>10}")
    print(f"  {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 10}")

    for pwr in powers:
        hist = run_rspi_pipeline(ts, date_to_cohorts, power=pwr)

        # V1 vs next-day return
        v1_pairs = []
        v1_vals = []
        for h in hist:
            if h.get("raw_variables") and h["raw_variables"].get("v1") is not None:
                v1 = h["raw_variables"]["v1"]
                v1_vals.append(v1)
                if h["date"] in ts_returns:
                    v1_pairs.append((v1, ts_returns[h["date"]]))

        xs, ys = zip(*v1_pairs) if v1_pairs else ([], [])
        corr, p = _pearson(list(xs), list(ys)) if len(v1_pairs) >= 3 else (0, 1)

        # Quintile spread
        sorted_p = sorted(v1_pairs, key=lambda x: x[0])
        q = len(sorted_p) // 5
        if q > 0:
            bot = statistics.mean([y for _, y in sorted_p[:q]])
            top = statistics.mean([y for _, y in sorted_p[-q:]])
            spread = top - bot
        else:
            spread = 0

        mean_v1 = statistics.mean(v1_vals) if v1_vals else 0

        # Strong bucket direction match
        strong_entries = [(h["rspi"], ts_returns.get(h["date"], 0))
                          for h in hist
                          if h.get("rspi") is not None and abs(h["rspi"]) >= 30 and h["date"] in ts_returns]
        if strong_entries:
            directional = [(r, ret) for r, ret in strong_entries if abs(r) >= 1]
            strong_match = sum(1 for r, ret in directional if (r < 0 and ret < 0) or (r > 0 and ret > 0)) / len(directional) if directional else 0.5
        else:
            strong_match = 0

        results.append({
            "power": pwr, "corr": corr, "p": p, "spread": spread,
            "mean_v1": mean_v1, "strong_match": strong_match, "history": hist,
        })

        print(f"  {pwr:<8.1f} {corr:>+8.4f} {p:>8.4f} {spread:>+8.4f} {mean_v1:>10.4f}")

    print(f"\n  Part B: RSPI strong 버킷 방향 일치율")
    print(f"  {'power':<8} {'strong 일치율':>14} {'최적 여부':>10}")
    print(f"  {'─' * 8} {'─' * 14} {'─' * 10}")

    best_idx = max(range(len(results)), key=lambda i: results[i]["strong_match"])
    default_idx = next(i for i, r in enumerate(results) if r["power"] == 2.5)

    for i, r in enumerate(results):
        marker = "★ 최적" if i == best_idx else ""
        print(f"  {r['power']:<8.1f} {r['strong_match']:>14.1%} {marker:>10}")

    # 결정
    best = results[best_idx]
    default = results[default_idx]
    diff = (best["strong_match"] - default["strong_match"]) * 100

    if diff > 5:
        chosen = best["power"]
        reason = f"기본값(2.5) 대비 {diff:+.1f}%p 차이 → 변경"
    else:
        chosen = 2.5
        reason = f"기본값(2.5) 대비 {diff:+.1f}%p 차이 (5% 미만) → 유지"

    print(f"\n  결정: power = {chosen}")
    print(f"  근거: {reason}")

    return {"chosen_power": chosen, "results": [(r["power"], r["corr"], r["strong_match"]) for r in results]}


# ──────────────────────────────────────────────
# 최종 리포트
# ──────────────────────────────────────────────

def generate_report(s1, s2, s3, s4, s5, s6, s7, s8, s9):
    """검증 결과 종합 리포트."""
    print("\n" + "=" * 60)
    print("RSPI v2.3.0 검증 리포트")
    print("=" * 60)

    # 1. 변수별 건강 상태
    print(f"\n  1. 변수별 건강 상태")
    print(f"  {'ID':<4} {'분포상태':>8} {'상관계수':>8} {'예측력':>6} {'판정':>6}")
    print(f"  {'─' * 4} {'─' * 8} {'─' * 8} {'─' * 6} {'─' * 6}")

    for vk in ["v1", "v2", "v3", "v4", "v5"]:
        dist = s1.get(vk, {})
        pred = s3.get(vk, {})
        # 분포 상태: near_zero 비율
        total = dist.get("count", 1)
        nz = dist.get("near_zero", 0)
        dist_status = "문제" if nz / total > 0.95 else "양호"
        corr = pred.get("corr", 0)
        verdict = pred.get("verdict", "N/A")
        print(f"  {vk.upper():<4} {dist_status:>8} {corr:>+8.4f} {pred.get('hit_rate', 0):>6.0%} {verdict:>6}")

    # 2. RSPI 전체 유효성
    print(f"\n  2. RSPI 전체 유효성")
    q1 = s2.get("q1_pass", False)
    q3 = s4.get("strong", {}).get("direction_match", 0) >= 0.65

    deep = s5.get("deep_decline", {})
    mild = s5.get("mild_decline", {})
    step5_pass = deep.get("avg_rspi", 0) < mild.get("avg_rspi", 0) if deep.get("count", 0) > 0 and mild.get("count", 0) > 0 else None

    print(f"    Q1 (중립 70%+): {'PASS' if q1 else 'FAIL'}")
    print(f"    Q3 (strong 65%+): {'PASS' if q3 else 'FAIL'}")
    print(f"    음전환 분리: {'PASS' if step5_pass else 'FAIL' if step5_pass is not None else 'N/A'}")

    overall = "유효" if (q1 and q3) else "부분유효" if (q1 or q3) else "무효"
    print(f"    전체 판정: {overall}")

    # 3. 발견된 문제점
    print(f"\n  3. 발견된 문제점")
    issue_num = 1
    fa_count = s7.get("count", 0)
    if fa_count > 0:
        top_culprit = max(s7.get("culprits", {}), key=lambda k: s7["culprits"][k]) if s7.get("culprits") else "N/A"
        print(f"    문제 {issue_num}: False alarm {fa_count}건, 주범={top_culprit}")
        issue_num += 1

    amp_induced = s7.get("amp_induced", 0)
    if amp_induced > 0:
        print(f"    문제 {issue_num}: amp 과증폭에 의한 false alarm {amp_induced}건")
        issue_num += 1

    for vk in ["v1", "v2", "v3", "v4", "v5"]:
        pred = s3.get(vk, {})
        if pred.get("verdict") == "무효":
            print(f"    문제 {issue_num}: {vk.upper()} 예측력 무효 (corr={pred.get('corr', 0):.4f})")
            issue_num += 1

    # 6. V1 power
    print(f"\n  6. V1 power 파라미터 결정")
    print(f"    최적 power: {s9.get('chosen_power', 2.5)}")

    # 7. 거래량 증폭기
    print(f"\n  7. 거래량 증폭기 판정")
    no_amp_strong = s6.get("no_amp", {}).get("strong", {}).get("dir_match", 0)
    with_amp_strong = s6.get("with_amp", {}).get("strong", {}).get("dir_match", 0)
    if with_amp_strong > no_amp_strong + 0.03:
        print(f"    판정: 유지 (amp 적용 시 strong 일치율 {with_amp_strong:.1%} > 미적용 {no_amp_strong:.1%})")
    elif with_amp_strong < no_amp_strong - 0.03:
        print(f"    판정: 제거 검토 (amp 적용 시 오히려 악화 {with_amp_strong:.1%} < {no_amp_strong:.1%})")
    else:
        print(f"    판정: 유지 (차이 미미, amp={with_amp_strong:.1%}, no-amp={no_amp_strong:.1%})")

    return overall


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RSPI v2.3.0 Validation Framework")
    parser.add_argument("--power-only", action="store_true", help="Step 9만 실행")
    args = parser.parse_args()

    print("RSPI v2.3.0 검증 프레임워크")
    print("─" * 60)

    print("데이터 로딩...")
    ts = load_timeseries()
    print(f"  timeseries: {len(ts)}일")

    print("코호트 빌드 (look-ahead bias 제거)...")
    date_to_cohorts = load_cohort_data()
    print(f"  날짜별 코호트: {len(date_to_cohorts)}일")

    if args.power_only:
        s9 = step9_power_optimization(ts, date_to_cohorts)
        return

    print("\nRSPI 파이프라인 실행 (power=2.5)...")
    history = run_rspi_pipeline(ts, date_to_cohorts, power=V1_PROXIMITY_POWER)
    valid_count = sum(1 for h in history if h.get("rspi") is not None)
    print(f"  RSPI 계산: {valid_count}/{len(history)}일")

    # Steps 1~7
    s1 = step1_variable_distribution(history)
    s2 = step2_rspi_distribution(history, ts)
    s3 = step3_variable_predictive_power(history, ts)
    s4 = step4_signal_strength(history, ts)
    s5 = step5_post_decline_tracking(history, ts)
    s6 = step6_volume_amplifier_comparison(history, ts)
    s7 = step7_false_alarm_analysis(history, ts)

    # Steps 8~9 (computationally expensive — run RSPI multiple times)
    print("\nStep 8~9 실행 (가중치 민감도 + power 최적화)...")
    s8 = step8_weight_sensitivity(ts, date_to_cohorts)
    s9 = step9_power_optimization(ts, date_to_cohorts)

    # 최종 리포트
    overall = generate_report(s1, s2, s3, s4, s5, s6, s7, s8, s9)

    print(f"\n{'=' * 60}")
    print(f"검증 완료. 전체 판정: {overall}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
