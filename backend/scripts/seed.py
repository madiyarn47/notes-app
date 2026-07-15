"""Seed a demo user with a few notes. Idempotent: wipes the demo user before inserting."""

import os
from datetime import date, timedelta

from app.auth import hash_password
from app.db import SessionLocal
from app.models import Note, User

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "demo1234"


def seed() -> None:
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == DEMO_USERNAME).one_or_none()
        if existing:
            db.delete(existing)
            db.commit()

        # Support optional Telegram demo: set TELEGRAM_CHAT_ID env var before
        # running `make seed` to wire the demo user up for live notifications.
        demo_chat_id = os.environ.get("TELEGRAM_CHAT_ID") or None

        user = User(
            username=DEMO_USERNAME,
            password_hash=hash_password(DEMO_PASSWORD),
            telegram_chat_id=demo_chat_id,
            telegram_notifications=demo_chat_id is not None,
        )
        db.add(user)
        db.flush()

        today = date.today()
        notes: list[Note] = [
            Note(
                user_id=user.id,
                title="Welcome",
                content="# Welcome\n\nThis is your first note. Edit me, or create new ones.",
                tags=["intro"],
                note_date=None,
            ),
            Note(
                user_id=user.id,
                title="Grocery list",
                content="- milk\n- bread\n- eggs",
                tags=["todo", "shopping"],
                note_date=today,
            ),
            Note(
                user_id=user.id,
                title="Project kickoff",
                content="Meeting with the team **tomorrow**. Prepare the agenda.",
                tags=["work"],
                note_date=today + timedelta(days=1),
            ),
            Note(
                user_id=user.id,
                title="Book idea",
                content="_Fleeting thought worth keeping._",
                tags=["ideas"],
                note_date=None,
            ),
        ]
        db.add_all(notes)
        db.commit()

        if demo_chat_id:
            print(
                f"Seeded '{DEMO_USERNAME}' / '{DEMO_PASSWORD}' with {len(notes)} notes. "
                f"Telegram chat_id={demo_chat_id} — notifications enabled."
            )
        else:
            print(f"Seeded '{DEMO_USERNAME}' / '{DEMO_PASSWORD}' with {len(notes)} notes.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
