"""FRED API를 통한 경제 데이터 수집"""
import time
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
from fredapi import Fred

from config.settings import FRED_API_KEY, RAW_DIR, CACHE_EXPIRY_HOURS
from config.constants import FRED_SERIES
from src.utils.logger import setup_logger

logger = setup_logger("fred_fetcher")


class FredFetcher:
    """
    FRED API wrapper.
    캐싱: data/raw/fred_{series}.csv
    Rate limit: 120 req/min (자동 throttle)
    """

    def __init__(self, api_key: str | None = None):
        key = api_key or FRED_API_KEY
        if not key:
            raise ValueError(
                "FRED API Key가 설정되지 않았습니다.\n"
                ".env 파일에 FRED_API_KEY=your_key 를 추가하세요.\n"
                "발급: https://fred.stlouisfed.org/docs/api/api_key.html"
            )
        self.fred = Fred(api_key=key)
        self._request_count = 0

    def fetch_series(
        self,
        series_id: str,
        start: str,
        end: str,
        frequency: str | None = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        단일 FRED 시리즈 수집.

        Returns: DataFrame[date, value]
        """
        # 캐시 확인
        if use_cache:
            cached = self._load_cache(series_id)
            if cached is not None:
                logger.info(f"[Cache Hit] {series_id}: {len(cached)} rows")
                return cached

        # API 호출 (rate limit throttle)
        self._throttle()

        try:
            logger.info(f"Fetching {series_id} from FRED ({start} ~ {end})...")
            kwargs = {
                "observation_start": start,
                "observation_end": end,
            }
            if frequency:
                kwargs["frequency"] = frequency

            series = self.fred.get_series(series_id, **kwargs)
            self._request_count += 1

            # DataFrame 변환
            df = pd.DataFrame({
                "date": series.index,
                "value": series.values,
            })
            df["date"] = pd.to_datetime(df["date"])
            df = df.dropna(subset=["value"])

            logger.info(f"Fetched {series_id}: {len(df)} rows "
                        f"({df['date'].min().strftime('%Y-%m')} ~ "
                        f"{df['date'].max().strftime('%Y-%m')})")

            # 캐시 저장
            self._save_cache(series_id, df)

            return df

        except Exception as e:
            logger.error(f"Failed to fetch {series_id}: {e}")
            # 만료된 캐시라도 반환 시도
            cached = self._load_cache(series_id, ignore_expiry=True)
            if cached is not None:
                logger.warning(f"Using expired cache for {series_id}")
                return cached
            raise

    def fetch_all_fred_series(
        self,
        start: str,
        end: str,
        use_cache: bool = True,
    ) -> dict[str, pd.DataFrame]:
        """
        FRED_SERIES 전체 배치 수집.
        Returns: {"WALCL": df, "RRP": df, ...}
        """
        results = {}
        for name, series_id in FRED_SERIES.items():
            try:
                df = self.fetch_series(series_id, start, end, use_cache=use_cache)
                results[name] = df
            except Exception as e:
                logger.error(f"Skipping {name} ({series_id}): {e}")
                results[name] = pd.DataFrame(columns=["date", "value"])

        logger.info(f"Fetched {len(results)} FRED series "
                    f"({sum(len(v) for v in results.values())} total rows)")
        return results

    def _throttle(self):
        """Rate limit: 120 req/min → 0.5초 대기"""
        if self._request_count > 0 and self._request_count % 5 == 0:
            time.sleep(0.5)

    def _cache_path(self, series_id: str) -> Path:
        return RAW_DIR / f"fred_{series_id}.csv"

    def _save_cache(self, series_id: str, df: pd.DataFrame) -> None:
        path = self._cache_path(series_id)
        df.to_csv(path, index=False)
        logger.debug(f"Cached {series_id} → {path}")

    def _load_cache(
        self,
        series_id: str,
        ignore_expiry: bool = False,
    ) -> pd.DataFrame | None:
        path = self._cache_path(series_id)
        if not path.exists():
            return None

        # 캐시 만료 확인
        if not ignore_expiry:
            mtime = datetime.fromtimestamp(path.stat().st_mtime)
            if datetime.now() - mtime > timedelta(hours=CACHE_EXPIRY_HOURS):
                logger.debug(f"Cache expired for {series_id}")
                return None

        try:
            df = pd.read_csv(path, parse_dates=["date"])
            return df
        except Exception:
            return None
