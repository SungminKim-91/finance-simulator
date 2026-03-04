#!/usr/bin/env python3
"""
Naver Finance 스크래핑 — 고객예탁금 + 신용잔고 일간 조회.

URL: https://finance.naver.com/sise/sise_deposit.naver?page={n}
테이블 구조: [날짜, 예탁금(억원), 증감, 신용잔고(억원), 증감, ...]
페이지네이션: 역순(최신→과거), 날짜가 start 이전이면 중단.
"""
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

URL_TEMPLATE = "https://finance.naver.com/sise/sise_deposit.naver?page={page}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

ISO_FMT = "%Y-%m-%d"


def _parse_number(text: str) -> float | None:
    """한글 숫자 문자열 → float. 예: '118,732' → 118732.0"""
    if not text:
        return None
    cleaned = text.strip().replace(",", "").replace(" ", "")
    if not cleaned or cleaned == "-":
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _get_max_page(session: requests.Session) -> int:
    """첫 페이지에서 마지막 페이지 번호 추출."""
    resp = session.get(URL_TEMPLATE.format(page=1), headers=HEADERS, timeout=15)
    resp.encoding = "euc-kr"
    soup = BeautifulSoup(resp.text, "html.parser")

    # 페이지네이션에서 마지막 페이지 찾기
    paging = soup.select("td.pgRR a")
    if paging:
        href = paging[0].get("href", "")
        match = re.search(r"page=(\d+)", href)
        if match:
            return int(match.group(1))

    # fallback: 모든 페이지 링크에서 최대값
    links = soup.select("table.Nnavi a")
    pages = []
    for link in links:
        href = link.get("href", "")
        match = re.search(r"page=(\d+)", href)
        if match:
            pages.append(int(match.group(1)))
    return max(pages) if pages else 1


def fetch_naver_deposit_credit(start: str, end: str) -> dict[str, dict]:
    """Naver Finance sise_deposit에서 예탁금/신용잔고 스크래핑.

    Args:
        start: 시작일 (YYYYMMDD 또는 YYYY-MM-DD)
        end: 종료일 (YYYYMMDD 또는 YYYY-MM-DD)

    Returns: {
        "2026-02-27": {
            "deposit_billion": 53.45,       # 억원 → 십억원 변환
            "credit_balance_billion": 17.82,
        }, ...
    }
    """
    # 날짜 정규화
    if "-" in start:
        start_dt = datetime.strptime(start, ISO_FMT)
        end_dt = datetime.strptime(end, ISO_FMT)
    else:
        start_dt = datetime.strptime(start, "%Y%m%d")
        end_dt = datetime.strptime(end, "%Y%m%d")

    session = requests.Session()
    max_page = _get_max_page(session)
    print(f"  [Naver] 총 {max_page} 페이지, {start_dt.date()} ~ {end_dt.date()} 조회")

    result: dict[str, dict] = {}
    done = False

    for page in range(1, max_page + 1):
        if done:
            break

        try:
            resp = session.get(
                URL_TEMPLATE.format(page=page), headers=HEADERS, timeout=15
            )
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"  [WARN] Naver page {page} 요청 실패: {e}")
            break

        # 데이터 테이블 파싱
        table = soup.select_one("table.type_1")
        if not table:
            continue

        rows = table.select("tr")
        for row in rows:
            cols = row.select("td")
            if len(cols) < 5:
                continue

            date_text = cols[0].get_text(strip=True)
            if not date_text:
                continue

            # 날짜 파싱 (2자리 연도: 26.02.27 또는 4자리: 2026.02.27)
            try:
                if re.match(r"\d{2}\.\d{2}\.\d{2}$", date_text):
                    row_dt = datetime.strptime(date_text, "%y.%m.%d")
                elif re.match(r"\d{4}\.\d{2}\.\d{2}$", date_text):
                    row_dt = datetime.strptime(date_text, "%Y.%m.%d")
                else:
                    continue
            except ValueError:
                continue

            # 범위 밖이면 건너뛰기
            if row_dt > end_dt:
                continue
            if row_dt < start_dt:
                done = True
                break

            iso_date = row_dt.strftime(ISO_FMT)

            # 예탁금 (2번째 컬럼, 억원)
            deposit_raw = _parse_number(cols[1].get_text(strip=True))
            # 신용잔고 (4번째 컬럼, 억원)
            credit_raw = _parse_number(cols[3].get_text(strip=True))

            record = {}
            if deposit_raw is not None:
                record["deposit_billion"] = round(deposit_raw / 10, 2)  # 억원 → 십억원
            if credit_raw is not None:
                record["credit_balance_billion"] = round(credit_raw / 10, 2)  # 억원 → 십억원

            if record:
                result[iso_date] = record

        if page % 20 == 0:
            print(f"  [Naver] {page}/{max_page} 페이지 처리, {len(result)}일 수집")
        time.sleep(0.3)  # rate limit

    print(f"  [Naver] 총 {len(result)}일 예탁금/신용잔고 수집 완료")
    return result
