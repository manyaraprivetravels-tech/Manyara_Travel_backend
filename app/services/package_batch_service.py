

from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.package import Package, StatusEnum
from app.models.package_batch import (
    PackageBatch,
    BatchStatusEnum,
    BatchDurationModeEnum,
    BatchPriceModeEnum,
    BatchItineraryModeEnum,
    BatchInclusionsModeEnum,
    BatchExclusionsModeEnum,
    BatchTermsModeEnum,
    BatchCancellationModeEnum,
)
from app.schemas.package_batch import (
    PackageBatchCreate,
    PackageBatchUpdate,
)
from app.core.redis_client import (
    cache_get,
    cache_set,
    cache_delete_pattern,
)
from app.core.slugify import unique_slug


CACHE_PREFIX = "package_batches"


# ============================================================
# SLUG
# ============================================================


def _generate_batch_slug(
    db: Session,
    package: Package,
    departure_date: date,
    batch_id: Optional[int] = None,
) -> str:
    """
    Generate a unique slug for a package batch.

    Example:
        kerala-backwaters-hills-2026-10-10
    """

    base_slug = f"{package.slug}-{departure_date.isoformat()}"

    return unique_slug(
        db=db,
        model=PackageBatch,
        base_text=base_slug,
        exclude_id=batch_id,
    )


# ============================================================
# DISPLAY ORDER
# ============================================================
#
# Display order is PER PACKAGE.
#
# Example:
#
# Package A:
#   Batch 1 -> 1
#   Batch 2 -> 2
#   Batch 3 -> 3
#
# Package B:
#   Batch 4 -> 1
#   Batch 5 -> 2
#
# ============================================================


def _normalize_package(
    db: Session,
    package_id: int,
    exclude_id: Optional[int] = None,
) -> None:
    """
    Normalize all batches belonging to one package.

    This fixes existing 0 / duplicate / missing display_order
    values and converts them into:

        1, 2, 3, 4, ...

    Ordering priority:
        1. Existing display_order
        2. Departure date
        3. ID

    exclude_id can be used when a batch is temporarily being
    repositioned.
    """

    query = (
        db.query(PackageBatch)
        .filter(PackageBatch.package_id == package_id)
    )

    if exclude_id is not None:
        query = query.filter(PackageBatch.id != exclude_id)

    entries = (
        query
        .order_by(
            PackageBatch.display_order.asc(),
            PackageBatch.departure_date.asc(),
            PackageBatch.id.asc(),
        )
        .all()
    )

    for index, entry in enumerate(entries, start=1):
        entry.display_order = index


def _place_in_order(
    db: Session,
    batch: PackageBatch,
    new_order: Optional[int],
    package_id: int,
    exclude_id: Optional[int] = None,
) -> None:
    """
    Place a batch at a requested position inside one package.

    IMPORTANT:
    Existing batches are normalized first.

    This means even if the database currently contains:

        0
        0
        0

    editing one batch to position 2 will correctly result in:

        1
        2
        3

    If new_order is:
        None / 0 -> batch goes last
        1         -> first
        2         -> second
        3         -> third
        > total   -> last

    The batch itself does not need to already be in the database.
    """

    # --------------------------------------------------------
    # First normalize existing batches
    # --------------------------------------------------------

    _normalize_package(
        db=db,
        package_id=package_id,
        exclude_id=exclude_id,
    )

    # --------------------------------------------------------
    # Get normalized batches excluding current batch
    # --------------------------------------------------------

    query = (
        db.query(PackageBatch)
        .filter(PackageBatch.package_id == package_id)
    )

    if exclude_id is not None:
        query = query.filter(PackageBatch.id != exclude_id)

    others = (
        query
        .order_by(
            PackageBatch.display_order.asc(),
            PackageBatch.departure_date.asc(),
            PackageBatch.id.asc(),
        )
        .all()
    )

    # --------------------------------------------------------
    # Calculate position
    # --------------------------------------------------------

    total = len(others) + 1

    if not new_order:
        position = total
    else:
        position = max(
            1,
            min(int(new_order), total),
        )

    # --------------------------------------------------------
    # Insert batch into requested position
    # --------------------------------------------------------

    others.insert(
        position - 1,
        batch,
    )

    # --------------------------------------------------------
    # Renumber EVERYTHING
    # --------------------------------------------------------

    for index, entry in enumerate(
        others,
        start=1,
    ):
        entry.display_order = index


# ============================================================
# SERIALIZATION
# ============================================================


def _serialize(
    batch: PackageBatch,
    include_package: bool = True,
) -> dict:
    """
    Convert PackageBatch SQLAlchemy object into JSON-safe data.

    Batch custom values are used when their corresponding mode
    is custom.

    Otherwise values are inherited from the parent Package.
    """

    package = batch.package

    # --------------------------------------------------------
    # Duration
    # --------------------------------------------------------

    if batch.duration_mode == BatchDurationModeEnum.custom:
        duration_days = batch.days
        duration_nights = batch.nights
    else:
        duration_days = (
            package.duration_days
            if package
            else None
        )

        duration_nights = (
            package.duration_nights
            if package
            else None
        )

    # --------------------------------------------------------
    # Price
    # --------------------------------------------------------

    if batch.price_mode == BatchPriceModeEnum.custom:
        price = (
            str(batch.price_per_person)
            if batch.price_per_person is not None
            else None
        )
    else:
        price = (
            str(package.price)
            if package and package.price is not None
            else None
        )

    # --------------------------------------------------------
    # Itinerary
    # --------------------------------------------------------

    if batch.itinerary_mode == BatchItineraryModeEnum.custom:
        itinerary = batch.custom_itinerary or []
    else:
        itinerary = (
            package.itinerary or []
            if package
            else []
        )

    # --------------------------------------------------------
    # Inclusions
    # --------------------------------------------------------

    if batch.inclusions_mode == BatchInclusionsModeEnum.custom:
        inclusions = batch.custom_inclusions or []
    else:
        inclusions = (
            package.inclusions or []
            if package
            else []
        )

    # --------------------------------------------------------
    # Exclusions
    # --------------------------------------------------------

    if batch.exclusions_mode == BatchExclusionsModeEnum.custom:
        exclusions = batch.custom_exclusions or []
    else:
        exclusions = (
            package.exclusions or []
            if package
            else []
        )

    # --------------------------------------------------------
    # Terms
    # --------------------------------------------------------

    if batch.terms_mode == BatchTermsModeEnum.custom:
        terms_and_conditions = (
            batch.custom_terms_and_conditions or []
        )
    else:
        terms_and_conditions = (
            package.terms_and_conditions or []
            if package
            else []
        )

    # --------------------------------------------------------
    # Cancellation
    # --------------------------------------------------------

    if batch.cancellation_mode == BatchCancellationModeEnum.custom:
        cancellation_policy = (
            batch.custom_cancellation_policy or []
        )
    else:
        cancellation_policy = (
            package.cancellation_policy or []
            if package
            else []
        )

    # --------------------------------------------------------
    # Base response
    # --------------------------------------------------------

    data = {
        "id": batch.id,
        "package_id": batch.package_id,
        "slug": batch.slug,

        # Display order
        "display_order": batch.display_order,

        # Dates
        "departure_date": (
            batch.departure_date.isoformat()
            if batch.departure_date
            else None
        ),
        "return_date": (
            batch.return_date.isoformat()
            if batch.return_date
            else None
        ),

        # Duration
        "duration_mode": (
            batch.duration_mode.value
            if batch.duration_mode
            else None
        ),
        "duration_days": duration_days,
        "duration_nights": duration_nights,
        "days": batch.days,
        "nights": batch.nights,

        # Price
        "price_mode": (
            batch.price_mode.value
            if batch.price_mode
            else None
        ),
        "price_per_person": price,

        # Itinerary
        "itinerary_mode": (
            batch.itinerary_mode.value
            if batch.itinerary_mode
            else None
        ),
        "itinerary": itinerary,
        "custom_itinerary": (
            batch.custom_itinerary or []
            if batch.itinerary_mode
            == BatchItineraryModeEnum.custom
            else None
        ),

        # Inclusions
        "inclusions_mode": (
            batch.inclusions_mode.value
            if batch.inclusions_mode
            else None
        ),
        "inclusions": inclusions,
        "custom_inclusions": (
            batch.custom_inclusions or []
            if batch.inclusions_mode
            == BatchInclusionsModeEnum.custom
            else None
        ),

        # Exclusions
        "exclusions_mode": (
            batch.exclusions_mode.value
            if batch.exclusions_mode
            else None
        ),
        "exclusions": exclusions,
        "custom_exclusions": (
            batch.custom_exclusions or []
            if batch.exclusions_mode
            == BatchExclusionsModeEnum.custom
            else None
        ),

        # Terms
        "terms_mode": (
            batch.terms_mode.value
            if batch.terms_mode
            else None
        ),
        "terms_and_conditions": terms_and_conditions,
        "custom_terms_and_conditions": (
            batch.custom_terms_and_conditions or []
            if batch.terms_mode
            == BatchTermsModeEnum.custom
            else None
        ),

        # Cancellation
        "cancellation_mode": (
            batch.cancellation_mode.value
            if batch.cancellation_mode
            else None
        ),
        "cancellation_policy": cancellation_policy,
        "custom_cancellation_policy": (
            batch.custom_cancellation_policy or []
            if batch.cancellation_mode
            == BatchCancellationModeEnum.custom
            else None
        ),

        # Availability
        "availability": (
            batch.availability.value
            if hasattr(batch.availability, "value")
            else batch.availability
        ),

        # Status
        "status": (
            batch.status.value
            if batch.status
            else None
        ),

        # Metadata
        "created_at": (
            batch.created_at.isoformat()
            if batch.created_at
            else None
        ),
        "updated_at": (
            batch.updated_at.isoformat()
            if batch.updated_at
            else None
        ),
    }

    # --------------------------------------------------------
    # Parent package
    # --------------------------------------------------------

    if include_package and package:
        data["package"] = {
            "id": package.id,
            "title": package.title,
            "slug": package.slug,
            "destination": package.destination,
            "package_type": (
                package.package_type.value
                if package.package_type
                else None
            ),
            "images": package.images or [],
        }

    return data


# ============================================================
# CACHE
# ============================================================


def _invalidate_cache() -> None:
    """
    Delete every package_batches cache key.
    """

    cache_delete_pattern(
        f"{CACHE_PREFIX}:*"
    )


# ============================================================
# VALIDATION
# ============================================================


def _validate_dates(
    departure_date: date,
    return_date: date,
) -> None:
    """
    Validate travel dates.
    """

    if return_date < departure_date:
        raise HTTPException(
            status_code=400,
            detail="Return date cannot be before departure date.",
        )


def _validate_modes(
    duration_mode,
    days,
    nights,
    price_mode,
    price_per_person,
    itinerary_mode,
    custom_itinerary,
    inclusions_mode,
    custom_inclusions,
    exclusions_mode,
    custom_exclusions,
    terms_mode,
    custom_terms_and_conditions,
    cancellation_mode,
    custom_cancellation_policy,
) -> None:
    """
    Validate custom-mode requirements.
    """

    # --------------------------------------------------------
    # Duration
    # --------------------------------------------------------

    if duration_mode == BatchDurationModeEnum.custom:

        if days is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "days is required when "
                    "duration_mode is custom."
                ),
            )

        if nights is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "nights is required when "
                    "duration_mode is custom."
                ),
            )

    # --------------------------------------------------------
    # Price
    # --------------------------------------------------------

    if price_mode == BatchPriceModeEnum.custom:

        if price_per_person is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    "price_per_person is required when "
                    "price_mode is custom."
                ),
            )

    # --------------------------------------------------------
    # Itinerary
    # --------------------------------------------------------

    if itinerary_mode == BatchItineraryModeEnum.custom:

        if not custom_itinerary:
            raise HTTPException(
                status_code=400,
                detail=(
                    "custom_itinerary is required when "
                    "itinerary_mode is custom."
                ),
            )

    # --------------------------------------------------------
    # Inclusions
    # --------------------------------------------------------

    if inclusions_mode == BatchInclusionsModeEnum.custom:

        if not custom_inclusions:
            raise HTTPException(
                status_code=400,
                detail=(
                    "custom_inclusions is required when "
                    "inclusions_mode is custom."
                ),
            )

    # --------------------------------------------------------
    # Exclusions
    # --------------------------------------------------------

    if exclusions_mode == BatchExclusionsModeEnum.custom:

        if not custom_exclusions:
            raise HTTPException(
                status_code=400,
                detail=(
                    "custom_exclusions is required when "
                    "exclusions_mode is custom."
                ),
            )

    # --------------------------------------------------------
    # Terms
    # --------------------------------------------------------

    if terms_mode == BatchTermsModeEnum.custom:

        if not custom_terms_and_conditions:
            raise HTTPException(
                status_code=400,
                detail=(
                    "custom_terms_and_conditions is required "
                    "when terms_mode is custom."
                ),
            )

    # --------------------------------------------------------
    # Cancellation
    # --------------------------------------------------------

    if cancellation_mode == BatchCancellationModeEnum.custom:

        if not custom_cancellation_policy:
            raise HTTPException(
                status_code=400,
                detail=(
                    "custom_cancellation_policy is required "
                    "when cancellation_mode is custom."
                ),
            )


# ============================================================
# PACKAGE
# ============================================================


def _get_package(
    db: Session,
    package_id: int,
) -> Package:
    """
    Get parent package.
    """

    package = (
        db.query(Package)
        .filter(Package.id == package_id)
        .first()
    )

    if not package:
        raise HTTPException(
            status_code=404,
            detail="Package not found",
        )

    return package


# ============================================================
# PUBLIC — GET UPCOMING BATCHES
# ============================================================


def get_upcoming_batches(
    db: Session,
) -> list[dict]:
    """
    Return future published batches belonging to
    published packages.
    """

    cache_key = f"{CACHE_PREFIX}:upcoming"

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    today = date.today()

    batches = (
        db.query(PackageBatch)
        .join(
            Package,
            Package.id == PackageBatch.package_id,
        )
        .filter(
            PackageBatch.status == BatchStatusEnum.published,
            PackageBatch.departure_date > today,
            Package.status == StatusEnum.published,
        )
        .order_by(
            PackageBatch.departure_date.asc(),
            PackageBatch.display_order.asc(),
        )
        .all()
    )

    data = [
        _serialize(batch)
        for batch in batches
    ]

    cache_set(
        cache_key,
        data,
    )

    return data


# ============================================================
# PUBLIC — GET PACKAGE BATCHES
# ============================================================


def get_package_batches(
    db: Session,
    package_id: int,
) -> list[dict]:
    """
    Get upcoming published batches for one package.

    Ordered by display_order.
    """

    package = _get_package(
        db,
        package_id,
    )

    if package.status != StatusEnum.published:
        raise HTTPException(
            status_code=404,
            detail="Package not found",
        )

    cache_key = (
        f"{CACHE_PREFIX}:package:{package_id}"
    )

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    today = date.today()

    batches = (
        db.query(PackageBatch)
        .filter(
            PackageBatch.package_id == package_id,
            PackageBatch.status == BatchStatusEnum.published,
            PackageBatch.departure_date > today,
        )
        .order_by(
            PackageBatch.display_order.asc(),
            PackageBatch.departure_date.asc(),
        )
        .all()
    )

    data = [
        _serialize(batch)
        for batch in batches
    ]

    cache_set(
        cache_key,
        data,
    )

    return data


# ============================================================
# PUBLIC — GET BATCH BY SLUG
# ============================================================


def get_package_batch_by_slug(
    db: Session,
    slug: str,
) -> dict:
    """
    Public batch lookup by slug.
    """

    cache_key = (
        f"{CACHE_PREFIX}:slug:{slug}"
    )

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    today = date.today()

    batch = (
        db.query(PackageBatch)
        .join(
            Package,
            Package.id == PackageBatch.package_id,
        )
        .filter(
            PackageBatch.slug == slug,
            PackageBatch.status == BatchStatusEnum.published,
            PackageBatch.departure_date > today,
            Package.status == StatusEnum.published,
        )
        .first()
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Package batch not found",
        )

    data = _serialize(batch)

    cache_set(
        cache_key,
        data,
    )

    return data


# ============================================================
# ADMIN — GET BATCH BY ID
# ============================================================


def get_package_batch_by_id(
    db: Session,
    batch_id: int,
) -> dict:
    """
    Get any batch by ID.

    Used by admin editing.
    """

    cache_key = (
        f"{CACHE_PREFIX}:id:{batch_id}"
    )

    cached = cache_get(cache_key)

    if cached is not None:
        return cached

    batch = (
        db.query(PackageBatch)
        .filter(PackageBatch.id == batch_id)
        .first()
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Package batch not found",
        )

    data = _serialize(batch)

    cache_set(
        cache_key,
        data,
    )

    return data


# ============================================================
# ADMIN — GET ALL BATCHES
# ============================================================


def get_all_batches_admin(
    db: Session,
) -> list[dict]:
    """
    Admin view.

    Includes:
        - draft
        - published
        - expired

    Grouped by package and ordered by display_order.
    """

    batches = (
        db.query(PackageBatch)
        .order_by(
            PackageBatch.package_id.asc(),
            PackageBatch.display_order.asc(),
            PackageBatch.departure_date.asc(),
            PackageBatch.id.asc(),
        )
        .all()
    )

    return [
        _serialize(batch)
        for batch in batches
    ]


# ============================================================
# CREATE BATCH
# ============================================================


def create_package_batch(
    db: Session,
    payload: PackageBatchCreate,
) -> PackageBatch:
    """
    Create a new package batch.

    The batch is inserted into the requested position
    within its package.

    Existing batches are automatically renumbered.
    """

    # --------------------------------------------------------
    # Package
    # --------------------------------------------------------

    package = _get_package(
        db,
        payload.package_id,
    )

    # --------------------------------------------------------
    # Dates
    # --------------------------------------------------------

    _validate_dates(
        payload.departure_date,
        payload.return_date,
    )

    # --------------------------------------------------------
    # Modes
    # --------------------------------------------------------

    _validate_modes(
        payload.duration_mode,
        payload.days,
        payload.nights,
        payload.price_mode,
        payload.price_per_person,
        payload.itinerary_mode,
        payload.custom_itinerary,
        payload.inclusions_mode,
        payload.custom_inclusions,
        payload.exclusions_mode,
        payload.custom_exclusions,
        payload.terms_mode,
        payload.custom_terms_and_conditions,
        payload.cancellation_mode,
        payload.custom_cancellation_policy,
    )

    # --------------------------------------------------------
    # Slug
    # --------------------------------------------------------

    batch_slug = _generate_batch_slug(
        db,
        package,
        payload.departure_date,
    )

    # --------------------------------------------------------
    # Custom itinerary
    # --------------------------------------------------------

    custom_itinerary = None

    if (
        payload.itinerary_mode
        == BatchItineraryModeEnum.custom
    ):
        custom_itinerary = [
            item.model_dump()
            for item in payload.custom_itinerary
        ]

    # --------------------------------------------------------
    # Custom inclusions
    # --------------------------------------------------------

    custom_inclusions = None

    if (
        payload.inclusions_mode
        == BatchInclusionsModeEnum.custom
    ):
        custom_inclusions = payload.custom_inclusions

    # --------------------------------------------------------
    # Custom exclusions
    # --------------------------------------------------------

    custom_exclusions = None

    if (
        payload.exclusions_mode
        == BatchExclusionsModeEnum.custom
    ):
        custom_exclusions = payload.custom_exclusions

    # --------------------------------------------------------
    # Custom terms
    # --------------------------------------------------------

    custom_terms_and_conditions = None

    if (
        payload.terms_mode
        == BatchTermsModeEnum.custom
    ):
        custom_terms_and_conditions = (
            payload.custom_terms_and_conditions
        )

    # --------------------------------------------------------
    # Custom cancellation
    # --------------------------------------------------------

    custom_cancellation_policy = None

    if (
        payload.cancellation_mode
        == BatchCancellationModeEnum.custom
    ):
        custom_cancellation_policy = (
            payload.custom_cancellation_policy
        )

    # --------------------------------------------------------
    # Create batch
    # --------------------------------------------------------

    batch = PackageBatch(
        package_id=package.id,
        slug=batch_slug,

        # Temporary value.
        # _place_in_order() will assign the real order.
        display_order=0,

        departure_date=payload.departure_date,
        return_date=payload.return_date,

        # Duration
        duration_mode=payload.duration_mode,
        days=(
            payload.days
            if payload.duration_mode
            == BatchDurationModeEnum.custom
            else None
        ),
        nights=(
            payload.nights
            if payload.duration_mode
            == BatchDurationModeEnum.custom
            else None
        ),

        # Price
        price_mode=payload.price_mode,
        price_per_person=(
            payload.price_per_person
            if payload.price_mode
            == BatchPriceModeEnum.custom
            else None
        ),

        # Itinerary
        itinerary_mode=payload.itinerary_mode,
        custom_itinerary=custom_itinerary,

        # Inclusions
        inclusions_mode=payload.inclusions_mode,
        custom_inclusions=custom_inclusions,

        # Exclusions
        exclusions_mode=payload.exclusions_mode,
        custom_exclusions=custom_exclusions,

        # Terms
        terms_mode=payload.terms_mode,
        custom_terms_and_conditions=(
            custom_terms_and_conditions
        ),

        # Cancellation
        cancellation_mode=payload.cancellation_mode,
        custom_cancellation_policy=(
            custom_cancellation_policy
        ),

        # Availability
        availability=(
            payload.availability.value
            if payload.availability
            and hasattr(payload.availability, "value")
            else payload.availability
        ),

        # Status
        status=payload.status,
    )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Add the batch BEFORE reordering.
    #
    # This allows SQLAlchemy to track the new object and
    # makes the transaction easier to reason about.
    # --------------------------------------------------------

    db.add(batch)

    # Flush gives the object its identity without committing.
    db.flush()

    # --------------------------------------------------------
    # Place batch in requested position
    # --------------------------------------------------------

    _place_in_order(
        db=db,
        batch=batch,
        new_order=getattr(
            payload,
            "display_order",
            None,
        ),
        package_id=package.id,
        exclude_id=batch.id,
    )

    # --------------------------------------------------------
    # Commit
    # --------------------------------------------------------

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise

    db.refresh(batch)

    # --------------------------------------------------------
    # Cache
    # --------------------------------------------------------

    _invalidate_cache()

    return batch


# ============================================================
# UPDATE BATCH
# ============================================================


def update_package_batch(
    db: Session,
    batch_id: int,
    payload: PackageBatchUpdate,
) -> PackageBatch:
    """
    Update an existing package batch.

    Display order behavior:

        Current:
            1
            2
            3

        Edit batch 3 -> display_order = 1

        Result:
            1
            2
            3

    The moved batch becomes position 1 and the other
    batches shift automatically.

    If the database contains old 0 values, they are
    normalized before applying the requested position.
    """

    # --------------------------------------------------------
    # Find batch
    # --------------------------------------------------------

    batch = (
        db.query(PackageBatch)
        .filter(PackageBatch.id == batch_id)
        .first()
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Package batch not found",
        )

    # --------------------------------------------------------
    # Convert payload
    # --------------------------------------------------------

    update_data = payload.model_dump(
        exclude_unset=True
    )

    # --------------------------------------------------------
    # Original package
    # --------------------------------------------------------

    old_package_id = batch.package_id

    # --------------------------------------------------------
    # Validate package if changed
    # --------------------------------------------------------

    if "package_id" in update_data:
        _get_package(
            db,
            update_data["package_id"],
        )

    final_package_id = update_data.get(
        "package_id",
        batch.package_id,
    )

    final_package = _get_package(
        db,
        final_package_id,
    )

    # --------------------------------------------------------
    # Final dates
    # --------------------------------------------------------

    final_departure_date = update_data.get(
        "departure_date",
        batch.departure_date,
    )

    final_return_date = update_data.get(
        "return_date",
        batch.return_date,
    )

    _validate_dates(
        final_departure_date,
        final_return_date,
    )

    # ========================================================
    # Final modes
    # ========================================================

    final_duration_mode = update_data.get(
        "duration_mode",
        batch.duration_mode,
    )

    final_price_mode = update_data.get(
        "price_mode",
        batch.price_mode,
    )

    final_itinerary_mode = update_data.get(
        "itinerary_mode",
        batch.itinerary_mode,
    )

    final_inclusions_mode = update_data.get(
        "inclusions_mode",
        batch.inclusions_mode,
    )

    final_exclusions_mode = update_data.get(
        "exclusions_mode",
        batch.exclusions_mode,
    )

    final_terms_mode = update_data.get(
        "terms_mode",
        batch.terms_mode,
    )

    final_cancellation_mode = update_data.get(
        "cancellation_mode",
        batch.cancellation_mode,
    )

    # ========================================================
    # Final custom values
    # ========================================================

    final_days = update_data.get(
        "days",
        batch.days,
    )

    final_nights = update_data.get(
        "nights",
        batch.nights,
    )

    final_price = update_data.get(
        "price_per_person",
        batch.price_per_person,
    )

    final_itinerary = update_data.get(
        "custom_itinerary",
        batch.custom_itinerary,
    )

    final_inclusions = update_data.get(
        "custom_inclusions",
        batch.custom_inclusions,
    )

    final_exclusions = update_data.get(
        "custom_exclusions",
        batch.custom_exclusions,
    )

    final_terms_and_conditions = update_data.get(
        "custom_terms_and_conditions",
        batch.custom_terms_and_conditions,
    )

    final_cancellation_policy = update_data.get(
        "custom_cancellation_policy",
        batch.custom_cancellation_policy,
    )

    # ========================================================
    # Validate modes
    # ========================================================

    _validate_modes(
        final_duration_mode,
        final_days,
        final_nights,
        final_price_mode,
        final_price,
        final_itinerary_mode,
        final_itinerary,
        final_inclusions_mode,
        final_inclusions,
        final_exclusions_mode,
        final_exclusions,
        final_terms_mode,
        final_terms_and_conditions,
        final_cancellation_mode,
        final_cancellation_policy,
    )

    # ========================================================
    # Convert itinerary
    # ========================================================

    if (
        final_itinerary_mode
        == BatchItineraryModeEnum.custom
        and final_itinerary is not None
    ):
        final_itinerary = [
            item
            if isinstance(item, dict)
            else item.model_dump()
            for item in final_itinerary
        ]

    # ========================================================
    # Clear duration when default
    # ========================================================

    if (
        final_duration_mode
        == BatchDurationModeEnum.default
    ):
        update_data["days"] = None
        update_data["nights"] = None

    # ========================================================
    # Clear price when default
    # ========================================================

    if (
        final_price_mode
        == BatchPriceModeEnum.default
    ):
        update_data["price_per_person"] = None

    # ========================================================
    # Clear itinerary when default
    # ========================================================

    if (
        final_itinerary_mode
        == BatchItineraryModeEnum.default
    ):
        update_data["custom_itinerary"] = None

    elif "custom_itinerary" in update_data:
        update_data["custom_itinerary"] = final_itinerary

    # ========================================================
    # Clear inclusions when default
    # ========================================================

    if (
        final_inclusions_mode
        == BatchInclusionsModeEnum.default
    ):
        update_data["custom_inclusions"] = None

    # ========================================================
    # Clear exclusions when default
    # ========================================================

    if (
        final_exclusions_mode
        == BatchExclusionsModeEnum.default
    ):
        update_data["custom_exclusions"] = None

    # ========================================================
    # Clear terms when default
    # ========================================================

    if (
        final_terms_mode
        == BatchTermsModeEnum.default
    ):
        update_data["custom_terms_and_conditions"] = None

    # ========================================================
    # Clear cancellation when default
    # ========================================================

    if (
        final_cancellation_mode
        == BatchCancellationModeEnum.default
    ):
        update_data["custom_cancellation_policy"] = None

    # ========================================================
    # Availability
    # ========================================================

    if "availability" in update_data:

        availability = update_data["availability"]

        if hasattr(availability, "value"):
            update_data["availability"] = (
                availability.value
            )

    # ========================================================
    # Slug
    # ========================================================

    package_changed = (
        final_package_id != batch.package_id
    )

    departure_changed = (
        final_departure_date
        != batch.departure_date
    )

    if package_changed or departure_changed:

        update_data["slug"] = _generate_batch_slug(
            db,
            final_package,
            final_departure_date,
            batch_id=batch.id,
        )

    # ========================================================
    # Display order
    # ========================================================

    has_order_change = (
        "display_order" in update_data
    )

    new_order = update_data.pop(
        "display_order",
        None,
    )

    # ========================================================
    # Apply normal updates
    # ========================================================

    for field, value in update_data.items():
        setattr(
            batch,
            field,
            value,
        )

    # --------------------------------------------------------
    # Flush normal field changes
    # --------------------------------------------------------

    db.flush()

    # ========================================================
    # DISPLAY ORDER
    # ========================================================

    if package_changed:

        # ----------------------------------------------------
        # Remove batch from old package's sequence.
        # ----------------------------------------------------

        _normalize_package(
            db=db,
            package_id=old_package_id,
            exclude_id=batch.id,
        )

        # ----------------------------------------------------
        # Place batch into new package.
        # ----------------------------------------------------

        _place_in_order(
            db=db,
            batch=batch,
            new_order=(
                new_order
                if has_order_change
                else None
            ),
            package_id=final_package_id,
            exclude_id=batch.id,
        )

    elif has_order_change:

        # ----------------------------------------------------
        # Same package:
        # normalize + reposition.
        # ----------------------------------------------------

        _place_in_order(
            db=db,
            batch=batch,
            new_order=new_order,
            package_id=final_package_id,
            exclude_id=batch.id,
        )

    # --------------------------------------------------------
    # If display_order was not supplied and package did not
    # change, preserve the existing order.
    # --------------------------------------------------------

    else:

        # If this batch had a legacy 0 order, normalize its
        # package so old 0 values don't remain.
        if batch.display_order == 0:

            _place_in_order(
                db=db,
                batch=batch,
                new_order=None,
                package_id=final_package_id,
                exclude_id=batch.id,
            )

    # ========================================================
    # Commit
    # ========================================================

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise

    db.refresh(batch)

    # ========================================================
    # Cache
    # ========================================================

    _invalidate_cache()

    return batch


# ============================================================
# DELETE BATCH
# ============================================================


def delete_package_batch(
    db: Session,
    batch_id: int,
) -> None:
    """
    Delete a batch and close the display_order gap.
    """

    batch = (
        db.query(PackageBatch)
        .filter(PackageBatch.id == batch_id)
        .first()
    )

    if not batch:
        raise HTTPException(
            status_code=404,
            detail="Package batch not found",
        )

    package_id = batch.package_id

    # --------------------------------------------------------
    # Delete
    # --------------------------------------------------------

    db.delete(batch)

    db.flush()

    # --------------------------------------------------------
    # Normalize remaining batches
    # --------------------------------------------------------

    _normalize_package(
        db,
        package_id,
    )

    # --------------------------------------------------------
    # Commit
    # --------------------------------------------------------

    try:
        db.commit()

    except Exception:
        db.rollback()
        raise

    # --------------------------------------------------------
    # Cache
    # --------------------------------------------------------

    _invalidate_cache()


# ============================================================
# ONE-TIME UTILITY
# ============================================================


def renumber_display_orders(
    db: Session,
) -> int:
    """
    One-time utility.

    Fixes existing display_order values.

    Every package receives its own:

        1, 2, 3, ...

    Existing ordering is preserved where possible.
    Zero/duplicate values are resolved using:

        display_order
        departure_date
        id
    """

    package_ids = [
        row[0]
        for row in (
            db.query(
                PackageBatch.package_id
            )
            .distinct()
            .all()
        )
    ]

    for package_id in package_ids:

        _normalize_package(
            db,
            package_id,
        )

    db.commit()

    _invalidate_cache()

    return (
        db.query(PackageBatch)
        .count()
    )









