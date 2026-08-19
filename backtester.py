"""
Backtesting Engine
==================
Test strategies on historical data.
"""
import numpy as np
import pandas as pd
from typing import List, Dict
from indicators import Indicators
from config import config


class Backtester:
    """Backtest trading strategies on historical data"""

    def __init__(self, initial_capital: float = 10000):
        self.initial_capital = initial_capital

    def run(self, df: pd.DataFrame, strategy_fn=None) -> Dict:
        """
        Run backtest on historical data.

        Args:
            df: OHLCV dataframe
            strategy_fn: Custom strategy function (optional)

        Returns:
            Backtest results dictionary
        """
        df = Indicators.calculate_all(df.copy())

        capital = self.initial_capital
        position = None
        trades = []
        equity_curve = [capital]

        for i in range(100, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i - 1]

            # Check exit
            if position:
                price = row["close"]
                if position["direction"] == "long":
                    if price <= position["stop_loss"] or price >= position["take_profit"]:
                        pnl = (price - position["entry"]) * position["quantity"]
                        capital += position["value"] + pnl
                        trades.append({
                            "entry": position["entry"],
                            "exit": price,
                            "pnl": pnl,
                            "pnl_pct": (pnl / position["value"]) * 100,
                            "direction": position["direction"]
                        })
                        position = None

            # Check entry
            if not position:
                signal = self._simple_strategy(df, i)
                if signal:
                    entry_price = row["close"]
                    atr = row.get("atr", entry_price * 0.02)

                    if signal == "long":
                        stop_loss = entry_price - (atr * 2)
                        take_profit = entry_price + (atr * 2 * config.risk.risk_reward_ratio)
                    else:
                        stop_loss = entry_price + (atr * 2)
                        take_profit = entry_price - (atr * 2 * config.risk.risk_reward_ratio)

                    risk_amount = capital * config.risk.max_risk_per_trade
                    risk_per_share = abs(entry_price - stop_loss)
                    quantity = risk_amount / risk_per_share if risk_per_share > 0 else 0

                    if quantity > 0:
                        value = entry_price * quantity
                        if value <= capital:
                            capital -= value
                            position = {
                                "direction": signal,
                                "entry": entry_price,
                                "quantity": quantity,
                                "stop_loss": stop_loss,
                                "take_profit": take_profit,
                                "value": value
                            }

            equity_curve.append(capital + (position["value"] if position else 0))

        # Calculate metrics
        equity = np.array(equity_curve)
        returns = np.diff(equity) / equity[:-1]

        winning_trades = [t for t in trades if t["pnl"] > 0]
        losing_trades = [t for t in trades if t["pnl"] <= 0]

        total_return = ((equity[-1] - self.initial_capital) / self.initial_capital) * 100
        max_drawdown = self._max_drawdown(equity)
        sharpe = self._sharpe_ratio(returns)

        return {
            "total_return": total_return,
            "total_trades": len(trades),
            "winning_trades": len(winning_trades),
            "losing_trades": len(losing_trades),
            "win_rate": (len(winning_trades) / len(trades) * 100) if trades else 0,
            "avg_win": np.mean([t["pnl"] for t in winning_trades]) if winning_trades else 0,
            "avg_loss": np.mean([t["pnl"] for t in losing_trades]) if losing_trades else 0,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe,
            "final_capital": equity[-1],
            "equity_curve": equity_curve,
            "trades": trades
        }

    def _simple_strategy(self, df: pd.DataFrame, idx: int) -> str:
        """Simple strategy for backtesting"""
        row = df.iloc[idx]

        buy_signals = 0
        sell_signals = 0

        # RSI
        rsi = row.get("rsi", 50)
        if rsi < 35:
            buy_signals += 1
        elif rsi > 65:
            sell_signals += 1

        # MACD
        if row.get("macd_hist", 0) > 0 and df.iloc[idx - 1].get("macd_hist", 0) <= 0:
            buy_signals += 1
        elif row.get("macd_hist", 0) < 0 and df.iloc[idx - 1].get("macd_hist", 0) >= 0:
            sell_signals += 1

        # Supertrend
        if row.get("supertrend_dir", 0) > 0:
            buy_signals += 1
        elif row.get("supertrend_dir", 0) < 0:
            sell_signals += 1

        if buy_signals >= 2:
            return "long"
        elif sell_signals >= 2:
            return "short"
        return None

    def _max_drawdown(self, equity: np.ndarray) -> float:
        """Calculate maximum drawdown"""
        peak = np.maximum.accumulate(equity)
        drawdown = (peak - equity) / peak
        return np.max(drawdown) * 100

    def _sharpe_ratio(self, returns: np.ndarray, risk_free: float = 0) -> float:
        """Calculate Sharpe ratio"""
        if len(returns) < 2 or np.std(returns) == 0:
            return 0
        excess_returns = returns - risk_free / 252
        return np.sqrt(252) * np.mean(excess_returns) / np.std(excess_returns)
