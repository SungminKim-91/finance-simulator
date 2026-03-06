#!/usr/bin/env python3
"""
Naver Finance 스크래핑 + 종목별 시가총액.

1. 고객예탁금 + 신용잔고: sise_deposit.naver
2. 투자자별 매매동향: investorDealTrendDay.naver (개인/외국인/기관/금투, 억원)
3. 종목별 시가총액 + 가격: yfinance (신용잔고 가중 배분용)
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


# ──────────────────────────────────────────────
# 투자자별 매매동향 (investorDealTrendDay)
# ──────────────────────────────────────────────

INVESTOR_URL = "https://finance.naver.com/sise/investorDealTrendDay.naver"


def fetch_naver_investor_flows(start: str, end: str) -> dict[str, dict]:
    """Naver 투자자별 일간 순매수 스크래핑 (억원 단위).

    Args:
        start: 시작일 (YYYYMMDD 또는 YYYY-MM-DD)
        end: 종료일 (YYYYMMDD 또는 YYYY-MM-DD)

    Returns: {
        "2026-03-04": {
            "individual_billion": 0.796,
            "foreign_billion": 2.303,
            "institution_billion": -5.978,
            "financial_invest_billion": -5.830,
        }, ...
    }
    """
    if "-" in start:
        start_dt = datetime.strptime(start, ISO_FMT)
        end_dt = datetime.strptime(end, ISO_FMT)
    else:
        start_dt = datetime.strptime(start, "%Y%m%d")
        end_dt = datetime.strptime(end, "%Y%m%d")

    bizdate = end_dt.strftime("%Y%m%d")
    session = requests.Session()
    result: dict[str, dict] = {}
    done = False

    # 동적 max page 감지
    try:
        resp0 = session.get(
            INVESTOR_URL,
            params={"bizdate": bizdate, "sosok": "01", "page": 1},
            headers=HEADERS, timeout=15,
        )
        resp0.encoding = "euc-kr"
        soup0 = BeautifulSoup(resp0.text, "html.parser")
        paging = soup0.select("td.pgRR a")
        if paging:
            href = paging[0].get("href", "")
            match = re.search(r"page=(\d+)", href)
            max_pages = int(match.group(1)) if match else 600
        else:
            max_pages = 600
    except Exception:
        max_pages = 600

    print(f"  [Naver Investor] 총 {max_pages}페이지, {start_dt.date()} ~ {end_dt.date()} 조회")

    for page in range(1, max_pages + 1):
        if done:
            break
        try:
            resp = session.get(
                INVESTOR_URL,
                params={"bizdate": bizdate, "sosok": "01", "page": page},
                headers=HEADERS,
                timeout=15,
            )
            resp.encoding = "euc-kr"
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            print(f"  [WARN] Naver investor page {page} 실패: {e}")
            break

        table = soup.select_one("table.type_1")
        if not table:
            continue

        rows = table.select("tr")
        for row in rows:
            cols = row.select("td")
            if len(cols) < 11:
                continue

            date_cell = cols[0]
            if "date2" not in (date_cell.get("class") or []):
                continue

            date_text = date_cell.get_text(strip=True)
            try:
                if re.match(r"\d{2}\.\d{2}\.\d{2}$", date_text):
                    row_dt = datetime.strptime(date_text, "%y.%m.%d")
                elif re.match(r"\d{4}\.\d{2}\.\d{2}$", date_text):
                    row_dt = datetime.strptime(date_text, "%Y.%m.%d")
                else:
                    continue
            except ValueError:
                continue

            if row_dt > end_dt:
                continue
            if row_dt < start_dt:
                done = True
                break

            iso_date = row_dt.strftime(ISO_FMT)
            # 억원 → 십억원 (/10)
            individual = _parse_number(cols[1].get_text(strip=True))
            foreign = _parse_number(cols[2].get_text(strip=True))
            institution = _parse_number(cols[3].get_text(strip=True))
            financial_invest = _parse_number(cols[4].get_text(strip=True))

            record = {}
            if individual is not None:
                record["individual_billion"] = round(individual / 10, 2)
            if foreign is not None:
                record["foreign_billion"] = round(foreign / 10, 2)
            if institution is not None:
                record["institution_billion"] = round(institution / 10, 2)
            if financial_invest is not None:
                record["financial_invest_billion"] = round(financial_invest / 10, 2)

            if record:
                result[iso_date] = record

        if page % 10 == 0:
            print(f"  [Naver Investor] {page}/{max_pages} 페이지, {len(result)}일 수집")
        time.sleep(0.3)

    print(f"  [Naver Investor] 총 {len(result)}일 투자자별 수급 수집 완료")
    return result


# ──────────────────────────────────────────────
# 종목별 시가총액 + 가격 (yfinance)
# ──────────────────────────────────────────────

def fetch_stock_daily_prices(tickers_config: dict, start: str, end: str) -> dict:
    """Top N 종목 일간 종가 시계열 (yfinance batch).

    Args:
        tickers_config: {ticker: {name, group}} from constants.TOP_10_TICKERS
        start: 시작일 (YYYY-MM-DD)
        end: 종료일 (YYYY-MM-DD)

    Returns: {
        "005930": {"2026-03-03": 58200, "2026-03-04": 55000, ...},
        ...
    }
    """
    try:
        import yfinance as yf
        import pandas as pd
    except ImportError:
        print("  [WARN] yfinance/pandas not installed — stock daily prices unavailable")
        return {}

    yf_symbols = {t: f"{t}.KS" for t in tickers_config}
    symbols_list = list(yf_symbols.values())

    try:
        end_dt = datetime.strptime(end, ISO_FMT) if "-" in end else datetime.strptime(end, "%Y%m%d")
        from datetime import timedelta
        end_plus = (end_dt + timedelta(days=1)).strftime(ISO_FMT)
        start_str = start if "-" in start else f"{start[:4]}-{start[4:6]}-{start[6:]}"

        df = yf.download(symbols_list, start=start_str, end=end_plus, progress=False)
        if df.empty:
            print("  [WARN] yfinance stock prices: empty result")
            return {}
    except Exception as e:
        print(f"  [WARN] yfinance stock daily prices failed: {e}")
        return {}

    result = {}
    for ticker, yf_sym in yf_symbols.items():
        prices = {}
        try:
            close_col = df[("Close", yf_sym)] if ("Close", yf_sym) in df.columns else None
            if close_col is not None:
                for idx, val in close_col.items():
                    if pd.notna(val) and float(val) > 0:
                        date_str = idx.strftime(ISO_FMT)
                        prices[date_str] = int(round(float(val)))
        except Exception:
            pass
        result[ticker] = prices

    n_ok = sum(1 for t in result if len(result[t]) > 0)
    total_days = max((len(v) for v in result.values()), default=0)
    print(f"  [Stock Prices] {n_ok}/{len(tickers_config)} 종목, {total_days}일 종가 수집")
    return result


def fetch_stock_market_caps(tickers_config: dict) -> dict:
    """Top N 종목의 시가총액·종가를 yfinance로 조회.

    Args:
        tickers_config: {ticker: {name, group}} from constants.TOP_10_TICKERS

    Returns: {
        "005930": {"name": "삼성전자", "market_cap_billion": 1151300, "close": 172200},
        ...
        "_total_market_cap_billion": 2185100,
        "_weights": {"005930": 0.527, ...},
    }

    Note: 개별 종목 신용잔고 데이터가 공개 API로 제공되지 않으므로,
          시가총액 비중을 신용잔고 배분 가중치로 사용 (proxy).
    """
    try:
        import yfinance as yf
    except ImportError:
        print("  [WARN] yfinance not installed — stock market cap unavailable")
        return {}

    result = {}
    yf_symbols = {t: f"{t}.KS" for t in tickers_config}

    symbols_list = list(yf_symbols.values())
    try:
        tickers_obj = yf.Tickers(" ".join(symbols_list))
    except Exception as e:
        print(f"  [WARN] yfinance Tickers failed: {e}")
        return {}

    total_cap = 0
    for ticker, yf_sym in yf_symbols.items():
        try:
            info = tickers_obj.tickers[yf_sym].info
            cap = info.get("marketCap", 0) or 0
            close = info.get("currentPrice") or info.get("regularMarketPrice", 0) or 0
            cap_billion = round(cap / 1e9)  # Won → 십억원
            result[ticker] = {
                "name": tickers_config[ticker]["name"],
                "group": tickers_config[ticker]["group"],
                "market_cap_billion": cap_billion,
                "close": round(close),
            }
            total_cap += cap_billion
        except Exception as e:
            print(f"  [WARN] {ticker} market cap failed: {e}")
            result[ticker] = {
                "name": tickers_config[ticker]["name"],
                "group": tickers_config[ticker]["group"],
                "market_cap_billion": 0,
                "close": 0,
            }

    # Compute weights
    weights = {}
    if total_cap > 0:
        for ticker in result:
            cap = result[ticker]["market_cap_billion"]
            weights[ticker] = round(cap / total_cap, 4) if cap > 0 else 0

    result["_total_market_cap_billion"] = total_cap
    result["_weights"] = weights

    n_ok = sum(1 for t in tickers_config if result.get(t, {}).get("market_cap_billion", 0) > 0)
    print(f"  [Stock MarketCap] {n_ok}/{len(tickers_config)} 종목 시가총액 조회 완료, 합계 {total_cap/1000:.0f}조원")
    return result
