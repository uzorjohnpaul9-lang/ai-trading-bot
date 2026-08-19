"""
Signal Generator
================
Combines all analysis into trade signals.
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import List, Optional
from indicators import Indicators
from ml_predictor import MLPredictor
from risk_manager import RiskManager
from strategies import Strategies
from config import config


@dataclass
class TradeSignal:
    """Represents a trade signal"""
    symbol: str
    direction: str  # "long" or "short"
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    reasons: List[str]
    timestamp: pd.Timestamp = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = pd.Timestamp.now()


class SignalGenerator:
    """Generate trade signals from market data"""

    def __init__(self, risk_manager: RiskManager):
        self.ml = MLPredictor()
        self.risk_manager = risk_manager
        self.strategies = Strategies()
        self.ml_trained = False

    def analyze(self, df: pd.DataFrame, symbol: str) -> Optional[TradeSignal]:
        """
        Run full analysis and generate signal.

        Returns TradeSignal or None if no valid signal.
        """
        if len(df) < 100:
            return None

        # Calculate indicators
        df = Indicators.calculate_all(df)
        latest = df.iloc[-1]

        # Collect signals
        signals = []
        reasons = []

        # 1. RSI signal
        rsi_val = latest.get("rsi", 50)
        if rsi_val < config.indicators.rsi_oversold:
            signals.append(("buy", 0.7))
            reasons.append(f"RSI oversold ({rsi_val:.1f})")
        elif rsi_val > config.indicators.rsi_overbought:
            signals.append(("sell", 0.7))
            reasons.append(f"RSI overbought ({rsi_val:.1f})")

        # 2. MACD signal
        macd_hist = latest.get("macd_hist", 0)
        macd_signal_val = latest.get("macd_signal_val", 0)
        if macd_signal_val > 0:
            signals.append(("buy", 0.6))
            reasons.append("MACD bullish crossover")
        elif macd_signal_val < 0:
            signals.append(("sell", 0.6))
            reasons.append("MACD bearish crossover")

        # 3. Bollinger Bands
        bb_signal = latest.get("bb_signal", 0)
        if bb_signal > 0:
            signals.append(("buy", 0.65))
            reasons.append("Price below lower Bollinger Band")
        elif bb_signal < 0:
            signals.append(("sell", 0.65))
            reasons.append("Price above upper Bollinger Band")

        # 4. Supertrend
        st_dir = latest.get("supertrend_dir", 0)
        if st_dir > 0:
            signals.append(("buy", 0.7))
            reasons.append("Supertrend bullish")
        elif st_dir < 0:
            signals.append(("sell", 0.7))
            reasons.append("Supertrend bearish")

        # 5. ADX trend strength
        adx_val = latest.get("adx", 0)
        if adx_val > config.indicators.adx_threshold:
            reasons.append(f"Strong trend (ADX {adx_val:.1f})")
        else:
            reasons.append(f"Weak trend (ADX {adx_val:.1f})")

        # 6. Strategy-based signals
        strategy_signal = self.strategies.get_best_signal(df)
        if strategy_signal:
            strategy_name = strategy_signal.reasons[0] if strategy_signal.reasons else "[Strategy]"
            if strategy_signal.direction == "long":
                signals.append(("buy", strategy_signal.confidence))
                reasons.extend(strategy_signal.reasons)
            elif strategy_signal.direction == "short":
                signals.append(("sell", strategy_signal.confidence))
                reasons.extend(strategy_signal.reasons)

        # 7. ML prediction
        if config.ml.enabled:
            if not self.ml_trained:
                accuracy = self.ml.train(df)
                if accuracy > 0:
                    self.ml_trained = True
                    reasons.append(f"ML trained (accuracy: {accuracy:.1%})")

            ml_signal, ml_conf = self.ml.predict(df)
            if ml_signal == 1:
                signals.append(("buy", ml_conf))
                reasons.append(f"ML predicts UP ({ml_conf:.1%})")
            elif ml_signal == -1:
                signals.append(("sell", ml_conf))
                reasons.append(f"ML predicts DOWN ({ml_conf:.1%})")

        # Aggregate signals
        if not signals:
            return None

        buy_score = sum(conf for direction, conf in signals if direction == "buy")
        sell_score = sum(conf for direction, conf in signals if direction == "sell")

        # Need minimum agreement
        min_signals = 2
        buy_signals = sum(1 for d, _ in signals if d == "buy")
        sell_signals = sum(1 for d, _ in signals if d == "sell")

        if buy_signals >= min_signals and buy_score > sell_score:
            direction = "long"
            confidence = buy_score / buy_signals
        elif sell_signals >= min_signals and sell_score > buy_score:
            direction = "short"
            confidence = sell_score / sell_signals
        else:
            return None

        # Calculate entry, stop loss, take profit
        entry_price = latest["close"]
        atr = latest.get("atr", entry_price * 0.02)

        stop_loss = self.risk_manager.calculate_stop_loss(entry_price, direction, atr)
        take_profit = self.risk_manager.calculate_take_profit(entry_price, stop_loss, direction)

        return TradeSignal(
            symbol=symbol,
            direction=direction,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            confidence=confidence,
            reasons=reasons
        )
