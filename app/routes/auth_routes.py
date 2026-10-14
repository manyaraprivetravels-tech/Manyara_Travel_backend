from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.user import UserCreate, UserLogin, UserOut, Token
from app.services import auth_service
from app.core.deps import get_current_user, require_admin
from app.models.user import User
from app.core.security import create_access_token

from datetime import datetime, timezone

from app.schemas.password_reset import (
    ForgotPasswordRequest,
    VerifyResetCodeRequest,
    VerifyResetCodeResponse,
    ResetPasswordRequest,
    PasswordResetResponse,
)

from app.services.password_reset_service import (
    forgot_password,
    verify_reset_code,
    reset_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserOut)
def register(
    payload: UserCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Only an existing admin can create new users (admin or creator).

    The logged-in admin is passed down so that creating another admin is
    verified against THEIR password.
    """
    return auth_service.register_user(db, payload, admin)


@router.post("/login", response_model=Token)
def login(
    payload: UserLogin,
    db: Session = Depends(get_db),
):
    user, token = auth_service.authenticate_user(db, payload)

    # Build the response BEFORE committing. After a commit SQLAlchemy
    # expires the object, and reading it again costs an extra SELECT
    # (that is what db.refresh(user) was doing).
    user_out = UserOut.model_validate(user)

    # Start the 30-minute inactivity period (admins and creators are the
    # only roles, so no role check is needed).
    user.last_activity_at = datetime.now(timezone.utc)
    db.commit()

    return Token(access_token=token, user=user_out)


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post(
    "/forgot-password",
    response_model=PasswordResetResponse,
)
def forgot_password_endpoint(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    forgot_password(
        db=db,
        payload=payload,
        background_tasks=background_tasks,
    )

    return {
        "message": (
            "If an account exists for this email, a verification code has been sent."
        )
    }


@router.post(
    "/verify-reset-code",
    response_model=VerifyResetCodeResponse,
)
def verify_reset_code_endpoint(
    payload: VerifyResetCodeRequest,
    db: Session = Depends(get_db),
):
    reset_token = verify_reset_code(
        db=db,
        payload=payload,
    )

    return {
        "message": "Verification code verified successfully.",
        "reset_token": reset_token,
    }


@router.post(
    "/reset-password",
    response_model=PasswordResetResponse,
)
def reset_password_endpoint(
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    reset_password(
        db=db,
        payload=payload,
    )

    return {"message": "Password reset successfully."}


@router.post("/heartbeat")
def heartbeat(current_user: User = Depends(get_current_user)):
    """
    Called by the frontend every few minutes ONLY while the admin is
    actively using the panel. get_current_user already refreshes
    last_activity_at; here we also issue a fresh token so the JWT's
    60-minute expiry slides forward instead of being absolute.
    """
    token = create_access_token(
        {"sub": str(current_user.id), "role": current_user.role.value}
    )
    return {"access_token": token, "token_type": "bearer"}