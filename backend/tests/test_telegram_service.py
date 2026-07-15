"""Unit tests for app.services.telegram.send_message."""

from unittest.mock import MagicMock, call, patch

import httpx
import pytest

from app.services.telegram import _MAX_RETRIES, _RETRY_BASE_DELAY, send_message

BOT_TOKEN = "123:ABC"
CHAT_ID = "999"
TEXT = "Hello"
_SEND_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"


def _make_response(status_code: int, body: dict | None = None) -> MagicMock:
    mock = MagicMock(spec=httpx.Response)
    mock.status_code = status_code
    mock.json.return_value = body or {"ok": True}
    return mock


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_send_message_returns_true_on_200():
    with patch("app.services.telegram.httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.post.return_value = _make_response(200)

        result = send_message(BOT_TOKEN, CHAT_ID, TEXT)

    assert result is True
    instance.post.assert_called_once_with(
        _SEND_URL, json={"chat_id": CHAT_ID, "text": TEXT, "parse_mode": "HTML"}
    )


# ---------------------------------------------------------------------------
# Client errors (4xx) — no retry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("status_code", [400, 403, 404])
def test_send_message_returns_false_on_client_error_without_retry(status_code):
    with patch("app.services.telegram.httpx.Client") as MockClient:
        instance = MockClient.return_value.__enter__.return_value
        instance.post.return_value = _make_response(
            status_code, {"ok": False, "description": "Bad"}
        )

        result = send_message(BOT_TOKEN, CHAT_ID, TEXT)

    assert result is False
    assert instance.post.call_count == 1  # no retry for client errors


# ---------------------------------------------------------------------------
# Server errors (5xx) — retried
# ---------------------------------------------------------------------------


def test_send_message_retries_on_500_and_returns_false_after_exhaustion():
    with (
        patch("app.services.telegram.httpx.Client") as MockClient,
        patch("app.services.telegram.time.sleep") as mock_sleep,
    ):
        instance = MockClient.return_value.__enter__.return_value
        instance.post.return_value = _make_response(500, {"ok": False})

        result = send_message(BOT_TOKEN, CHAT_ID, TEXT)

    assert result is False
    assert instance.post.call_count == _MAX_RETRIES
    assert mock_sleep.call_count == _MAX_RETRIES - 1


def test_send_message_succeeds_after_one_retry():
    with (
        patch("app.services.telegram.httpx.Client") as MockClient,
        patch("app.services.telegram.time.sleep"),
    ):
        instance = MockClient.return_value.__enter__.return_value
        instance.post.side_effect = [
            _make_response(500),
            _make_response(200),
        ]

        result = send_message(BOT_TOKEN, CHAT_ID, TEXT)

    assert result is True
    assert instance.post.call_count == 2


# ---------------------------------------------------------------------------
# Transport errors — retried
# ---------------------------------------------------------------------------


def test_send_message_retries_on_transport_error():
    with (
        patch("app.services.telegram.httpx.Client") as MockClient,
        patch("app.services.telegram.time.sleep"),
    ):
        instance = MockClient.return_value.__enter__.return_value
        instance.post.side_effect = httpx.ConnectError("connection refused")

        result = send_message(BOT_TOKEN, CHAT_ID, TEXT)

    assert result is False
    assert instance.post.call_count == _MAX_RETRIES


def test_send_message_recovers_after_transport_error():
    with (
        patch("app.services.telegram.httpx.Client") as MockClient,
        patch("app.services.telegram.time.sleep"),
    ):
        instance = MockClient.return_value.__enter__.return_value
        instance.post.side_effect = [
            httpx.ConnectError("timeout"),
            _make_response(200),
        ]

        result = send_message(BOT_TOKEN, CHAT_ID, TEXT)

    assert result is True
    assert instance.post.call_count == 2


# ---------------------------------------------------------------------------
# Back-off timing
# ---------------------------------------------------------------------------


def test_send_message_uses_exponential_backoff():
    with (
        patch("app.services.telegram.httpx.Client") as MockClient,
        patch("app.services.telegram.time.sleep") as mock_sleep,
    ):
        instance = MockClient.return_value.__enter__.return_value
        instance.post.return_value = _make_response(500)

        send_message(BOT_TOKEN, CHAT_ID, TEXT)

    expected_delays = [_RETRY_BASE_DELAY * (2**i) for i in range(_MAX_RETRIES - 1)]
    assert mock_sleep.call_args_list == [call(d) for d in expected_delays]
