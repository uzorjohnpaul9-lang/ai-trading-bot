"""
AI Trading Bot - Configuration
==============================
Central configuration for all bot settings.
"""
import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class ExchangeConfig:
    """Exchange connection settings"""
    name: str = os.getenv("EXCHANGE", "bybit")
    api_key: str = os.getenv("BYBIT_API_KEY", "")
    api_secret: str = os.getenv("BYBIT_API_SECRET", "")
    private_key_path: str = os.getenv("BYBIT_PRIVATE_KEY", "")
    testnet: bool = os.getenv("USE_TESTNET", "false").lower() == "true"


@dataclass
class TradingConfig:
    """Trading parameters"""
    pairs: List[str] = field(default_factory=lambda: [
        "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "ADA/USDT", "XRP/USDT"
    ])
    timeframe: str = "1h"
    check_interval: int = 300  # seconds between checks
    mode: str = os.getenv("MODE", "paper")  # paper or live


@dataclass
class RiskConfig:
    """Risk management settings"""
    max_risk_per_trade: float = 0.02  # 2% of capital
    max_daily_loss: float = 0.05  # 5% daily loss limit
    max_drawdown: float = 0.15  # 15% max drawdown
    max_open_positions: int = 3
    risk_reward_ratio: float = 2.0
    use_kelly: bool = True
    kelly_fraction: float = 0.25


@dataclass
class IndicatorConfig:
    """Technical indicator settings"""
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    ema_fast: int = 12
    ema_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0
    atr_period: int = 14
    adx_period: int = 14
    adx_threshold: float = 25.0


@dataclass
class MLConfig:
    """Machine learning settings"""
    enabled: bool = True
    lookback: int = 60
    train_split: float = 0.8
    min_accuracy: float = 0.55
    retrain_interval: int = 24  # hours


@dataclass
class TelegramConfig:
    """Telegram channel settings"""
    bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    channel_id: str = os.getenv("TELEGRAM_CHANNEL_ID", "")
    free_daily_limit: int = int(os.getenv("FREE_DAILY_LIMIT", "10"))
    enabled: bool = os.getenv("TELEGRAM_ENABLED", "true").lower() == "true"


@dataclass
class BotConfig:
    """Main bot configuration"""
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    indicators: IndicatorConfig = field(default_factory=IndicatorConfig)
    ml: MLConfig = field(default_factory=MLConfig)
    telegram: TelegramConfig = field(default_factory=TelegramConfig)
    initial_capital: float = float(os.getenv("INITIAL_CAPITAL", "10000"))
    log_trades: bool = True
    verbose: bool = True


# Global config instance
config = BotConfig()
