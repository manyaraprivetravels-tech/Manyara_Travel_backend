


from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.faq import FAQ
from app.schemas.faq import FAQCreate, FAQUpdate
from app.core.redis_client import (
    cache_get,
    cache_set,
    cache_delete_pattern,
)

CACHE_PREFIX = "faqs"


def _serialize(f: FAQ) -> dict:
    return {
        "id": f.id,
        "question": f.question,
        "answer": f.answer,
        "category": f.category,
        "display_order": f.display_order,
        "status": f.status,
        "created_by": f.created_by,
        "created_at": (
            f.created_at.isoformat()
            if f.created_at
            else None
        ),
    }


def _invalidate_cache() -> None:
    cache_delete_pattern(f"{CACHE_PREFIX}:*")


# ============================================================
# DISPLAY ORDER (per category)
# ============================================================
#
# FAQs are shown and filtered by category, so display_order is a
# position INSIDE each category: every category is numbered
# 1, 2, 3, ... independently.
# ============================================================


def _place_in_order(
    db: Session,
    item: FAQ,
    new_order: Optional[int],
    category: str,
    exclude_id: Optional[int] = None,
) -> None:
  

    query = db.query(FAQ).filter(FAQ.category == category)

    if exclude_id is not None:
        query = query.filter(FAQ.id != exclude_id)

    others = query.order_by(
        FAQ.display_order.asc(),
        FAQ.id.asc(),
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


def _normalize_category(db: Session, category: str) -> None:
    """
    Renumber every FAQ of one category 1..n
    (used after delete or when an FAQ leaves a category).
    """

    entries = (
        db.query(FAQ)
        .filter(FAQ.category == category)
        .order_by(
            FAQ.display_order.asc(),
            FAQ.id.asc(),
        )
        .all()
    )

    for index, entry in enumerate(entries, start=1):
        if entry.display_order != index:
            entry.display_order = index


# ============================================================
# PUBLIC FAQs
# ============================================================

def get_all_faqs(
    db: Session,
    category: str | None = None,
) -> list[dict]:
    """
    Return published FAQs only.

    If a category is supplied, return only published FAQs
    belonging to that category.
    """

    cache_key = (
        f"{CACHE_PREFIX}:{category}"
        if category
        else f"{CACHE_PREFIX}:all"
    )

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    query = (
        db.query(FAQ)
        .filter(FAQ.status == "published")
    )

    if category:
        query = query.filter(
            FAQ.category == category
        )

    items = (
        query
        .order_by(FAQ.display_order.asc(), FAQ.id.asc())
        .all()
    )

    data = [_serialize(f) for f in items]

    cache_set(cache_key, data)

    return data


# ============================================================
# ADMIN — CREATE
# ============================================================

def create_faq(
    db: Session,
    payload: FAQCreate,
    user_id: int,
) -> FAQ:
    """
    Create an FAQ.

    display_order: the FAQ is inserted at the requested position
    inside its category and that category is renumbered 1..n.
    Empty / 0 adds it last in the category.
    """

    data = payload.model_dump()

    requested_order = data.pop("display_order", None)
    category = data.get("category") or "general"
    data["category"] = category

    item = FAQ(
        **data,
        # temporary value, set properly by _place_in_order
        display_order=0,
        created_by=user_id,
    )

    # Must run BEFORE db.add(item) so the new FAQ is not
    # already part of the query result.
    _place_in_order(
        db,
        item,
        requested_order,
        category,
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


# ============================================================
# ADMIN — UPDATE
# ============================================================

def update_faq(
    db: Session,
    item_id: int,
    payload: FAQUpdate,
) -> FAQ:
    """
    Update an FAQ.

    - display_order: the FAQ is moved to that position inside its
      category and the category is renumbered 1..n.
    - category change: the FAQ is placed in the new category
      (at the requested position, or last) and the old category
      is renumbered so it has no gap.
    """

    item = (
        db.query(FAQ)
        .filter(FAQ.id == item_id)
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="FAQ not found",
        )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    old_category = item.category
    new_category = update_data.get("category") or old_category
    category_changed = new_category != old_category

    if category_changed:
        update_data["category"] = new_category

    # Display order is applied by _place_in_order below
    has_order_change = "display_order" in update_data
    new_order = update_data.pop("display_order", None)

    for field, value in update_data.items():
        setattr(item, field, value)

    # Reposition inside the (new) category and renumber it 1..n
    if category_changed or (has_order_change and new_order is not None):
        _place_in_order(
            db,
            item,
            new_order if has_order_change else None,
            new_category,
            exclude_id=item.id,
        )

    # Close the gap left in the old category
    if category_changed:
        _normalize_category(db, old_category)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(item)

    _invalidate_cache()

    return item


# ============================================================
# ADMIN — DELETE
# ============================================================

def delete_faq(
    db: Session,
    item_id: int,
) -> None:
    """
    Delete an FAQ and renumber the rest of its category 1..n.
    """

    item = (
        db.query(FAQ)
        .filter(FAQ.id == item_id)
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="FAQ not found",
        )

    category = item.category

    db.delete(item)
    db.flush()

    _normalize_category(db, category)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    _invalidate_cache()


# ============================================================
# ONE-TIME UTILITY — RENUMBER EVERY CATEGORY 1, 2, 3, ...
# ============================================================


def renumber_display_orders(db: Session) -> int:
    """
    Optional: run once to clean existing data immediately.
    (Every create / update / delete now also keeps orders clean.)

    Returns the number of FAQs renumbered.
    """

    categories = [row[0] for row in db.query(FAQ.category).distinct().all()]

    for category in categories:
        _normalize_category(db, category)

    db.commit()

    _invalidate_cache()

    return db.query(FAQ).count()


def rename_category(db: Session, old: str, new: str) -> int:
    """
    One-time utility: move every FAQ from one category to another
    and renumber the target category 1..n.
    Returns the number of FAQs moved.
    """

    moved = (
        db.query(FAQ)
        .filter(FAQ.category == old)
        .update({FAQ.category: new}, synchronize_session=False)
    )

    db.flush()

    _normalize_category(db, new)

    db.commit()

    _invalidate_cache()

    return moved