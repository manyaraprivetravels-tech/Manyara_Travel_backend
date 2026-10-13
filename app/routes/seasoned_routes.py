


from typing import Literal
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db

from app.schemas.seasoned_schema import (
    SeasonedDestinationCreate,
    SeasonedDestinationUpdate,
    SeasonedDestinationResponse,
    SeasonedDestinationDetailResponse,
    SeasonedDestinationListResponse,
    SeasonedDestinationAdminListResponse,
    SeasonedDestinationStatsResponse
)

from app.services import seasoned_service
from app.core.deps import require_admin_or_creator
from app.models.user import User


router = APIRouter(
    prefix="/seasoned-destinations",
    tags=["Seasoned Destinations"],
)


# ============================================================
# PUBLIC ROUTES
# ============================================================


# ------------------------------------------------------------
# PUBLIC — GET PUBLISHED SEASONED DESTINATIONS
# ------------------------------------------------------------


@router.get(
    "",
    response_model=list[SeasonedDestinationListResponse],
)
def list_published_seasoned_destinations(
    db: Session = Depends(get_db),
):
    """
    Get all published seasoned destinations.

    Returns only destinations with:

        status = published

    Results are ordered by display_order.
    """

    return seasoned_service.get_published_seasoned_destinations(
        db,
    )


# ------------------------------------------------------------
# PUBLIC — GET SEASONED DESTINATION BY SLUG
# ------------------------------------------------------------


@router.get(
    "/{slug}",
    response_model=SeasonedDestinationDetailResponse,
)
def get_seasoned_destination_by_slug(
    slug: str,
    db: Session = Depends(get_db),
):
    """
    Get a published seasoned destination by slug.

    The response includes:

        - seasonal destination information
        - season label
        - season start date
        - season end date
        - best time to visit
        - starting price
        - associated published packages
    """

    return seasoned_service.get_seasoned_destination_by_slug(
        db,
        slug,
    )




@router.get(
    "/admin/all",
    response_model=list[SeasonedDestinationResponse],
    dependencies=[Depends(require_admin_or_creator)],
)
def list_all_seasoned_destinations(
    db: Session = Depends(get_db),
):
    """
    Get all seasoned destinations for admin/creator management.

    Includes:

        - draft destinations
        - published destinations
    """

    return seasoned_service.get_all_seasoned_destinations_admin(
        db,
    )

@router.get(
    "/admin/paged",
    response_model=SeasonedDestinationAdminListResponse,
    dependencies=[Depends(require_admin_or_creator)],
)
def list_seasoned_destinations_admin_paged(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    search: str | None = Query(default=None, max_length=100),
    status: Literal["all", "draft", "published"] | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Paginated admin list (draft + published). Returns { items, total }."""
    return seasoned_service.get_seasoned_destinations_admin_paged(
        db, skip=skip, limit=limit, search=search, status=status
    )


@router.get(
    "/admin/stats",
    response_model=SeasonedDestinationStatsResponse,
    dependencies=[Depends(require_admin_or_creator)],
)
def get_seasoned_destinations_stats(db: Session = Depends(get_db)):
    """Counts for the admin summary cards."""
    return seasoned_service.get_seasoned_destinations_stats_admin(db)


# ------------------------------------------------------------
# ADMIN — GET SEASONED DESTINATION BY ID
# ------------------------------------------------------------


@router.get(
    "/admin/{destination_id}",
    response_model=SeasonedDestinationDetailResponse,
    dependencies=[Depends(require_admin_or_creator)],
)
def get_seasoned_destination_admin(
    destination_id: int,
    db: Session = Depends(get_db),
):
    """
    Get a seasoned destination by ID.

    This endpoint is intended for admin/creator
    management and can return draft destinations.

    Associated published packages are included.
    """

    return seasoned_service.get_seasoned_destination_by_id(
        db,
        destination_id,
    )


# ------------------------------------------------------------
# ADMIN — CREATE SEASONED DESTINATION
# ------------------------------------------------------------


@router.post(
    "/admin",
    response_model=SeasonedDestinationResponse,
    status_code=201,
)
def create_seasoned_destination(
    payload: SeasonedDestinationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_creator),
):
    """
    Create a new seasoned destination.

    The authenticated admin/creator ID is stored
    as created_by.

    The service handles:

        - slug generation
        - display order
        - date validation
        - database creation
        - cache invalidation
    """

    return seasoned_service.create_seasoned_destination(
        db,
        payload,
        current_user.id,
    )




# ------------------------------------------------------------
# ADMIN — UPDATE SEASONED DESTINATION
# ------------------------------------------------------------


@router.put(
    "/admin/{destination_id}",
    response_model=SeasonedDestinationResponse,
    dependencies=[Depends(require_admin_or_creator)],
)
def update_seasoned_destination(
    destination_id: int,
    payload: SeasonedDestinationUpdate,
    db: Session = Depends(get_db),
):
    

    return seasoned_service.update_seasoned_destination(
        db,
        destination_id,
        payload,
    )


# ------------------------------------------------------------
# ADMIN — DELETE SEASONED DESTINATION
# ------------------------------------------------------------


@router.delete(
    "/admin/{destination_id}",
    status_code=204,
    dependencies=[Depends(require_admin_or_creator)],
)
def delete_seasoned_destination(
    destination_id: int,
    db: Session = Depends(get_db),
):
    

    seasoned_service.delete_seasoned_destination(
        db,
        destination_id,
    )

    return None


# ------------------------------------------------------------
# ADMIN — RENUMBER DISPLAY ORDERS
# ------------------------------------------------------------


@router.post(
    "/admin/renumber",
    status_code=200,
)
def renumber_seasoned_destinations(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_creator),
):


    return seasoned_service.renumber_display_orders(
        db,
    )