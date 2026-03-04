#!/usr/bin/env python3
"""
금투협(KOFIA) 신용공여잔고 데이터 수집.

소스 우선순위:
1. 공공데이터포털 API (data.go.kr, 인증키 필요)
2. FreeSIS XHR (freesis.kofia.or.kr, 리버스 엔지니어링)
3. Naver Finance fallback (D-2 지연)

환경변수: KOFIA_API_KEY (공공데이터포털)
"""
import os

try:
    import requests
except ImportError:
    requests = None

KOFIA_API_KEY = os.getenv("KOFIA_API_KEY", "")
KOFIA_API_BASE = "https://apis.data.go.kr/1160100/service/GetFinaStatInfoSvc"


def fetch_credit_balance(date: str) -> dict | None:
    """3-tier fallback으로 신용잔고 수집.

    Returns:
        {
            "date": "2026-03-04",
            "kospi_stock_credit_mm": 21778077,   # 유가증권 신용잔고 (백만원)
            "kosdaq_credit_mm": 11025996,
            "total_credit_mm": 32804073,
            "source": "kofia_api" | "freesis" | "naver",
        }
    """
    # Tier 1: 공공데이터포털 API
    if KOFIA_API_KEY and requests:
        result = _fetch_from_data_go_kr(date)
        if result:
            return {**result, "source": "kofia_api"}

    # Tier 2: FreeSIS XHR
    result = _fetch_from_freesis(date)
    if result:
        return {**result, "source": "freesis"}

    # Tier 3: Naver fallback (기존 naver_scraper에서 처리)
    return None


def _fetch_from_data_go_kr(date: str) -> dict | None:
    """공공데이터포털 금융투자협회종합통계 API.

    Note: API 엔드포인트/스키마는 실제 서비스 확인 후 조정 필요.
    """
    if not requests:
        return None

    params = {
        "serviceKey": KOFIA_API_KEY,
        "numOfRows": 10,
        "pageNo": 1,
        "resultType": "json",
        "basDt": date.replace("-", ""),
    }
    try:
        resp = requests.get(
            f"{KOFIA_API_BASE}/getItemBasiInfo",
            params=params, timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return _parse_kofia_response(data)
    except Exception:
        pass
    return None


def _parse_kofia_response(data: dict) -> dict | None:
    """공공데이터포털 API 응답 파싱.

    TODO: 실제 API 응답 스키마에 맞게 구현.
    """
    try:
        body = data.get("response", {}).get("body", {})
        items = body.get("items", {}).get("item", [])
        if not items:
            return None
        # 파싱 로직 추가 예정
        return None
    except Exception:
        return None


def _fetch_from_freesis(date: str) -> dict | None:
    """FreeSIS SPA XHR 엔드포인트.

    Note: 리버스 엔지니어링 필요. 초기에는 None 반환.
    향후 브라우저 DevTools로 XHR 패턴 확인 후 구현.
    """
    # TODO: FreeSIS XHR 엔드포인트 구현
    return None
