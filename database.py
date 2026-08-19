"""
Database Models
===============
SQLite database for users, subscriptions, and trading data.
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass
import hashlib
import secrets

DB_FILE = "trading_bot.db"


def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize database tables"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            api_key TEXT,
            api_secret TEXT,
            subscription_tier TEXT DEFAULT 'free',
            subscription_expires TIMESTAMP,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS bot_instances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            pairs TEXT DEFAULT 'BTCUSDT,ETHUSDT',
            timeframe TEXT DEFAULT '1h',
            mode TEXT DEFAULT 'paper',
            is_running BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            bot_instance_id INTEGER,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            quantity REAL NOT NULL,
            stop_loss REAL,
            take_profit REAL,
            pnl REAL,
            pnl_pct REAL,
            status TEXT DEFAULT 'open',
            opened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            stop_loss REAL,
            take_profit REAL,
            confidence REAL,
            reasons TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            tier TEXT NOT NULL,
            amount REAL NOT NULL,
            start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            end_date TIMESTAMP,
            payment_id TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    conn.commit()
    conn.close()


class UserModel:
    """User database operations"""

    @staticmethod
    def hash_password(password: str, salt: str = None) -> tuple:
        """Hash password with salt"""
        if salt is None:
            salt = secrets.token_hex(32)
        password_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            salt.encode(),
            100000
        )
        return password_hash.hex(), salt

    @staticmethod
    def verify_password(password: str, password_hash: str, salt: str) -> bool:
        """Verify password against hash"""
        computed_hash, _ = UserModel.hash_password(password, salt)
        return computed_hash == password_hash

    @staticmethod
    def create_user(username: str, email: str, password: str) -> dict:
        """Create new user"""
        conn = get_db()
        cursor = conn.cursor()

        # Check if user exists
        cursor.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email)
        )
        if cursor.fetchone():
            conn.close()
            return {"error": "Username or email already exists"}

        # Hash password
        password_hash, salt = UserModel.hash_password(password)

        # Generate API key
        api_key = f"tb_{secrets.token_hex(16)}"

        cursor.execute(
            """INSERT INTO users (username, email, password_hash, salt, api_key)
               VALUES (?, ?, ?, ?, ?)""",
            (username, email, password_hash, salt, api_key)
        )

        user_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return {
            "id": user_id,
            "username": username,
            "email": email,
            "api_key": api_key
        }

    @staticmethod
    def authenticate(username: str, password: str) -> Optional[dict]:
        """Authenticate user"""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE username = ? OR email = ?",
            (username, username)
        )
        user = cursor.fetchone()

        if not user:
            conn.close()
            return None

        if not UserModel.verify_password(password, user["password_hash"], user["salt"]):
            conn.close()
            return None

        # Update last login
        cursor.execute(
            "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?",
            (user["id"],)
        )
        conn.commit()
        conn.close()

        return {
            "id": user["id"],
            "username": user["username"],
            "email": user["email"],
            "api_key": user["api_key"],
            "subscription_tier": user["subscription_tier"]
        }

    @staticmethod
    def get_user(user_id: int) -> Optional[dict]:
        """Get user by ID"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        user = cursor.fetchone()
        conn.close()

        if user:
            return dict(user)
        return None

    @staticmethod
    def update_api_keys(user_id: int, api_key: str, api_secret: str):
        """Update user's exchange API keys"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET api_key = ?, api_secret = ? WHERE id = ?",
            (api_key, api_secret, user_id)
        )
        conn.commit()
        conn.close()

    @staticmethod
    def update_subscription(user_id: int, tier: str, expires: datetime = None):
        """Update user subscription"""
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET subscription_tier = ?, subscription_expires = ? WHERE id = ?",
            (tier, expires, user_id)
        )
        conn.commit()
        conn.close()


class TradeModel:
    """Trade database operations"""

    @staticmethod
    def record_trade(user_id: int, symbol: str, direction: str,
                     entry_price: float, quantity: float,
                     stop_loss: float, take_profit: float,
                     bot_instance_id: int = None) -> int:
        """Record a new trade"""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO trades
               (user_id, bot_instance_id, symbol, direction, entry_price,
                quantity, stop_loss, take_profit, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')""",
            (user_id, bot_instance_id, symbol, direction,
             entry_price, quantity, stop_loss, take_profit)
        )

        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return trade_id

    @staticmethod
    def close_trade(trade_id: int, exit_price: float, pnl: float, pnl_pct: float):
        """Close a trade"""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """UPDATE trades
               SET exit_price = ?, pnl = ?, pnl_pct = ?, status = 'closed',
                   closed_at = CURRENT_TIMESTAMP
               WHERE id = ?""",
            (exit_price, pnl, pnl_pct, trade_id)
        )

        conn.commit()
        conn.close()

    @staticmethod
    def get_user_trades(user_id: int, limit: int = 50) -> List[dict]:
        """Get user's trade history"""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT * FROM trades
               WHERE user_id = ?
               ORDER BY opened_at DESC
               LIMIT ?""",
            (user_id, limit)
        )

        trades = [dict(row) for row in cursor.fetchall()]
        conn.close()

        return trades

    @staticmethod
    def get_user_stats(user_id: int) -> dict:
        """Get user's trading statistics"""
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute(
            """SELECT
                COUNT(*) as total_trades,
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing_trades,
                SUM(pnl) as total_pnl,
                AVG(pnl) as avg_pnl,
                MAX(pnl) as best_trade,
                MIN(pnl) as worst_trade
               FROM trades
               WHERE user_id = ? AND status = 'closed'""",
            (user_id,)
        )

        stats = dict(cursor.fetchone())
        stats["win_rate"] = (
            (stats["winning_trades"] / stats["total_trades"] * 100)
            if stats["total_trades"] > 0 else 0
        )

        conn.close()
        return stats
