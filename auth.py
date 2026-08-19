"""
Authentication System
=====================
JWT-based authentication for API and dashboard.
"""
import os
import secrets
from datetime import datetime, timedelta
from typing import Optional
import hashlib
import json
import base64

SECRET_KEY = os.getenv("AUTH_SECRET_KEY", secrets.token_hex(32))
TOKEN_EXPIRY_HOURS = 24


class AuthToken:
    """Simple JWT-like token implementation"""

    @staticmethod
    def create_token(user_id: int, username: str, tier: str = "free") -> str:
        """Create authentication token"""
        payload = {
            "user_id": user_id,
            "username": username,
            "tier": tier,
            "exp": (datetime.now() + timedelta(hours=TOKEN_EXPIRY_HOURS)).isoformat(),
            "iat": datetime.now().isoformat()
        }

        # Encode payload
        payload_b64 = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode()

        # Create signature
        signature = hashlib.sha256(
            f"{payload_b64}.{SECRET_KEY}".encode()
        ).hexdigest()

        return f"{payload_b64}.{signature}"

    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """Verify and decode token"""
        try:
            parts = token.split(".")
            if len(parts) != 2:
                return None

            payload_b64, signature = parts

            # Verify signature
            expected_sig = hashlib.sha256(
                f"{payload_b64}.{SECRET_KEY}".encode()
            ).hexdigest()

            if signature != expected_sig:
                return None

            # Decode payload
            payload = json.loads(base64.urlsafe_b64decode(payload_b64))

            # Check expiry
            exp = datetime.fromisoformat(payload["exp"])
            if datetime.now() > exp:
                return None

            return payload

        except Exception:
            return None


class AuthMiddleware:
    """Authentication middleware for API"""

    def __init__(self):
        self.active_tokens = {}  # In production, use Redis

    def login(self, username: str, password: str) -> dict:
        """Login user and return token"""
        from database import UserModel

        user = UserModel.authenticate(username, password)
        if not user:
            return {"error": "Invalid credentials"}

        token = AuthToken.create_token(
            user["id"],
            user["username"],
            user.get("subscription_tier", "free")
        )

        self.active_tokens[token] = user["id"]

        return {
            "token": token,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "tier": user.get("subscription_tier", "free")
            }
        }

    def register(self, username: str, email: str, password: str) -> dict:
        """Register new user"""
        from database import UserModel

        result = UserModel.create_user(username, email, password)
        if "error" in result:
            return result

        # Auto-login after registration
        return self.login(username, password)

    def verify_request(self, token: str) -> Optional[dict]:
        """Verify API request token"""
        payload = AuthToken.verify_token(token)
        if not payload:
            return None

        if token not in self.active_tokens:
            return None

        return payload


# Global auth instance
auth = AuthMiddleware()
