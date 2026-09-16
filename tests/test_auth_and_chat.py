"""Tests for AuthManager, Password Strength, and AI Chat Engine."""

import pytest
from fastapi.testclient import TestClient
from trading_agent.core.auth import AuthManager, check_password_strength
from trading_agent.ai.chat_engine import TradingChatEngine
from trading_agent.web.app import app


def test_password_strength():
    """Verify password strength score and criteria evaluation."""
    empty = check_password_strength("")
    assert empty["level"] == "weak"

    weak = check_password_strength("abc")
    assert weak["level"] == "weak"
    assert weak["score"] < 40

    strong = check_password_strength("Tr@derPro2026!#$")
    assert strong["level"] in ("strong", "pro")
    assert strong["checks"]["length_min"] is True
    assert strong["checks"]["uppercase"] is True
    assert strong["checks"]["digit"] is True
    assert strong["checks"]["special"] is True


def test_auth_manager_registration_and_duplicate_prevention(tmp_path):
    """Verify user registration, hashing, and duplicate email prevention."""
    users_file = tmp_path / "test_users.json"
    auth = AuthManager(storage_file=str(users_file))

    # 1. Successful registration
    user = auth.register(
        name="Alice Trader",
        email="alice@mino.com",
        password="ValidPassword123!",
        experience_level="Pro",
        trading_website="binance",
    )
    assert user["email"] == "alice@mino.com"
    assert "password_hash" not in user  # Sanitized

    # 2. Duplicate email rejection
    with pytest.raises(ValueError) as exc:
        auth.register(
            name="Alice Imposter",
            email="alice@mino.com",
            password="ValidPassword123!",
        )
    assert "already exists" in str(exc.value)

    # 3. Authentication
    auth_ok = auth.authenticate("alice@mino.com", "ValidPassword123!")
    assert auth_ok is not None
    assert auth_ok["name"] == "Alice Trader"

    # 4. Authentication with wrong password
    auth_fail = auth.authenticate("alice@mino.com", "WrongPassword!")
    assert auth_fail is None


def test_web_auth_and_mode_endpoints(tmp_path):
    """Test web API endpoints using FastAPI TestClient."""
    client = TestClient(app)

    # 1. Strength endpoint
    res = client.post("/api/auth/strength", json={"password": "TestPassword123!"})
    assert res.status_code == 200
    assert res.json()["level"] in ("strong", "pro")

    # 2. Register endpoint
    import uuid
    test_email = f"user_{uuid.uuid4().hex[:8]}@mino.com"
    res = client.post(
        "/api/auth/register",
        json={
            "name": "Bob Vance",
            "email": test_email,
            "password": "SecurePassword123!",
            "experience_level": "Intermediate",
            "trading_website": "bybit",
        },
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # 3. Duplicate email on API endpoint
    res_dup = client.post(
        "/api/auth/register",
        json={
            "name": "Bob Clone",
            "email": test_email,
            "password": "SecurePassword123!",
        },
    )
    assert res_dup.status_code == 400
    assert "already exists" in res_dup.json()["detail"]

    # 4. Mode toggle endpoint
    res_mode = client.post("/api/mode", json={"mode": "autonomous"})
    assert res_mode.status_code == 200
    assert res_mode.json()["mode"] == "autonomous"

    res_mode2 = client.post("/api/mode", json={"mode": "copilot"})
    assert res_mode2.status_code == 200
    assert res_mode2.json()["mode"] == "copilot"

    # 5. Settings endpoint
    res_set = client.get("/api/settings")
    assert res_set.status_code == 200
    data = res_set.json()
    assert "safety_barriers" in data
    assert "release" in data
    assert data["release"]["version"] == "v2.5.0-LTS"
