"""
API Server for Monetization
===========================
FastAPI server with user auth and trading signals.
"""
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

from config import config
from data_fetcher import DataFetcher
from signals import SignalGenerator
from risk_manager import RiskManager
from database import init_db, UserModel, TradeModel
from auth import auth


app = FastAPI(
    title="AI Trading Bot API",
    description="Trading signals and analysis API with user management",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer(auto_error=False)

# Initialize
init_db()
fetcher = DataFetcher()
risk_manager = RiskManager(config.initial_capital)
signal_generator = SignalGenerator(risk_manager)


# --- Request/Response Models ---

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class AuthResponse(BaseModel):
    token: str
    user: dict

class SignalResponse(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float
    reasons: List[str]

class AnalysisRequest(BaseModel):
    symbol: str
    timeframe: str = "1h"

class TradeRequest(BaseModel):
    symbol: str
    direction: str
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float


# --- Auth Dependency ---

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get current authenticated user"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    payload = auth.verify_request(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = UserModel.get_user(payload["user_id"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user


# --- Auth Endpoints ---

@app.post("/auth/register", response_model=AuthResponse)
def register(request: RegisterRequest):
    """Register new user"""
    result = auth.register(request.username, request.email, request.password)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.post("/auth/login", response_model=AuthResponse)
def login(request: LoginRequest):
    """Login user"""
    result = auth.login(request.username, request.password)
    if "error" in result:
        raise HTTPException(status_code=401, detail=result["error"])
    return result


@app.get("/auth/me")
def get_me(user=Depends(get_current_user)):
    """Get current user info"""
    return {
        "id": user["id"],
        "username": user["username"],
        "email": user["email"],
        "tier": user.get("subscription_tier", "free")
    }


# --- Public Endpoints ---

@app.get("/")
def root():
    return {
        "name": "AI Trading Bot API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "auth": {
                "register": "POST /auth/register",
                "login": "POST /auth/login",
                "me": "GET /auth/me"
            },
            "trading": {
                "analyze": "POST /api/analyze (auth required)",
                "signals": "GET /api/signals (auth required)",
                "trade": "POST /api/trade (auth required)",
                "trades": "GET /api/trades (auth required)"
            },
            "public": {
                "health": "GET /health",
                "backtest": "POST /api/backtest"
            }
        }
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


# --- Protected Trading Endpoints ---

@app.post("/api/analyze", response_model=SignalResponse)
def analyze_symbol(request: AnalysisRequest, user=Depends(get_current_user)):
    """Analyze a trading pair (requires auth)"""
    df = fetcher.fetch_klines(request.symbol, request.timeframe)
    if df.empty:
        raise HTTPException(status_code=400, detail="Could not fetch data")

    signal = signal_generator.analyze(df, request.symbol)
    if not signal:
        raise HTTPException(status_code=404, detail="No signal found")

    return SignalResponse(
        symbol=signal.symbol,
        direction=signal.direction,
        entry_price=signal.entry_price,
        stop_loss=signal.stop_loss,
        take_profit=signal.take_profit,
        confidence=signal.confidence,
        reasons=signal.reasons
    )


@app.get("/api/signals")
def get_signals(user=Depends(get_current_user)):
    """Get signals for all pairs (requires auth)"""
    signals = []

    for symbol in config.trading.pairs:
        df = fetcher.fetch_klines(symbol)
        if not df.empty:
            signal = signal_generator.analyze(df, symbol)
            if signal:
                signals.append({
                    "symbol": signal.symbol,
                    "direction": signal.direction,
                    "entry_price": signal.entry_price,
                    "stop_loss": signal.stop_loss,
                    "take_profit": signal.take_profit,
                    "confidence": signal.confidence
                })

    return {"signals": signals, "count": len(signals)}


@app.post("/api/trade")
def record_trade(request: TradeRequest, user=Depends(get_current_user)):
    """Record a trade (requires auth)"""
    trade_id = TradeModel.record_trade(
        user_id=user["id"],
        symbol=request.symbol,
        direction=request.direction,
        entry_price=request.entry_price,
        quantity=request.quantity,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit
    )

    return {"trade_id": trade_id, "status": "recorded"}


@app.get("/api/trades")
def get_trades(user=Depends(get_current_user), limit: int = 50):
    """Get user's trade history (requires auth)"""
    trades = TradeModel.get_user_trades(user["id"], limit)
    return {"trades": trades, "count": len(trades)}


@app.get("/api/stats")
def get_stats(user=Depends(get_current_user)):
    """Get user's trading stats (requires auth)"""
    stats = TradeModel.get_user_stats(user["id"])
    return stats


@app.post("/api/backtest")
def run_backtest(symbol: str = "BTCUSDT", timeframe: str = "1h"):
    """Run backtest (public)"""
    bt = Backtester()
    df = fetcher.fetch_klines(symbol, timeframe, limit=1000)
    results = bt.run(df)

    return {
        "symbol": symbol,
        "total_return": results["total_return"],
        "total_trades": results["total_trades"],
        "win_rate": results["win_rate"],
        "max_drawdown": results["max_drawdown"],
        "sharpe_ratio": results["sharpe_ratio"]
    }


if __name__ == "__main__":
    from backtester import Backtester
    uvicorn.run(app, host="0.0.0.0", port=8000)
