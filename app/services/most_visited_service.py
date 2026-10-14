


from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from fastapi import HTTPException

from app.models.most_visited import MostVisited
from app.models.package import Package

from app.schemas.most_visited import (
    MostVisitedCreate,
    MostVisitedUpdate,
)

from app.core.redis_client import (
    cache_get,
    cache_set,
    cache_delete_pattern,
)

from app.core.slugify import unique_slug

CACHE_PREFIX = "most_visited"


def _serialize_package(package: Package) -> dict:
    """
    Serialize a published package belonging to a destination.
    Used inside the destination response.
    """

    return {
        "id": package.id,
        "title": package.title,
        "slug": package.slug,
        "destination_id": package.destination_id,
        "price": str(package.price),
        "duration_days": package.duration_days,
        "duration_nights": package.duration_nights,
        "description": package.description,
        "images": package.images or [],
        "package_type": (
            package.package_type.value
            if hasattr(package.package_type, "value")
            else package.package_type
        ),
        "display_order": package.display_order,
        "is_popular": package.is_popular,
        "is_recommended": package.is_recommended,
        "is_trending": package.is_trending,
        "is_featured": package.is_featured,
        "is_new": package.is_new,
        "is_most_visited": package.is_most_visited,
        "status": (
            package.status.value if hasattr(package.status, "value") else package.status
        ),
    }


def _serialize(
    db: Session,
    m: MostVisited,
) -> dict:
    """
    Serialize a destination together with its
    published packages.
    """

    packages = (
        db.query(Package)
        .filter(
            Package.destination_id == m.id,
            Package.status == "published",
        )
        .order_by(
            Package.display_order.asc(),
            Package.created_at.desc(),
        )
        .all()
    )

    return {
        "id": m.id,
        "place_name": m.place_name,
        "slug": m.slug,
        "image": m.image,
        "description": m.description,
        # Destination details
        "best_time_to_visit": m.best_time_to_visit,
        "starting_from": (
            str(m.starting_from) if m.starting_from is not None else None
        ),
        "display_order": m.display_order,
        # Status
        "status": (m.status.value if hasattr(m.status, "value") else m.status),
        # Metadata
        "created_by": m.created_by,
        "created_at": (m.created_at.isoformat() if m.created_at else None),
        "updated_at": (m.updated_at.isoformat() if m.updated_at else None),
        # Related published packages
        "packages": [_serialize_package(package) for package in packages],
    }


# ============================================================
# DISPLAY ORDER
# ============================================================


def _place_in_order(
    db: Session,
    item: MostVisited,
    new_order: Optional[int],
    exclude_id: Optional[int] = None,
) -> None:
    """
    Put `item` at position `new_order` and renumber ALL
    destinations 1..n.

    - Fixes duplicate / zero display_order values automatically.
    - new_order empty / 0 / beyond the end -> the item goes last.
    - exclude_id: pass item.id when the item already exists in the DB,
      so it is not counted twice.

    Examples (unique orders 1..5):
        move 5 -> 2 : old 2, 3, 4 become 3, 4, 5
        move 2 -> 5 : old 3, 4, 5 become 2, 3, 4

    Call this BEFORE db.commit() so the reorder and the save
    happen in one transaction.
    """

    query = db.query(MostVisited)

    if exclude_id is not None:
        query = query.filter(MostVisited.id != exclude_id)

    others = query.order_by(
        MostVisited.display_order.asc(),
        MostVisited.id.asc(),
    ).all()

    total = len(others) + 1

    if not new_order:
        position = total
    else:
        position = max(1, min(int(new_order), total))

    others.insert(position - 1, item)

    for index, entry in enumerate(others, start=1):
        if entry.display_order != index:
            entry.display_order = index


def _normalize_display_orders(db: Session) -> None:
    """
    Renumber every destination 1..n (used after delete).
    """

    entries = (
        db.query(MostVisited)
        .order_by(
            MostVisited.display_order.asc(),
            MostVisited.id.asc(),
        )
        .all()
    )

    for index, entry in enumerate(entries, start=1):
        if entry.display_order != index:
            entry.display_order = index


def _invalidate_cache() -> None:
    """
    Delete all cached MostVisited entries
    after any create, update, or delete.
    """

    cache_delete_pattern(f"{CACHE_PREFIX}:*")


# def get_all_most_visited(
#     db: Session,
# ) -> list[dict]:
#     """
#     Public homepage endpoint.

#     Returns published MostVisited destinations
#     ordered by display_order.

#     NOTE:
#     Packages are included for each destination.
#     """

#     cache_key = f"{CACHE_PREFIX}:all"

#     cached = cache_get(cache_key)

#     if cached is not None:
#         return cached

#     items = (
#         db.query(MostVisited)
#         .filter(MostVisited.status == "published")
#         .order_by(MostVisited.display_order.asc())
#         .all()
#     )

#     data = [_serialize(db, item) for item in items]

#     cache_set(cache_key, data)

#     return data


def get_all_most_visited(db: Session) -> list[dict]:
    cache_key = f"{CACHE_PREFIX}:all"

    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    # Lowest published package price per destination, in the same query
    price_sq = (
        db.query(
            Package.destination_id.label("destination_id"),
            func.min(Package.price).label("min_price"),
        )
        .filter(Package.status == "published")
        .group_by(Package.destination_id)
        .subquery()
    )

    rows = (
        db.query(MostVisited, price_sq.c.min_price)
        .outerjoin(price_sq, price_sq.c.destination_id == MostVisited.id)
        .filter(MostVisited.status == "published")
        .order_by(MostVisited.display_order.asc())
        .all()
    )

    data = []
    for m, min_price in rows:
        own = m.starting_from
        price = own if own is not None else min_price
        data.append(
            {
                "id": m.id,
                "place_name": m.place_name,
                "slug": m.slug,
                "image": m.image,
                "description": m.description,
                "best_time_to_visit": m.best_time_to_visit,
                "starting_from": str(price) if price is not None else None,
                "display_order": m.display_order,
                "status": m.status.value if hasattr(m.status, "value") else m.status,
            }
        )

    cache_set(cache_key, data)
    return data


def get_by_slug(
    db: Session,
    slug: str,
) -> dict:
    """
    Public endpoint.

    Returns only the published destination
    by slug, including its published packages.
    """

    cache_key = f"{CACHE_PREFIX}:slug:{slug}"

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    item = (
        db.query(MostVisited)
        .filter(
            MostVisited.slug == slug,
            MostVisited.status == "published",
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Destination not found",
        )

    data = _serialize(db, item)

    cache_set(cache_key, data)

    return data


def get_all_most_visited_admin(
    db: Session,
) -> list[MostVisited]:
    """
    Admin endpoint.

    Returns both draft and published
    destinations.
    """

    return (
        db.query(MostVisited)
        .order_by(
            MostVisited.display_order.asc(),
            MostVisited.created_at.desc(),
        )
        .all()
    )

def get_most_visited_admin_paged(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """
    Admin endpoint (paginated + filtered).

    Returns {"items": [...], "total": <count after filters>}.
    """

    query = db.query(MostVisited)

    # Search by place name
    if search and search.strip():
        query = query.filter(
            MostVisited.place_name.ilike(f"%{search.strip()}%")
        )

    # Status filter
    if status and status != "all":
        if status not in ("draft", "published"):
            raise HTTPException(
                status_code=400,
                detail="Invalid status filter",
            )

        query = query.filter(MostVisited.status == status)

    # Total BEFORE offset/limit
    total = query.count()

    items = (
        query
        # MostVisitedOut includes `packages`; load them in one extra
        # query instead of one query per destination (N+1).
        .options(selectinload(MostVisited.packages))
        .order_by(
            MostVisited.display_order.asc(),
            MostVisited.created_at.desc(),
            MostVisited.id.desc(),  # stable tiebreaker for paging
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "items": items,
        "total": total,
    }


def get_most_visited_stats_admin(db: Session) -> dict:
    """
    Counts for the admin summary cards.
    """

    rows = (
        db.query(
            MostVisited.status,
            func.count(MostVisited.id),
        )
        .group_by(MostVisited.status)
        .all()
    )

    counts = {str(status): count for status, count in rows}

    published = counts.get("published", 0)
    draft = counts.get("draft", 0)

    return {
        "total": published + draft,
        "published": published,
        "draft": draft,
    }



def create_most_visited(
    db: Session,
    payload: MostVisitedCreate,
    user_id: int,
) -> MostVisited:
    """
    Create a new MostVisited destination.

    display_order: the destination is inserted at the requested
    position and all destinations are renumbered 1..n.
    Empty / 0 adds it last.
    """

    slug = unique_slug(
        db,
        MostVisited,
        payload.place_name,
    )

    item = MostVisited(
        place_name=payload.place_name,
        image=payload.image.model_dump(),
        description=payload.description,
        best_time_to_visit=payload.best_time_to_visit,
        starting_from=payload.starting_from,
        # temporary value, set properly by _place_in_order
        display_order=0,
        status=payload.status,
        slug=slug,
        created_by=user_id,
    )

    # Must run BEFORE db.add(item) so the new item is not
    # already part of the query result.
    _place_in_order(
        db,
        item,
        payload.display_order,
    )

    db.add(item)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(item)

    _invalidate_cache()

    return item


def update_most_visited(
    db: Session,
    item_id: int,
    payload: MostVisitedUpdate,
) -> MostVisited:
    """
    Update an existing MostVisited destination.

    display_order: when provided, the destination is moved to that
    position and all destinations are renumbered 1..n, so no two
    share the same order.
    """

    item = db.query(MostVisited).filter(MostVisited.id == item_id).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Entry not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    # Convert image object to dictionary
    if "image" in update_data and update_data["image"] is not None:
        update_data["image"] = (
            update_data["image"]
            if isinstance(update_data["image"], dict)
            else update_data["image"].model_dump()
        )

    # Generate a new slug if place name changes
    if "place_name" in update_data and update_data["place_name"] != item.place_name:
        update_data["slug"] = unique_slug(
            db,
            MostVisited,
            update_data["place_name"],
            exclude_id=item.id,
        )

    # Display order is applied by _place_in_order below
    has_order_change = "display_order" in update_data
    new_order = update_data.pop("display_order", None)

    # Apply updates
    for field, value in update_data.items():
        setattr(item, field, value)

    # Reposition and renumber everything 1..n
    if has_order_change and new_order is not None:
        _place_in_order(
            db,
            item,
            new_order,
            exclude_id=item.id,
        )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(item)

    _invalidate_cache()

    return item


def delete_most_visited(
    db: Session,
    item_id: int,
) -> None:
    """
    Delete a MostVisited destination and renumber the
    remaining ones 1..n.

    Because packages.destination_id has
    ON DELETE RESTRICT, deletion will fail
    if packages are still linked to this destination.
    """

    item = db.query(MostVisited).filter(MostVisited.id == item_id).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Entry not found",
        )

    db.delete(item)

    try:
        # flush first so a foreign-key violation is caught here
        db.flush()

        _normalize_display_orders(db)

        db.commit()
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=400,
            detail=(
                "Cannot delete this destination " "because packages are linked to it."
            ),
        )

    _invalidate_cache()


# ============================================================
# ONE-TIME UTILITY — RENUMBER display_order AS 1, 2, 3, ...
# ============================================================


def renumber_display_orders(db: Session) -> int:
    """
    Optional: run once to clean existing data immediately.
    (Every create / update / delete now also keeps orders clean.)

    Returns the number of destinations renumbered.
    """

    _normalize_display_orders(db)

    db.commit()

    _invalidate_cache()

    return db.query(MostVisited).count()







