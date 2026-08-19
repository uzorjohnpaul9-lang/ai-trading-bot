"""
Paper Trading Engine
====================
Simulates trades without real money.
"""
import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field, asdict
from risk_manager import Position


STATE_FILE = "paper_trader_state.json"


@dataclass
class TradeRecord:
    """Record of a completed trade"""
    symbol: str
    direction: str
    entry_price: float
    exit_price: float
    quantity: float
    entry_time: str
    exit_time: str
    pnl: float
    pnl_pct: float


class PaperTrader:
    """Simulates trading with paper money"""

    def __init__(self, initial_balance: float):
        self.initial_balance = initial_balance
        self.balance = initial_balance
        self.positions: Dict[str, Position] = {}
        self.trade_history: List[TradeRecord] = []
        self._load_state()

    def open_position(
        self,
        symbol: str,
        direction: str,
        price: float,
        quantity: float,
        stop_loss: float,
        take_profit: float
    ) -> Optional[Position]:
        """Open a new paper position"""
        if symbol in self.positions:
            return None

        # Check if we have enough balance
        cost = price * quantity
        if cost > self.balance:
            quantity = self.balance / price * 0.95  # Leave some buffer
            if quantity <= 0:
                return None

        position = Position(
            symbol=symbol,
            direction=direction,
            entry_price=price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit
        )

        self.positions[symbol] = position
        self.balance -= price * quantity
        self._save_state()

        return position

    def close_position(self, symbol: str, current_price: float) -> Optional[TradeRecord]:
        """Close an open position"""
        if symbol not in self.positions:
            return None

        position = self.positions[symbol]

        # Calculate PnL
        if position.direction == "long":
            pnl = (current_price - position.entry_price) * position.quantity
        else:
            pnl = (position.entry_price - current_price) * position.quantity

        pnl_pct = pnl / (position.entry_price * position.quantity) * 100

        # Record trade
        record = TradeRecord(
            symbol=symbol,
            direction=position.direction,
            entry_price=position.entry_price,
            exit_price=current_price,
            quantity=position.quantity,
            entry_time=position.entry_time.isoformat(),
            exit_time=datetime.now().isoformat(),
            pnl=pnl,
            pnl_pct=pnl_pct
        )

        self.trade_history.append(record)
        self.balance += position.entry_price * position.quantity + pnl

        del self.positions[symbol]
        self._save_state()

        return record

    def check_positions(self, current_prices: Dict[str, float]) -> List[TradeRecord]:
        """Check all positions for stop loss / take profit hits"""
        closed = []

        for symbol in list(self.positions.keys()):
            if symbol not in current_prices:
                continue

            position = self.positions[symbol]
            price = current_prices[symbol]

            should_close = False
            if position.direction == "long":
                if price <= position.stop_loss or price >= position.take_profit:
                    should_close = True
            else:
                if price >= position.stop_loss or price <= position.take_profit:
                    should_close = True

            if should_close:
                record = self.close_position(symbol, price)
                if record:
                    closed.append(record)

        return closed

    def get_stats(self) -> dict:
        """Get trading statistics"""
        total_trades = len(self.trade_history)
        winning_trades = sum(1 for t in self.trade_history if t.pnl > 0)
        total_pnl = sum(t.pnl for t in self.trade_history)

        # Calculate total equity (balance + value of open positions)
        open_position_value = sum(
            p.entry_price * p.quantity for p in self.positions.values()
        )
        total_equity = self.balance + open_position_value

        return {
            "balance": self.balance,
            "initial_balance": self.initial_balance,
            "total_equity": total_equity,
            "total_return": ((total_equity - self.initial_balance) / self.initial_balance) * 100,
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "win_rate": (winning_trades / total_trades * 100) if total_trades > 0 else 0,
            "total_pnl": total_pnl,
            "open_positions": len(self.positions),
            "open_position_value": open_position_value,
            "positions": {s: {
                "direction": p.direction,
                "entry": p.entry_price,
                "stop_loss": p.stop_loss,
                "take_profit": p.take_profit
            } for s, p in self.positions.items()}
        }

    def _save_state(self):
        """Save state to file"""
        state = {
            "balance": self.balance,
            "positions": {
                s: {
                    "symbol": p.symbol,
                    "direction": p.direction,
                    "entry_price": p.entry_price,
                    "quantity": p.quantity,
                    "stop_loss": p.stop_loss,
                    "take_profit": p.take_profit,
                    "entry_time": p.entry_time.isoformat()
                }
                for s, p in self.positions.items()
            },
            "trade_history": [asdict(t) for t in self.trade_history]
        }

        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)

    def _load_state(self):
        """Load state from file"""
        if not os.path.exists(STATE_FILE):
            return

        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)

            self.balance = state.get("balance", self.initial_balance)

            for s, data in state.get("positions", {}).items():
                self.positions[s] = Position(
                    symbol=data["symbol"],
                    direction=data["direction"],
                    entry_price=data["entry_price"],
                    quantity=data["quantity"],
                    stop_loss=data["stop_loss"],
                    take_profit=data["take_profit"],
                    entry_time=datetime.fromisoformat(data["entry_time"])
                )

            for t in state.get("trade_history", []):
                self.trade_history.append(TradeRecord(**t))

        except Exception as e:
            print(f"  [WARN] Could not load state: {e}")
