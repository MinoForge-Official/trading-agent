"""AI-Assisted Trading Strategy using LLM reasoning (Gemini API) with robust fallback."""

from __future__ import annotations

import json
import logging
import os
from typing import Optional
import pandas as pd
from trading_agent.core.models import Action, MarketSignal
from trading_agent.strategies.base import BaseStrategy
from trading_agent.strategies.technical import CompositeStrategy

logger = logging.getLogger(__name__)


class AIAgentStrategy(BaseStrategy):
    """Trading agent that combines quantitative indicators with LLM reasoning for high-conviction signals."""

    def __init__(self, api_key: Optional[str] = None, model_name: str = "gemini-2.5-flash"):
        super().__init__(name="AI_Agent_Reasoning")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model_name = model_name
        self.composite = CompositeStrategy()
        self._gemini_client = None

        if self.api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.api_key)
            except Exception as exc:
                logger.warning(f"Could not initialize Gemini Client: {exc}. Using heuristic engine.")

    def evaluate(self, symbol: str, data: pd.DataFrame) -> MarketSignal:
        if len(data) < 30:
            return MarketSignal(
                symbol=symbol,
                action=Action.HOLD,
                confidence=0.0,
                price=float(data["Close"].iloc[-1]) if not data.empty else 0.0,
                reason="Insufficient data for AI agent evaluation.",
            )

        row = data.iloc[-1]
        price = float(row["Close"])
        rsi = float(row.get("RSI", 50.0))
        macd = float(row.get("MACD", 0.0))
        macd_hist = float(row.get("MACD_Hist", 0.0))
        ema50 = float(row.get("EMA_50", price))
        ema200 = float(row.get("EMA_200", price))
        bb_width = float(row.get("BB_Width", 0.05))
        atr = float(row.get("ATR", price * 0.02))

        base_signal = self.composite.evaluate(symbol, data)

        # Attempt LLM reasoning if available
        if self._gemini_client:
            try:
                ai_signal = self._evaluate_with_gemini(
                    symbol=symbol,
                    price=price,
                    rsi=rsi,
                    macd=macd,
                    macd_hist=macd_hist,
                    ema50=ema50,
                    ema200=ema200,
                    bb_width=bb_width,
                    atr=atr,
                    base_signal=base_signal,
                )
                if ai_signal:
                    return ai_signal
            except Exception as e:
                logger.warning(f"Gemini evaluation failed: {e}. Falling back to internal engine.")

        # Fallback to deterministic AI reasoning heuristic
        return self._heuristic_ai_reasoning(
            symbol=symbol,
            price=price,
            rsi=rsi,
            macd=macd,
            macd_hist=macd_hist,
            ema50=ema50,
            ema200=ema200,
            bb_width=bb_width,
            atr=atr,
            base_signal=base_signal,
        )

    def _heuristic_ai_reasoning(
        self,
        symbol: str,
        price: float,
        rsi: float,
        macd: float,
        macd_hist: float,
        ema50: float,
        ema200: float,
        bb_width: float,
        atr: float,
        base_signal: MarketSignal,
    ) -> MarketSignal:
        thesis_points = []
        action = base_signal.action
        confidence = base_signal.confidence

        # Trend context
        if price > ema50 and ema50 > ema200:
            trend_state = "Bullish Uptrend (Golden Alignment)"
            thesis_points.append(f"Price is trading above both 50 and 200 EMAs ({price:.2f} > {ema50:.2f} > {ema200:.2f}).")
        elif price < ema50 and ema50 < ema200:
            trend_state = "Bearish Downtrend (Death Alignment)"
            thesis_points.append(f"Price is suppressed below both 50 and 200 EMAs ({price:.2f} < {ema50:.2f} < {ema200:.2f}).")
        else:
            trend_state = "Consolidation / Mixed Regime"
            thesis_points.append("Price is oscillating between medium and long-term moving averages.")

        # Momentum context
        if rsi < 35:
            thesis_points.append(f"RSI({rsi:.1f}) indicates oversold compression with high potential for mean reversion.")
        elif rsi > 65:
            thesis_points.append(f"RSI({rsi:.1f}) signals stretched momentum; caution advised for long entries.")
        else:
            thesis_points.append(f"RSI({rsi:.1f}) sits in neutral territory.")

        # Volatility context
        if bb_width < 0.04:
            thesis_points.append("Bollinger Band squeeze detected (low volatility prior to breakout).")
        elif bb_width > 0.12:
            thesis_points.append("Elevated volatility band expansion.")

        reasoning = (
            f"[AI Agent Thesis - {trend_state}] "
            + " ".join(thesis_points)
            + f" Recommended Action: {action.value}."
        )

        stop_loss = base_signal.stop_loss or (round(price - (atr * 2.0), 2) if action == Action.BUY else None)
        take_profit = base_signal.take_profit or (round(price + (atr * 3.5), 2) if action == Action.BUY else None)

        return MarketSignal(
            symbol=symbol,
            action=action,
            confidence=round(min(0.95, max(0.40, confidence + 0.05)), 2),
            price=price,
            reason=reasoning,
            indicators={
                "trend_state": trend_state,
                "rsi": rsi,
                "macd_hist": macd_hist,
                "atr": atr,
                "composite_signal": base_signal.action.value,
            },
            stop_loss=stop_loss,
            take_profit=take_profit,
        )

    def _evaluate_with_gemini(
        self,
        symbol: str,
        price: float,
        rsi: float,
        macd: float,
        macd_hist: float,
        ema50: float,
        ema200: float,
        bb_width: float,
        atr: float,
        base_signal: MarketSignal,
    ) -> Optional[MarketSignal]:
        prompt = f"""
You are an expert quantitative trading strategist. Analyze the following technical indicators for {symbol} and generate a disciplined trade decision.

Market Data:
- Symbol: {symbol}
- Current Price: ${price:.2f}
- RSI (14): {rsi:.2f}
- MACD: {macd:.4f}, MACD Histogram: {macd_hist:.4f}
- EMA 50: ${ema50:.2f}, EMA 200: ${ema200:.2f}
- Bollinger Band Width: {bb_width:.4f}
- ATR (14): ${atr:.2f}
- Algorithmic Baseline Recommendation: {base_signal.action.value} (Confidence: {base_signal.confidence:.2f})

Respond ONLY with valid JSON in this exact structure:
{{
  "action": "BUY" | "SELL" | "HOLD",
  "confidence": 0.0 to 1.0,
  "reason": "1-2 sentence structured rationale highlighting key drivers and risk/reward",
  "stop_loss": number or null,
  "take_profit": number or null
}}
"""
        response = self._gemini_client.models.generate_content(
            model=self.model_name,
            contents=prompt,
        )
        text = response.text.strip()
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        data = json.loads(text)
        action = Action(data["action"])
        return MarketSignal(
            symbol=symbol,
            action=action,
            confidence=float(data.get("confidence", 0.7)),
            price=price,
            reason=f"[Gemini AI] {data.get('reason', '')}",
            stop_loss=data.get("stop_loss"),
            take_profit=data.get("take_profit"),
            indicators={"rsi": rsi, "atr": atr, "llm_model": self.model_name},
        )

    def generate_all_signals(self, symbol: str, data: pd.DataFrame) -> pd.Series:
        return self.composite.generate_all_signals(symbol, data)