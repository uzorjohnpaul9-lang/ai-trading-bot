"""
AI Trading Bot - Main Entry Point
==================================
The core bot that ties everything together.
"""
import time
import os
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout

from config import config
from data_fetcher import DataFetcher
from signals import SignalGenerator
from risk_manager import RiskManager
from paper_trader import PaperTrader
from backtester import Backtester
from telegram_bot import TelegramBot


console = Console()


class TradingBot:
    """Main AI Trading Bot"""

    def __init__(self):
        console.print(Panel(
            "[bold cyan]AI Trading Bot[/bold cyan]\n"
            "Version 1.0 | Binance Integration",
            title="Initializing"
        ))

        self.fetcher = DataFetcher()
        self.risk_manager = RiskManager(config.initial_capital)
        self.paper_trader = PaperTrader(config.initial_capital)
        self.signal_generator = SignalGenerator(self.risk_manager)
        self.backtester = Backtester(config.initial_capital)
        self.telegram = TelegramBot()

        self.stats = {
            "signals_found": 0,
            "trades_taken": 0,
            "signals_sent": 0,
            "start_time": datetime.now()
        }

        if self.telegram.enabled:
            console.print("[green]Telegram bot connected![/green]")
            self.telegram.send_welcome()
        else:
            console.print("[yellow]Telegram not configured - signals won't be posted[/yellow]")

        console.print("[green]Bot initialized successfully![/green]\n")

    def analyze_symbol(self, symbol: str):
        """Analyze a single trading pair"""
        df = self.fetcher.fetch_klines(symbol, limit=200)
        if df.empty:
            return None

        signal = self.signal_generator.analyze(df, symbol)
        if not signal:
            return None

        self.stats["signals_found"] += 1

        # Calculate position size
        quantity = self.risk_manager.calculate_position_size(
            signal.entry_price, signal.stop_loss
        )

        if quantity <= 0:
            return None

        return {
            "signal": signal,
            "quantity": quantity
        }

    def execute_trade(self, analysis: dict):
        """Execute a paper trade and post signal to Telegram"""
        signal = analysis["signal"]

        # Check risk limits
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
            console.print(f"[yellow]  Skipped: {reason}[/yellow]")
            return False

        # Open paper position
        position = self.paper_trader.open_position(
            symbol=signal.symbol,
            direction=signal.direction,
            price=signal.entry_price,
            quantity=analysis["quantity"],
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit
        )

        if position:
            self.risk_manager.record_trade_open()
            self.stats["trades_taken"] += 1

            # Send signal to Telegram
            if self.telegram.enabled:
                sent = self.telegram.send_signal(signal)
                if sent:
                    self.stats["signals_sent"] += 1
                    console.print("[cyan]  Signal posted to Telegram![/cyan]")

            # Display trade
            direction_color = "green" if signal.direction == "long" else "red"
            console.print(Panel(
                f"[bold {direction_color}]{signal.direction.upper()}[/bold {direction_color}]\n\n"
                f"Entry:    ${signal.entry_price:,.2f}\n"
                f"Stop:     ${signal.stop_loss:,.2f}\n"
                f"Target:   ${signal.take_profit:,.2f}\n"
                f"Quantity: {analysis['quantity']:.6f}\n"
                f"Confidence: {signal.confidence:.1%}\n\n"
                f"[dim]Reasons:[/dim]\n" +
                "\n".join(f"  - {r}" for r in signal.reasons),
                title=f"TRADE: {signal.symbol}"
            ))
            return True

        return False

    def check_positions(self):
        """Check open positions for exits"""
        if not self.paper_trader.positions:
            return

        current_prices = {}
        for symbol in self.paper_trader.positions:
            price = self.fetcher.get_current_price(symbol)
            if price > 0:
                current_prices[symbol] = price

        closed = self.paper_trader.check_positions(current_prices)
        for trade in closed:
            self.risk_manager.record_trade_close(trade.pnl)
            emoji = "+" if trade.pnl >= 0 else ""
            console.print(
                f"[{'green' if trade.pnl >= 0 else 'red'}]"
                f"  Closed {trade.symbol}: {emoji}${trade.pnl:,.2f} ({trade.pnl_pct:+.1f}%)"
                f"[/]"
            )

    def display_status(self, send_to_telegram: bool = False):
        """Display current bot status"""
        stats = self.paper_trader.get_stats()
        risk_stats = self.risk_manager.get_stats()

        table = Table(title="Bot Status", show_header=True)
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Mode", config.trading.mode.upper())
        table.add_row("Balance (Cash)", f"${stats['balance']:,.2f}")
        table.add_row("Open Positions", f"${stats['open_position_value']:,.2f}")
        table.add_row("Total Equity", f"${stats['total_equity']:,.2f}")
        table.add_row("Return", f"{stats['total_return']:+.2f}%")
        table.add_row("Total Trades", str(stats['total_trades']))
        table.add_row("Win Rate", f"{stats['win_rate']:.1f}%")
        table.add_row("Open Positions", str(stats['open_positions']))
        table.add_row("Drawdown", f"{risk_stats['drawdown']:.1f}%")
        table.add_row("Signals Found", str(self.stats['signals_found']))
        table.add_row("Signals Sent", str(self.stats['signals_sent']))

        console.print(table)

        # Send status to Telegram every 10 cycles
        if send_to_telegram and self.telegram.enabled:
            risk_stats["balance"] = stats["total_equity"]
            risk_stats["total_return"] = stats["total_return"]
            self.telegram.send_status(risk_stats)

    def run_backtest(self, symbol: str = "BTCUSDT"):
        """Run backtest on historical data"""
        console.print(f"\n[bold]Running backtest for {symbol}...[/bold]")

        df = self.fetcher.fetch_klines(symbol, limit=1000)
        results = self.backtester.run(df)

        table = Table(title=f"Backtest Results: {symbol}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Total Return", f"{results['total_return']:+.2f}%")
        table.add_row("Total Trades", str(results['total_trades']))
        table.add_row("Win Rate", f"{results['win_rate']:.1f}%")
        table.add_row("Avg Win", f"${results['avg_win']:,.2f}")
        table.add_row("Avg Loss", f"${results['avg_loss']:,.2f}")
        table.add_row("Max Drawdown", f"{results['max_drawdown']:.1f}%")
        table.add_row("Sharpe Ratio", f"{results['sharpe_ratio']:.2f}")
        table.add_row("Final Capital", f"${results['final_capital']:,.2f}")

        console.print(table)
        return results

    def run(self):
        """Main bot loop"""
        console.print(Panel(
            f"[bold green]Bot Started![/bold green]\n\n"
            f"Mode:      {config.trading.mode.upper()}\n"
            f"Pairs:     {', '.join(config.trading.pairs)}\n"
            f"Timeframe: {config.trading.timeframe}\n"
            f"Capital:   ${config.initial_capital:,.2f}\n"
            f"Telegram:  {'Connected' if self.telegram.enabled else 'Disabled'}\n\n"
            f"Press Ctrl+C to stop",
            title="AI Trading Bot"
        ))

        last_daily_reset = datetime.now().date()
        cycle_count = 0

        while True:
            try:
                # Reset daily stats
                today = datetime.now().date()
                if today != last_daily_reset:
                    self.risk_manager.reset_daily()
                    last_daily_reset = today
                    cycle_count = 0

                cycle_count += 1

                # Check existing positions
                self.check_positions()

                # Analyze each pair
                for symbol in config.trading.pairs:
                    console.print(f"\n[dim]Analyzing {symbol}...[/dim]")

                    analysis = self.analyze_symbol(symbol)
                    if analysis:
                        self.execute_trade(analysis)

                # Show status (send to Telegram every 10 cycles)
                self.display_status(send_to_telegram=(cycle_count % 10 == 0))

                # Wait
                console.print(f"\n[dim]Next check in {config.trading.check_interval}s...[/dim]")
                time.sleep(config.trading.check_interval)

            except KeyboardInterrupt:
                console.print("\n[yellow]Bot stopped by user[/yellow]")
                self.display_status()
                break
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                if self.telegram.enabled:
                    self.telegram.send_error(str(e))
                time.sleep(30)


def main():
    """Entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="AI Trading Bot")
    parser.add_argument("--backtest", action="store_true", help="Run backtest instead of live trading")
    parser.add_argument("--symbol", default="BTCUSDT", help="Symbol for backtest")
    args = parser.parse_args()

    bot = TradingBot()

    if args.backtest:
        bot.run_backtest(args.symbol)
    else:
        bot.run()


if __name__ == "__main__":
    main()
