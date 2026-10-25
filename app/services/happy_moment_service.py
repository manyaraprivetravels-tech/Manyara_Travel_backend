

from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.happy_moment import HappyMoment
from app.schemas.happy_moment import (
    HappyMomentCreate,
    HappyMomentUpdate,
)

from app.core.redis_client import (
    cache_get,
    cache_set,
    cache_delete_pattern,
)

from app.core.slugify import unique_slug

CACHE_PREFIX = "happy_moments"


# ============================================================
# SERIALIZER
# ============================================================


def _serialize(m: HappyMoment) -> dict:
    return {
        "id": m.id,
        # SEO-friendly slug
        "slug": m.slug,
        # Cover image
        "image": m.image,
        # Additional gallery images
        "gallery_images": m.gallery_images or [],
        # Main title
        "title": m.title,
        # Homepage caption
        "short_caption": m.short_caption,
        # Destination
        "place_name": m.place_name,
        # Destination description
        "place_description": m.place_description,
        # Traveller experience
        "experience": m.experience,
        # Things travellers liked
        "highlights": m.highlights or [],
        # Optional travel date
        "travel_date": (m.travel_date.isoformat() if m.travel_date else None),
        # Homepage ordering
        "display_order": m.display_order,
        # Homepage visibility
        "is_featured": m.is_featured,
        "created_by": m.created_by,
        "created_at": (m.created_at.isoformat() if m.created_at else None),
        "updated_at": (m.updated_at.isoformat() if m.updated_at else None),
    }


# ============================================================
# DISPLAY ORDER
# ============================================================


def _place_in_order(
    db: Session,
    item: HappyMoment,
    new_order: Optional[int],
    exclude_id: Optional[int] = None,
) -> None:
    """
    Put `item` at position `new_order` and renumber ALL
    happy moments 1..n.

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

    query = db.query(HappyMoment)

    if exclude_id is not None:
        query = query.filter(HappyMoment.id != exclude_id)

    others = query.order_by(
        HappyMoment.display_order.asc(),
        HappyMoment.id.asc(),
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
    Renumber every happy moment 1..n (used after delete).
    """

    entries = (
        db.query(HappyMoment)
        .order_by(
            HappyMoment.display_order.asc(),
            HappyMoment.id.asc(),
        )
        .all()
    )

    for index, entry in enumerate(entries, start=1):
        if entry.display_order != index:
            entry.display_order = index


# ============================================================
# CACHE INVALIDATION
# ============================================================


def _invalidate_cache():
    """
    Clear all Happy Moments related Redis caches.
    """
    cache_delete_pattern(f"{CACHE_PREFIX}:*")


# ============================================================
# GET ALL HAPPY MOMENTS
# ============================================================


def get_all(
    db: Session,
) -> list[dict]:

    cache_key = f"{CACHE_PREFIX}:all"

    # 1. Check Redis
    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    # 2. Query database
    items = (
        db.query(HappyMoment)
        .order_by(
            HappyMoment.display_order.asc(),
            HappyMoment.created_at.desc(),
        )
        .all()
    )

    # 3. Serialize
    data = [_serialize(m) for m in items]

    # 4. Store in Redis
    cache_set(
        cache_key,
        data,
    )

    return data


# ============================================================
# GET FEATURED HAPPY MOMENTS
# ============================================================


def get_featured(
    db: Session,
    limit: int = 6,
) -> list[dict]:

    cache_key = f"{CACHE_PREFIX}:featured:{limit}"

    # 1. Check Redis
    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    # 2. Query database
    items = (
        db.query(HappyMoment)
        .filter(HappyMoment.is_featured.is_(True))
        .order_by(
            HappyMoment.display_order.asc(),
            HappyMoment.created_at.desc(),
        )
        .limit(limit)
        .all()
    )

    # 3. Serialize
    data = [_serialize(m) for m in items]

    # 4. Store in Redis
    cache_set(
        cache_key,
        data,
    )

    return data


# ============================================================
# GET SINGLE HAPPY MOMENT BY SLUG
# ============================================================


def get_by_slug(
    db: Session,
    slug: str,
) -> dict:

    cache_key = f"{CACHE_PREFIX}:slug:{slug}"

    # 1. Check Redis
    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    # 2. Query database
    item = db.query(HappyMoment).filter(HappyMoment.slug == slug).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Happy moment not found",
        )

    # 3. Serialize
    data = _serialize(item)

    # 4. Store in Redis
    cache_set(
        cache_key,
        data,
    )

    return data


# ============================================================
# CREATE HAPPY MOMENT
# ============================================================


def create(
    db: Session,
    payload: HappyMomentCreate,
    user_id: int,
) -> HappyMoment:
    """
    Create a happy moment.

    display_order: the item is inserted at the requested position
    and all happy moments are renumbered 1..n. Empty / 0 adds it last.
    """

    # --------------------------------------------------------
    # Generate SEO-friendly slug automatically
    # --------------------------------------------------------

    slug_source = payload.title or payload.place_name or "happy-moment"

    slug = unique_slug(
        db,
        HappyMoment,
        slug_source,
    )

    # --------------------------------------------------------
    # Create item
    # --------------------------------------------------------

    item = HappyMoment(
        # SEO slug
        slug=slug,
        # Cover image
        image=payload.image.model_dump(),
        # Gallery images
        gallery_images=(
            [image.model_dump() for image in payload.gallery_images]
            if payload.gallery_images
            else []
        ),
        title=payload.title,
        short_caption=payload.short_caption,
        place_name=payload.place_name,
        place_description=payload.place_description,
        experience=payload.experience,
        highlights=payload.highlights or [],
        travel_date=payload.travel_date,
        # temporary value, set properly by _place_in_order
        display_order=0,
        is_featured=payload.is_featured,
        created_by=user_id,
    )

    # --------------------------------------------------------
    # Display order
    # Must run BEFORE db.add(item) so the new item is not
    # already part of the query result.
    # --------------------------------------------------------

    _place_in_order(
        db,
        item,
        payload.display_order,
    )

    # --------------------------------------------------------
    # Save (reorder + insert in one transaction)
    # --------------------------------------------------------

    db.add(item)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(item)

    # --------------------------------------------------------
    # Clear Redis
    # --------------------------------------------------------

    _invalidate_cache()

    return item


# ============================================================
# UPDATE HAPPY MOMENT
# ============================================================


def update(
    db: Session,
    item_id: int,
    payload: HappyMomentUpdate,
) -> HappyMoment:
    """
    Update a happy moment.

    display_order: when provided, the item is moved to that
    position and all happy moments are renumbered 1..n, so no two
    share the same order.
    """

    # --------------------------------------------------------
    # Find item
    # --------------------------------------------------------

    item = db.query(HappyMoment).filter(HappyMoment.id == item_id).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Happy moment not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    # --------------------------------------------------------
    # Slug
    # --------------------------------------------------------

    if "slug" in update_data:

        new_slug = update_data.pop("slug")

        if new_slug is not None and new_slug != item.slug:

            existing = (
                db.query(HappyMoment)
                .filter(
                    HappyMoment.slug == new_slug,
                    HappyMoment.id != item.id,
                )
                .first()
            )

            if existing:
                raise HTTPException(
                    status_code=409,
                    detail=("A happy moment with " "this slug already exists"),
                )

            item.slug = new_slug

    # --------------------------------------------------------
    # Cover Image
    # --------------------------------------------------------

    if "image" in update_data:

        image_data = update_data.pop("image")

        if image_data is not None:

            item.image = (
                image_data.model_dump()
                if hasattr(
                    image_data,
                    "model_dump",
                )
                else image_data
            )

    # --------------------------------------------------------
    # Gallery Images
    # --------------------------------------------------------

    if "gallery_images" in update_data:

        gallery_data = update_data.pop("gallery_images")

        if gallery_data is not None:

            item.gallery_images = [
                (
                    image.model_dump()
                    if hasattr(
                        image,
                        "model_dump",
                    )
                    else image
                )
                for image in gallery_data
            ]

        else:
            item.gallery_images = []

    # --------------------------------------------------------
    # Display order: take it out of update_data,
    # it is applied by _place_in_order below
    # --------------------------------------------------------

    has_order_change = "display_order" in update_data
    new_order = update_data.pop("display_order", None)

    # --------------------------------------------------------
    # Other fields
    # --------------------------------------------------------

    for field, value in update_data.items():

        setattr(
            item,
            field,
            value,
        )

    # --------------------------------------------------------
    # Display order: reposition and renumber everything 1..n
    # --------------------------------------------------------

    if has_order_change and new_order is not None:
        _place_in_order(
            db,
            item,
            new_order,
            exclude_id=item.id,
        )

    # --------------------------------------------------------
    # Save (reorder + update in one transaction)
    # --------------------------------------------------------

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(item)

    # --------------------------------------------------------
    # Clear Redis
    # --------------------------------------------------------

    _invalidate_cache()

    return item


# ============================================================
# DELETE HAPPY MOMENT
# ============================================================


def delete(
    db: Session,
    item_id: int,
) -> None:
    """
    Delete a happy moment and renumber the remaining ones 1..n.
    """

    # --------------------------------------------------------
    # Find item
    # --------------------------------------------------------

    item = db.query(HappyMoment).filter(HappyMoment.id == item_id).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Happy moment not found",
        )

    # --------------------------------------------------------
    # Delete + close the gap in display_order
    # --------------------------------------------------------

    db.delete(item)
    db.flush()

    _normalize_display_orders(db)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    # --------------------------------------------------------
    # Clear Redis
    # --------------------------------------------------------

    _invalidate_cache()


# ============================================================
# ONE-TIME UTILITY — RENUMBER display_order AS 1, 2, 3, ...
# ============================================================


def renumber_display_orders(db: Session) -> int:
    """
    Optional: run once to clean existing data immediately.
    (Every create / update / delete now also keeps orders clean.)

    Returns the number of happy moments renumbered.
    """

    _normalize_display_orders(db)

    db.commit()

    _invalidate_cache()

    return db.query(HappyMoment).count()








