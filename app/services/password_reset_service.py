import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.email import send_password_reset_email
from app.core.security import hash_password

from app.models.password_reset import PasswordResetToken
from app.models.user import User

from app.schemas.password_reset import (
    ForgotPasswordRequest,
    VerifyResetCodeRequest,
    ResetPasswordRequest,
)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def _generate_reset_token() -> str:
    return secrets.token_urlsafe(48)


def _get_current_time() -> datetime:
    return datetime.now(timezone.utc)


def forgot_password(
    db: Session,
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
) -> None:

    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    # Do not reveal whether email exists.
    if not user or not user.is_active:
        return

    # Invalidate previous unused reset tokens
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used.is_(False),
    ).update(
        {PasswordResetToken.used: True},
        synchronize_session=False,
    )

    otp = _generate_otp()

    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=_hash_token(otp),
        expires_at=_get_current_time()
        + timedelta(minutes=settings.OTP_EXPIRY_MINUTES),
        used=False,
    )

    db.add(reset_token)
    db.commit()

    # Sent after the response, so the page never waits on email.
    background_tasks.add_task(
        send_password_reset_email,
        recipient_email=user.email,
        otp=otp,
    )


def verify_reset_code(
    db: Session,
    payload: VerifyResetCodeRequest,
) -> str:

    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    otp_hash = _hash_token(payload.code)

    reset_record = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.token_hash == otp_hash,
            PasswordResetToken.used.is_(False),
        )
        .order_by(PasswordResetToken.created_at.desc())
        .first()
    )

    if not reset_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    now = _get_current_time()

    expires_at = reset_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= now:
        reset_record.used = True
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired",
        )

    # Swap the OTP for a separate reset token (same record, new hash).
    reset_token = _generate_reset_token()

    reset_record.token_hash = _hash_token(reset_token)
    reset_record.expires_at = now + timedelta(
        minutes=settings.RESET_SESSION_EXPIRY_MINUTES
    )
    reset_record.used = False

    db.commit()

    return reset_token


def reset_password(
    db: Session,
    payload: ResetPasswordRequest,
) -> None:

    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password and Confirm Password do not match",
        )

    reset_token_hash = _hash_token(payload.reset_token)

    reset_record = (
        db.query(PasswordResetToken)
        .filter(
            PasswordResetToken.token_hash == reset_token_hash,
            PasswordResetToken.used.is_(False),
        )
        .first()
    )

    if not reset_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    now = _get_current_time()

    expires_at = reset_record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at <= now:
        reset_record.used = True
        db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset session has expired",
        )

    user = db.query(User).filter(User.id == reset_record.user_id).first()

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to reset password",
        )

    user.password_hash = hash_password(payload.new_password)

    # One-time use.
    reset_record.used = True

    db.commit()