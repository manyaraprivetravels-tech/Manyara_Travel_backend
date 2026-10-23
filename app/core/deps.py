import logging
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.core.security import decode_access_token
from app.models.user import User, RoleEnum

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# A signed-in admin OR creator stays signed in until they have been idle
# (no API call and no heartbeat) for this long.
INACTIVITY_LIMIT = timedelta(minutes=30)

# Don't write to the DB on every single request
ACTIVITY_WRITE_INTERVAL = timedelta(seconds=60)

# Old name, kept so any other import keeps working
ADMIN_INACTIVITY_LIMIT = INACTIVITY_LIMIT


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _as_utc(value: datetime | None) -> datetime | None:
    """DB drivers can return naive datetimes: treat those as UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_access_token(token)
    if payload is None:
        raise _unauthorized("Could not validate credentials")

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise _unauthorized("Could not validate credentials")

    user = db.query(User).filter(User.id == user_id).first()

    if user is None or not user.is_active:
        logger.info("Auth rejected: user %s is missing or disabled", user_id)
        raise _unauthorized("Could not validate credentials")

    now = datetime.now(timezone.utc)
    last = _as_utc(user.last_activity_at)

    if last is not None:
        idle = now - last

        if idle >= INACTIVITY_LIMIT:
            logger.info("Session expired: user %s was idle for %s", user.id, idle)
            raise _unauthorized("Session expired due to inactivity")

        # Active recently: skip the write. A negative idle time (a timestamp
        # in the future, e.g. from a timezone mix-up) is NOT skipped, so it
        # gets rewritten with the correct time below.
        if timedelta(0) <= idle < ACTIVITY_WRITE_INTERVAL:
            return user

    user.last_activity_at = now
    db.commit()

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != RoleEnum.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


def require_admin_or_creator(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in (RoleEnum.admin, RoleEnum.creator):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not permitted"
        )
    return current_user