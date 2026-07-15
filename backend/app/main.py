from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .routers import account as account_router
from .routers import auth as auth_router
from .routers import notes as notes_router
from .routers import tags as tags_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if settings.telegram_bot_token:
        from .scheduler import ReminderScheduler

        scheduler = ReminderScheduler(settings.telegram_bot_token)
        scheduler.start()
    yield
    if scheduler is not None:
        scheduler.stop()


app = FastAPI(title="Notes API", version="0.1.0", lifespan=lifespan)

_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


app.include_router(auth_router.router, prefix="/api")
app.include_router(account_router.router, prefix="/api")
app.include_router(notes_router.router, prefix="/api")
app.include_router(tags_router.router, prefix="/api")
