


from typing import Optional

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.policy import Policy
from app.schemas.policy import PolicyCreate, PolicyUpdate
from app.core.redis_client import (
    cache_get,
    cache_set,
    cache_delete_pattern,
)

CACHE_PREFIX = "policies"


# ============================================================
# SERIALIZATION
# ============================================================


def _serialize(policy: Policy) -> dict:
    return {
        "id": policy.id,
        "policy_type": (
            policy.policy_type.value
            if hasattr(policy.policy_type, "value")
            else policy.policy_type
        ),
        "question": policy.question,
        "answer": policy.answer,
        "display_order": policy.display_order,
        "status": (
            policy.status.value
            if hasattr(policy.status, "value")
            else policy.status
        ),
        "created_by": policy.created_by,
        "published_at": (
            policy.published_at.isoformat()
            if policy.published_at
            else None
        ),
        "created_at": (
            policy.created_at.isoformat()
            if policy.created_at
            else None
        ),
        "updated_at": (
            policy.updated_at.isoformat()
            if policy.updated_at
            else None
        ),
    }


# ============================================================
# DISPLAY ORDER
# ============================================================


def _place_in_order(
    db: Session,
    policy: Policy,
    new_order: Optional[int],
    exclude_id: Optional[int] = None,
) -> None:
    """
    Put the policy at the requested display_order position
    and renumber ALL policies as 1..n.

    Examples:

        Existing:
        1, 2, 3, 4, 5

        Move #5 -> #2:
        1, 5, 2, 3, 4

        Final display_order:
        1, 2, 3, 4, 5

    Empty / 0 / negative / beyond the end:
        policy is placed at the last position.

    exclude_id:
        Used during update so the current policy is not counted twice.

    This function should be called before commit.
    """

    query = db.query(Policy)

    if exclude_id is not None:
        query = query.filter(Policy.id != exclude_id)

    others = (
        query
        .order_by(
            Policy.display_order.asc(),
            Policy.id.asc(),
        )
        .all()
    )

    total = len(others) + 1

    if not new_order or int(new_order) <= 0:
        position = total
    else:
        position = max(
            1,
            min(int(new_order), total),
        )

    others.insert(position - 1, policy)

    for index, item in enumerate(others, start=1):
        if item.display_order != index:
            item.display_order = index


def _normalize_display_orders(db: Session) -> None:
    """
    Renumber every policy as:

        1, 2, 3, 4, ...

    Used after deletion and for cleanup.
    """

    policies = (
        db.query(Policy)
        .order_by(
            Policy.display_order.asc(),
            Policy.id.asc(),
        )
        .all()
    )

    for index, item in enumerate(policies, start=1):
        if item.display_order != index:
            item.display_order = index


# ============================================================
# CACHE
# ============================================================


def _invalidate_cache() -> None:
    cache_delete_pattern(f"{CACHE_PREFIX}:*")


# ============================================================
# ADMIN — GET ALL POLICIES
# ============================================================


def get_all_policies(db: Session) -> list[dict]:
    """
    Get all company policies for admin management.

    Both draft and published policies are returned.

    Policies are always returned in display_order.
    """

    cache_key = f"{CACHE_PREFIX}:all"

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    items = (
        db.query(Policy)
        .order_by(
            Policy.display_order.asc(),
            Policy.id.asc(),
        )
        .all()
    )

    data = [_serialize(policy) for policy in items]

    cache_set(cache_key, data)

    return data


# ============================================================
# GET SINGLE POLICY
# ============================================================


def get_policy(
    db: Session,
    item_id: int,
) -> dict:
    """
    Get a single policy by ID.
    """

    item = (
        db.query(Policy)
        .filter(Policy.id == item_id)
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Policy not found",
        )

    return _serialize(item)


# ============================================================
# CREATE POLICY
# ============================================================


def create_policy(
    db: Session,
    payload: PolicyCreate,
    user_id: int,
) -> Policy:
    """
    Create a new company policy.

    display_order behavior:

    - display_order = 1 -> insert at first position
    - display_order = 2 -> insert at second position
    - display_order = 0 / empty -> add at the end
    - display_order greater than total -> add at the end

    All policies are renumbered 1..n.
    """

    policy_data = payload.model_dump()

    requested_order = policy_data.pop(
        "display_order",
        None,
    )

    item = Policy(
        **policy_data,
        display_order=0,
        created_by=user_id,
    )

    # Put the new policy into the requested position.
    #
    # The object is intentionally NOT added to the session yet.
    # This matches your Package implementation.
    _place_in_order(
        db,
        item,
        requested_order,
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
# UPDATE POLICY
# ============================================================


def update_policy(
    db: Session,
    item_id: int,
    payload: PolicyUpdate,
) -> Policy:
    """
    Update an existing company policy.

    If display_order is supplied, the policy is moved to that
    position and all policies are renumbered 1..n.

    Other fields are updated normally.
    """

    item = (
        db.query(Policy)
        .filter(Policy.id == item_id)
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Policy not found",
        )

    update_data = payload.model_dump(
        exclude_unset=True,
    )

    # --------------------------------------------------------
    # DISPLAY ORDER
    # --------------------------------------------------------

    has_order_change = "display_order" in update_data

    new_order = update_data.pop(
        "display_order",
        None,
    )

    # --------------------------------------------------------
    # APPLY OTHER UPDATES
    # --------------------------------------------------------

    for field, value in update_data.items():
        setattr(
            item,
            field,
            value,
        )

    # --------------------------------------------------------
    # MOVE POLICY
    # --------------------------------------------------------

    if has_order_change and new_order is not None:
        _place_in_order(
            db,
            item,
            new_order,
            exclude_id=item.id,
        )

    # --------------------------------------------------------
    # SAVE
    # --------------------------------------------------------

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(item)

    _invalidate_cache()

    return item


# ============================================================
# DELETE POLICY
# ============================================================


def delete_policy(
    db: Session,
    item_id: int,
) -> None:
    """
    Delete a company policy and renumber the remaining policies
    as 1..n.
    """

    item = (
        db.query(Policy)
        .filter(Policy.id == item_id)
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Policy not found",
        )

    db.delete(item)

    # Make sure the deleted policy is removed from the
    # current transaction before reordering the remaining rows.
    db.flush()

    _normalize_display_orders(db)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    _invalidate_cache()


# ============================================================
# ONE-TIME UTILITY
# ============================================================


def renumber_display_orders(
    db: Session,
) -> int:
    """
    One-time utility to clean existing policy data.

    Converts existing orders into:

        1, 2, 3, 4, ...

    Returns the total number of policies.
    """

    _normalize_display_orders(db)

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    _invalidate_cache()

    return db.query(Policy).count()







