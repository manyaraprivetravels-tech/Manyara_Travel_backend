from fastapi import APIRouter, Depends, Query 
from sqlalchemy.orm import Session

from app.db.database import get_db

from app.schemas.most_visited import (
    MostVisitedCreate,
    MostVisitedUpdate,
    MostVisitedOut,
    MostVisitedListOut,
    MostVisitedStatsOut
)

from app.services import most_visited_service

from app.core.deps import require_admin_or_creator
from app.models.user import User

router = APIRouter(
    prefix="/most-visited",
    tags=["Most Visited"],
)


# ============================================================
# PUBLIC ROUTES
# ============================================================


# ------------------------------------------------------------
# GET ALL PUBLISHED DESTINATIONS
# ------------------------------------------------------------


@router.get(
    "",
    response_model=list[dict],
)
def list_most_visited(
    db: Session = Depends(get_db),
):
    """
    Get all published most-visited destinations.

    Each destination can include its published packages.
    """

    return most_visited_service.get_all_most_visited(db)


# ------------------------------------------------------------
# GET DESTINATION BY SLUG
# ------------------------------------------------------------


@router.get(
    "/slug/{slug}",
    response_model=MostVisitedOut,
)
def get_most_visited_by_slug(
    slug: str,
    db: Session = Depends(get_db),
):
    """
    Get a published destination by slug.

    Example:
        GET /most-visited/slug/kerala

    Response includes:
        - destination information
        - published packages belonging to that destination
    """

    return most_visited_service.get_by_slug(
        db,
        slug,
    )


# ============================================================
# ADMIN / CREATOR ROUTES
# ============================================================

# ------------------------------------------------------------
# ADMIN — PAGINATED LIST
# ------------------------------------------------------------


@router.get(
    "/admin/paged",
    response_model=MostVisitedListOut,
    dependencies=[Depends(require_admin_or_creator)],
)
def list_most_visited_admin_paged(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=200),
    search: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Paginated admin list (draft + published).
    Returns { items: [...], total: N }.
    """

    return most_visited_service.get_most_visited_admin_paged(
        db,
        skip=skip,
        limit=limit,
        search=search,
        status=status,
    )


# ------------------------------------------------------------
# ADMIN — STATS
# ------------------------------------------------------------


@router.get(
    "/admin/stats",
    response_model=MostVisitedStatsOut,
    dependencies=[Depends(require_admin_or_creator)],
)
def get_most_visited_stats(
    db: Session = Depends(get_db),
):
    """
    Counts for the admin summary cards.
    """

    return most_visited_service.get_most_visited_stats_admin(db)




# ------------------------------------------------------------
# CREATE DESTINATION
# ------------------------------------------------------------


@router.post(
    "/admin",
    response_model=MostVisitedOut,
)
def create(
    payload: MostVisitedCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_creator),
):
    """
    Create a new most-visited destination.
    """

    return most_visited_service.create_most_visited(
        db,
        payload,
        current_user.id,
    )


# ------------------------------------------------------------
# UPDATE DESTINATION
# ------------------------------------------------------------


@router.put(
    "/admin/{item_id}",
    response_model=MostVisitedOut,
    dependencies=[Depends(require_admin_or_creator)],
)
def update(
    item_id: int,
    payload: MostVisitedUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing destination.
    """

    return most_visited_service.update_most_visited(
        db,
        item_id,
        payload,
    )


# ------------------------------------------------------------
# DELETE DESTINATION
# ------------------------------------------------------------


@router.delete(
    "/admin/{item_id}",
    status_code=204,
    dependencies=[Depends(require_admin_or_creator)],
)
def delete(
    item_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a destination.

    If packages are linked through destination_id,
    the service should prevent deletion because the
    database FK uses ON DELETE RESTRICT.
    """

    most_visited_service.delete_most_visited(
        db,
        item_id,
    )

    return None
