from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User, RoleEnum
from app.schemas.user import UserCreate, UserLogin
from app.core.security import hash_password, verify_password, create_access_token


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

    existing = (
        db.query(User)
        .filter(User.email == payload.email)
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
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def authenticate_user(db: Session, payload: UserLogin) -> tuple[User, str]:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return user, token


def list_creators(db: Session) -> list[User]:
    return db.query(User).filter(User.role == RoleEnum.creator).all()


def set_user_active_status(db: Session, user_id: int, is_active: bool) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    return user


def delete_user(db: Session, user_id: int) -> None:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()