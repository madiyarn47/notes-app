"""Background reminder scheduler.

Runs as a daemon thread alongside the FastAPI process.  On every tick it
finds notes whose date has arrived and whose reminder has not yet been sent,
then delivers a Telegram message to the note owner.

Idempotency guarantee
---------------------
Before attempting to send, the scheduler atomically claims the note by
executing:

    UPDATE notes
       SET reminder_sent_at = <now>
     WHERE id = :id
       AND reminder_sent_at IS NULL

If the rowcount is 0 another instance (or a previous tick) already claimed
this note and no message is sent.  If the rowcount is 1 the current process
"owns" the delivery attempt and calls send_message() with up to
_MAX_RETRIES internal retries.  If all retries fail the error is logged and
reminder_sent_at is rolled back so the scheduler will retry on the next tick.

This keeps "never send twice" as the strict invariant while still supporting
retry on transient Telegram failures.

Multi-instance behaviour
------------------------
Two concurrent instances might both observe a note with reminder_sent_at IS
NULL before either commit their UPDATE.  The database serialises the two
writes; the second UPDATE returns rowcount=0 and is a no-op.  The first
instance owns the send, so no duplicate message is ever delivered.
"""

from __future__ import annotations

import logging
import threading
from datetime import UTC, date, datetime

from sqlalchemy import update

from .db import SessionLocal
from .models import Note, User
from .services.telegram import send_message

logger = logging.getLogger(__name__)

_TICK_SECONDS = 60


def _format_reminder(note: Note) -> str:
    date_str = note.note_date.strftime("%d %b %Y") if note.note_date else ""
    return f"<b>Reminder: {note.title}</b>\n{date_str}"


class ReminderScheduler:
    """Daemon thread that dispatches Telegram reminders on note dates."""

    def __init__(self, bot_token: str) -> None:
        self._bot_token = bot_token
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return  # already running
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="reminder-scheduler",
            daemon=True,
        )
        self._thread.start()
        logger.info("Reminder scheduler started (tick=%ds)", _TICK_SECONDS)

    def stop(self, timeout: float = 10.0) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
            self._thread = None
        logger.info("Reminder scheduler stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run(self) -> None:
        # Fire an initial tick immediately so reminders are not delayed by
        # one full cycle after a container restart.
        self._safe_tick()
        while not self._stop_event.wait(_TICK_SECONDS):
            self._safe_tick()

    def _safe_tick(self) -> None:
        try:
            self._tick()
        except Exception:
            logger.exception("Reminder scheduler tick raised an unexpected error")

    def _tick(self) -> None:
        today = date.today()
        db = SessionLocal()
        try:
            # Load all candidates in one query; the list is expected to be
            # small (only notes due today or earlier with unsent reminders).
            candidates = (
                db.query(Note)
                .join(User, Note.user_id == User.id)
                .filter(
                    Note.note_date <= today,
                    Note.reminder_sent_at.is_(None),
                    Note.archived_at.is_(None),
                    User.telegram_chat_id.is_not(None),
                    User.telegram_notifications.is_(True),
                )
                .all()
            )
            for note in candidates:
                self._process(db, note)
        finally:
            db.close()

    def _process(self, db, note: Note) -> None:
        now = datetime.now(UTC)

        # Atomic claim: only one instance/tick will win the UPDATE.
        result = db.execute(
            update(Note)
            .where(Note.id == note.id, Note.reminder_sent_at.is_(None))
            .values(reminder_sent_at=now)
        )
        db.commit()

        if result.rowcount == 0:
            # Already claimed by another instance or a concurrent tick.
            return

        # Re-fetch the user after the commit to get the latest settings.
        user = db.get(User, note.user_id)
        if user is None or not user.telegram_chat_id or not user.telegram_notifications:
            # User disconnected Telegram between the batch query and now.
            # Roll back the claim so we do not silently discard the reminder.
            db.execute(update(Note).where(Note.id == note.id).values(reminder_sent_at=None))
            db.commit()
            return

        sent = send_message(self._bot_token, user.telegram_chat_id, _format_reminder(note))

        if not sent:
            # All retries exhausted.  Roll back so the scheduler retries on
            # the next tick rather than silently losing the reminder.
            db.execute(update(Note).where(Note.id == note.id).values(reminder_sent_at=None))
            db.commit()
            logger.error(
                "Failed to send reminder for note id=%d (user_id=%d); will retry next tick",
                note.id,
                note.user_id,
            )
        else:
            logger.info(
                "Sent reminder for note id=%d to chat_id=%s",
                note.id,
                user.telegram_chat_id,
            )
