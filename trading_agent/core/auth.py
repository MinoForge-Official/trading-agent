"""User Authentication & Account Management Module.

Provides robust user registration with duplicate-email prevention,
real-time password strength validation, PBKDF2-HMAC-SHA256 password hashing,
and persistent user profile storage.
"""

from __future__ import annotations

import datetime
import hashlib
import hmac
import json
import os
import re
import secrets
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def check_password_strength(password: str) -> Dict[str, Any]:
    """Calculate password strength score, rating, and feedback checklist.

    Returns:
        dict with keys: score (0-100), level ('weak', 'medium', 'strong', 'pro'),
        label, and checks (dict of individual criteria met).
    """
    if not password:
        return {
            "score": 0,
            "level": "weak",
            "label": "Empty Password",
            "checks": {
                "length_min": False,
                "length_good": False,
                "uppercase": False,
                "lowercase": False,
                "digit": False,
                "special": False,
            },
            "suggestions": ["Password cannot be empty."],
        }

    checks = {
        "length_min": len(password) >= 8,
        "length_good": len(password) >= 12,
        "uppercase": bool(re.search(r"[A-Z]", password)),
        "lowercase": bool(re.search(r"[a-z]", password)),
        "digit": bool(re.search(r"[0-9]", password)),
        "special": bool(re.search(r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]]", password)),
    }

    score = 0
    suggestions = []

    if checks["length_min"]:
        score += 25
    else:
        suggestions.append("Use at least 8 characters.")

    if checks["length_good"]:
        score += 15

    if checks["uppercase"]:
        score += 15
    else:
        suggestions.append("Include uppercase letters (A-Z).")

    if checks["lowercase"]:
        score += 15
    else:
        suggestions.append("Include lowercase letters (a-z).")

    if checks["digit"]:
        score += 15
    else:
        suggestions.append("Include at least one number (0-9).")

    if checks["special"]:
        score += 15
    else:
        suggestions.append("Include at least one special character (!@#$...).")

    # Determine level and label
    if score < 40:
        level = "weak"
        label = "Weak Password"
    elif score < 70:
        level = "medium"
        label = "Moderate Password"
    elif score < 90:
        level = "strong"
        label = "Strong Password"
    else:
        level = "pro"
        label = "Maximum Security"

    return {
        "score": min(100, score),
        "level": level,
        "label": label,
        "checks": checks,
        "suggestions": suggestions,
    }


class AuthManager:
    """Manages persistent user accounts, authentication, and profile settings."""

    def __init__(self, storage_file: str = "data/users.json") -> None:
        self.storage_file = Path(storage_file)
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)
        self.users: Dict[str, Dict[str, Any]] = self._load_users()

    def _load_users(self) -> Dict[str, Dict[str, Any]]:
        """Load user accounts from disk."""
        if not self.storage_file.exists():
            return {}
        try:
            with open(self.storage_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_users(self) -> None:
        """Persist user accounts to disk."""
        with open(self.storage_file, "w", encoding="utf-8") as f:
            json.dump(self.users, f, indent=2)

    def _hash_password(self, password: str, salt: Optional[str] = None) -> Tuple[str, str]:
        """Hash a password using PBKDF2-HMAC-SHA256 with 100,000 rounds."""
        if salt is None:
            salt = secrets.token_hex(16)
        pwd_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations=100000,
        ).hex()
        return pwd_hash, salt

    def email_exists(self, email: str) -> bool:
        """Check if an email is already registered."""
        email_clean = email.strip().lower()
        return email_clean in self.users

    def register(
        self,
        name: str,
        email: str,
        password: str,
        experience_level: str = "Intermediate",
        trading_website: str = "binance",
        traded_assets: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Register a new user account.

        Raises:
            ValueError: If email is invalid, duplicate, or password is too weak.
        """
        email_clean = email.strip().lower()
        name_clean = name.strip()

        # Validation checks
        if not name_clean:
            raise ValueError("Full name is required.")

        if not email_clean or not re.match(r"^[^@]+@[^@]+\.[^@]+$", email_clean):
            raise ValueError("Please provide a valid email address.")

        if self.email_exists(email_clean):
            raise ValueError(f"An account with email '{email_clean}' already exists. Please sign in.")

        strength = check_password_strength(password)
        if strength["score"] < 40 or len(password) < 6:
            raise ValueError(
                f"Password is too weak. {', '.join(strength['suggestions'])}"
            )

        pwd_hash, salt = self._hash_password(password)
        user_id = f"usr_{secrets.token_hex(6)}"
        now_str = datetime.datetime.now(datetime.timezone.utc).strftime("%B %d, %Y")

        user_data = {
            "user_id": user_id,
            "name": name_clean,
            "email": email_clean,
            "password_hash": pwd_hash,
            "salt": salt,
            "created_at": now_str,
            "experience_level": experience_level,
            "trading_mode": "copilot",  # 'autonomous' or 'copilot'
            "trading_website": trading_website,
            "traded_assets": traded_assets or ["BTC/USDT", "XAU/USD"],
            "theme": "cyberpunk",  # cyberpunk, midnight, light, emerald
            "safety_barriers": {
                "max_risk_per_trade_pct": 1.0,
                "stop_loss_pct": 2.0,
                "take_profit_pct": 4.0,
                "max_drawdown_pct": 15.0,
                "max_open_positions": 3,
                "require_manual_confirmation": False,
            },
            "exchange_credentials": {
                "exchange_id": trading_website,
                "testnet": True,
                "api_key": "",
                "api_secret": "",
            },
        }

        self.users[email_clean] = user_data
        self._save_users()

        return self._sanitize_user(user_data)

    def authenticate(self, email: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify user credentials and return sanitized user profile if valid."""
        email_clean = email.strip().lower()
        if email_clean not in self.users:
            return None

        user = self.users[email_clean]
        expected_hash, _ = self._hash_password(password, salt=user["salt"])

        if hmac.compare_digest(expected_hash, user["password_hash"]):
            return self._sanitize_user(user)
        return None

    def get_user(self, email: str) -> Optional[Dict[str, Any]]:
        """Retrieve sanitized user data by email."""
        email_clean = email.strip().lower()
        user = self.users.get(email_clean)
        return self._sanitize_user(user) if user else None

    def update_profile(self, email: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update allowed profile attributes."""
        email_clean = email.strip().lower()
        if email_clean not in self.users:
            raise ValueError("User not found.")

        user = self.users[email_clean]
        allowed_keys = {
            "name",
            "experience_level",
            "trading_mode",
            "trading_website",
            "traded_assets",
            "theme",
            "safety_barriers",
            "exchange_credentials",
        }

        for k, v in updates.items():
            if k in allowed_keys:
                if isinstance(v, dict) and isinstance(user.get(k), dict):
                    user[k].update(v)
                else:
                    user[k] = v

        self._save_users()
        return self._sanitize_user(user)

    def change_password(self, email: str, old_password: str, new_password: str) -> bool:
        """Update account password with strength validation."""
        email_clean = email.strip().lower()
        if email_clean not in self.users:
            raise ValueError("User not found.")

        user = self.users[email_clean]
        expected_hash, _ = self._hash_password(old_password, salt=user["salt"])
        if not hmac.compare_digest(expected_hash, user["password_hash"]):
            raise ValueError("Incorrect current password.")

        strength = check_password_strength(new_password)
        if strength["score"] < 40 or len(new_password) < 6:
            raise ValueError(
                f"New password is too weak. {', '.join(strength['suggestions'])}"
            )

        new_hash, new_salt = self._hash_password(new_password)
        user["password_hash"] = new_hash
        user["salt"] = new_salt
        self._save_users()
        return True

    def _sanitize_user(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Remove sensitive hashes and secret keys before sending to clients."""
        copy = dict(user)
        copy.pop("password_hash", None)
        copy.pop("salt", None)
        if "exchange_credentials" in copy and copy["exchange_credentials"].get("api_secret"):
            secret = copy["exchange_credentials"]["api_secret"]
            copy["exchange_credentials"] = dict(copy["exchange_credentials"])
            copy["exchange_credentials"]["api_secret_masked"] = (
                secret[:4] + "..." + secret[-4:] if len(secret) > 8 else "***"
            )
        return copy
