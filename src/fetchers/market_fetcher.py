"""Yahoo Finance — DXY, BTC, CME BTC Futures 수집"""
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from config.settings import RAW_DIR, CACHE_EXPIRY_HOURS
from config.constants import TICKERS
from src.utils.logger import setup_logger
from src.utils.date_utils import resample_to_monthly

logger = setup_logger("market_fetcher")


class MarketFetcher:
    """
    yfinance 기반 시장 데이터 수집.
    캐싱: data/raw/market_{ticker_name}.csv
    """

    def fetch_ticker(
        self,
        ticker: str,
        start: str,
        end: str,
        interval: str = "1d",
        use_cache: bool = True,
        cache_name: str | None = None,
    ) -> pd.DataFrame:
        """
        단일 티커 수집.
        Returns: DataFrame[date, open, high, low, close, volume]
        """
        name = cache_name or ticker.replace(".", "_").replace("-", "_").replace("=", "_")

        if use_cache:
            cached = self._load_cache(name)
            if cached is not None:
                logger.info(f"[Cache Hit] {ticker}: {len(cached)} rows")
                return cached

        logger.info(f"Fetching {ticker} from Yahoo Finance ({start} ~ {end})...")

        try:
            t = yf.Ticker(ticker)
            df = t.history(start=start, end=end, interval=interval)

            if df.empty:
                logger.warning(f"No data returned for {ticker}")
                return pd.DataFrame()

            df = df.reset_index()
            df = df.rename(columns={"Date": "date"})
            df["date"] = pd.to_datetime(df["date"]).dt.tz_localize(None)

            # 필요한 컬럼만
            cols = ["date", "Open", "High", "Low", "Close", "Volume"]
            available_cols = [c for c in cols if c in df.columns]
            df = df[available_cols]
            df.columns = [c.lower() for c in df.columns]

            logger.info(f"Fetched {ticker}: {len(df)} rows")

            self._save_cache(name, df)
            return df

        except Exception as e:
            logger.error(f"Failed to fetch {ticker}: {e}")
            cached = self._load_cache(name, ignore_expiry=True)
            if cached is not None:
                logger.warning(f"Using expired cache for {ticker}")
                return cached
            raise

    def fetch_dxy(self, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
        """DXY 월말 종가 → DataFrame[date, dxy]"""
        df = self.fetch_ticker(
            TICKERS["DXY"], start, end, use_cache=use_cache, cache_name="dxy"
        )
        if df.empty:
            return pd.DataFrame(columns=["date", "dxy"])

        df = df[["date", "close"]].rename(columns={"close": "dxy"})
        return resample_to_monthly(df, "dxy")

    def fetch_btc_spot(self, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
        """BTC-USD 월말 종가 → DataFrame[date, btc_spot]"""
        df = self.fetch_ticker(
            TICKERS["BTC_SPOT"], start, end, use_cache=use_cache, cache_name="btc_spot"
        )
        if df.empty:
            return pd.DataFrame(columns=["date", "btc_spot"])

        df = df[["date", "close"]].rename(columns={"close": "btc_spot"})
        return resample_to_monthly(df, "btc_spot")

    def fetch_cme_futures(self, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
        """
        CME BTC 근월물(BTC=F) 월말 종가.
        2017-12 이전 데이터 없음 → NaN.
        Returns: DataFrame[date, cme_futures]
        """
        df = self.fetch_ticker(
            TICKERS["CME_BTC_FUTURES"], start, end,
            use_cache=use_cache, cache_name="cme_btc_futures",
        )
        if df.empty:
            return pd.DataFrame(columns=["date", "cme_futures"])

        df = df[["date", "close"]].rename(columns={"close": "cme_futures"})
        return resample_to_monthly(df, "cme_futures")

    def fetch_btc_daily(self, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
        """BTC-USD 일간 종가 (CME Basis 계산용)"""
        df = self.fetch_ticker(
            TICKERS["BTC_SPOT"], start, end, use_cache=use_cache, cache_name="btc_spot"
        )
        if df.empty:
            return pd.DataFrame(columns=["date", "btc_spot"])
        return df[["date", "close"]].rename(columns={"close": "btc_spot"})

    def fetch_cme_daily(self, start: str, end: str, use_cache: bool = True) -> pd.DataFrame:
        """CME BTC 선물 일간 종가 (CME Basis 계산용)"""
        df = self.fetch_ticker(
            TICKERS["CME_BTC_FUTURES"], start, end,
            use_cache=use_cache, cache_name="cme_btc_futures",
        )
        if df.empty:
            return pd.DataFrame(columns=["date", "cme_futures"])
        return df[["date", "close"]].rename(columns={"close": "cme_futures"})

    # ── Cache ──

    def _cache_path(self, name: str) -> Path:
        return RAW_DIR / f"market_{name}.csv"

    def _save_cache(self, name: str, df: pd.DataFrame) -> None:
        df.to_csv(self._cache_path(name), index=False)

    def _load_cache(self, name: str, ignore_expiry: bool = False) -> pd.DataFrame | None:
        path = self._cache_path(name)
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
