"""CoinGecko / Binance — BTC 현물 보조 데이터 (fallback)"""
import time
from datetime import datetime

import pandas as pd
import requests

from config.constants import COINGECKO_BTC_URL, BINANCE_KLINES_URL
from src.utils.logger import setup_logger
from src.utils.date_utils import resample_to_monthly

logger = setup_logger("fallback_fetcher")


class FallbackFetcher:
    """
    yfinance 실패 시 fallback 체인.
    CoinGecko → Binance 순차 시도.
    """

    def fetch_coingecko_btc(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """
        CoinGecko /market_chart/range API.
        무료 tier: 365일 제한 → 분할 요청.
        Returns: DataFrame[date, btc_spot]
        """
        logger.info("Fetching BTC from CoinGecko...")

        start_ts = int(pd.Timestamp(start).timestamp())
        end_ts = int(pd.Timestamp(end).timestamp())

        all_prices = []
        chunk_days = 365
        current = start_ts

        while current < end_ts:
            chunk_end = min(current + chunk_days * 86400, end_ts)

            params = {
                "vs_currency": "usd",
                "from": current,
                "to": chunk_end,
            }

            try:
                resp = requests.get(COINGECKO_BTC_URL, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                prices = data.get("prices", [])
                for ts_ms, price in prices:
                    all_prices.append({
                        "date": pd.Timestamp(ts_ms, unit="ms").normalize(),
                        "btc_spot": price,
                    })

                # CoinGecko rate limit: ~50 req/min
                time.sleep(1.5)

            except Exception as e:
                logger.warning(f"CoinGecko chunk failed ({current}~{chunk_end}): {e}")

            current = chunk_end

        if not all_prices:
            logger.error("CoinGecko returned no data")
            return pd.DataFrame(columns=["date", "btc_spot"])

        df = pd.DataFrame(all_prices)
        df = df.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)
        logger.info(f"CoinGecko BTC: {len(df)} rows")
        return df

    def fetch_binance_btc(
        self,
        start: str,
        end: str,
    ) -> pd.DataFrame:
        """
        Binance /api/v3/klines API.
        Returns: DataFrame[date, btc_spot]
        """
        logger.info("Fetching BTC from Binance...")

        start_ms = int(pd.Timestamp(start).timestamp() * 1000)
        end_ms = int(pd.Timestamp(end).timestamp() * 1000)

        all_rows = []
        current = start_ms
        limit = 1000

        while current < end_ms:
            params = {
                "symbol": "BTCUSDT",
                "interval": "1d",
                "startTime": current,
                "endTime": end_ms,
                "limit": limit,
            }

            try:
                resp = requests.get(BINANCE_KLINES_URL, params=params, timeout=30)
                resp.raise_for_status()
                klines = resp.json()

                if not klines:
                    break

                for k in klines:
                    all_rows.append({
                        "date": pd.Timestamp(k[0], unit="ms").normalize(),
                        "btc_spot": float(k[4]),  # Close price
                    })

                # 다음 청크
                current = klines[-1][6] + 1  # close_time + 1ms
                time.sleep(0.2)

            except Exception as e:
                logger.warning(f"Binance request failed: {e}")
                break

        if not all_rows:
            logger.error("Binance returned no data")
            return pd.DataFrame(columns=["date", "btc_spot"])

        df = pd.DataFrame(all_rows)
        df = df.drop_duplicates(subset="date").sort_values("date").reset_index(drop=True)
        logger.info(f"Binance BTC: {len(df)} rows")
        return df

    def fetch_btc_spot_with_fallback(
        self,
        start: str,
        end: str,
        monthly: bool = True,
    ) -> pd.DataFrame:
        """
        Yahoo → CoinGecko → Binance 순차 시도.
        monthly=True: 월말 리샘플링 적용.
        """
        # Yahoo (MarketFetcher에서 호출하므로 여기선 CoinGecko부터)
        for fetcher_name, fetcher_fn in [
            ("CoinGecko", lambda: self.fetch_coingecko_btc(start, end)),
            ("Binance", lambda: self.fetch_binance_btc(start, end)),
        ]:
            try:
                df = fetcher_fn()
                if not df.empty and len(df) > 10:
                    logger.info(f"Fallback success: {fetcher_name}")
                    if monthly:
                        return resample_to_monthly(df, "btc_spot")
                    return df
            except Exception as e:
                logger.warning(f"Fallback {fetcher_name} failed: {e}")
                continue

        logger.error("All BTC fallback sources failed")
        return pd.DataFrame(columns=["date", "btc_spot"])
