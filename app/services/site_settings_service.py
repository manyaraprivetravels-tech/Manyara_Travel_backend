from sqlalchemy.orm import Session

from app.models.site_settings import SiteSettings
from app.schemas.site_settings import SiteSettingsUpdate
from app.core.config import settings as app_settings
from app.core.redis_client import (
    cache_get,
    cache_set,
    cache_delete,
)

# v3: the cached payload gained address_landmark, so a new key stops any
# old cached copy from being served.
CACHE_KEY = "site_settings:singleton:v3"

# Columns that are NOT NULL in the database. If the client ever sends null for
# one of these, it is ignored instead of crashing the update.
NON_NULLABLE_FIELDS = {"top_bar_enabled", "show_address_landmark"}


def _get_or_create_row(db: Session) -> SiteSettings:
    """
    Get the singleton SiteSettings row.

    The application always uses id=1 for site settings.
    If it does not exist, create it with the default values.
    """

    row = (
        db.query(SiteSettings)
        .filter(SiteSettings.id == 1)
        .first()
    )

    if not row:
        row = SiteSettings(
            id=1,

            # ====================================================
            # Contact information
            # ====================================================
            email_address=None,
            phone_number=None,
            whatsapp_number=app_settings.WHATSAPP_NUMBER,
            company_address=None,
            address_landmark=None,
            show_address_landmark=False,
            address_url=None,

            # ====================================================
            # Website / marketing settings
            # ====================================================
            homepage_headline=(
                "Trips that feel like they were planned "
                "by a friend, not a form."
            ),
            trust_line="The two Telugu states' trusted travel company",
            offer_banner_text=None,

            # ====================================================
            # Top Info Bar
            # ====================================================
            top_bar_enabled=True,
            top_bar_location_1="Hyderabad",
            top_bar_location_2="Bengaluru",
            top_bar_traveller_text="5000+ successful travelers",

            top_bar_social_1_name="Instagram",
            top_bar_social_1_url=None,

            top_bar_social_2_name="YouTube",
            top_bar_social_2_url=None,

            top_bar_social_3_name=None,
            top_bar_social_3_url=None,

            top_bar_social_4_name=None,
            top_bar_social_4_url=None,
        )

        db.add(row)
        db.commit()
        db.refresh(row)

    return row


def get_settings(db: Session) -> dict:
    """
    Get site settings.

    Uses Redis cache first. If the cache is empty,
    fetches the singleton row from MySQL and caches it.
    """

    cached = cache_get(CACHE_KEY)

    if cached is not None:
        return cached

    row = _get_or_create_row(db)

    data = {
        # ========================================================
        # Website / marketing settings
        # ========================================================
        "offer_banner_text": row.offer_banner_text,
        "homepage_headline": row.homepage_headline,
        "trust_line": row.trust_line,

        # ========================================================
        # Top Info Bar
        # ========================================================
        "top_bar_enabled": row.top_bar_enabled,
        "top_bar_location_1": row.top_bar_location_1,
        "top_bar_location_2": row.top_bar_location_2,
        "top_bar_traveller_text": row.top_bar_traveller_text,

        "top_bar_social_1_name": row.top_bar_social_1_name,
        "top_bar_social_1_url": row.top_bar_social_1_url,

        "top_bar_social_2_name": row.top_bar_social_2_name,
        "top_bar_social_2_url": row.top_bar_social_2_url,

        "top_bar_social_3_name": row.top_bar_social_3_name,
        "top_bar_social_3_url": row.top_bar_social_3_url,

        "top_bar_social_4_name": row.top_bar_social_4_name,
        "top_bar_social_4_url": row.top_bar_social_4_url,

        # ========================================================
        # Contact information
        # ========================================================
        "email_address": row.email_address,
        "phone_number": row.phone_number,
        "whatsapp_number": row.whatsapp_number,
        "company_address": row.company_address,
        "address_landmark": row.address_landmark,
        "show_address_landmark": bool(row.show_address_landmark),
        "address_url": row.address_url,

        # ========================================================
        # Metadata
        # ========================================================
        "updated_at": row.updated_at,
    }

    cache_set(CACHE_KEY, data)

    return data


def update_settings(
    db: Session,
    payload: SiteSettingsUpdate,
) -> SiteSettings:
    """
    Update the singleton site settings row.

    Only fields explicitly provided in the request are updated.

    Redis cache is cleared after a successful update.
    """

    row = _get_or_create_row(db)

    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        # Never write null into a NOT NULL column.
        if value is None and field in NON_NULLABLE_FIELDS:
            continue

        setattr(row, field, value)

    db.commit()
    db.refresh(row)

    # Remove old cached settings so the next GET
    # retrieves the newly updated values.
    cache_delete(CACHE_KEY)

    return row