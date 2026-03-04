#!/usr/bin/env python3
"""
ECOS (한국은행 경제통계시스템) 802Y001 일간 주식시장 데이터 조회.

API: https://ecos.bok.or.kr/api/StatisticSearch/{API_KEY}/json/kr/1/100/802Y001/D/{start}/{end}/{item_code}
항목코드:
  0001000 — KOSPI 종가
  0089000 — KOSDAQ 종가
  0030000 — 외국인 순매수 (백만원)
  0087000 — 거래량 (천주)
  0088000 — 거래대금 (백만원)
  0183000 — 시가총액 (십억원)

환경변수: ECOS_API_KEY (.env)
"""
import os
import time

import requests

BASE_URL = "https://ecos.bok.or.kr/api/StatisticSearch"
TABLE_CODE = "802Y001"
FREQ = "D"

# 항목코드 → 필드명 매핑
ITEM_MAP = {
    "0001000": "kospi",
    "0089000": "kosdaq",
    "0030000": "foreign_net_million",   # 백만원
    "0087000": "volume_thousand",       # 천주
    "0088000": "trading_value_million",  # 백만원
    "0183000": "market_cap_billion",    # 십억원
}


def _fetch_item(api_key: str, start: str, end: str, item_code: str) -> list[dict]:
    """단일 항목코드 조회. 최대 1000건씩 페이징."""
    results = []
    page = 1
    page_size = 1000

    while True:
        start_idx = (page - 1) * page_size + 1
        end_idx = page * page_size
        url = f"{BASE_URL}/{api_key}/json/kr/{start_idx}/{end_idx}/{TABLE_CODE}/{FREQ}/{start}/{end}/{item_code}"

        try:
            resp = requests.get(url, timeout=30)
            data = resp.json()
        except Exception as e:
            print(f"  [WARN] ECOS {item_code} 요청 실패: {e}")
            break

        stat = data.get("StatisticSearch")
        if not stat:
            err = data.get("RESULT", {})
            if err.get("CODE") == "INFO-200":  # 데이터 없음
                break
            print(f"  [WARN] ECOS {item_code} 응답 오류: {err}")
            break

        rows = stat.get("row", [])
        results.extend(rows)

        total = int(stat.get("list_total_count", 0))
        if end_idx >= total:
            break
        page += 1
        time.sleep(0.2)

    return results


def fetch_ecos_daily(start: str, end: str) -> dict[str, dict]:
    """ECOS 802Y001에서 일간 주식시장 데이터 조회.

    Args:
        start: 시작일 (YYYYMMDD)
        end: 종료일 (YYYYMMDD)

    Returns: {
        "2025-02-20": {
            "kospi": 2654.06,
            "kosdaq": 768.27,
            "foreign_net_billion": -2.884,
            "volume_thousand": 52930,
            "trading_value_billion": 14.55,
            "market_cap_billion": 2176898,
        }, ...
    }
    """
    api_key = os.environ.get("ECOS_API_KEY")
    if not api_key:
        print("  [WARN] ECOS_API_KEY 미설정 — ECOS 데이터 건너뜀")
        return {}

    merged: dict[str, dict] = {}

    for item_code, field_name in ITEM_MAP.items():
        print(f"  [ECOS] {field_name} ({item_code}) 조회중...")
        rows = _fetch_item(api_key, start, end, item_code)

        for row in rows:
            raw_date = row.get("TIME", "")  # YYYYMMDD
            if len(raw_date) != 8:
                continue
            iso_date = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            val_str = row.get("DATA_VALUE", "")

            try:
                val = float(val_str.replace(",", ""))
            except (ValueError, TypeError):
                continue

            if iso_date not in merged:
                merged[iso_date] = {}

            # 단위 변환
            if field_name == "foreign_net_million":
                merged[iso_date]["foreign_net_billion"] = round(val / 1000, 2)  # 백만 → 십억
            elif field_name == "trading_value_million":
                merged[iso_date]["trading_value_billion"] = round(val / 1000, 2)  # 백만 → 십억
            elif field_name in ("kospi", "kosdaq"):
                merged[iso_date][field_name] = round(val, 2)
            else:
                merged[iso_date][field_name] = val

        time.sleep(0.3)  # rate limit

    print(f"  [ECOS] {len(merged)}일 데이터 수집 완료")
    return merged
