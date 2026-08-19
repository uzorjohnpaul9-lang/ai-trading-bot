"""
Market Data Fetcher
===================
Handles all data retrieval from Binance using ccxt.
"""
import ccxt
import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from config import config


class DataFetcher:
    """Fetch market data from Binance via ccxt"""

    def __init__(self):
        self.exchange = None
        self._connect()

    def _connect(self):
        """Connect to exchange via ccxt"""
        try:
            exchange_config = {
                "apiKey": config.exchange.api_key,
                "secret": config.exchange.api_secret,
                "enableRateLimit": True,
                "options": {
                    "defaultType": "spot"
                }
            }

            # Choose exchange
            exchange_name = config.exchange.name.lower()
            if exchange_name == "bybit":
                self.exchange = ccxt.bybit(exchange_config)
                if config.exchange.testnet:
                    self.exchange.set_sandbox_mode(True)
            else:
                # Binance with optional RSA key
                private_key_path = config.exchange.private_key_path
                if private_key_path and os.path.exists(private_key_path):
                    with open(private_key_path, "r") as f:
                        private_key = f.read()
                    exchange_config["secret"] = private_key
                    exchange_config["options"]["rsaKey"] = private_key

                self.exchange = ccxt.binance(exchange_config)
                if config.exchange.testnet:
                    self.exchange.set_sandbox_mode(True)

            # Try different endpoints if main one fails
            if config.exchange.testnet:
                self.exchange.set_sandbox_mode(True)
            else:
                # Try alternative endpoints for blocked regions
                try:
                    self.exchange.load_markets()
                except Exception:
                    # Try Binance.US or other mirrors
                    alternative_urls = [
                        "https://api1.binance.com",
                        "https://api2.binance.com",
                        "https://api3.binance.com",
                        "https://api4.binance.com",
                    ]
                    for url in alternative_urls:
                        try:
                            self.exchange.urls["api"]["public"] = url
                            self.exchange.urls["api"]["private"] = url
                            self.exchange.load_markets()
                            print(f"  [OK] Connected via {url}")
                            break
                        except Exception:
                            continue
                    else:
                        raise Exception("All endpoints failed")

            print(f"  [OK] Connected to Binance")
            print(f"  [OK] Loaded {len(self.exchange.markets)} markets")

            # Markets already loaded above

        except Exception as e:
            print(f"  [WARN] Could not connect to Binance: {e}")
            print("  [INFO] Using sample data mode")
            self.exchange = None

    def fetch_klines(self, symbol: str, timeframe: str = None, limit: int = 200) -> pd.DataFrame:
        """Fetch OHLCV candlestick data"""
        timeframe = timeframe or config.trading.timeframe

        if self.exchange:
            return self._fetch_from_exchange(symbol, timeframe, limit)
        else:
            return self._generate_sample_data(symbol, limit)

    def _fetch_from_exchange(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Fetch from Binance via ccxt"""
        try:
            # Fetch OHLCV data
            ohlcv = self.exchange.fetch_ohlcv(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit
            )

            if not ohlcv:
                return self._generate_sample_data(symbol, limit)

            df = pd.DataFrame(
                ohlcv,
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )

            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df.set_index("timestamp", inplace=True)

            return df

        except Exception as e:
            print(f"  [ERROR] Fetch failed for {symbol}: {e}")
            return self._generate_sample_data(symbol, limit)

    def get_current_price(self, symbol: str) -> float:
        """Get latest price from exchange"""
        if self.exchange:
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                return ticker["last"]
            except Exception as e:
                print(f"  [ERROR] Price fetch failed: {e}")

        # Fallback to sample data
        df = self.fetch_klines(symbol, limit=1)
        return df["close"].iloc[-1] if not df.empty else 0

    def get_ticker(self, symbol: str) -> dict:
        """Get full ticker data"""
        if self.exchange:
            try:
                ticker = self.exchange.fetch_ticker(symbol)
                return {
                    "symbol": symbol,
                    "last": ticker["last"],
                    "bid": ticker["bid"],
                    "ask": ticker["ask"],
                    "high": ticker["high"],
                    "low": ticker["low"],
                    "volume": ticker["baseVolume"],
                    "change": ticker["percentage"],
                    "timestamp": datetime.now()
                }
            except Exception as e:
                print(f"  [ERROR] Ticker fetch failed: {e}")

        return {}

    def get_order_book(self, symbol: str, limit: int = 20) -> dict:
        """Get order book depth"""
        if self.exchange:
            try:
                orderbook = self.exchange.fetch_order_book(symbol, limit)
                return {
                    "bids": orderbook["bids"][:limit],
                    "asks": orderbook["asks"][:limit],
                    "spread": orderbook["asks"][0][0] - orderbook["bids"][0][0]
                }
            except Exception as e:
                print(f"  [ERROR] Order book fetch failed: {e}")

        return {"bids": [], "asks": [], "spread": 0}

    def get_recent_trades(self, symbol: str, limit: int = 50) -> List[dict]:
        """Get recent trades"""
        if self.exchange:
            try:
                trades = self.exchange.fetch_trades(symbol, limit=limit)
                return [
                    {
                        "price": t["price"],
                        "amount": t["amount"],
                        "side": t["side"],
                        "timestamp": t["datetime"]
                    }
                    for t in trades
                ]
            except Exception as e:
                print(f"  [ERROR] Trades fetch failed: {e}")

        return []

    def get_balance(self) -> dict:
        """Get account balance"""
        if self.exchange:
            try:
                balance = self.exchange.fetch_balance()
                return {
                    asset: {
                        "free": float(info.get("free", 0)),
                        "used": float(info.get("used", 0)),
                        "total": float(info.get("total", 0))
                    }
                    for asset, info in balance.items()
                    if isinstance(info, dict) and float(info.get("total", 0)) > 0
                }
            except Exception as e:
                print(f"  [ERROR] Balance fetch failed: {e}")

        return {"USDT": {"free": config.initial_capital, "used": 0, "total": config.initial_capital}}

    def place_order(self, symbol: str, side: str, amount: float,
                    price: float = None, order_type: str = "market") -> dict:
        """Place an order on the exchange"""
        if not self.exchange:
            return {"error": "Not connected to exchange"}

        if config.trading.mode == "paper":
            return {"error": "Cannot place orders in paper mode"}

        try:
            if order_type == "market":
                if side == "buy":
                    order = self.exchange.create_market_buy_order(symbol, amount)
                else:
                    order = self.exchange.create_market_sell_order(symbol, amount)
            else:
                if side == "buy":
                    order = self.exchange.create_limit_buy_order(symbol, amount, price)
                else:
                    order = self.exchange.create_limit_sell_order(symbol, amount, price)

            return {
                "id": order["id"],
                "status": order["status"],
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": order.get("price"),
                "average": order.get("average"),
                "filled": order.get("filled"),
                "remaining": order.get("remaining"),
                "fee": order.get("fee")
            }

        except Exception as e:
            return {"error": str(e)}

    def get_all_tickers(self) -> Dict[str, dict]:
        """Get all tickers at once"""
        if self.exchange:
            try:
                tickers = self.exchange.fetch_tickers()
                return {
                    symbol: {
                        "last": t.get("last", 0),
                        "change": t.get("percentage", 0),
                        "volume": t.get("baseVolume", 0)
                    }
                    for symbol, t in tickers.items()
                    if "/USDT" in symbol
                }
            except Exception as e:
                print(f"  [ERROR] Tickers fetch failed: {e}")

        return {}

    def _generate_sample_data(self, symbol: str, limit: int) -> pd.DataFrame:
        """Generate realistic sample data for testing"""
        base_prices = {
            "BTC/USDT": 65000, "ETH/USDT": 3500, "SOL/USDT": 150,
            "BNB/USDT": 600, "ADA/USDT": 0.6, "XRP/USDT": 0.55,
            "BTCUSDT": 65000, "ETHUSDT": 3500, "SOLUSDT": 150,
            "BNBUSDT": 600, "ADAUSDT": 0.6, "XRPUSDT": 0.55
        }
        base_price = base_prices.get(symbol, 100)

        np.random.seed((int(datetime.now().timestamp()) + hash(symbol)) % (2**32 - 1))

        returns = np.random.normal(0.0001, 0.015, limit)
        prices = base_price * np.exp(np.cumsum(returns))

        dates = pd.date_range(end=datetime.now(), periods=limit, freq="1h")
        df = pd.DataFrame(index=dates)
        df["close"] = prices
        df["high"] = prices * (1 + np.random.uniform(0, 0.015, limit))
        df["low"] = prices * (1 - np.random.uniform(0, 0.015, limit))
        df["open"] = prices * (1 + np.random.uniform(-0.008, 0.008, limit))
        df["volume"] = np.random.exponential(1000, limit) * base_price / 100

        return df
