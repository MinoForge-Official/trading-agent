"""Market data provider supporting Yahoo Finance, CCXT (Crypto), and synthetic test data."""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Union
import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class MarketDataProvider:
    """Unified market data provider for stocks, ETFs, crypto, and synthetic data."""

    def __init__(self, cache_enabled: bool = True):
        self.cache_enabled = cache_enabled
        self._cache: dict[str, pd.DataFrame] = {}

    def get_historical_data(
        self,
        symbol: str,
        period: str = "6mo",
        interval: str = "1d",
        start: Optional[Union[str, datetime]] = None,
        end: Optional[Union[str, datetime]] = None,
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """Fetch historical OHLCV data for a given symbol."""
        cache_key = f"{symbol}_{period}_{interval}_{start}_{end}"
        if use_cache and self.cache_enabled and cache_key in self._cache:
            return self._cache[cache_key].copy()

        try:
            # Check if crypto pair (e.g., BTC/USDT) or stock ticker
            if "/" in symbol:
                df = self._fetch_crypto_ccxt(symbol, interval=interval, limit=200)
            else:
                df = self._fetch_yfinance(symbol, period=period, interval=interval, start=start, end=end)
            
            if df.empty or len(df) < 5:
                logger.warning(f"Data for {symbol} returned fewer than 5 candles. Falling back to synthetic.")
                df = self.generate_synthetic_data(symbol, days=180)

        except Exception as exc:
            logger.error(f"Failed to fetch market data for {symbol}: {exc}. Using synthetic fallback.")
            df = self.generate_synthetic_data(symbol, days=180)

        # Standardize columns: Open, High, Low, Close, Volume
        df = self._standardize_dataframe(df)
        df = self.compute_indicators(df)

        if self.cache_enabled:
            self._cache[cache_key] = df

        return df.copy()

    def _fetch_yfinance(
        self,
        symbol: str,
        period: str = "6mo",
        interval: str = "1d",
        start: Optional[Union[str, datetime]] = None,
        end: Optional[Union[str, datetime]] = None,
    ) -> pd.DataFrame:
        ticker = yf.Ticker(symbol)
        if start and end:
            df = ticker.history(start=start, end=end, interval=interval)
        else:
            df = ticker.history(period=period, interval=interval)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [col[0] for col in df.columns]

        return df

    def _fetch_crypto_ccxt(
        self,
        symbol: str,
        exchange_name: str = "binance",
        interval: str = "1d",
        limit: int = 200,
    ) -> pd.DataFrame:
        import ccxt
        exchange_class = getattr(ccxt, exchange_name, None)
        if not exchange_class:
            exchange_class = ccxt.binance

        exchange = exchange_class({"enableRateLimit": True})
        timeframe_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "1d": "1d"}
        ccxt_tf = timeframe_map.get(interval, "1d")

        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=ccxt_tf, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["timestamp", "Open", "High", "Low", "Close", "Volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        return df

    def generate_synthetic_data(
        self,
        symbol: str = "SYNTH",
        days: int = 180,
        start_price: float = 100.0,
        volatility: float = 0.02,
        seed: Optional[int] = 42,
    ) -> pd.DataFrame:
        """Generate realistic geometric Brownian motion price series for offline testing."""
        if seed is not None:
            np.random.seed(seed)

        dates = pd.date_range(end=datetime.now(timezone.utc), periods=days, freq="D")
        returns = np.random.normal(0.0005, volatility, size=days)
        price_curve = start_price * np.cumprod(1 + returns)

        high = price_curve * (1 + np.abs(np.random.normal(0.005, 0.005, size=days)))
        low = price_curve * (1 - np.abs(np.random.normal(0.005, 0.005, size=days)))
        open_p = price_curve * (1 + np.random.normal(0, 0.002, size=days))
        volume = np.random.lognormal(mean=14, sigma=0.5, size=days)

        df = pd.DataFrame(
            {
                "Open": open_p,
                "High": high,
                "Low": low,
                "Close": price_curve,
                "Volume": volume,
            },
            index=dates,
        )
        return df

    def _standardize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        col_rename = {}
        for col in df.columns:
            lower = str(col).lower()
            if "open" in lower:
                col_rename[col] = "Open"
            elif "high" in lower:
                col_rename[col] = "High"
            elif "low" in lower:
                col_rename[col] = "Low"
            elif "close" in lower:
                col_rename[col] = "Close"
            elif "volume" in lower:
                col_rename[col] = "Volume"

        df.rename(columns=col_rename, inplace=True)
        for req in ["Open", "High", "Low", "Close"]:
            if req not in df.columns:
                raise ValueError(f"Missing required price column: {req}")
        if "Volume" not in df.columns:
            df["Volume"] = 1000.0

        # Ensure index is datetime
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)

        return df.dropna(subset=["Open", "High", "Low", "Close"])

    @staticmethod
    def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Calculate standard technical indicators on the DataFrame."""
        df = df.copy()
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # Moving Averages
        df["SMA_20"] = close.rolling(window=20).mean()
        df["SMA_50"] = close.rolling(window=50).mean()
        df["EMA_12"] = close.ewm(span=12, adjust=False).mean()
        df["EMA_26"] = close.ewm(span=26, adjust=False).mean()
        df["EMA_50"] = close.ewm(span=50, adjust=False).mean()
        df["EMA_200"] = close.ewm(span=200, adjust=False).mean()

        # MACD
        df["MACD"] = df["EMA_12"] - df["EMA_26"]
        df["MACD_Signal"] = df["MACD"].ewm(span=9, adjust=False).mean()
        df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

        # RSI (14-period)
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.rolling(window=14, min_periods=14).mean()
        avg_loss = loss.rolling(window=14, min_periods=14).mean()
        rs = avg_gain / (avg_loss + 1e-10)
        df["RSI"] = 100 - (100 / (1 + rs))

        # Bollinger Bands (20-period, 2 std)
        sma20 = df["SMA_20"]
        std20 = close.rolling(window=20).std()
        df["BB_Upper"] = sma20 + (std20 * 2)
        df["BB_Lower"] = sma20 - (std20 * 2)
        df["BB_Middle"] = sma20
        df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / (df["BB_Middle"] + 1e-10)

        # Average True Range (ATR 14)
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(window=14).mean()

        return df