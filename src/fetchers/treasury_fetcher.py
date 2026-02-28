"""Treasury Fiscal Data API — TGA(재무부 일반계정) 수집"""
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

from config.settings import RAW_DIR, CACHE_EXPIRY_HOURS
from config.constants import (
    TREASURY_TGA_ENDPOINT,
    TREASURY_TGA_FIELDS,
    TREASURY_TGA_FILTER_OLD,
    TREASURY_TGA_FILTER_NEW,
    TREASURY_PAGE_SIZE,
)
from src.utils.logger import setup_logger

logger = setup_logger("treasury_fetcher")


class TreasuryFetcher:
    """
    Treasury Fiscal Data API — 키 불필요.
    TGA (Treasury General Account) 일간 잔액 수집.

    주의: 2021-10-01 이후 account_type 명칭이 변경됨:
      - 이전: "Federal Reserve Account"
      - 이후: "Treasury General Account (TGA) Closing Balance"
    """

    def fetch_tga(
        self,
        start: str,
        end: str,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        TGA 일간 잔액 수집 (두 기간 합산).
        Returns: DataFrame[date, tga_balance] (단위: $T)
        """
        if use_cache:
            cached = self._load_cache()
            if cached is not None:
                logger.info(f"[Cache Hit] TGA: {len(cached)} rows")
                return cached

        logger.info(f"Fetching TGA from Treasury API ({start} ~ {end})...")

        # 기간 1: 이전 명칭 (~ 2021-09-30)
        old_records = self._fetch_with_filter(
            TREASURY_TGA_FILTER_OLD, start, "2021-09-30"
        )
        logger.info(f"TGA (old filter): {len(old_records)} records")

        # 기간 2: 새 명칭 (2021-10-01 ~)
        new_records = self._fetch_with_filter(
            TREASURY_TGA_FILTER_NEW, "2021-10-01", end
        )
        logger.info(f"TGA (new filter): {len(new_records)} records")

        all_records = old_records + new_records

        if not all_records:
            logger.error("No TGA records fetched")
            cached = self._load_cache(ignore_expiry=True)
            if cached is not None:
                return cached
            return pd.DataFrame(columns=["date", "tga_balance"])

        df = self._parse_records(all_records)
        # 중복 제거 (경계일)
        df = df.drop_duplicates(subset="date", keep="last")
        df = df.sort_values("date").reset_index(drop=True)

        logger.info(f"Fetched TGA: {len(df)} rows "
                    f"({df['date'].min().strftime('%Y-%m')} ~ "
                    f"{df['date'].max().strftime('%Y-%m')})")

        self._save_cache(df)
        return df

    def _fetch_with_filter(
        self,
        account_filter: str,
        start: str,
        end: str,
    ) -> list[dict]:
        """특정 account_type 필터로 API 호출 (페이지네이션 포함)"""
        all_records = []
        page = 1

        while True:
            params = {
                "fields": TREASURY_TGA_FIELDS,
                "filter": f"{account_filter},"
                          f"record_date:gte:{start},"
                          f"record_date:lte:{end}",
                "sort": "record_date",
                "page[number]": page,
                "page[size]": TREASURY_PAGE_SIZE,
            }

            try:
                resp = requests.get(TREASURY_TGA_ENDPOINT, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"Treasury API request failed (page {page}): {e}")
                break

            records = data.get("data", [])
            if not records:
                break

            all_records.extend(records)

            meta = data.get("meta", {})
            total_pages = meta.get("total-pages", 1)
            if page >= total_pages:
                break
            page += 1

        return all_records

    def _parse_records(self, records: list[dict]) -> pd.DataFrame:
        """API 응답 레코드 → DataFrame 변환"""
        rows = []
        for r in records:
            try:
                date = pd.to_datetime(r["record_date"])
                # open_today_bal: $ millions 단위
                bal_str = str(r.get("open_today_bal", "0")).replace(",", "")
                balance_millions = float(bal_str)
                # $M → $T 변환
                balance_t = balance_millions / 1_000_000
                rows.append({"date": date, "tga_balance": balance_t})
            except (ValueError, KeyError, TypeError):
                continue

        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame(columns=["date", "tga_balance"])
        df = df.sort_values("date").reset_index(drop=True)
        return df

    def _cache_path(self) -> Path:
        return RAW_DIR / "treasury_tga.csv"

    def _save_cache(self, df: pd.DataFrame) -> None:
        df.to_csv(self._cache_path(), index=False)

    def _load_cache(self, ignore_expiry: bool = False) -> pd.DataFrame | None:
        path = self._cache_path()
        if not path.exists():
            return None
        if not ignore_expiry:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            if datetime.now() - mtime > timedelta(hours=CACHE_EXPIRY_HOURS):
                return None
        try:
            return pd.read_csv(path, parse_dates=["date"])
        except Exception:
            return None
