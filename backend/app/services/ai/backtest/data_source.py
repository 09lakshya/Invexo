"""
Historical price data source for the backtest engine (Phase 2).

The engine depends only on the DataSource interface, so a higher-quality
vendor (NSE Bhavcopy, a broker API, a purchased dataset) can be swapped in
later without touching the engine. The default implementation reuses yfinance
— the same vendor used elsewhere in the repo — with a short on-disk cache so
repeated backtests don't re-download.
"""

import os
import time
import pickle
from abc import ABC, abstractmethod

import pandas as pd

from app.utils.logger import get_logger

logger = get_logger("backtest_data_source")

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
CACHE_DIR = os.path.join(_BACKEND_DIR, "data_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


class DataSource(ABC):
    """Returns daily OHLCV history per symbol as a DataFrame indexed by naive
    date (tz stripped), with columns Open/High/Low/Close/Volume."""

    @abstractmethod
    def get_history(self, symbols: list[str], period: str = "5y") -> dict[str, pd.DataFrame]:
        ...


class YFinanceDataSource(DataSource):
    CHUNK_SIZE = 40
    CACHE_TTL_HOURS = 20

    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache

    def _cache_path(self, period: str) -> str:
        return os.path.join(CACHE_DIR, f"backtest_prices_{period}.pkl")

    def get_history(self, symbols: list[str], period: str = "5y") -> dict[str, pd.DataFrame]:
        cache_path = self._cache_path(period)
        cached: dict[str, pd.DataFrame] = {}
        if self.use_cache and os.path.exists(cache_path):
            age_h = (time.time() - os.path.getmtime(cache_path)) / 3600
            if age_h < self.CACHE_TTL_HOURS:
                try:
                    with open(cache_path, "rb") as f:
                        cached = pickle.load(f)
                except Exception:
                    cached = {}

        need = [s for s in symbols if s not in cached]
        if not need:
            return {s: cached[s] for s in symbols if s in cached}

        import yfinance as yf
        from app.services.market.ticker_utils import _yf_session

        fetched: dict[str, pd.DataFrame] = {}
        chunks = [need[i:i + self.CHUNK_SIZE] for i in range(0, len(need), self.CHUNK_SIZE)]
        for chunk in chunks:
            try:
                raw = yf.download(tickers=" ".join(chunk), period=period, interval="1d",
                                  group_by="ticker", auto_adjust=True, threads=False,
                                  progress=False, session=_yf_session)
            except Exception as e:
                logger.error(f"Backtest history download failed: {e}")
                continue
            for sym in chunk:
                try:
                    df = raw[sym] if isinstance(raw.columns, pd.MultiIndex) else raw
                    df = df.dropna(subset=["Close"])[["Open", "High", "Low", "Close", "Volume"]].copy()
                    if df.index.tz is not None:
                        df.index = df.index.tz_localize(None)
                    if len(df) >= 100:
                        fetched[sym] = df
                except Exception:
                    continue
            time.sleep(0.5)

        merged = {**cached, **fetched}
        if self.use_cache and fetched:
            try:
                with open(cache_path, "wb") as f:
                    pickle.dump(merged, f)
            except Exception as e:
                logger.error(f"Failed to write backtest price cache: {e}")

        return {s: merged[s] for s in symbols if s in merged}
