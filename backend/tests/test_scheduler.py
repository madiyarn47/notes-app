"""Unit tests for app.scheduler.ReminderScheduler._tick logic.

The scheduler thread itself is not started in these tests — we call _tick()
directly to keep tests fast and deterministic.
"""

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-with-at-least-32-characters")

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Note, User
from app.scheduler import ReminderScheduler, _format_reminder

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'sched_test.db'}",
        connect_args={"check_same_thread": False},
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    db = Session()
    try:
        yield db
    finally:
        db.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def scheduler():
    return ReminderScheduler(bot_token="123:TEST")


def _make_user(db, telegram_chat_id="111", notifications=True) -> User:
    from app.auth import hash_password

    user = User(
        username=f"u{id(db)}",
        password_hash=hash_password("pw123456"),
        telegram_chat_id=telegram_chat_id,
        telegram_notifications=notifications,
    )
    db.add(user)
    db.flush()
    return user


def _make_note(db, user_id: int, note_date: date, reminder_sent_at=None) -> Note:
    note = Note(
        user_id=user_id,
        title="Test note",
        content="body",
        tags=[],
        note_date=note_date,
        reminder_sent_at=reminder_sent_at,
    )
    db.add(note)
    db.flush()
    return note


# ---------------------------------------------------------------------------
# _format_reminder
# ---------------------------------------------------------------------------


def test_format_reminder_includes_title_and_date():
    note = MagicMock()
    note.title = "Stand-up"
    note.note_date = date(2026, 7, 15)
    result = _format_reminder(note)
    assert "Stand-up" in result
    assert "15 Jul 2026" in result


# ---------------------------------------------------------------------------
# Scheduler _tick — happy path
# ---------------------------------------------------------------------------


def test_tick_sends_reminder_for_due_note(db_session, scheduler):
    user = _make_user(db_session)
    note = _make_note(db_session, user.id, note_date=date.today())
    db_session.commit()

    with (
        patch.object(scheduler, "_process") as mock_process,
        patch("app.scheduler.SessionLocal", return_value=db_session),
    ):
        scheduler._tick()

    mock_process.assert_called_once()
    processed_note = mock_process.call_args[0][1]
    assert processed_note.id == note.id


def test_tick_skips_future_notes(db_session, scheduler):
    user = _make_user(db_session)
    _make_note(db_session, user.id, note_date=date.today() + timedelta(days=1))
    db_session.commit()

    with (
        patch.object(scheduler, "_process") as mock_process,
        patch("app.scheduler.SessionLocal", return_value=db_session),
    ):
        scheduler._tick()

    mock_process.assert_not_called()


def test_tick_skips_already_sent(db_session, scheduler):
    user = _make_user(db_session)
    _make_note(
        db_session,
        user.id,
        note_date=date.today(),
        reminder_sent_at=datetime.now(UTC),
    )
    db_session.commit()

    with (
        patch.object(scheduler, "_process") as mock_process,
        patch("app.scheduler.SessionLocal", return_value=db_session),
    ):
        scheduler._tick()

    mock_process.assert_not_called()


def test_tick_skips_archived_notes(db_session, scheduler):
    user = _make_user(db_session)
    note = _make_note(db_session, user.id, note_date=date.today())
    note.archived_at = datetime.now(UTC)
    db_session.commit()

    with (
        patch.object(scheduler, "_process") as mock_process,
        patch("app.scheduler.SessionLocal", return_value=db_session),
    ):
        scheduler._tick()

    mock_process.assert_not_called()


def test_tick_skips_user_without_chat_id(db_session, scheduler):
    user = _make_user(db_session, telegram_chat_id=None)
    _make_note(db_session, user.id, note_date=date.today())
    db_session.commit()

    with (
        patch.object(scheduler, "_process") as mock_process,
        patch("app.scheduler.SessionLocal", return_value=db_session),
    ):
        scheduler._tick()

    mock_process.assert_not_called()


def test_tick_skips_user_with_notifications_disabled(db_session, scheduler):
    user = _make_user(db_session, notifications=False)
    _make_note(db_session, user.id, note_date=date.today())
    db_session.commit()

    with (
        patch.object(scheduler, "_process") as mock_process,
        patch("app.scheduler.SessionLocal", return_value=db_session),
    ):
        scheduler._tick()

    mock_process.assert_not_called()


def test_tick_includes_past_due_notes(db_session, scheduler):
    """Notes from yesterday should also get a reminder."""
    user = _make_user(db_session)
    _make_note(db_session, user.id, note_date=date.today() - timedelta(days=1))
    db_session.commit()

    with (
        patch.object(scheduler, "_process") as mock_process,
        patch("app.scheduler.SessionLocal", return_value=db_session),
    ):
        scheduler._tick()

    mock_process.assert_called_once()


# ---------------------------------------------------------------------------
# Scheduler _process — idempotency
# ---------------------------------------------------------------------------


def test_process_sets_reminder_sent_at_on_success(db_session, scheduler):
    user = _make_user(db_session)
    note = _make_note(db_session, user.id, note_date=date.today())
    db_session.commit()

    with patch("app.scheduler.send_message", return_value=True):
        scheduler._process(db_session, note)

    db_session.refresh(note)
    assert note.reminder_sent_at is not None


def test_process_does_not_set_reminder_sent_at_on_failure(db_session, scheduler):
    user = _make_user(db_session)
    note = _make_note(db_session, user.id, note_date=date.today())
    db_session.commit()

    with patch("app.scheduler.send_message", return_value=False):
        scheduler._process(db_session, note)

    db_session.refresh(note)
    assert note.reminder_sent_at is None


def test_process_idempotent_second_call_skipped(db_session, scheduler):
    """Calling _process twice on the same note sends the message only once."""
    user = _make_user(db_session)
    note = _make_note(db_session, user.id, note_date=date.today())
    db_session.commit()

    with patch("app.scheduler.send_message", return_value=True) as mock_send:
        scheduler._process(db_session, note)
        scheduler._process(db_session, note)  # reminder_sent_at is now set

    assert mock_send.call_count == 1


def test_process_rolls_back_when_user_disabled_between_query_and_send(db_session, scheduler):
    """If the user disables notifications between batch query and _process, don't send."""
    user = _make_user(db_session)
    note = _make_note(db_session, user.id, note_date=date.today())
    db_session.commit()

    # Simulate user disabling notifications after the batch query
    user.telegram_notifications = False
    db_session.commit()

    with patch("app.scheduler.send_message", return_value=True) as mock_send:
        scheduler._process(db_session, note)

    assert mock_send.call_count == 0
    db_session.refresh(note)
    # reminder_sent_at must be rolled back so next tick can retry if re-enabled
    assert note.reminder_sent_at is None


# ---------------------------------------------------------------------------
# Scheduler lifecycle
# ---------------------------------------------------------------------------


def test_scheduler_start_stop():
    sched = ReminderScheduler("tok")
    with patch.object(sched, "_safe_tick"):
        sched.start()
        assert sched._thread is not None
        assert sched._thread.is_alive()
        thread = sched._thread  # capture before stop() clears it
        sched.stop()
        # _thread is set to None after stop(); original thread should be done
        assert sched._thread is None
        assert not thread.is_alive()


def test_scheduler_double_start_is_safe():
    sched = ReminderScheduler("tok")
    with patch.object(sched, "_safe_tick"):
        sched.start()
        first_thread = sched._thread
        sched.start()  # must not create a second thread
        assert sched._thread is first_thread
        sched.stop()


def test_safe_tick_catches_exceptions(scheduler):
    with patch.object(scheduler, "_tick", side_effect=RuntimeError("boom")):
        scheduler._safe_tick()  # must not propagate
