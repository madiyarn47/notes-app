"""Integration tests for the Telegram notification settings API.

Covers GET /account/telegram and PATCH /account/telegram.
"""

from __future__ import annotations

from unittest.mock import patch


def _auth(client, username="tguser", password="pw123456"):
    client.post("/api/auth/register", json={"username": username, "password": password})
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# GET /account/telegram
# ---------------------------------------------------------------------------


def test_get_telegram_settings_defaults(client):
    h = _auth(client)
    r = client.get("/api/account/telegram", headers=h)
    assert r.status_code == 200
    body = r.json()
    assert body["telegram_chat_id"] is None
    assert body["telegram_notifications"] is False


def test_get_telegram_settings_bot_not_configured(client):
    h = _auth(client)
    with patch("app.routers.account.settings") as mock_settings:
        mock_settings.telegram_bot_token = None
        r = client.get("/api/account/telegram", headers=h)
    assert r.status_code == 200
    assert r.json()["telegram_bot_configured"] is False


def test_get_telegram_settings_bot_empty_string_is_not_configured(client):
    h = _auth(client)
    with patch("app.routers.account.settings") as mock_settings:
        mock_settings.telegram_bot_token = ""
        r = client.get("/api/account/telegram", headers=h)
    assert r.status_code == 200
    assert r.json()["telegram_bot_configured"] is False


def test_patch_telegram_settings_returns_503_when_bot_empty_string(client):
    h = _auth(client)
    with patch("app.routers.account.settings") as mock_settings:
        mock_settings.telegram_bot_token = ""
        r = client.patch(
            "/api/account/telegram",
            headers=h,
            json={"telegram_chat_id": "999", "telegram_notifications": True},
        )
    assert r.status_code == 503


def test_get_telegram_settings_bot_configured(client):
    h = _auth(client)
    with patch("app.routers.account.settings") as mock_settings:
        mock_settings.telegram_bot_token = "123:TOKEN"
        r = client.get("/api/account/telegram", headers=h)
    assert r.status_code == 200
    assert r.json()["telegram_bot_configured"] is True


def test_get_telegram_settings_requires_auth(client):
    r = client.get("/api/account/telegram")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /account/telegram
# ---------------------------------------------------------------------------


def test_patch_telegram_settings_returns_503_when_bot_not_configured(client):
    h = _auth(client)
    with patch("app.routers.account.settings") as mock_settings:
        mock_settings.telegram_bot_token = None
        r = client.patch(
            "/api/account/telegram",
            headers=h,
            json={"telegram_chat_id": "999", "telegram_notifications": True},
        )
    assert r.status_code == 503


def test_patch_telegram_settings_saves_chat_id(client):
    h = _auth(client)
    with patch("app.routers.account.settings") as mock_settings:
        mock_settings.telegram_bot_token = "123:TOKEN"
        r = client.patch(
            "/api/account/telegram",
            headers=h,
            json={"telegram_chat_id": "12345678", "telegram_notifications": True},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["telegram_chat_id"] == "12345678"
    assert body["telegram_notifications"] is True


def test_patch_telegram_settings_persists_across_requests(client):
    h = _auth(client)
    with patch("app.routers.account.settings") as mock_settings:
        mock_settings.telegram_bot_token = "123:TOKEN"
        client.patch(
            "/api/account/telegram",
            headers=h,
            json={"telegram_chat_id": "42", "telegram_notifications": True},
        )

    r = client.get("/api/account/telegram", headers=h)
    assert r.json()["telegram_chat_id"] == "42"
    assert r.json()["telegram_notifications"] is True


def test_patch_telegram_settings_can_disconnect(client):
    h = _auth(client)
    with patch("app.routers.account.settings") as mock_settings:
        mock_settings.telegram_bot_token = "123:TOKEN"
        # First connect
        client.patch(
            "/api/account/telegram",
            headers=h,
            json={"telegram_chat_id": "42", "telegram_notifications": True},
        )
        # Then disconnect (clear chat_id)
        r = client.patch(
            "/api/account/telegram",
            headers=h,
            json={"telegram_chat_id": None, "telegram_notifications": False},
        )
    assert r.status_code == 200
    assert r.json()["telegram_chat_id"] is None
    assert r.json()["telegram_notifications"] is False


def test_patch_telegram_settings_requires_auth(client):
    r = client.patch(
        "/api/account/telegram",
        json={"telegram_chat_id": "1", "telegram_notifications": True},
    )
    assert r.status_code == 401


def test_patch_telegram_settings_empty_string_chat_id_treated_as_null(client):
    h = _auth(client)
    with patch("app.routers.account.settings") as mock_settings:
        mock_settings.telegram_bot_token = "123:TOKEN"
        r = client.patch(
            "/api/account/telegram",
            headers=h,
            json={"telegram_chat_id": "", "telegram_notifications": False},
        )
    assert r.status_code == 200
    assert r.json()["telegram_chat_id"] is None


def test_patch_telegram_settings_isolation_between_users(client):
    h1 = _auth(client, "alice", "pw123456")
    h2 = _auth(client, "bob", "pw123456")
    with patch("app.routers.account.settings") as mock_settings:
        mock_settings.telegram_bot_token = "123:TOKEN"
        client.patch(
            "/api/account/telegram",
            headers=h1,
            json={"telegram_chat_id": "111", "telegram_notifications": True},
        )

    r2 = client.get("/api/account/telegram", headers=h2)
    assert r2.json()["telegram_chat_id"] is None
