"""
Trading Strategies
==================
Multiple strategies for signal generation.
"""
import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import List, Optional
from indicators import Indicators
from config import config


@dataclass
class StrategySignal:
    """Signal from a strategy"""
    direction: str  # "long", "short", or "flat"
    confidence: float
    reasons: List[str]
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0


class MeanReversionStrategy:
    """
    Mean Reversion Strategy
    Buys when price is oversold relative to moving average,
    sells when overbought.
    """

    def __init__(self):
        self.lookback = 20
        self.entry_zscore = -1.5
        self.exit_zscore = 0.5

    def analyze(self, df: pd.DataFrame) -> Optional[StrategySignal]:
        if len(df) < self.lookback + 10:
            return None

        close = df["close"]
        sma = close.rolling(window=self.lookback).mean()
        std = close.rolling(window=self.lookback).std()

        zscore = (close - sma) / std

        current_zscore = zscore.iloc[-1]
        rsi = df.get("rsi", pd.Series([50]))
        current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 50

        reasons = []

        if current_zscore < self.entry_zscore and current_rsi < 35:
            reasons.append(f"Z-score oversold ({current_zscore:.2f})")
            reasons.append(f"RSI oversold ({current_rsi:.1f})")
            reasons.append(f"Price {abs(current_zscore):.1f} std below mean")
            return StrategySignal(
                direction="long",
                confidence=min(0.8, 0.5 + abs(current_zscore) * 0.1),
                reasons=reasons
            )

        elif current_zscore > -self.entry_zscore and current_rsi > 65:
            reasons.append(f"Z-score overbought ({current_zscore:.2f})")
            reasons.append(f"RSI overbought ({current_rsi:.1f})")
            return StrategySignal(
                direction="short",
                confidence=min(0.8, 0.5 + abs(current_zscore) * 0.1),
                reasons=reasons
            )

        return None


class BreakoutStrategy:
    """
    Breakout Strategy
    Enters when price breaks above/below key levels with volume confirmation.
    """

    def __init__(self):
        self.lookback = 20
        self.volume_mult = 1.5

    def analyze(self, df: pd.DataFrame) -> Optional[StrategySignal]:
        if len(df) < self.lookback + 10:
            return None

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # Calculate levels
        resistance = high.rolling(window=self.lookback).max()
        support = low.rolling(window=self.lookback).min()
        avg_volume = volume.rolling(window=self.lookback).mean()

        current_price = close.iloc[-1]
        current_volume = volume.iloc[-1]
        prev_price = close.iloc[-2]

        current_resistance = resistance.iloc[-2]
        current_support = support.iloc[-2]
        current_avg_vol = avg_volume.iloc[-1]

        reasons = []

        # Bullish breakout
        if current_price > current_resistance and prev_price <= current_resistance:
            vol_ratio = current_volume / current_avg_vol if current_avg_vol > 0 else 0
            if vol_ratio > self.volume_mult:
                reasons.append(f"Breakout above resistance ${current_resistance:,.2f}")
                reasons.append(f"Volume surge ({vol_ratio:.1f}x average)")
                return StrategySignal(
                    direction="long",
                    confidence=min(0.85, 0.6 + vol_ratio * 0.05),
                    reasons=reasons
                )

        # Bearish breakout
        elif current_price < current_support and prev_price >= current_support:
            vol_ratio = current_volume / current_avg_vol if current_avg_vol > 0 else 0
            if vol_ratio > self.volume_mult:
                reasons.append(f"Breakdown below support ${current_support:,.2f}")
                reasons.append(f"Volume surge ({vol_ratio:.1f}x average)")
                return StrategySignal(
                    direction="short",
                    confidence=min(0.85, 0.6 + vol_ratio * 0.05),
                    reasons=reasons
                )

        return None


class MomentumStrategy:
    """
    Momentum Strategy
    Rides strong trends using MACD, RSI, and ADX confirmation.
    """

    def __init__(self):
        self.adx_threshold = 25

    def analyze(self, df: pd.DataFrame) -> Optional[StrategySignal]:
        if len(df) < 50:
            return None

        latest = df.iloc[-1]
        prev = df.iloc[-2]

        adx = latest.get("adx", 0)
        rsi = latest.get("rsi", 50)
        macd = latest.get("macd", 0)
        macd_signal = latest.get("macd_signal", 0)
        macd_hist = latest.get("macd_hist", 0)
        prev_macd_hist = prev.get("macd_hist", 0)

        ema_fast = latest.get("ema_fast", 0)
        ema_slow = latest.get("ema_slow", 0)

        reasons = []

        # Strong uptrend momentum
        if (adx > self.adx_threshold and
            rsi > 50 and rsi < 75 and
            macd > macd_signal and
            macd_hist > prev_macd_hist and
            ema_fast > ema_slow):

            reasons.append(f"Strong uptrend (ADX {adx:.1f})")
            reasons.append("MACD accelerating upward")
            reasons.append(f"RSI momentum ({rsi:.1f})")
            reasons.append("EMA alignment bullish")

            return StrategySignal(
                direction="long",
                confidence=min(0.85, 0.5 + adx * 0.01),
                reasons=reasons
            )

        # Strong downtrend momentum
        elif (adx > self.adx_threshold and
              rsi < 50 and rsi > 25 and
              macd < macd_signal and
              macd_hist < prev_macd_hist and
              ema_fast < ema_slow):

            reasons.append(f"Strong downtrend (ADX {adx:.1f})")
            reasons.append("MACD accelerating downward")
            reasons.append(f"RSI momentum ({rsi:.1f})")
            reasons.append("EMA alignment bearish")

            return StrategySignal(
                direction="short",
                confidence=min(0.85, 0.5 + adx * 0.01),
                reasons=reasons
            )

        return None


class VWAPStrategy:
    """
    VWAP Strategy
    Trades based on price position relative to VWAP.
    """

    def analyze(self, df: pd.DataFrame) -> Optional[StrategySignal]:
        if len(df) < 20:
            return None

        # Calculate VWAP (simplified - using typical price)
        typical_price = (df["high"] + df["low"] + df["close"]) / 3
        vwap = (typical_price * df["volume"]).cumsum() / df["volume"].cumsum()

        current_price = df["close"].iloc[-1]
        current_vwap = vwap.iloc[-1]
        prev_price = df["close"].iloc[-2]
        prev_vwap = vwap.iloc[-2]

        rsi = df.get("rsi", pd.Series([50]))
        current_rsi = rsi.iloc[-1] if len(rsi) > 0 else 50

        reasons = []
        deviation = (current_price - current_vwap) / current_vwap * 100

        # Price crosses above VWAP
        if current_price > current_vwap and prev_price <= prev_vwap:
            reasons.append(f"Price crossed above VWAP")
            reasons.append(f"VWAP deviation: {deviation:+.2f}%")

            if current_rsi < 60:
                reasons.append(f"RSI not overbought ({current_rsi:.1f})")
                return StrategySignal(
                    direction="long",
                    confidence=0.65,
                    reasons=reasons
                )

        # Price crosses below VWAP
        elif current_price < current_vwap and prev_price >= prev_vwap:
            reasons.append(f"Price crossed below VWAP")
            reasons.append(f"VWAP deviation: {deviation:+.2f}%")

            if current_rsi > 40:
                reasons.append(f"RSI not oversold ({current_rsi:.1f})")
                return StrategySignal(
                    direction="short",
                    confidence=0.65,
                    reasons=reasons
                )

        return None


class ScalpingStrategy:
    """
    Scalping Strategy
    Quick trades on small price movements using multiple timeframes.
    """

    def __init__(self):
        self.min_bars = 5

    def analyze(self, df: pd.DataFrame) -> Optional[StrategySignal]:
        if len(df) < 30:
            return None

        # Use very short-term indicators
        close = df["close"]
        ema_5 = Indicators.ema(close, 5)
        ema_8 = Indicators.ema(close, 8)
        ema_13 = Indicators.ema(close, 13)

        rsi = Indicators.rsi(df, period=7)

        current_ema5 = ema_5.iloc[-1]
        current_ema8 = ema_8.iloc[-1]
        current_ema13 = ema_13.iloc[-1]
        current_rsi = rsi.iloc[-1]

        prev_ema5 = ema_5.iloc[-2]
        prev_ema8 = ema_8.iloc[-2]

        reasons = []

        # Quick long scalp
        if (current_ema5 > current_ema8 > current_ema13 and
            prev_ema5 <= prev_ema8 and
            current_rsi > 40 and current_rsi < 70):

            reasons.append("EMA 5/8/13 bullish alignment")
            reasons.append(f"RSI favorable ({current_rsi:.1f})")
            return StrategySignal(
                direction="long",
                confidence=0.6,
                reasons=reasons
            )

        # Quick short scalp
        elif (current_ema5 < current_ema8 < current_ema13 and
              prev_ema5 >= prev_ema8 and
              current_rsi > 30 and current_rsi < 60):

            reasons.append("EMA 5/8/13 bearish alignment")
            reasons.append(f"RSI favorable ({current_rsi:.1f})")
            return StrategySignal(
                direction="short",
                confidence=0.6,
                reasons=reasons
            )

        return None


class Strategies:
    """Container for all strategies"""

    def __init__(self):
        self.mean_reversion = MeanReversionStrategy()
        self.breakout = BreakoutStrategy()
        self.momentum = MomentumStrategy()
        self.vwap = VWAPStrategy()
        self.scalping = ScalpingStrategy()

    def analyze_all(self, df: pd.DataFrame) -> List[StrategySignal]:
        """Run all strategies and return signals"""
        signals = []

        strategies = [
            ("Mean Reversion", self.mean_reversion),
            ("Breakout", self.breakout),
            ("Momentum", self.momentum),
            ("VWAP", self.vwap),
            ("Scalping", self.scalping),
        ]

        for name, strategy in strategies:
            try:
                signal = strategy.analyze(df)
                if signal:
                    # Tag with strategy name
                    signal.reasons.insert(0, f"[{name}]")
                    signals.append(signal)
            except Exception as e:
                continue

        return signals

    def get_best_signal(self, df: pd.DataFrame) -> Optional[StrategySignal]:
        """Get the highest confidence signal from all strategies"""
        signals = self.analyze_all(df)

        if not signals:
            return None

        # Sort by confidence
        signals.sort(key=lambda s: s.confidence, reverse=True)
        return signals[0]
