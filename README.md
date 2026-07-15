# Notes

A personal Markdown notes app. Keep notes, tag them, search them, and pin some to a date so you can browse them on a calendar.

Each user has their own private space. Every note is a Markdown document with a live preview while editing.

## What's inside

- Log in / register (single-user-per-account — no sharing).
- CRUD for notes with Markdown preview.
- Tags with filtering.
- Full-text search across title and body.
- Optional date on a note + a calendar view.
- **Telegram reminders** — get a message when a note's date arrives (optional; requires a bot token).

## Run it

Requirements: Docker with Compose.

```bash
make up          # start db + backend + frontend
make seed        # (optional) create a demo user with a few notes
```

Then open <http://localhost:5173>.

Demo credentials (after `make seed`):

- **username:** `demo`
- **password:** `demo1234`

### Telegram reminders (optional)

1. Create a bot via [@BotFather](https://t.me/BotFather) and copy the token.
2. Add it to the backend environment (e.g. in `docker-compose.yml` or a `.env` file):
   ```
   TELEGRAM_BOT_TOKEN=123456789:AABBcc...
   ```
3. `make up` — the scheduler starts automatically when the token is present.
4. In the app, go to **Settings → Telegram notifications**, enter your chat ID
   (send `/start` to [@userinfobot](https://t.me/userinfobot) to find it), and
   enable reminders.

Any note with a date set to today or earlier will trigger a reminder message.
To test immediately after `make seed`, run:

```bash
TELEGRAM_CHAT_ID=<your_chat_id> make seed
```

This wires the demo user's Telegram on creation so a reminder fires within the
first scheduler tick (≤ 60 s after `make up`).

## Common commands

```bash
make help        # list all targets
make logs        # tail logs
make test        # run backend tests
make down        # stop the stack
make clean       # stop and wipe the database volume
```

## Layout

- `backend/` — FastAPI + SQLAlchemy + Alembic, talks to Postgres.
- `frontend/` — React + Vite.
- `docker-compose.yml` — db + backend + frontend.
