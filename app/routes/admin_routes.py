from fastapi import APIRouter, Depends,Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.user import UserOut, UserUpdateStatus
from app.services import auth_service
from app.core.deps import require_admin
from app.models.user import User,RoleEnum

router = APIRouter(
    prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)]
)


@router.get("/users", response_model=list[UserOut])
def list_users(
    role: str | None = Query(None, pattern="^(admin|creator)$"),
    db: Session = Depends(get_db),
):
    return auth_service.list_users(db, role)


@router.patch("/users/{user_id}/status", response_model=UserOut)
def set_status(
    user_id: int,
    payload: UserUpdateStatus,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    return auth_service.set_user_active_status(
        db, user_id, payload.is_active, current_admin
    )


@router.delete("/users/{user_id}", status_code=204)
def remove_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_admin: User = Depends(require_admin),
):
    auth_service.delete_user(db, user_id, current_admin)

