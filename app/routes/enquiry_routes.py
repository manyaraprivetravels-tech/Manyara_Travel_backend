from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session


from app.db.database import get_db
from app.schemas.enquiry import (
    EnquiryCreate,
    EnquiryResponse,
    EnquiryListOut,
    EnquiryStatsOut
)

from app.services.enquiry_service import (
    create_enquiry,
    get_all_enquiries,
    get_enquiries_admin_paged,
    get_enquiry_stats_admin,
    get_enquiry_by_id,
    delete_enquiry,
)

from app.core.deps import require_admin_or_creator

router = APIRouter(
    prefix="/enquiries",
    tags=["Enquiries"],
)


# =========================================================
# PUBLIC - CUSTOMER SUBMITS ENQUIRY
# =========================================================


@router.post(
    "",
    response_model=EnquiryResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_enquiry(
    enquiry_data: EnquiryCreate,
    db: Session = Depends(get_db),
):
    return create_enquiry(
        db=db,
        enquiry_data=enquiry_data,
    )


# =========================================================
# ADMIN - GET ALL ENQUIRIES
# =========================================================


@router.get(
    "/admin",
    response_model=list[EnquiryResponse],
    dependencies=[Depends(require_admin_or_creator)],
)
def get_admin_enquiries(
    db: Session = Depends(get_db),
):
    return get_all_enquiries(db)


# =========================================================
# ADMIN - PAGINATED LIST
# =========================================================


@router.get(
    "/admin/paged",
    response_model=EnquiryListOut,
    dependencies=[Depends(require_admin_or_creator)],
)
def get_admin_enquiries_paged(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    search: str | None = Query(default=None, max_length=100),
    package_type: str | None = Query(default=None, max_length=50),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_from cannot be after date_to",
        )

    return get_enquiries_admin_paged(
        db=db,
        skip=skip,
        limit=limit,
        search=search,
        package_type=package_type,
        date_from=date_from,
        date_to=date_to,
    )


# =========================================================
# ADMIN - STATS
# =========================================================


@router.get(
    "/admin/stats",
    response_model=EnquiryStatsOut,
    dependencies=[Depends(require_admin_or_creator)],
)
def get_admin_enquiry_stats(
    db: Session = Depends(get_db),
):
    return get_enquiry_stats_admin(db)

















# =========================================================
# ADMIN - GET SINGLE ENQUIRY
# =========================================================



@router.get(
    "/admin/{enquiry_id}",
    response_model=EnquiryResponse,
    dependencies=[Depends(require_admin_or_creator)],
)
def get_admin_enquiry(
    enquiry_id: int,
    db: Session = Depends(get_db),
):
    enquiry = get_enquiry_by_id(
        db=db,
        enquiry_id=enquiry_id,
    )

    if not enquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enquiry not found",
        )

    return enquiry


# =========================================================
# ADMIN - DELETE ENQUIRY
# =========================================================


@router.delete(
    "/admin/{enquiry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_or_creator)],
)
def delete_admin_enquiry(
    enquiry_id: int,
    db: Session = Depends(get_db),
):
    enquiry = delete_enquiry(
        db=db,
        enquiry_id=enquiry_id,
    )

    if not enquiry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enquiry not found",
        )

    return None
