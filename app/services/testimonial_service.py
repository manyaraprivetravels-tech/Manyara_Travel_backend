

from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.testimonial import Testimonial, StatusEnum
from app.schemas.testimonial import (
    TestimonialPublicCreate,
    TestimonialCreate,
    TestimonialUpdate,
)
from app.core.redis_client import (
    cache_get,
    cache_set,
    cache_delete_pattern,
)
from app.core.slugify import unique_slug

CACHE_PREFIX = "testimonials"


# ============================================================
# SERIALIZER
# ============================================================


def _serialize(t: Testimonial) -> dict:
    """
    Convert a Testimonial SQLAlchemy object into a
    JSON-serializable dictionary.
    """

    return {
        "id": t.id,
        "customer_name": t.customer_name,
        "customer_city": t.customer_city,
        "destination": t.destination,
        "package_id": t.package_id,
        "package_slug": t.package_slug,
        "package_title": t.package_title,
        "package_type": t.package_type,
        "region": t.region,
        "slug": t.slug,
        "rating": t.rating,
        "review": t.review,
        "image": t.image,
        "display_order": t.display_order,
        "status": (t.status.value if t.status else None),
        "created_by": t.created_by,
        "created_at": (t.created_at.isoformat() if t.created_at else None),
        "updated_at": (t.updated_at.isoformat() if t.updated_at else None),
    }


def _package_fields(payload) -> dict:
    """
    The package columns shared by public and admin creation.
    """

    return {
        "package_id": payload.package_id,
        "package_slug": payload.package_slug,
        "package_title": payload.package_title,
        "package_type": payload.package_type,
        "region": payload.region,
    }


# ============================================================
# CACHE
# ============================================================


def _invalidate_cache() -> None:
    """
    Remove all testimonial-related cached data.

    This clears:
        testimonials:published
        testimonials:slug:<slug>
        any future testimonial cache keys
    """

    cache_delete_pattern(f"{CACHE_PREFIX}:*")


# ============================================================
# PUBLIC - GET PUBLISHED TESTIMONIALS
# ============================================================


def get_published_testimonials(
    db: Session,
) -> list[dict]:
    """
    Return all published testimonials for the public website.

    Ordered by:
        1. display_order ASC
        2. created_at DESC
    """

    cache_key = f"{CACHE_PREFIX}:published"

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    items = (
        db.query(Testimonial)
        .filter(Testimonial.status == StatusEnum.published)
        .order_by(
            Testimonial.display_order.asc(),
            Testimonial.created_at.desc(),
        )
        .all()
    )

    data = [_serialize(t) for t in items]

    cache_set(
        cache_key,
        data,
    )

    return data


# ============================================================
# PUBLIC - GET SINGLE TESTIMONIAL BY SLUG
# ============================================================


def get_published_testimonial_by_slug(
    db: Session,
    slug: str,
) -> dict:
    """
    Return one published testimonial by its SEO-friendly slug.

    Used by:
        GET /testimonials/{slug}

    Draft testimonials are never exposed through this function.
    """

    cache_key = f"{CACHE_PREFIX}:slug:{slug}"

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    item = (
        db.query(Testimonial)
        .filter(
            Testimonial.slug == slug,
            Testimonial.status == StatusEnum.published,
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Testimonial not found",
        )

    data = _serialize(item)

    cache_set(
        cache_key,
        data,
    )

    return data


# ============================================================
# ADMIN - GET ALL TESTIMONIALS
# ============================================================


def get_all_testimonials_admin(
    db: Session,
) -> list[dict]:
    """
    Return all testimonials for the admin panel.

    Includes:
        - draft
        - published
    """

    items = (
        db.query(Testimonial)
        .order_by(
            Testimonial.display_order.asc(),
            Testimonial.created_at.desc(),
        )
        .all()
    )

    return [_serialize(t) for t in items]


# ============================================================
# PUBLIC - SUBMIT TESTIMONIAL
# ============================================================


def create_public_testimonial(
    db: Session,
    payload: TestimonialPublicCreate,
) -> Testimonial:
    """
    Create a testimonial submitted from the public website.

    Public submissions always:
        - generate a slug automatically
        - start as draft
        - have display_order = 0
        - have created_by = None

    Admin must publish the review before it becomes public.
    """

    slug = unique_slug(
        db=db,
        model=Testimonial,
        base_text=(f"{payload.customer_name}-" f"{payload.destination}"),
    )

    item = Testimonial(
        customer_name=payload.customer_name,
        customer_city=payload.customer_city,
        destination=payload.destination,
        **_package_fields(payload),
        slug=slug,
        rating=payload.rating,
        review=payload.review,
        image=(payload.image.model_dump() if payload.image else None),
        # Public submissions always start as draft.
        display_order=0,
        status=StatusEnum.draft,
        # Visitor is not an admin/creator.
        created_by=None,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    _invalidate_cache()

    return item


# ============================================================
# ADMIN - CREATE TESTIMONIAL
# ============================================================


def create_testimonial(
    db: Session,
    payload: TestimonialCreate,
    user_id: int,
) -> Testimonial:
    """
    Create a testimonial from the admin/creator panel.

    Slug is generated automatically from:

        customer_name + destination

    Example:
        Rahul Kumar + Kashmir
        -> rahul-kumar-kashmir
    """

    slug = unique_slug(
        db=db,
        model=Testimonial,
        base_text=(f"{payload.customer_name}-" f"{payload.destination}"),
    )

    item = Testimonial(
        customer_name=payload.customer_name,
        customer_city=payload.customer_city,
        destination=payload.destination,
        **_package_fields(payload),
        slug=slug,
        rating=payload.rating,
        review=payload.review,
        image=(payload.image.model_dump() if payload.image else None),
        display_order=payload.display_order,
        status=payload.status,
        created_by=user_id,
    )

    db.add(item)
    db.commit()
    db.refresh(item)

    _invalidate_cache()

    return item


# ============================================================
# ADMIN - UPDATE TESTIMONIAL
# ============================================================


def update_testimonial(
    db: Session,
    item_id: int,
    payload: TestimonialUpdate,
) -> Testimonial:
    """
    Update an existing testimonial.

    IMPORTANT:
    The slug is NOT regenerated when customer_name or
    destination changes.

    This keeps existing public URLs stable.

    Example:

        /reviews/rahul-kumar-kashmir

    remains valid even if an admin later changes the
    customer's display name or destination text.
    """

    item = db.query(Testimonial).filter(Testimonial.id == item_id).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Testimonial not found",
        )

    update_data = payload.model_dump(exclude_unset=True)

    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    if "image" in update_data:

        if update_data["image"] is not None:

            update_data["image"] = (
                update_data["image"].model_dump()
                if hasattr(
                    update_data["image"],
                    "model_dump",
                )
                else update_data["image"]
            )

    # --------------------------------------------------------
    # UPDATE FIELDS (package_* and region are included
    # automatically because they are part of the schema)
    # --------------------------------------------------------

    for field, value in update_data.items():

        setattr(
            item,
            field,
            value,
        )

    # --------------------------------------------------------
    # DO NOT CHANGE item.slug HERE
    # --------------------------------------------------------

    db.commit()
    db.refresh(item)

    _invalidate_cache()

    return item


# ============================================================
# ADMIN - DELETE TESTIMONIAL
# ============================================================


def delete_testimonial(
    db: Session,
    item_id: int,
) -> None:
    """
    Delete a testimonial permanently.
    """

    item = db.query(Testimonial).filter(Testimonial.id == item_id).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Testimonial not found",
        )

    db.delete(item)
    db.commit()

    _invalidate_cache()
















































# from sqlalchemy.orm import Session
# from fastapi import HTTPException

# from app.models.testimonial import Testimonial, StatusEnum
# from app.schemas.testimonial import (
#     TestimonialPublicCreate,
#     TestimonialCreate,
#     TestimonialUpdate,
# )
# from app.core.redis_client import (
#     cache_get,
#     cache_set,
#     cache_delete_pattern,
# )
# from app.core.slugify import unique_slug

# CACHE_PREFIX = "testimonials"


# # ============================================================
# # SERIALIZER
# # ============================================================


# def _serialize(t: Testimonial) -> dict:
#     """
#     Convert a Testimonial SQLAlchemy object into a
#     JSON-serializable dictionary.
#     """

#     return {
#         "id": t.id,
#         "customer_name": t.customer_name,
#         "customer_city": t.customer_city,
#         "destination": t.destination,
#         "slug": t.slug,
#         "rating": t.rating,
#         "review": t.review,
#         "image": t.image,
#         "display_order": t.display_order,
#         "status": (t.status.value if t.status else None),
#         "created_by": t.created_by,
#         "created_at": (t.created_at.isoformat() if t.created_at else None),
#         "updated_at": (t.updated_at.isoformat() if t.updated_at else None),
#     }


# # ============================================================
# # CACHE
# # ============================================================


# def _invalidate_cache() -> None:
#     """
#     Remove all testimonial-related cached data.

#     This clears:
#         testimonials:published
#         testimonials:slug:<slug>
#         any future testimonial cache keys
#     """

#     cache_delete_pattern(f"{CACHE_PREFIX}:*")


# # ============================================================
# # PUBLIC - GET PUBLISHED TESTIMONIALS
# # ============================================================


# def get_published_testimonials(
#     db: Session,
# ) -> list[dict]:
#     """
#     Return all published testimonials for the public website.

#     Ordered by:
#         1. display_order ASC
#         2. created_at DESC
#     """

#     cache_key = f"{CACHE_PREFIX}:published"

#     cached = cache_get(cache_key)

#     if cached is not None:
#         return cached

#     items = (
#         db.query(Testimonial)
#         .filter(Testimonial.status == StatusEnum.published)
#         .order_by(
#             Testimonial.display_order.asc(),
#             Testimonial.created_at.desc(),
#         )
#         .all()
#     )

#     data = [_serialize(t) for t in items]

#     cache_set(
#         cache_key,
#         data,
#     )

#     return data


# # ============================================================
# # PUBLIC - GET SINGLE TESTIMONIAL BY SLUG
# # ============================================================


# def get_published_testimonial_by_slug(
#     db: Session,
#     slug: str,
# ) -> dict:
#     """
#     Return one published testimonial by its SEO-friendly slug.

#     Used by:
#         GET /testimonials/{slug}

#     Draft testimonials are never exposed through this function.
#     """

#     cache_key = f"{CACHE_PREFIX}:slug:{slug}"

#     cached = cache_get(cache_key)

#     if cached is not None:
#         return cached

#     item = (
#         db.query(Testimonial)
#         .filter(
#             Testimonial.slug == slug,
#             Testimonial.status == StatusEnum.published,
#         )
#         .first()
#     )

#     if not item:
#         raise HTTPException(
#             status_code=404,
#             detail="Testimonial not found",
#         )

#     data = _serialize(item)

#     cache_set(
#         cache_key,
#         data,
#     )

#     return data


# # ============================================================
# # ADMIN - GET ALL TESTIMONIALS
# # ============================================================


# def get_all_testimonials_admin(
#     db: Session,
# ) -> list[dict]:
#     """
#     Return all testimonials for the admin panel.

#     Includes:
#         - draft
#         - published
#     """

#     items = (
#         db.query(Testimonial)
#         .order_by(
#             Testimonial.display_order.asc(),
#             Testimonial.created_at.desc(),
#         )
#         .all()
#     )

#     return [_serialize(t) for t in items]


# # ============================================================
# # PUBLIC - SUBMIT TESTIMONIAL
# # ============================================================


# def create_public_testimonial(
#     db: Session,
#     payload: TestimonialPublicCreate,
# ) -> Testimonial:
#     """
#     Create a testimonial submitted from the public website.

#     Public submissions always:
#         - generate a slug automatically
#         - start as draft
#         - have display_order = 0
#         - have created_by = None

#     Admin must publish the review before it becomes public.
#     """

#     slug = unique_slug(
#         db=db,
#         model=Testimonial,
#         base_text=(f"{payload.customer_name}-" f"{payload.destination}"),
#     )

#     item = Testimonial(
#         customer_name=payload.customer_name,
#         customer_city=payload.customer_city,
#         destination=payload.destination,
#         slug=slug,
#         rating=payload.rating,
#         review=payload.review,
#         image=(payload.image.model_dump() if payload.image else None),
#         # Public submissions always start as draft.
#         display_order=0,
#         status=StatusEnum.draft,
#         # Visitor is not an admin/creator.
#         created_by=None,
#     )

#     db.add(item)
#     db.commit()
#     db.refresh(item)

#     _invalidate_cache()

#     return item


# # ============================================================
# # ADMIN - CREATE TESTIMONIAL
# # ============================================================


# def create_testimonial(
#     db: Session,
#     payload: TestimonialCreate,
#     user_id: int,
# ) -> Testimonial:
#     """
#     Create a testimonial from the admin/creator panel.

#     Slug is generated automatically from:

#         customer_name + destination

#     Example:
#         Rahul Kumar + Kashmir
#         -> rahul-kumar-kashmir
#     """

#     slug = unique_slug(
#         db=db,
#         model=Testimonial,
#         base_text=(f"{payload.customer_name}-" f"{payload.destination}"),
#     )

#     item = Testimonial(
#         customer_name=payload.customer_name,
#         customer_city=payload.customer_city,
#         destination=payload.destination,
#         slug=slug,
#         rating=payload.rating,
#         review=payload.review,
#         image=(payload.image.model_dump() if payload.image else None),
#         display_order=payload.display_order,
#         status=payload.status,
#         created_by=user_id,
#     )

#     db.add(item)
#     db.commit()
#     db.refresh(item)

#     _invalidate_cache()

#     return item


# # ============================================================
# # ADMIN - UPDATE TESTIMONIAL
# # ============================================================


# def update_testimonial(
#     db: Session,
#     item_id: int,
#     payload: TestimonialUpdate,
# ) -> Testimonial:
#     """
#     Update an existing testimonial.

#     IMPORTANT:
#     The slug is NOT regenerated when customer_name or
#     destination changes.

#     This keeps existing public URLs stable.

#     Example:

#         /reviews/rahul-kumar-kashmir

#     remains valid even if an admin later changes the
#     customer's display name or destination text.
#     """

#     item = db.query(Testimonial).filter(Testimonial.id == item_id).first()

#     if not item:
#         raise HTTPException(
#             status_code=404,
#             detail="Testimonial not found",
#         )

#     update_data = payload.model_dump(exclude_unset=True)

#     # --------------------------------------------------------
#     # IMAGE
#     # --------------------------------------------------------

#     if "image" in update_data:

#         if update_data["image"] is not None:

#             update_data["image"] = (
#                 update_data["image"].model_dump()
#                 if hasattr(
#                     update_data["image"],
#                     "model_dump",
#                 )
#                 else update_data["image"]
#             )

#     # --------------------------------------------------------
#     # UPDATE FIELDS
#     # --------------------------------------------------------

#     for field, value in update_data.items():

#         setattr(
#             item,
#             field,
#             value,
#         )

#     # --------------------------------------------------------
#     # DO NOT CHANGE item.slug HERE
#     # --------------------------------------------------------
#     #
#     # Slug remains stable after creation.
#     #
#     # This prevents broken URLs when:
#     # - customer name changes
#     # - destination changes
#     #
#     # --------------------------------------------------------

#     db.commit()
#     db.refresh(item)

#     _invalidate_cache()

#     return item


# # ============================================================
# # ADMIN - DELETE TESTIMONIAL
# # ============================================================


# def delete_testimonial(
#     db: Session,
#     item_id: int,
# ) -> None:
#     """
#     Delete a testimonial permanently.
#     """

#     item = db.query(Testimonial).filter(Testimonial.id == item_id).first()

#     if not item:
#         raise HTTPException(
#             status_code=404,
#             detail="Testimonial not found",
#         )

#     db.delete(item)
#     db.commit()

#     _invalidate_cache()
