#!/usr/bin/env python3
"""
데이터 단위 검증 모듈 — 파이프라인 전체에서 공용 사용.

모든 필드의 기대 범위를 정의하고, 범위 밖 값을 경고/자동 수정.
fetch_daily, kofia_excel_parser, timeseries merge 등에서 호출.
"""

# (필드명, 최소, 최대, 설명)
# None = 검증 안 함 (범위 미정)
FIELD_RANGES = {
    # 시장 지수
    "kospi":                   (100,    10000,  "KOSPI 지수"),
    "kosdaq":                  (100,    3000,   "KOSDAQ 지수"),
    "samsung":                 (1000,   500000, "삼성전자 주가 (원)"),
    "hynix":                   (1000,   2000000,"SK하이닉스 주가 (원)"),
    "kospi_volume":            (0,      5e9,    "KOSPI 거래량 (주)"),
    "samsung_volume":          (0,      1e9,    "삼성전자 거래량 (주)"),
    "hynix_volume":            (0,      1e9,    "SK하이닉스 거래량 (주)"),

    # 글로벌
    "sp500":                   (600,    10000,  "S&P 500 지수"),
    "usd_krw":                 (800,    2500,   "USD/KRW 환율"),
    "vix":                     (3,      100,    "VIX 지수"),
    "wti":                     (-50,    200,    "WTI 유가 (USD)"),
    "ewy_close":               (3,      300,    "EWY ETF (USD)"),
    "koru_close":              (1,      1000,   "KORU 3x ETF (USD, 역분할 반영)"),

    # 신용/예탁 (십억원)
    "credit_balance_billion":  (10,     50000,  "전체 신용잔고 (십억원)"),
    "credit_kospi_billion":    (1,      50000,  "KOSPI 신용잔고 (십억원)"),
    "credit_kosdaq_billion":   (1,      50000,  "KOSDAQ 신용잔고 (십억원)"),
    "deposit_billion":         (100,    300000, "고객예탁금 (십억원)"),
    "forced_liq_billion":      (0,      5000,   "반대매매 (십억원)"),
    "unsettled_billion":       (0,      50000,  "미수금 (십억원)"),

    # 투자자 수급 (십억원) — 음수 가능
    "individual_billion":      (-10000, 10000,  "개인 순매수 (십억원)"),
    "foreign_billion":         (-10000, 10000,  "외국인 순매수 (십억원)"),
    "institution_billion":     (-10000, 10000,  "기관 순매수 (십억원)"),
    "financial_invest_billion":(-10000, 10000,  "금투 순매수 (십억원)"),

    # 시가총액 (십억원)
    "market_cap_billion":      (10000,  10000000, "시가총액 (십억원)"),
    "kospi_trading_value_billion": (0,  100000, "KOSPI 거래대금 (십억원)"),

    # 변동률 (%)
    "kospi_change_pct":        (-40,    40,     "KOSPI 변동률 (%)"),
    "samsung_change_pct":      (-40,    40,     "삼성전자 변동률 (%)"),
    "hynix_change_pct":        (-40,    40,     "SK하이닉스 변동률 (%)"),
    "ewy_change_pct":          (-30,    30,     "EWY 변동률 (%)"),
    "koru_change_pct":         (-90,    90,     "KORU 변동률 (%, 3x)"),
    "sp500_change_pct":        (-20,    20,     "S&P 500 변동률 (%)"),
}


def validate_record(record: dict, date: str = "", source: str = "", fix: bool = False) -> list[str]:
    """단일 레코드의 모든 필드를 검증.

    Args:
        record: {field: value} dict
        date: 날짜 문자열 (로그용)
        source: 데이터 소스 (로그용)
        fix: True면 범위 밖 값을 None으로 교체

    Returns: 경고 메시지 리스트 (빈 리스트 = 정상)
    """
    warnings = []
    for field, value in list(record.items()):
        if value is None:
            continue
        if field not in FIELD_RANGES:
            continue

        lo, hi, desc = FIELD_RANGES[field]
        try:
            v = float(value)
        except (ValueError, TypeError):
            continue

        if v < lo or v > hi:
            msg = f"[VALIDATE] {date} {source} {field}={v} 범위 밖 [{lo}~{hi}] ({desc})"
            warnings.append(msg)
            if fix:
                record[field] = None
    return warnings


def validate_timeseries(ts: list[dict], fix: bool = False, quiet: bool = False) -> dict:
    """전체 timeseries 검증.

    Returns: {field: {count, samples}} 필드별 이상치 요약
    """
    from collections import defaultdict
    issues = defaultdict(lambda: {"count": 0, "samples": []})
    total_warnings = 0

    for record in ts:
        date = record.get("date", "?")
        warnings = validate_record(record, date=date, source="timeseries", fix=fix)
        for w in warnings:
            total_warnings += 1
            # Extract field name
            parts = w.split()
            field = next((p.split("=")[0] for p in parts if "=" in p), "?")
            issues[field]["count"] += 1
            if len(issues[field]["samples"]) < 3:
                issues[field]["samples"].append(w)

    if not quiet:
        if total_warnings == 0:
            print("  [VALIDATE] All fields within expected ranges")
        else:
            print(f"  [VALIDATE] {total_warnings} warnings across {len(issues)} fields:")
            for field, info in sorted(issues.items(), key=lambda x: -x[1]["count"]):
                print(f"    {field}: {info['count']} outliers")
                for s in info["samples"]:
                    print(f"      {s}")

    return dict(issues)
