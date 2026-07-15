"""Telegram Bot API client.

Provides a single send_message() function with built-in retries and timeouts.
Business logic (who to notify, what to say) lives in the scheduler, not here.
"""

from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger(__name__)

_TELEGRAM_API = "https://api.telegram.org"
_TIMEOUT = httpx.Timeout(10.0)
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 1.0  # seconds; doubles on each attempt


def send_message(bot_token: str, chat_id: str, text: str) -> bool:
    """Send a Telegram message via the Bot API.

    Retries up to _MAX_RETRIES times on network errors or 5xx responses,
    with exponential back-off.  Client errors (4xx) are not retried.

    Returns True if the message was accepted by Telegram, False otherwise.
    """
    url = f"{_TELEGRAM_API}/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}

    with httpx.Client(timeout=_TIMEOUT) as client:
        for attempt in range(_MAX_RETRIES):
            try:
                resp = client.post(url, json=payload)
                if resp.status_code == 200:
                    return True
                data = resp.json()
                logger.warning(
                    "Telegram API returned %s (attempt %d/%d): %s",
                    resp.status_code,
                    attempt + 1,
                    _MAX_RETRIES,
                    data,
                )
                # Client errors (e.g. chat not found, bot blocked) → no retry.
                if resp.status_code < 500:
                    return False
            except httpx.TransportError as exc:
                logger.warning(
                    "Telegram transport error (attempt %d/%d): %s",
                    attempt + 1,
                    _MAX_RETRIES,
                    exc,
                )

            if attempt < _MAX_RETRIES - 1:
                time.sleep(_RETRY_BASE_DELAY * (2**attempt))

    logger.error(
        "Failed to deliver Telegram message to chat_id=%s after %d attempts",
        chat_id,
        _MAX_RETRIES,
    )
    return False
