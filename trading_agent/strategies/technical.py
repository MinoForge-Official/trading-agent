"""Technical analysis trading strategies: EMA Trend, RSI Momentum, Bollinger Bands, and Composite."""

from __future__ import annotations

import numpy as np
import pandas as pd
from trading_agent.core.models import Action, MarketSignal
from trading_agent.strategies.base import BaseStrategy


class EMATrendStrategy(BaseStrategy):
    """Exponential Moving Average (EMA) trend-following strategy with ATR stop-loss."""

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        trend_period: int = 50,
        atr_multiplier: float = 2.0,
    ):
        super().__init__(
            name="EMA_Trend",
            params={
                "fast_period": fast_period,
                "slow_period": slow_period,
                "trend_period": trend_period,
                "atr_multiplier": atr_multiplier,
            },
        )
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.trend_period = trend_period
        self.atr_multiplier = atr_multiplier

    def evaluate(self, symbol: str, data: pd.DataFrame) -> MarketSignal:
        if len(data) < self.trend_period:
            return MarketSignal(
                symbol=symbol,
                action=Action.HOLD,
                confidence=0.0,
                price=float(data["Close"].iloc[-1]) if not data.empty else 0.0,
                reason=f"Insufficient data (need {self.trend_period} candles, got {len(data)})",
            )

        row = data.iloc[-1]
        prev_row = data.iloc[-2]
        price = float(row["Close"])
        atr = float(row.get("ATR", price * 0.02))

        fast_curr = float(row.get("EMA_12", row["Close"]))
        slow_curr = float(row.get("EMA_26", row["Close"]))
        fast_prev = float(prev_row.get("EMA_12", prev_row["Close"]))
        slow_prev = float(prev_row.get("EMA_26", prev_row["Close"]))
        trend_ma = float(row.get("EMA_50", row["Close"]))

        # Golden Cross (Fast crosses above Slow)
        is_bullish_cross = (fast_prev <= slow_prev) and (fast_curr > slow_curr)
        # Death Cross (Fast crosses below Slow)
        is_bearish_cross = (fast_prev >= slow_prev) and (fast_curr < slow_curr)

        is_uptrend = price > trend_ma
        is_downtrend = price < trend_ma

        action = Action.HOLD
        confidence = 0.5
        reason = "Trend neutral; waiting for crossover."
        stop_loss = None
        take_profit = None

        if is_bullish_cross:
            action = Action.BUY
            confidence = 0.85 if is_uptrend else 0.65
            stop_loss = round(price - (atr * self.atr_multiplier), 2)
            take_profit = round(price + (atr * self.atr_multiplier * 2.0), 2)
            reason = (
                f"Bullish EMA({self.fast_period}/{self.slow_period}) golden cross. "
                f"{'Confirmed by primary uptrend above EMA_' + str(self.trend_period) if is_uptrend else 'Counter-trend caution'}."
            )
        elif is_bearish_cross:
            action = Action.SELL
            confidence = 0.85 if is_downtrend else 0.65
            reason = f"Bearish EMA({self.fast_period}/{self.slow_period}) death cross."
        elif fast_curr > slow_curr and is_uptrend:
            action = Action.BUY
            confidence = 0.60
            reason = f"Ongoing bullish momentum above EMA_{self.slow_period} and EMA_{self.trend_period}."
        elif fast_curr < slow_curr and is_downtrend:
            action = Action.SELL
            confidence = 0.60
            reason = f"Ongoing bearish trend below EMA_{self.slow_period} and EMA_{self.trend_period}."

        return MarketSignal(
            symbol=symbol,
            action=action,
            confidence=confidence,
            price=price,
            reason=reason,
            indicators={
                "EMA_fast": fast_curr,
                "EMA_slow": slow_curr,
                "EMA_trend": trend_ma,
                "ATR": atr,
            },
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def generate_all_signals(self, symbol: str, data: pd.DataFrame) -> pd.Series:
        fast = data["Close"].ewm(span=self.fast_period, adjust=False).mean()
        slow = data["Close"].ewm(span=self.slow_period, adjust=False).mean()
        trend = data["Close"].ewm(span=self.trend_period, adjust=False).mean()

        signals = pd.Series(0, index=data.index)
        bullish = (fast > slow) & (data["Close"] > trend)
        bearish = (fast < slow) & (data["Close"] < trend)

        signals[bullish] = 1
        signals[bearish] = -1
        return signals


class RSIOscillatorStrategy(BaseStrategy):
    """Relative Strength Index (RSI) momentum & mean-reversion strategy."""

    def __init__(self, rsi_period: int = 14, oversold: float = 30.0, overbought: float = 70.0):
        super().__init__(
            name="RSI_Oscillator",
            params={"rsi_period": rsi_period, "oversold": oversold, "overbought": overbought},
        )
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought

    def evaluate(self, symbol: str, data: pd.DataFrame) -> MarketSignal:
        if len(data) < self.rsi_period + 5:
            return MarketSignal(
                symbol=symbol,
                action=Action.HOLD,
                confidence=0.0,
                price=float(data["Close"].iloc[-1]) if not data.empty else 0.0,
                reason="Insufficient data for RSI calculation.",
            )

        row = data.iloc[-1]
        prev_row = data.iloc[-2]
        price = float(row["Close"])
        rsi_curr = float(row.get("RSI", 50.0))
        rsi_prev = float(prev_row.get("RSI", 50.0))
        macd_hist = float(row.get("MACD_Hist", 0.0))

        action = Action.HOLD
        confidence = 0.5
        reason = f"RSI is neutral at {rsi_curr:.1f}."
        stop_loss = None
        take_profit = None

        # Oversold recovery
        if rsi_curr < self.oversold:
            action = Action.BUY
            confidence = 0.80 if macd_hist > 0 else 0.65
            reason = f"RSI deeply oversold at {rsi_curr:.1f} (< {self.oversold}). Rebound expected."
            stop_loss = round(price * 0.96, 2)
            take_profit = round(price * 1.08, 2)
        elif rsi_prev <= self.oversold and rsi_curr > self.oversold:
            action = Action.BUY
            confidence = 0.75
            reason = f"RSI crossed back above oversold barrier ({rsi_curr:.1f} > {self.oversold})."
            stop_loss = round(price * 0.97, 2)
            take_profit = round(price * 1.06, 2)
        elif rsi_curr > self.overbought:
            action = Action.SELL
            confidence = 0.80
            reason = f"RSI severely overbought at {rsi_curr:.1f} (> {self.overbought}). Pullback likely."
        elif rsi_prev >= self.overbought and rsi_curr < self.overbought:
            action = Action.SELL
            confidence = 0.75
            reason = f"RSI falling back below overbought line ({rsi_curr:.1f} < {self.overbought})."

        return MarketSignal(
            symbol=symbol,
            action=action,
            confidence=confidence,
            price=price,
            reason=reason,
            indicators={"RSI": rsi_curr, "MACD_Hist": macd_hist},
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def generate_all_signals(self, symbol: str, data: pd.DataFrame) -> pd.Series:
        rsi = data.get("RSI")
        if rsi is None:
            delta = data["Close"].diff()
            gain = delta.clip(lower=0).rolling(window=self.rsi_period).mean()
            loss = (-delta.clip(upper=0)).rolling(window=self.rsi_period).mean()
            rs = gain / (loss + 1e-10)
            rsi = 100 - (100 / (1 + rs))

        signals = pd.Series(0, index=data.index)
        signals[rsi < self.oversold] = 1
        signals[rsi > self.overbought] = -1
        return signals


class BollingerBandStrategy(BaseStrategy):
    """Bollinger Bands mean-reversion & breakout strategy."""

    def __init__(self, window: int = 20, num_std: float = 2.0):
        super().__init__(
            name="Bollinger_Bands",
            params={"window": window, "num_std": num_std},
        )
        self.window = window
        self.num_std = num_std

    def evaluate(self, symbol: str, data: pd.DataFrame) -> MarketSignal:
        if len(data) < self.window:
            return MarketSignal(
                symbol=symbol,
                action=Action.HOLD,
                confidence=0.0,
                price=float(data["Close"].iloc[-1]) if not data.empty else 0.0,
                reason="Insufficient data for Bollinger Bands.",
            )

        row = data.iloc[-1]
        price = float(row["Close"])
        upper = float(row.get("BB_Upper", price * 1.05))
        lower = float(row.get("BB_Lower", price * 0.95))
        middle = float(row.get("BB_Middle", price))

        action = Action.HOLD
        confidence = 0.5
        reason = f"Price {price:.2f} within normal volatility band [{lower:.2f} - {upper:.2f}]."
        stop_loss = None
        take_profit = None

        if price <= lower:
            action = Action.BUY
            confidence = 0.75
            reason = f"Price touched lower Bollinger Band ({price:.2f} <= {lower:.2f}). Mean reversion setup."
            stop_loss = round(price * 0.96, 2)
            take_profit = round(middle, 2)
        elif price >= upper:
            action = Action.SELL
            confidence = 0.75
            reason = f"Price breached upper Bollinger Band ({price:.2f} >= {upper:.2f}). Mean reversion exit."

        return MarketSignal(
            symbol=symbol,
            action=action,
            confidence=confidence,
            price=price,
            reason=reason,
            indicators={"BB_Upper": upper, "BB_Lower": lower, "BB_Middle": middle},
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def generate_all_signals(self, symbol: str, data: pd.DataFrame) -> pd.Series:
        close = data["Close"]
        sma = close.rolling(window=self.window).mean()
        std = close.rolling(window=self.window).std()
        upper = sma + (std * self.num_std)
        lower = sma - (std * self.num_std)

        signals = pd.Series(0, index=data.index)
        signals[close <= lower] = 1
        signals[close >= upper] = -1
        return signals


class CompositeStrategy(BaseStrategy):
    """Ensemble strategy combining EMA Trend, RSI, and Bollinger Bands with weighted voting."""

    def __init__(self):
        super().__init__(name="Composite_Ensemble")
        self.ema = EMATrendStrategy()
        self.rsi = RSIOscillatorStrategy()
        self.bb = BollingerBandStrategy()

    def evaluate(self, symbol: str, data: pd.DataFrame) -> MarketSignal:
        s_ema = self.ema.evaluate(symbol, data)
        s_rsi = self.rsi.evaluate(symbol, data)
        s_bb = self.bb.evaluate(symbol, data)

        score = 0.0
        # Weights: EMA Trend 40%, RSI 35%, BB 25%
        signals_with_weights = [(s_ema, 0.40), (s_rsi, 0.35), (s_bb, 0.25)]
        for s, w in signals_with_weights:
            if s.action == Action.BUY:
                score += w * s.confidence
            elif s.action == Action.SELL:
                score -= w * s.confidence

        price = float(data["Close"].iloc[-1])
        if score >= 0.35:
            action = Action.BUY
            confidence = min(1.0, 0.5 + abs(score) * 0.5)
            reason = f"Multi-factor bullish consensus (Score: +{score:.2f}). EMA: {s_ema.action}, RSI: {s_rsi.action}, BB: {s_bb.action}."
            stop_loss = s_ema.stop_loss or round(price * 0.97, 2)
            take_profit = s_ema.take_profit or round(price * 1.06, 2)
        elif score <= -0.35:
            action = Action.SELL
            confidence = min(1.0, 0.5 + abs(score) * 0.5)
            reason = f"Multi-factor bearish consensus (Score: {score:.2f}). EMA: {s_ema.action}, RSI: {s_rsi.action}, BB: {s_bb.action}."
            stop_loss = None
            take_profit = None
        else:
            action = Action.HOLD
            confidence = 0.5
            reason = f"Mixed signals across indicators (Score: {score:.2f}). Holding position."
            stop_loss = None
            take_profit = None

        return MarketSignal(
            symbol=symbol,
            action=action,
            confidence=confidence,
            price=price,
            reason=reason,
            indicators={
                "composite_score": score,
                "ema_signal": s_ema.action.value,
                "rsi_signal": s_rsi.action.value,
                "bb_signal": s_bb.action.value,
            },
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def generate_all_signals(self, symbol: str, data: pd.DataFrame) -> pd.Series:
        sig_ema = self.ema.generate_all_signals(symbol, data)
        sig_rsi = self.rsi.generate_all_signals(symbol, data)
        sig_bb = self.bb.generate_all_signals(symbol, data)

        combined = (sig_ema * 0.4) + (sig_rsi * 0.35) + (sig_bb * 0.25)
        signals = pd.Series(0, index=data.index)
        signals[combined >= 0.3] = 1
        signals[combined <= -0.3] = -1
        return signals