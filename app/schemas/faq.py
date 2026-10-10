

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# FAQ ENUMS / TYPES
# ============================================================


FAQCategory = Literal[
    "general",
    "packages",
    "most_visited",
    "seasonal",
    "reviews",
    "about",
    "blogs",
]

FAQStatus = Literal[
    "published",
    "draft",
]


# ============================================================
# CREATE FAQ
# ============================================================


class FAQCreate(BaseModel):
    question: str = Field(
        min_length=5,
        max_length=300,
    )

    answer: str = Field(
        min_length=2,
    )

    category: FAQCategory = "general"

    display_order: int = Field(
        default=0,
        ge=0,
    )

    status: FAQStatus = "published"


# ============================================================
# UPDATE FAQ
# ============================================================


class FAQUpdate(BaseModel):
    question: Optional[str] = Field(
        default=None,
        min_length=5,
        max_length=300,
    )

    answer: Optional[str] = Field(
        default=None,
        min_length=2,
    )

    category: Optional[FAQCategory] = None

    display_order: Optional[int] = Field(
        default=None,
        ge=0,
    )

    status: Optional[FAQStatus] = None


# ============================================================
# FAQ RESPONSE
# ============================================================


class FAQOut(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int

    question: str

    answer: str

    category: FAQCategory

    display_order: int

    status: FAQStatus

    created_by: Optional[int] = None

    created_at: datetime
