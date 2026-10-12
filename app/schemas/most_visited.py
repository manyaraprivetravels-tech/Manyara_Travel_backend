

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# ENUMS
# ============================================================


class StatusEnum(str, Enum):
    draft = "draft"
    published = "published"


class PackageTypeEnum(str, Enum):
    pilgrimage = "pilgrimage"
    mountains_adventure = "mountains_adventure"
    romantic = "romantic"
    international = "international"
    beach = "beach"
    family = "family"
    wildlife_nature = "wildlife_nature"


# ============================================================
# IMAGE OBJECT
# ============================================================


class ImageObject(BaseModel):
    """
    Matches the image JSON object stored in the database
    and returned by the image upload endpoint.
    """

    url: str = Field(
        min_length=1,
    )

    public_id: Optional[str] = None


# ============================================================
# CREATE MOST VISITED DESTINATION
# ============================================================


class MostVisitedCreate(BaseModel):
    place_name: str = Field(
        min_length=2,
        max_length=150,
    )

    image: ImageObject

    description: Optional[str] = None

    best_time_to_visit: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    starting_from: Optional[Decimal] = Field(
        default=None,
        ge=0,
    )

    display_order: int = Field(
        default=0,
        ge=0,
    )

    status: StatusEnum = StatusEnum.published


# ============================================================
# UPDATE MOST VISITED DESTINATION
# ============================================================


class MostVisitedUpdate(BaseModel):
    place_name: Optional[str] = Field(
        default=None,
        min_length=2,
        max_length=150,
    )

    image: Optional[ImageObject] = None

    description: Optional[str] = None

    best_time_to_visit: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    starting_from: Optional[Decimal] = Field(
        default=None,
        ge=0,
    )

    display_order: Optional[int] = Field(
        default=None,
        ge=0,
    )

    status: Optional[StatusEnum] = None


# ============================================================
# PACKAGE SUMMARY INSIDE DESTINATION
# ============================================================


class MostVisitedPackageOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    # ---------------------------------------------------------
    # Basic package information
    # ---------------------------------------------------------

    id: int

    title: str

    slug: str

    # Relationship
    destination_id: int

    # ---------------------------------------------------------
    # Pricing & duration
    # ---------------------------------------------------------

    price: Decimal

    duration_days: int

    duration_nights: int

    # ---------------------------------------------------------
    # Content
    # ---------------------------------------------------------

    description: Optional[str] = None

    images: list[ImageObject] = Field(
        default_factory=list,
    )

    # ---------------------------------------------------------
    # Package classification
    # ---------------------------------------------------------

    package_type: PackageTypeEnum

    display_order: int

    status: StatusEnum

    # ---------------------------------------------------------
    # Discovery collections
    # ---------------------------------------------------------

    is_popular: bool

    is_recommended: bool

    is_trending: bool

    is_featured: bool

    is_new: bool

    is_most_visited: bool


# ============================================================
# MOST VISITED DESTINATION OUTPUT
# ============================================================


class MostVisitedOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    # ---------------------------------------------------------
    # Basic destination information
    # ---------------------------------------------------------

    id: int

    place_name: str

    slug: str

    # ---------------------------------------------------------
    # Destination image
    # ---------------------------------------------------------

    image: ImageObject

    # ---------------------------------------------------------
    # Destination content
    # ---------------------------------------------------------

    description: Optional[str] = None

    best_time_to_visit: Optional[str] = None

    starting_from: Optional[Decimal] = None

    # ---------------------------------------------------------
    # Display / publishing
    # ---------------------------------------------------------

    display_order: int

    status: StatusEnum

    # ---------------------------------------------------------
    # Metadata
    # ---------------------------------------------------------

    created_by: Optional[int] = None

    created_at: datetime

    updated_at: Optional[datetime] = None

    # ---------------------------------------------------------
    # Packages belonging to this destination
    # ---------------------------------------------------------

    packages: list[MostVisitedPackageOut] = Field(
        default_factory=list,
    )


# ============================================================
# ADMIN LIST (PAGINATED) + STATS
# ============================================================


class MostVisitedListOut(BaseModel):
    items: list[MostVisitedOut]
    total: int


class MostVisitedStatsOut(BaseModel):
    total: int
    published: int
    draft: int