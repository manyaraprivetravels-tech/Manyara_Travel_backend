


import enum

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)

from app.db.database import Base  # <-- use your existing Base import


class StatusEnum(str, enum.Enum):
    draft = "draft"
    published = "published"


class Testimonial(Base):
    __tablename__ = "testimonials"

    id = Column(Integer, primary_key=True, index=True)

    customer_name = Column(String(100), nullable=False)
    customer_city = Column(String(100), nullable=False)
    destination = Column(String(150), nullable=False)

    # ---- NEW: the package the review is about ----
    package_id = Column(
        Integer,
        ForeignKey("packages.id", ondelete="SET NULL"),  # drop the FK if you skipped it in SQL
        nullable=True,
        index=True,
    )
    package_slug = Column(String(255), nullable=True)
    package_title = Column(String(255), nullable=True)
    package_type = Column(String(100), nullable=True)
    region = Column(String(20), nullable=True)  # "domestic" | "international"
    # ----------------------------------------------

    slug = Column(String(255), unique=True, index=True, nullable=False)

    rating = Column(Integer, nullable=False)
    review = Column(Text, nullable=False)
    image = Column(JSON, nullable=True)  # {"url": ..., "public_id": ...}

    display_order = Column(Integer, nullable=False, default=0)
    status = Column(
        Enum(StatusEnum, name="testimonial_status"),
        nullable=False,
        default=StatusEnum.draft,
    )

    created_by = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

















































# import enum

# from sqlalchemy import (
#     Column,
#     Integer,
#     String,
#     SmallInteger,
#     Text,
#     JSON,
#     Enum,
#     ForeignKey,
#     DateTime,
#     CheckConstraint,
# )
# from sqlalchemy.sql import func

# from app.db.database import Base


# class StatusEnum(str, enum.Enum):
#     draft = "draft"
#     published = "published"


# class Testimonial(Base):
#     __tablename__ = "testimonials"

#     # ============================================================
#     # PRIMARY KEY
#     # ============================================================

#     id = Column(
#         Integer,
#         primary_key=True,
#         index=True,
#     )

#     # ============================================================
#     # CUSTOMER ATTRIBUTION
#     # ============================================================

#     customer_name = Column(
#         String(100),
#         nullable=False,
#     )

#     customer_city = Column(
#         String(100),
#         nullable=False,
#     )

#     # ============================================================
#     # DESTINATION VISITED
#     # ============================================================

#     destination = Column(
#         String(150),
#         nullable=False,
#         index=True,
#     )

    
#     slug = Column(
#         String(180),
#         nullable=True,
#         unique=True,
#         index=True,
#     )

#     # ============================================================
#     # REVIEW
#     # ============================================================

#     rating = Column(
#         SmallInteger,
#         nullable=False,
#     )

#     review = Column(
#         Text,
#         nullable=False,
#     )

#     # ============================================================
#     # OPTIONAL CUSTOMER IMAGE
#     #
#     # Example:
#     # {
#     #     "url": "...",
#     #     "public_id": "..."
#     # }
#     # ============================================================

#     image = Column(
#         JSON,
#         nullable=True,
#     )

#     # ============================================================
#     # ADMIN-CONTROLLED DISPLAY ORDER
#     #
#     # Lower number appears first.
#     # ============================================================

#     display_order = Column(
#         Integer,
#         nullable=False,
#         default=0,
#         index=True,
#     )

#     # ============================================================
#     # MODERATION
#     # ============================================================

#     status = Column(
#         Enum(StatusEnum, native_enum=False),
#         default=StatusEnum.draft,
#         nullable=False,
#         index=True,
#     )

#     # ============================================================
#     # ADMIN / CREATOR
#     # ============================================================

#     created_by = Column(
#         Integer,
#         ForeignKey("users.id"),
#         nullable=True,
#     )

#     # ============================================================
#     # TIMESTAMPS
#     # ============================================================

#     created_at = Column(
#         DateTime(timezone=True),
#         server_default=func.now(),
#     )

#     updated_at = Column(
#         DateTime(timezone=True),
#         onupdate=func.now(),
#     )

#     # ============================================================
#     # CONSTRAINTS
#     # ============================================================

#     __table_args__ = (
#         CheckConstraint(
#             "rating >= 1 AND rating <= 5",
#             name="check_testimonial_rating",
#         ),
#         CheckConstraint(
#             "display_order >= 0",
#             name="check_testimonial_display_order",
#         ),
#     )


