

import enum

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Enum,
    DateTime,
    ForeignKey,
)
from sqlalchemy.sql import func

from app.db.database import Base


# ============================================================
# POLICY TYPE
# ============================================================


class PolicyType(str, enum.Enum):
    terms_conditions = "terms_conditions"
    booking = "booking"
    cancellation = "cancellation"


# ============================================================
# POLICY STATUS
# ============================================================


class PolicyStatus(str, enum.Enum):
    draft = "draft"
    published = "published"


# ============================================================
# COMPANY POLICY
# ============================================================


class Policy(Base):
    __tablename__ = "company_policies"

    # --------------------------------------------------------
    # PRIMARY KEY
    # --------------------------------------------------------

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    # --------------------------------------------------------
    # POLICY TYPE
    # --------------------------------------------------------

    policy_type = Column(
        Enum(PolicyType, native_enum=False),
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # QUESTION / HEADING
    # --------------------------------------------------------

    question = Column(
        String(300),
        nullable=False,
    )

    # --------------------------------------------------------
    # ANSWER / CONTENT
    # --------------------------------------------------------

    answer = Column(
        Text,
        nullable=False,
    )

    # --------------------------------------------------------
    # DISPLAY ORDER
    # --------------------------------------------------------
    #
    # Lower number appears first.
    #
    # Example:
    #
    # 1 -> Booking Policy
    # 2 -> Cancellation Policy
    # 3 -> Payment Policy
    #
    # The service layer maintains this as 1..n.
    #

    display_order = Column(
        Integer,
        nullable=False,
        default=0,
        index=True,
    )

    # --------------------------------------------------------
    # STATUS
    # --------------------------------------------------------

    status = Column(
        Enum(PolicyStatus, native_enum=False),
        default=PolicyStatus.draft,
        nullable=False,
        index=True,
    )

    # --------------------------------------------------------
    # CREATED BY
    # --------------------------------------------------------

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    # --------------------------------------------------------
    # PUBLISHED AT
    # --------------------------------------------------------

    published_at = Column(
        DateTime(timezone=True),
        nullable=True,
    )

    # --------------------------------------------------------
    # TIMESTAMPS
    # --------------------------------------------------------

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
    )







