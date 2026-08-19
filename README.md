# AI Trading Bot

Production-ready cryptocurrency trading bot with web dashboard, user authentication, and SaaS-ready API.

## Features

- **Technical Analysis**: RSI, MACD, Bollinger Bands, Supertrend, ADX, Stochastic
- **ML Predictions**: Random Forest + Gradient Boosting ensemble
- **Risk Management**: Position sizing, stop-loss, take-profit, drawdown limits
- **Paper Trading**: Simulate trades without real money
- **Backtesting**: Test strategies on historical data
- **Web Dashboard**: Streamlit-based UI for managing trades
- **User Authentication**: JWT-based auth with database
- **REST API**: FastAPI server for monetization
- **Subscription Tiers**: Free, Pro, VIP plans

## Quick Start

```bash
# Run setup
python setup.py

# Or manually install
pip install -r requirements.txt
copy .env.example .env
```

## Run Options

```bash
# Interactive menu
python run.py

# Or run directly:
python bot.py                    # Trading bot (CLI)
python bot.py --backtest         # Run backtest
python dashboard.py              # Web dashboard (port 8501)
python api.py                    # API server (port 8000)
```

## Project Structure

```
ai-trading-bot/
  bot.py              - Main trading bot (CLI)
  dashboard.py        - Web dashboard (Streamlit)
  api.py              - REST API (FastAPI)
  config.py           - Configuration
  database.py         - SQLite database
  auth.py             - Authentication system
  data_fetcher.py     - Market data retrieval
  indicators.py       - Technical indicators
  ml_predictor.py     - ML predictions
  signals.py          - Signal generation
  risk_manager.py     - Risk management
  paper_trader.py     - Paper trading engine
  backtester.py       - Backtesting engine
  setup.py            - Setup script
  run.py              - Quick start menu
  requirements.txt    - Dependencies
  .env.example        - Environment template
```

## API Endpoints

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/auth/register` | POST | No | Create account |
| `/auth/login` | POST | No | Login |
| `/auth/me` | GET | Yes | Get user info |
| `/api/analyze` | POST | Yes | Analyze symbol |
| `/api/signals` | GET | Yes | Get all signals |
| `/api/trade` | POST | Yes | Record trade |
| `/api/trades` | GET | Yes | Trade history |
| `/api/stats` | GET | Yes | Trading stats |
| `/api/backtest` | POST | No | Run backtest |
| `/health` | GET | No | Health check |

## Monetization

### Pricing Tiers

| Tier | Price | Features |
|------|-------|----------|
| Free | $0 | 3 trades/day, paper trading, basic indicators |
| Pro | $29/mo | Unlimited, ML predictions, live trading |
| VIP | $99/mo | Priority signals, custom strategies, API access |

### How to Monetize

1. Deploy API server
2. Add Stripe integration for payments
3. Gate endpoints by subscription tier
4. Sell API access to other traders
5. Offer copy-trading as a service

## Configuration

Edit `.env`:

```
MODE=paper
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
INITIAL_CAPITAL=10000
AUTH_SECRET_KEY=your_secret_key
```

## License

MIT
