

from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.about import (
    AboutPage,
    AboutLeadership,
    AboutTeamMember,
    AboutMilestone,
    AboutValue,
)

from app.schemas.about import (
    AboutPageCreate,
    AboutPageUpdate,
    AboutLeadershipCreate,
    AboutLeadershipUpdate,
    AboutTeamMemberCreate,
    AboutTeamMemberUpdate,
    AboutMilestoneCreate,
    AboutMilestoneUpdate,
    AboutValueCreate,
    AboutValueUpdate,
)

from app.core.redis_client import (
    cache_get,
    cache_set,
    cache_delete_pattern,
)

from app.core.slugify import unique_slug


CACHE_PREFIX = "about"


# ============================================================
# HELPERS
# ============================================================


def _image_to_dict(image):
    """
    Convert Pydantic ImageObject into a JSON-safe dictionary.

    Supports:
        - Pydantic ImageObject
        - dict
        - None
    """

    if image is None:
        return None

    if hasattr(image, "model_dump"):
        return image.model_dump()

    return image


def _apply_image(update_data: dict) -> dict:
    """
    Convert image object to JSON-safe dict when an image
    field is supplied during update.
    """

    if "image" in update_data:
        update_data["image"] = _image_to_dict(
            update_data["image"]
        )

    return update_data


def _commit_and_refresh(
    db: Session,
    item,
):
    """
    Commit database changes and refresh the ORM object.
    """

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


# ============================================================
# ADMIN SERIALIZERS
# ============================================================


def _serialize_about_page(
    item: AboutPage,
) -> dict:
    return {
        "id": item.id,
        "company_name": item.company_name,
        "hero_title": item.hero_title,
        "hero_description": item.hero_description,
        "story_title": item.story_title,
        "story_content": item.story_content,
        "mission": item.mission,
        "vision": item.vision,
        "founded_year": item.founded_year,
        "years_experience": item.years_experience,
        "status": item.status,
        "created_at": (
            item.created_at.isoformat()
            if item.created_at
            else None
        ),
        "updated_at": (
            item.updated_at.isoformat()
            if item.updated_at
            else None
        ),
    }


def _serialize_leadership(
    item: AboutLeadership,
) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "slug": item.slug,
        "designation": item.designation,
        "short_bio": item.short_bio,
        "full_bio": item.full_bio,
        "image": item.image,
        "email": item.email,
        "phone": item.phone,
        "whatsapp": item.whatsapp,
        "experience_years": item.experience_years,
        "linkedin": item.linkedin,
        "instagram": item.instagram,
        "facebook": item.facebook,
        "company_message": item.company_message,
        "display_order": item.display_order,
        "is_active": item.is_active,
        "created_at": (
            item.created_at.isoformat()
            if item.created_at
            else None
        ),
        "updated_at": (
            item.updated_at.isoformat()
            if item.updated_at
            else None
        ),
    }


def _serialize_team_member(
    item: AboutTeamMember,
) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "slug": item.slug,
        "designation": item.designation,
        "department": item.department,
        "short_description": item.short_description,
        "full_description": item.full_description,
        "image": item.image,
        "email": item.email,
        "phone": item.phone,
        "whatsapp": item.whatsapp,
        "experience_years": item.experience_years,
        "linkedin": item.linkedin,
        "instagram": item.instagram,
        "display_order": item.display_order,
        "is_active": item.is_active,
        "show_public_profile": item.show_public_profile,
        "created_at": (
            item.created_at.isoformat()
            if item.created_at
            else None
        ),
        "updated_at": (
            item.updated_at.isoformat()
            if item.updated_at
            else None
        ),
    }


def _serialize_milestone(
    item: AboutMilestone,
) -> dict:
    return {
        "id": item.id,
        "year": item.year,
        "title": item.title,
        "description": item.description,
        "image": item.image,
        "display_order": item.display_order,
        "is_active": item.is_active,
        "created_at": (
            item.created_at.isoformat()
            if item.created_at
            else None
        ),
        "updated_at": (
            item.updated_at.isoformat()
            if item.updated_at
            else None
        ),
    }


def _serialize_value(
    item: AboutValue,
) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "icon": item.icon,
        "display_order": item.display_order,
        "is_active": item.is_active,
        "created_at": (
            item.created_at.isoformat()
            if item.created_at
            else None
        ),
        "updated_at": (
            item.updated_at.isoformat()
            if item.updated_at
            else None
        ),
    }


# ============================================================
# PUBLIC SERIALIZERS
# ============================================================


def _serialize_public_about_page(
    item: AboutPage,
) -> dict:
    return {
        "id": item.id,
        "company_name": item.company_name,
        "hero_title": item.hero_title,
        "hero_description": item.hero_description,
        "story_title": item.story_title,
        "story_content": item.story_content,
        "mission": item.mission,
        "vision": item.vision,
        "founded_year": item.founded_year,
        "years_experience": item.years_experience,
        "status": item.status,
        "created_at": (
            item.created_at.isoformat()
            if item.created_at
            else None
        ),
        "updated_at": (
            item.updated_at.isoformat()
            if item.updated_at
            else None
        ),
    }


def _serialize_public_leadership(
    item: AboutLeadership,
) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "slug": item.slug,
        "designation": item.designation,
        "short_bio": item.short_bio,
        "full_bio": item.full_bio,
        "image": item.image,
        "email": item.email,
        "phone": item.phone,
        "whatsapp": item.whatsapp,
        "experience_years": item.experience_years,
        "linkedin": item.linkedin,
        "instagram": item.instagram,
        "facebook": item.facebook,
        "company_message": item.company_message,
        "display_order": item.display_order,
    }


def _serialize_public_team_member(
    item: AboutTeamMember,
) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "slug": item.slug,
        "designation": item.designation,
        "department": item.department,
        "short_description": item.short_description,
        "full_description": item.full_description,
        "image": item.image,
        "email": item.email,
        "phone": item.phone,
        "whatsapp": item.whatsapp,
        "experience_years": item.experience_years,
        "linkedin": item.linkedin,
        "instagram": item.instagram,
        "display_order": item.display_order,
        "show_public_profile": item.show_public_profile,
    }


def _serialize_public_milestone(
    item: AboutMilestone,
) -> dict:
    return {
        "id": item.id,
        "year": item.year,
        "title": item.title,
        "description": item.description,
        "image": item.image,
        "display_order": item.display_order,
    }


def _serialize_public_value(
    item: AboutValue,
) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "description": item.description,
        "icon": item.icon,
        "display_order": item.display_order,
    }


# ============================================================
# CACHE
# ============================================================


def _invalidate_cache() -> None:
    """
    Invalidate every About-related cache entry.
    """

    cache_delete_pattern(
        f"{CACHE_PREFIX}:*"
    )


# ============================================================
# TEAM MEMBER DISPLAY ORDER
# ============================================================


def _place_team_member_in_order(
    db: Session,
    item: AboutTeamMember,
    new_order: Optional[int],
    exclude_id: Optional[int] = None,
) -> None:
    """
    Put `item` at position `new_order` and renumber ALL
    team members 1..n.

    Rules:
        - Empty / 0 -> item goes last.
        - Position greater than total -> item goes last.
        - Position below 1 -> position 1.
        - Existing item is excluded using exclude_id.

    Examples:

        1, 2, 3, 4, 5

        Move 5 -> 2:

        1, 5, 2, 3, 4

        Final:

        1, 2, 3, 4, 5

        Move 2 -> 5:

        1, 3, 4, 5, 2

        Final:

        1, 2, 3, 4, 5
    """

    query = db.query(AboutTeamMember)

    if exclude_id is not None:
        query = query.filter(
            AboutTeamMember.id != exclude_id
        )

    others = (
        query
        .order_by(
            AboutTeamMember.display_order.asc(),
            AboutTeamMember.id.asc(),
        )
        .all()
    )

    total = len(others) + 1

    if not new_order:
        position = total
    else:
        position = max(
            1,
            min(int(new_order), total),
        )

    others.insert(
        position - 1,
        item,
    )

    for index, entry in enumerate(
        others,
        start=1,
    ):
        if entry.display_order != index:
            entry.display_order = index


def _normalize_team_member_display_orders(
    db: Session,
) -> None:
    """
    Renumber every team member 1..n.

    Used after deletion and can also be used
    as a one-time cleanup utility.
    """

    entries = (
        db.query(AboutTeamMember)
        .order_by(
            AboutTeamMember.display_order.asc(),
            AboutTeamMember.id.asc(),
        )
        .all()
    )

    for index, entry in enumerate(
        entries,
        start=1,
    ):
        if entry.display_order != index:
            entry.display_order = index


# ============================================================
# PUBLIC - COMPLETE ABOUT PAGE
# ============================================================


def get_public_about_page(
    db: Session,
) -> dict:
    cache_key = (
        f"{CACHE_PREFIX}:public"
    )

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    # --------------------------------------------------------
    # About Page
    # --------------------------------------------------------

    about_page = (
        db.query(AboutPage)
        .filter(
            AboutPage.status.is_(True)
        )
        .order_by(
            AboutPage.id.asc()
        )
        .first()
    )

    if not about_page:
        raise HTTPException(
            status_code=404,
            detail="About page not found",
        )

    # --------------------------------------------------------
    # Leadership
    # --------------------------------------------------------

    leadership = (
        db.query(AboutLeadership)
        .filter(
            AboutLeadership.is_active.is_(True)
        )
        .order_by(
            AboutLeadership.display_order.asc(),
            AboutLeadership.created_at.desc(),
        )
        .all()
    )

    # --------------------------------------------------------
    # Team
    # --------------------------------------------------------

    team_members = (
        db.query(AboutTeamMember)
        .filter(
            AboutTeamMember.is_active.is_(True)
        )
        .order_by(
            AboutTeamMember.display_order.asc(),
            AboutTeamMember.created_at.desc(),
        )
        .all()
    )

    # --------------------------------------------------------
    # Milestones
    # --------------------------------------------------------

    milestones = (
        db.query(AboutMilestone)
        .filter(
            AboutMilestone.is_active.is_(True)
        )
        .order_by(
            AboutMilestone.display_order.asc(),
            AboutMilestone.year.asc(),
        )
        .all()
    )

    # --------------------------------------------------------
    # Values
    # --------------------------------------------------------

    values = (
        db.query(AboutValue)
        .filter(
            AboutValue.is_active.is_(True)
        )
        .order_by(
            AboutValue.display_order.asc(),
            AboutValue.created_at.desc(),
        )
        .all()
    )

    # --------------------------------------------------------
    # Response
    # --------------------------------------------------------

    data = {
        "about": _serialize_public_about_page(
            about_page
        ),
        "leadership": [
            _serialize_public_leadership(item)
            for item in leadership
        ],
        "team": [
            _serialize_public_team_member(item)
            for item in team_members
        ],
        "milestones": [
            _serialize_public_milestone(item)
            for item in milestones
        ],
        "values": [
            _serialize_public_value(item)
            for item in values
        ],
    }

    cache_set(
        cache_key,
        data,
    )

    return data


# ============================================================
# PUBLIC - LEADERSHIP
# ============================================================


def get_public_leadership(
    db: Session,
) -> list[dict]:
    cache_key = (
        f"{CACHE_PREFIX}:leadership:public"
    )

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    items = (
        db.query(AboutLeadership)
        .filter(
            AboutLeadership.is_active.is_(True)
        )
        .order_by(
            AboutLeadership.display_order.asc(),
            AboutLeadership.created_at.desc(),
        )
        .all()
    )

    data = [
        _serialize_public_leadership(item)
        for item in items
    ]

    cache_set(
        cache_key,
        data,
    )

    return data


def get_public_leadership_by_slug(
    db: Session,
    slug: str,
) -> dict:
    cache_key = (
        f"{CACHE_PREFIX}:leadership:slug:{slug}"
    )

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    item = (
        db.query(AboutLeadership)
        .filter(
            AboutLeadership.slug == slug,
            AboutLeadership.is_active.is_(True),
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Leadership profile not found",
        )

    data = _serialize_public_leadership(
        item
    )

    cache_set(
        cache_key,
        data,
    )

    return data


# ============================================================
# PUBLIC - TEAM MEMBERS
# ============================================================


def get_public_team_members(
    db: Session,
) -> list[dict]:
    cache_key = (
        f"{CACHE_PREFIX}:team:public"
    )

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    items = (
        db.query(AboutTeamMember)
        .filter(
            AboutTeamMember.is_active.is_(True)
        )
        .order_by(
            AboutTeamMember.display_order.asc(),
            AboutTeamMember.created_at.desc(),
        )
        .all()
    )

    data = [
        _serialize_public_team_member(item)
        for item in items
    ]

    cache_set(
        cache_key,
        data,
    )

    return data


def get_public_team_member_by_slug(
    db: Session,
    slug: str,
) -> dict:
    cache_key = (
        f"{CACHE_PREFIX}:team:slug:{slug}"
    )

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    item = (
        db.query(AboutTeamMember)
        .filter(
            AboutTeamMember.slug == slug,
            AboutTeamMember.is_active.is_(True),
            AboutTeamMember.show_public_profile.is_(True),
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Team member profile not found",
        )

    data = _serialize_public_team_member(
        item
    )

    cache_set(
        cache_key,
        data,
    )

    return data


# ============================================================
# ADMIN - ABOUT PAGE
# ============================================================


def get_about_page_admin(
    db: Session,
) -> dict:
    item = (
        db.query(AboutPage)
        .order_by(
            AboutPage.id.asc()
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="About page not found",
        )

    return _serialize_about_page(item)


def create_about_page(
    db: Session,
    payload: AboutPageCreate,
) -> AboutPage:
    existing = (
        db.query(AboutPage)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="About page already exists",
        )

    item = AboutPage(
        **payload.model_dump()
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    _invalidate_cache()

    return item


def update_about_page(
    db: Session,
    payload: AboutPageUpdate,
) -> AboutPage:
    item = (
        db.query(AboutPage)
        .order_by(
            AboutPage.id.asc()
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="About page not found",
        )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(
            item,
            field,
            value,
        )

    db.commit()
    db.refresh(item)

    _invalidate_cache()

    return item


# ============================================================
# ADMIN - LEADERSHIP
# ============================================================


def get_all_leadership_admin(
    db: Session,
) -> list[dict]:
    items = (
        db.query(AboutLeadership)
        .order_by(
            AboutLeadership.display_order.asc(),
            AboutLeadership.created_at.desc(),
        )
        .all()
    )

    return [
        _serialize_leadership(item)
        for item in items
    ]


def create_leadership(
    db: Session,
    payload: AboutLeadershipCreate,
) -> AboutLeadership:

    slug = unique_slug(
        db,
        AboutLeadership,
        payload.name,
    )

    item = AboutLeadership(
        name=payload.name,
        slug=slug,
        designation=payload.designation,
        short_bio=payload.short_bio,
        full_bio=payload.full_bio,
        image=_image_to_dict(
            payload.image
        ),
        email=payload.email,
        phone=payload.phone,
        whatsapp=payload.whatsapp,
        experience_years=payload.experience_years,
        linkedin=payload.linkedin,
        instagram=payload.instagram,
        facebook=payload.facebook,
        company_message=payload.company_message,
        display_order=payload.display_order,
        is_active=payload.is_active,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    _invalidate_cache()

    return item


def update_leadership(
    db: Session,
    item_id: int,
    payload: AboutLeadershipUpdate,
) -> AboutLeadership:

    item = (
        db.query(AboutLeadership)
        .filter(
            AboutLeadership.id == item_id
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Leadership profile not found",
        )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    update_data = _apply_image(
        update_data
    )

    for field, value in update_data.items():
        setattr(
            item,
            field,
            value,
        )

    db.commit()
    db.refresh(item)

    _invalidate_cache()

    return item


def delete_leadership(
    db: Session,
    item_id: int,
) -> None:

    item = (
        db.query(AboutLeadership)
        .filter(
            AboutLeadership.id == item_id
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Leadership profile not found",
        )

    db.delete(item)
    db.commit()

    _invalidate_cache()


# ============================================================
# ADMIN - TEAM MEMBERS
# ============================================================


def get_all_team_members_admin(
    db: Session,
) -> list[dict]:
    """
    Get ALL team members for admin.

    Important:
        is_active is NOT filtered here.

    Admin must be able to see and edit both
    active and inactive members.
    """

    items = (
        db.query(AboutTeamMember)
        .order_by(
            AboutTeamMember.display_order.asc(),
            AboutTeamMember.created_at.desc(),
        )
        .all()
    )

    return [
        _serialize_team_member(item)
        for item in items
    ]


def create_team_member(
    db: Session,
    payload: AboutTeamMemberCreate,
) -> AboutTeamMember:
    """
    Create a team member.

    display_order:
        - Requested position inserts the member there.
        - Empty / 0 puts the member last.
        - Existing members are shifted automatically.

    is_active:
        - Remains independent from display_order.
        - Admin controls whether the member is publicly visible.
    """

    slug = unique_slug(
        db,
        AboutTeamMember,
        payload.name,
    )

    item = AboutTeamMember(
        name=payload.name,
        slug=slug,
        designation=payload.designation,
        department=payload.department,
        short_description=payload.short_description,
        full_description=payload.full_description,
        image=_image_to_dict(
            payload.image
        ),
        email=payload.email,
        phone=payload.phone,
        whatsapp=payload.whatsapp,
        experience_years=payload.experience_years,
        linkedin=payload.linkedin,
        instagram=payload.instagram,
        display_order=0,
        is_active=payload.is_active,
        show_public_profile=payload.show_public_profile,
    )

    # --------------------------------------------------------
    # Insert at requested position.
    #
    # New item is not added to the DB yet, so it will not
    # appear in the query used by _place_team_member_in_order.
    # --------------------------------------------------------

    _place_team_member_in_order(
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


def update_team_member(
    db: Session,
    item_id: int,
    payload: AboutTeamMemberUpdate,
) -> AboutTeamMember:
    """
    Update a team member.

    display_order:
        If supplied, the member is moved to that position
        and all team members are renumbered 1..n.

    is_active:
        Completely independent from display_order.

        True:
            Publicly visible.

        False:
            Hidden from public website.

    show_public_profile:
        Controls whether the individual profile route is public.
    """

    item = (
        db.query(AboutTeamMember)
        .filter(
            AboutTeamMember.id == item_id
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Team member not found",
        )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    update_data = _apply_image(
        update_data
    )

    # --------------------------------------------------------
    # Display order
    #
    # Remove it from update_data because it must be handled
    # by _place_team_member_in_order().
    # --------------------------------------------------------

    has_order_change = (
        "display_order" in update_data
    )

    new_order = update_data.pop(
        "display_order",
        None,
    )

    # --------------------------------------------------------
    # Other fields
    #
    # This includes is_active.
    #
    # Therefore:
    #
    # display_order = ordering
    # is_active     = public visibility
    # --------------------------------------------------------

    for field, value in update_data.items():
        setattr(
            item,
            field,
            value,
        )

    # --------------------------------------------------------
    # Reposition member if admin changed display_order.
    # --------------------------------------------------------

    if (
        has_order_change
        and new_order is not None
    ):
        _place_team_member_in_order(
            db,
            item,
            new_order,
            exclude_id=item.id,
        )

    # --------------------------------------------------------
    # Commit update + reorder together.
    # --------------------------------------------------------

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    db.refresh(item)

    _invalidate_cache()

    return item


def delete_team_member(
    db: Session,
    item_id: int,
) -> None:
    """
    Delete a team member and close the display_order gap.
    """

    item = (
        db.query(AboutTeamMember)
        .filter(
            AboutTeamMember.id == item_id
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Team member not found",
        )

    # --------------------------------------------------------
    # Delete first.
    # --------------------------------------------------------

    db.delete(item)
    db.flush()

    # --------------------------------------------------------
    # Close the display_order gap.
    # --------------------------------------------------------

    _normalize_team_member_display_orders(
        db
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    _invalidate_cache()


def renumber_team_member_display_orders(
    db: Session,
) -> int:
    """
    One-time utility for cleaning existing team member
    display_order values.

    Example:

        Existing:
            1, 1, 4, 7, 0

        Becomes:
            1, 2, 3, 4, 5
    """

    _normalize_team_member_display_orders(
        db
    )

    db.commit()

    _invalidate_cache()

    return (
        db.query(AboutTeamMember)
        .count()
    )


# ============================================================
# ADMIN - MILESTONES
# ============================================================


def get_all_milestones_admin(
    db: Session,
) -> list[dict]:
    items = (
        db.query(AboutMilestone)
        .order_by(
            AboutMilestone.display_order.asc(),
            AboutMilestone.year.asc(),
        )
        .all()
    )

    return [
        _serialize_milestone(item)
        for item in items
    ]


def create_milestone(
    db: Session,
    payload: AboutMilestoneCreate,
) -> AboutMilestone:

    item = AboutMilestone(
        year=payload.year,
        title=payload.title,
        description=payload.description,
        image=_image_to_dict(
            payload.image
        ),
        display_order=payload.display_order,
        is_active=payload.is_active,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    _invalidate_cache()

    return item


def update_milestone(
    db: Session,
    item_id: int,
    payload: AboutMilestoneUpdate,
) -> AboutMilestone:

    item = (
        db.query(AboutMilestone)
        .filter(
            AboutMilestone.id == item_id
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Milestone not found",
        )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    update_data = _apply_image(
        update_data
    )

    for field, value in update_data.items():
        setattr(
            item,
            field,
            value,
        )

    db.commit()
    db.refresh(item)

    _invalidate_cache()

    return item


def delete_milestone(
    db: Session,
    item_id: int,
) -> None:

    item = (
        db.query(AboutMilestone)
        .filter(
            AboutMilestone.id == item_id
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Milestone not found",
        )

    db.delete(item)
    db.commit()

    _invalidate_cache()


# ============================================================
# ADMIN - VALUES
# ============================================================


def get_all_values_admin(
    db: Session,
) -> list[dict]:
    items = (
        db.query(AboutValue)
        .order_by(
            AboutValue.display_order.asc(),
            AboutValue.created_at.desc(),
        )
        .all()
    )

    return [
        _serialize_value(item)
        for item in items
    ]


def create_value(
    db: Session,
    payload: AboutValueCreate,
) -> AboutValue:

    item = AboutValue(
        title=payload.title,
        description=payload.description,
        icon=payload.icon,
        display_order=payload.display_order,
        is_active=payload.is_active,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    _invalidate_cache()

    return item


def update_value(
    db: Session,
    item_id: int,
    payload: AboutValueUpdate,
) -> AboutValue:

    item = (
        db.query(AboutValue)
        .filter(
            AboutValue.id == item_id
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Value not found",
        )

    update_data = payload.model_dump(
        exclude_unset=True
    )

    for field, value in update_data.items():
        setattr(
            item,
            field,
            value,
        )

    db.commit()
    db.refresh(item)

    _invalidate_cache()

    return item


def delete_value(
    db: Session,
    item_id: int,
) -> None:

    item = (
        db.query(AboutValue)
        .filter(
            AboutValue.id == item_id
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Value not found",
        )

    db.delete(item)
    db.commit()

    _invalidate_cache()



