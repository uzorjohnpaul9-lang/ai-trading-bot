"""
Risk Management System
======================
Controls position sizing, drawdown limits, and trade risk.
"""
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Tuple, Optional
from config import config


@dataclass
class Position:
    """Represents an open position"""
    symbol: str
    direction: str  # "long" or "short"
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    entry_time: datetime = field(default_factory=datetime.now)
    pnl: float = 0.0

    @property
    def risk_amount(self) -> float:
        return abs(self.entry_price - self.stop_loss) * self.quantity

    @property
    def reward_amount(self) -> float:
        return abs(self.take_profit - self.entry_price) * self.quantity


class RiskManager:
    """Manages all trading risk"""

    def __init__(self, initial_capital: float):
        self.initial_capital = initial_capital
        self.current_capital = initial_capital
        self.peak_capital = initial_capital
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.open_positions = 0
        self.last_reset_date = date.today()
        self.trade_history = []

    def reset_daily(self):
        """Reset daily counters"""
        self.daily_pnl = 0.0
        self.daily_trades = 0
        self.last_reset_date = date.today()

    def can_trade(self) -> Tuple[bool, str]:
        """Check if we're allowed to take a new trade"""
        today = date.today()
        if today != self.last_reset_date:
            self.reset_daily()

        # Check daily loss limit
        daily_loss_pct = abs(self.daily_pnl) / self.current_capital if self.daily_pnl < 0 else 0
        if daily_loss_pct >= config.risk.max_daily_loss:
            return False, f"Daily loss limit hit ({daily_loss_pct:.1%})"

        # Check max drawdown
        drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
        if drawdown >= config.risk.max_drawdown:
            return False, f"Max drawdown reached ({drawdown:.1%})"

        # Check open positions
        if self.open_positions >= config.risk.max_open_positions:
            return False, f"Max positions reached ({self.open_positions})"

        return True, "OK"

    def calculate_position_size(self, entry_price: float, stop_loss: float) -> float:
        """Calculate position size based on risk parameters"""
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share <= 0:
            return 0

        max_risk_amount = self.current_capital * config.risk.max_risk_per_trade
        position_size = max_risk_amount / risk_per_share

        # Cap at max position value
        max_position_value = self.current_capital * 0.3  # Max 30% per position
        max_quantity = max_position_value / entry_price

        return min(position_size, max_quantity)

    def calculate_stop_loss(self, entry_price: float, direction: str, atr: float) -> float:
        """Calculate stop loss price"""
        multiplier = 2.0
        if direction == "long":
            return entry_price - (atr * multiplier)
        else:
            return entry_price + (atr * multiplier)

    def calculate_take_profit(self, entry_price: float, stop_loss: float, direction: str) -> float:
        """Calculate take profit price"""
        risk = abs(entry_price - stop_loss)
        reward = risk * config.risk.risk_reward_ratio

        if direction == "long":
            return entry_price + reward
        else:
            return entry_price - reward

    def record_trade_open(self):
        """Record a new trade opening"""
        self.open_positions += 1
        self.daily_trades += 1

    def record_trade_close(self, pnl: float):
        """Record a trade closing"""
        self.current_capital += pnl
        self.peak_capital = max(self.peak_capital, self.current_capital)
        self.daily_pnl += pnl
        self.open_positions = max(0, self.open_positions - 1)
        self.trade_history.append({
            "pnl": pnl,
            "date": datetime.now(),
            "capital_after": self.current_capital
        })

    def get_stats(self) -> dict:
        """Get current risk statistics"""
        drawdown = (self.peak_capital - self.current_capital) / self.peak_capital if self.peak_capital > 0 else 0
        winning = sum(1 for t in self.trade_history if t.get("pnl", 0) > 0)
        total = len(self.trade_history)
        return {
            "current_capital": self.current_capital,
            "initial_capital": self.initial_capital,
            "total_return": ((self.current_capital - self.initial_capital) / self.initial_capital) * 100,
            "peak_capital": self.peak_capital,
            "drawdown": drawdown * 100,
            "daily_pnl": self.daily_pnl,
            "daily_trades": self.daily_trades,
            "open_positions": self.open_positions,
            "total_trades": total,
            "win_rate": (winning / total * 100) if total > 0 else 0
        }
