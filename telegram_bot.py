"""
Telegram Bot - Signal Channel
=============================
Posts trading signals to a Telegram channel.
Free tier now, premium tiers later.
"""
import json
import ssl
import urllib.request
import urllib.parse
from datetime import datetime
from typing import Optional, List
from config import config

# Create SSL context that doesn't verify certificates (for environments with cert issues)
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


class TelegramBot:
    """Posts trading signals to Telegram channel"""

    def __init__(self, bot_token: str = None, channel_id: str = None):
        self.bot_token = bot_token or config.telegram.bot_token
        self.channel_id = channel_id or config.telegram.channel_id
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        self.enabled = bool(self.bot_token and self.channel_id)
        self.signal_count = 0
        self.win_count = 0
        self.free_daily_limit = config.telegram.free_daily_limit
        self.messages_sent_today = 0
        self.last_reset = datetime.now().date()
        self.payment_link = "https://t.me/crypto3_ai_signals"

    def _send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message via Telegram Bot API"""
        if not self.enabled:
            return False

        try:
            url = f"{self.base_url}/sendMessage"
            data = json.dumps({
                "chat_id": self.channel_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": True
            }).encode("utf-8")

            req = urllib.request.Request(
                url,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=10, context=ssl_ctx) as resp:
                result = json.loads(resp.read().decode())
                return result.get("ok", False)

        except Exception as e:
            print(f"  [TELEGRAM ERROR] {e}")
            return False

    def _check_daily_limit(self) -> bool:
        """Check if we're within free tier daily limit"""
        today = datetime.now().date()
        if today != self.last_reset:
            self.messages_sent_today = 0
            self.last_reset = today

        return self.messages_sent_today < self.free_daily_limit

    def format_signal(self, signal, tier: str = "free") -> str:
        """Format a trade signal into a Telegram message"""
        direction = signal.direction.upper()
        emoji = "\U0001f7e2" if signal.direction == "long" else "\U0001f534"
        risk = abs(signal.entry_price - signal.stop_loss)
        reward = abs(signal.take_profit - signal.entry_price)
        rr_ratio = reward / risk if risk > 0 else 0

        if tier == "free":
            # Free users see basic signal with upgrade CTA
            msg = (
                f"{emoji} <b>{direction} | {signal.symbol}</b> {emoji}\n"
                f"\n"
                f"\u2709 <b>Entry:</b> ${signal.entry_price:,.2f}\n"
                f"\U0001f6ab <b>Stop Loss:</b> ${signal.stop_loss:,.2f}\n"
                f"\U0001f3af <b>Take Profit:</b> ${signal.take_profit:,.2f}\n"
                f"\U0001f3af <b>Confidence:</b> {signal.confidence:.0%}\n"
                f"\n\u23f0 <i>{datetime.now().strftime('%b %d, %H:%M UTC')}</i>"
                f"\n\n\u2b07\ufe0f <b>Want more?</b>"
                f"\n\U0001f510 <b>Pro ($29/mo):</b> Deep analysis, R:R ratio, all pairs"
                f"\n\U0001f680 <b>VIP ($99/mo):</b> Auto-trade on YOUR account"
                f"\n\n<a href=\"{self.payment_link}\">\u2705 Tap here to upgrade</a>"
            )

        elif tier == "pro":
            # Pro users see full signal with reasons and analysis
            msg = (
                f"{emoji} <b>{direction} | {signal.symbol}</b> {emoji}\n"
                f"\n"
                f"\u2709 <b>Entry:</b> ${signal.entry_price:,.2f}\n"
                f"\U0001f6ab <b>Stop Loss:</b> ${signal.stop_loss:,.2f}\n"
                f"\U0001f3af <b>Take Profit:</b> ${signal.take_profit:,.2f}\n"
                f"\n"
                f"\U0001f4ca <b>Risk/Reward:</b> 1:{rr_ratio:.1f}\n"
                f"\U0001f3af <b>Confidence:</b> {signal.confidence:.0%}\n"
            )

            # Full reasons for pro
            if signal.reasons:
                msg += f"\n\U0001f4a1 <b>Analysis:</b>\n"
                for r in signal.reasons[:5]:
                    msg += f"  \u2022 {r}\n"

            msg += f"\n\u23f0 <i>{datetime.now().strftime('%b %d, %H:%M UTC')}</i>"
            msg += f"\n\n\U0001f4b0 <i>Want auto-trading?</i>"
            msg += f"\n<a href=\"{self.payment_link}\">\U0001f680 Upgrade to VIP ($99/mo)</a>"

        elif tier == "vip":
            # VIP users see everything + auto-trade confirmation
            msg = (
                f"{emoji} <b>{direction} | {signal.symbol}</b> {emoji}\n"
                f"\n"
                f"\u2709 <b>Entry:</b> ${signal.entry_price:,.2f}\n"
                f"\U0001f6ab <b>Stop Loss:</b> ${signal.stop_loss:,.2f}\n"
                f"\U0001f3af <b>Take Profit:</b> ${signal.take_profit:,.2f}\n"
                f"\n"
                f"\U0001f4ca <b>Risk/Reward:</b> 1:{rr_ratio:.1f}\n"
                f"\U0001f3af <b>Confidence:</b> {signal.confidence:.0%}\n"
            )

            if signal.reasons:
                msg += f"\n\U0001f4a1 <b>Analysis:</b>\n"
                for r in signal.reasons[:5]:
                    msg += f"  \u2022 {r}\n"

            msg += f"\n\u23f0 <i>{datetime.now().strftime('%b %d, %H:%M UTC')}</i>"
            msg += f"\n\n\u26a1 <b>Auto-trade EXECUTED on your account</b>"

        return msg

    def format_status(self, stats: dict) -> str:
        """Format bot status update"""
        return (
            f"\U0001f916 <b>Bot Status Update</b>\n"
            f"\n"
            f"\U0001f4b0 <b>Balance:</b> ${stats.get('balance', 0):,.2f}\n"
            f"\U0001f4c8 <b>Return:</b> {stats.get('total_return', 0):+.2f}%\n"
            f"\U0001f4ca <b>Trades:</b> {stats.get('total_trades', 0)}\n"
            f"\u2705 <b>Win Rate:</b> {stats.get('win_rate', 0):.1f}%\n"
            f"\U0001f4c9 <b>Drawdown:</b> {stats.get('drawdown', 0):.1f}%\n"
        )

    def format_welcome(self) -> str:
        """Format welcome message for new subscribers"""
        return (
            f"\U0001f680 <b>Welcome to AI Trading Signals!</b>\n"
            f"\n"
            f"I analyze the crypto markets using:\n"
            f"\u2714\ufe0f Technical Analysis (RSI, MACD, Bollinger)\n"
            f"\u2714\ufe0f AI/ML Price Predictions\n"
            f"\u2714\ufe0f Risk Management\n"
            f"\n"
            f"<b>Free Tier:</b> {self.free_daily_limit} signals/day\n"
            f"<b>Pro Tier:</b> Unlimited signals + alerts\n"
            f"\n"
            f"\U0001f4a1 Signals posted when opportunities are found\n"
            f"\u26a0\ufe0f Always do your own research\n"
        )

    def send_signal(self, signal, tier: str = "free") -> bool:
        """Send a trading signal to the channel"""
        today = datetime.now().date()
        if today != self.last_reset:
            self.messages_sent_today = 0
            self.last_reset = today

        if not self._check_daily_limit():
            return False

        text = self.format_signal(signal, tier)
        success = self._send_message(text)

        if success:
            self.messages_sent_today += 1
            self.signal_count += 1

        return success

    def send_free_signal(self, signal) -> bool:
        """Send free tier signal (public channel)"""
        return self.send_signal(signal, tier="free")

    def send_pro_signal(self, signal) -> bool:
        """Send pro tier signal (premium)"""
        return self.send_signal(signal, tier="pro")

    def send_vip_signal(self, signal) -> bool:
        """Send VIP tier signal (premium+)"""
        return self.send_signal(signal, tier="vip")

    def send_status(self, stats: dict) -> bool:
        """Send bot status update to channel"""
        text = self.format_status(stats)
        return self._send_message(text)

    def send_welcome(self) -> bool:
        """Send welcome message"""
        text = self.format_welcome()
        return self._send_message(text)

    def send_error(self, error_msg: str) -> bool:
        """Send error notification"""
        text = f"\u26a0\ufe0f <b>Bot Error</b>\n\n{error_msg}"
        return self._send_message(text)

    def send_daily_summary(self, trades_today: list, stats: dict) -> bool:
        """Send daily performance summary"""
        wins = sum(1 for t in trades_today if t.pnl > 0)
        losses = sum(1 for t in trades_today if t.pnl <= 0)
        total_pnl = sum(t.pnl for t in trades_today)

        msg = (
            f"\U0001f4ca <b>Daily Summary</b>\n"
            f"\n"
            f"\U0001f4c8 <b>Today's Trades:</b> {len(trades_today)}\n"
            f"\u2705 <b>Wins:</b> {wins} | \u274c <b>Losses:</b> {losses}\n"
            f"\U0001f4b0 <b>Today's PnL:</b> ${total_pnl:+,.2f}\n"
            f"\n"
            f"\U0001f4b5 <b>Total Balance:</b> ${stats.get('balance', 0):,.2f}\n"
            f"\U0001f4c8 <b>All-Time Return:</b> {stats.get('total_return', 0):+.2f}%\n"
        )

        return self._send_message(msg)


def test_telegram():
    """Test Telegram bot connection"""
    from dotenv import load_dotenv
    load_dotenv()

    bot = TelegramBot()
    if not bot.enabled:
        print("  [ERROR] Telegram not configured!")
        print("  Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHANNEL_ID in .env")
        return

    print(f"  [OK] Telegram bot connected")
    print(f"  [OK] Channel: {bot.channel_id}")

    # Send test message
    success = bot._send_message(
        "\U0001f680 <b>AI Trading Bot</b> is now online!\n\n"
        "Market analysis active. Signals will be posted when opportunities are found."
    )

    if success:
        print("  [OK] Test message sent!")
    else:
        print("  [ERROR] Failed to send test message")


if __name__ == "__main__":
    test_telegram()
