import logging

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.user import User, RoleEnum
from app.schemas.user import UserCreate, UserLogin
from app.core.security import hash_password, verify_password, create_access_token

logger = logging.getLogger(__name__)


def _normalize_email(email: str) -> str:
    """Emails are compared trimmed and lower-case.

    Phones often auto-capitalise the first letter ("Admin@..."), and the
    database comparison is case-sensitive, so the same address would be
    "not found".
    """
    return str(email).strip().lower()


def _password_matches(plain: str, hashed: str) -> bool:
    try:
        return verify_password(plain, hashed)
    except (ValueError, TypeError):
        # A broken/unknown hash, or a password bcrypt cannot handle
        logger.exception("Password check raised an error")
        return False


def register_user(db: Session, payload: UserCreate, current_admin: User) -> User:
    """
    Create a new admin or creator.

    `current_admin` is the admin who is making this request (injected by
    require_admin in the route). Creating another admin must be authorised
    with THAT admin's own password, not the password of whichever admin
    happens to be first in the table.
    """
    # The frontend checks this too, but the server must not trust the client.
    if payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=400,
            detail="Password and Confirm Password do not match",
        )

    email = _normalize_email(payload.email)

    existing = (
        db.query(User)
        .filter(func.lower(User.email) == email)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Email already registered",
        )

    # =========================================================
    # ADMIN REGISTRATION
    # The logged-in admin must confirm with their own password.
    # =========================================================
    if payload.role == RoleEnum.admin:
        if not payload.admin_verification_password:
            raise HTTPException(
                status_code=400,
                detail="Your admin password is required",
            )

        # 403, not 401: the frontend treats ANY 401 on an authenticated
        # request as an expired session and logs the user out.
        if not verify_password(
            payload.admin_verification_password,
            current_admin.password_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid admin password",
            )

    # =========================================================
    # CREATE USER
    # =========================================================
    user = User(
        name=payload.name,
        email=email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate_user(db: Session, payload: UserLogin) -> tuple[User, str]:
    email = _normalize_email(payload.email)

    # func.lower also finds older rows that were saved with capital letters
    user = db.query(User).filter(func.lower(User.email) == email).first()

    # The client always gets the same message. The REAL reason goes to the
    # server log, so you can tell the two cases apart in Render.
    if user is None:
        logger.warning("Login failed: no account for %s", email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not _password_matches(payload.password, user.password_hash):
        logger.warning("Login failed: wrong password for user id %s", user.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return user, token


def list_users(db: Session, role: RoleEnum | None = None) -> list[User]:
    q = db.query(User)
    if role:
        q = q.filter(User.role == role)
    return q.order_by(User.id.desc()).all()


def list_creators(db: Session) -> list[User]:
    # kept so any other code that imports it still works
    return list_users(db, RoleEnum.creator)


def _active_admin_count(db: Session) -> int:
    return (
        db.query(User)
        .filter(User.role == RoleEnum.admin, User.is_active.is_(True))
        .count()
    )


def set_user_active_status(
    db: Session, user_id: int, is_active: bool, current_admin: User
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="You can't change your own status.")

    if (
        user.role == RoleEnum.admin
        and user.is_active
        and not is_active
        and _active_admin_count(db) <= 1
    ):
        raise HTTPException(
            status_code=400, detail="You can't disable the last active admin."
        )

    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int, current_admin: User) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.id == current_admin.id:
        raise HTTPException(status_code=400, detail="You can't delete your own account.")

    if (
        user.role == RoleEnum.admin
        and user.is_active
        and _active_admin_count(db) <= 1
    ):
        raise HTTPException(
            status_code=400, detail="You can't delete the last active admin."
        )

    db.delete(user)
    db.commit()