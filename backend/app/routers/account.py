from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..auth import hash_password, verify_password
from ..config import settings
from ..deps import get_current_user, get_db
from ..models import User
from ..rate_limit import (
    auth_rate_limit_key,
    check_auth_rate_limit,
    clear_auth_failures,
    record_auth_failure,
)
from ..schemas import (
    ChangePasswordIn,
    DeleteAccountIn,
    OkOut,
    TelegramSettingsIn,
    TelegramSettingsOut,
)

router = APIRouter(prefix="/account", tags=["account"])


@router.post("/change-password", response_model=OkOut)
def change_password(
    request: Request,
    payload: ChangePasswordIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> OkOut:
    rate_limit_key = auth_rate_limit_key(request, "change-password", user.id)
    check_auth_rate_limit(rate_limit_key)
    if not verify_password(payload.current_password, user.password_hash):
        record_auth_failure(rate_limit_key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is wrong")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    clear_auth_failures(rate_limit_key)
    return OkOut()


@router.get("/telegram", response_model=TelegramSettingsOut)
def get_telegram_settings(
    user: User = Depends(get_current_user),
) -> TelegramSettingsOut:
    return TelegramSettingsOut(
        telegram_bot_configured=bool(settings.telegram_bot_token),
        telegram_chat_id=user.telegram_chat_id,
        telegram_notifications=user.telegram_notifications,
    )


@router.patch("/telegram", response_model=TelegramSettingsOut)
def update_telegram_settings(
    payload: TelegramSettingsIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TelegramSettingsOut:
    if not settings.telegram_bot_token:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Telegram integration is not configured on this server.",
        )
    user.telegram_chat_id = payload.telegram_chat_id or None
    user.telegram_notifications = payload.telegram_notifications
    db.commit()
    return TelegramSettingsOut(
        telegram_bot_configured=True,
        telegram_chat_id=user.telegram_chat_id,
        telegram_notifications=user.telegram_notifications,
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    request: Request,
    payload: DeleteAccountIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    rate_limit_key = auth_rate_limit_key(request, "delete-account", user.id)
    check_auth_rate_limit(rate_limit_key)
    if not verify_password(payload.password, user.password_hash):
        record_auth_failure(rate_limit_key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Password is wrong")
    db.delete(user)
    db.commit()
    clear_auth_failures(rate_limit_key)
