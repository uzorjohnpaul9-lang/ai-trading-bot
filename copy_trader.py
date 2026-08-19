"""
Copy Trading Engine
===================
Executes trades on behalf of subscribed users.
Auto take-profit, notifications, and dynamic sizing.
"""
import ccxt
import json
import os
import time
import urllib.request
import ssl
from datetime import datetime, date
from typing import Optional, Dict, List
from database import get_db
from config import config

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


class PerformanceTracker:
    """Tracks bot performance to adjust position sizes dynamically"""

    def __init__(self):
        self.total_trades = 0
        self.winning_trades = 0
        self.consecutive_wins = 0
        self.consecutive_losses = 0
        self.win_rate = 0.0
        self.tier_multiplier = 1.0

    def record_trade(self, won: bool):
        self.total_trades += 1
        if won:
            self.winning_trades += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.consecutive_losses += 1
            self.consecutive_wins = 0

        self.win_rate = self.winning_trades / self.total_trades if self.total_trades > 0 else 0
        self._update_multiplier()

    def _update_multiplier(self):
        """Increase position sizes as bot becomes more profitable"""
        if self.win_rate >= 0.65 and self.total_trades >= 10:
            self.tier_multiplier = 1.5  # 50% bigger positions
        elif self.win_rate >= 0.60 and self.total_trades >= 10:
            self.tier_multiplier = 1.25  # 25% bigger
        elif self.win_rate >= 0.55 and self.total_trades >= 10:
            self.tier_multiplier = 1.1  # 10% bigger
        else:
            self.tier_multiplier = 1.0  # baseline

    def get_risk_pct(self, tier: str) -> float:
        """Get risk percentage based on tier and performance"""
        base_risk = {"free": 0.01, "pro": 0.02, "vip": 0.03}
        risk = base_risk.get(tier, 0.02)
        return risk * self.tier_multiplier


performance = PerformanceTracker()


class UserExchange:
    """Manages a single user's exchange connection"""

    def __init__(self, user_id: int, exchange_name: str, api_key: str, api_secret: str):
        self.user_id = user_id
        self.exchange_name = exchange_name
        self.exchange = None

        try:
            exchange_class = getattr(ccxt, exchange_name)
            self.exchange = exchange_class({
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot"}
            })

            if config.exchange.testnet:
                self.exchange.set_sandbox_mode(True)

            self.exchange.load_markets()

        except Exception as e:
            print(f"  [EXCHANGE ERROR] User {user_id}: {e}")

    def get_balance(self) -> float:
        if not self.exchange:
            return 0
        try:
            balance = self.exchange.fetch_balance()
            return float(balance.get("USDT", {}).get("free", 0))
        except:
            return 0

    def place_trade(self, symbol: str, side: str, amount: float) -> dict:
        if not self.exchange:
            return {"error": "Exchange not connected"}
        try:
            if side == "buy":
                order = self.exchange.create_market_buy_order(symbol, amount)
            else:
                order = self.exchange.create_market_sell_order(symbol, amount)
            return {
                "id": order["id"],
                "status": order["status"],
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "average": order.get("average"),
                "fee": order.get("fee")
            }
        except Exception as e:
            return {"error": str(e)}

    def get_ticker_price(self, symbol: str) -> float:
        if not self.exchange:
            return 0
        try:
            ticker = self.exchange.fetch_ticker(symbol)
            return ticker["last"]
        except:
            return 0


class CopyTrader:
    """Executes trades for subscribed users based on bot signals"""

    def __init__(self):
        self.user_exchanges: Dict[int, UserExchange] = {}
        self.user_chat_ids: Dict[int, str] = {}

    def connect_user(self, user_id: int, exchange_name: str,
                     api_key: str, api_secret: str) -> bool:
        try:
            user_exchange = UserExchange(user_id, exchange_name, api_key, api_secret)
            if user_exchange.exchange:
                self.user_exchanges[user_id] = user_exchange
                return True
        except:
            pass
        return False

    def disconnect_user(self, user_id: int):
        self.user_exchanges.pop(user_id, None)

    def set_user_chat_id(self, user_id: int, chat_id: str):
        """Set Telegram chat ID for user notifications"""
        self.user_chat_ids[user_id] = chat_id

    def get_subscribed_users(self) -> List[dict]:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.id, u.username, u.subscription_tier, u.api_key, u.api_secret
            FROM users u
            WHERE u.subscription_tier IN ('pro', 'vip')
            AND u.api_key IS NOT NULL
            AND u.api_key != ''
        """)
        users = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return users

    def _notify_user(self, user_id: int, message: str):
        """Send notification to user via Telegram"""
        chat_id = self.user_chat_ids.get(user_id)
        if not chat_id:
            # Try to get from database
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute("SELECT telegram_chat_id FROM users WHERE id = ?", (user_id,))
            row = cursor.fetchone()
            conn.close()
            if row and row["telegram_chat_id"]:
                chat_id = row["telegram_chat_id"]
                self.user_chat_ids[user_id] = chat_id
            else:
                return

        token = config.telegram.bot_token
        if not token:
            return

        try:
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = json.dumps({
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "HTML"
            }).encode("utf-8")

            req = urllib.request.Request(url, data=data,
                                        headers={"Content-Type": "application/json"},
                                        method="POST")
            urllib.request.urlopen(req, timeout=10, context=ssl_ctx)
        except:
            pass

    def execute_signal_for_users(self, signal) -> List[dict]:
        """Execute a trade signal for all subscribed users"""
        results = []

        for user in self.get_subscribed_users():
            user_id = user["id"]
            tier = user.get("subscription_tier", "pro")

            if user_id not in self.user_exchanges:
                exchange_name = "binance"
                if user.get("api_key", "").startswith("v5"):
                    exchange_name = "bybit"

                self.connect_user(user_id, exchange_name, user["api_key"], user.get("api_secret", ""))

            if user_id not in self.user_exchanges:
                continue

            user_exchange = self.user_exchanges[user_id]
            balance = user_exchange.get_balance()

            if balance < 10:
                results.append({"user_id": user_id, "status": "skipped", "reason": "insufficient balance"})
                continue

            # Dynamic risk based on performance and tier
            risk_pct = performance.get_risk_pct(tier)
            risk_amount = balance * risk_pct
            risk_per_unit = abs(signal.entry_price - signal.stop_loss)
            quantity = risk_amount / risk_per_unit if risk_per_unit > 0 else 0

            max_quantity = (balance * 0.25) / signal.entry_price
            quantity = min(quantity, max_quantity)

            if quantity <= 0:
                results.append({"user_id": user_id, "status": "skipped", "reason": "quantity too small"})
                continue

            side = "buy" if signal.direction == "long" else "sell"
            order = user_exchange.place_trade(symbol=signal.symbol, side=side, amount=quantity)

            if "error" in order:
                results.append({"user_id": user_id, "status": "error", "error": order["error"]})
            else:
                self._record_user_trade(user_id, signal, order, quantity)

                # Notify user
                emoji = "\U0001f7e2" if signal.direction == "long" else "\U0001f534"
                msg = (
                    f"{emoji} <b>Trade Executed!</b>\n\n"
                    f"<b>{signal.direction.upper()} {signal.symbol}</b>\n"
                    f"Entry: ${order.get('average', signal.entry_price):,.2f}\n"
                    f"Stop Loss: ${signal.stop_loss:,.2f}\n"
                    f"Take Profit: ${signal.take_profit:,.2f}\n"
                    f"Size: {quantity:.6f}\n"
                    f"Confidence: {signal.confidence:.0%}\n\n"
                    f"<i>Auto take-profit is active</i>"
                )
                self._notify_user(user_id, msg)

                results.append({"user_id": user_id, "status": "executed", "order": order})
                print(f"  [COPY] {user['username']}: {signal.direction} {signal.symbol} x{quantity:.6f}")

        return results

    def check_and_close_positions(self):
        """Check all user positions for take-profit / stop-loss"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.*, u.username, u.subscription_tier
            FROM trades t
            JOIN users u ON t.user_id = u.id
            WHERE t.status = 'open'
        """)
        open_trades = [dict(row) for row in cursor.fetchall()]
        conn.close()

        for trade in open_trades:
            user_id = trade["user_id"]

            if user_id not in self.user_exchanges:
                continue

            user_exchange = self.user_exchanges[user_id]
            current_price = user_exchange.get_ticker_price(trade["symbol"])

            if current_price <= 0:
                continue

            should_close = False
            reason = ""

            if trade["direction"] == "long":
                if current_price >= trade["take_profit"]:
                    should_close = True
                    reason = "take profit"
                elif current_price <= trade["stop_loss"]:
                    should_close = True
                    reason = "stop loss"
            else:
                if current_price <= trade["take_profit"]:
                    should_close = True
                    reason = "take profit"
                elif current_price >= trade["stop_loss"]:
                    should_close = True
                    reason = "stop loss"

            if should_close:
                side = "sell" if trade["direction"] == "long" else "buy"
                order = user_exchange.place_trade(trade["symbol"], side, trade["quantity"])

                if "error" not in order:
                    exit_price = order.get("average", current_price)
                    if trade["direction"] == "long":
                        pnl = (exit_price - trade["entry_price"]) * trade["quantity"]
                    else:
                        pnl = (trade["entry_price"] - exit_price) * trade["quantity"]

                    pnl_pct = pnl / (trade["entry_price"] * trade["quantity"]) * 100

                    from database import TradeModel
                    TradeModel.close_trade(trade["id"], exit_price, pnl, pnl_pct)

                    won = pnl > 0
                    performance.record_trade(won)

                    emoji = "\u2705" if won else "\u274c"
                    msg = (
                        f"{emoji} <b>Position Closed ({reason})</b>\n\n"
                        f"<b>{trade['symbol']}</b>\n"
                        f"Entry: ${trade['entry_price']:,.2f}\n"
                        f"Exit: ${exit_price:,.2f}\n"
                        f"PnL: ${pnl:+,.2f} ({pnl_pct:+.1f}%)\n\n"
                        f"<i>Win rate: {performance.win_rate:.0%} | "
                        f"Multiplier: {performance.tier_multiplier:.1f}x</i>"
                    )
                    self._notify_user(user_id, msg)

                    print(f"  [COPY CLOSE] {trade['username']}: {trade['symbol']} "
                          f"{'WIN' if won else 'LOSS'} ${pnl:+,.2f}")

    def _record_user_trade(self, user_id: int, signal, order: dict, quantity: float):
        from database import TradeModel
        TradeModel.record_trade(
            user_id=user_id,
            symbol=signal.symbol,
            direction=signal.direction,
            entry_price=order.get("average", signal.entry_price),
            quantity=quantity,
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit
        )


# Global instance
copy_trader = CopyTrader()
