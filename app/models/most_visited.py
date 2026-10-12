

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Numeric,
    JSON,
    Enum,
    ForeignKey,
    DateTime,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.database import Base


class MostVisited(Base):
    __tablename__ = "most_visited"

    id = Column(Integer, primary_key=True, index=True)

    place_name = Column(String(150), nullable=False)

    slug = Column(
        String(180),
        unique=True,
        nullable=False,
        index=True,
    )

    image = Column(JSON, nullable=False)

    description = Column(Text, nullable=True)

    best_time_to_visit = Column(
        String(255),
        nullable=True,
    )

    starting_from = Column(
        Numeric(10, 2),
        nullable=True,
    )

    # Position among all destinations (1, 2, 3, ...).
    # Kept unique and sequential by most_visited_service._place_in_order.
    display_order = Column(
        Integer,
        nullable=False,
        default=0,
        index=True,
    )

    status = Column(
        Enum("draft", "published"),
        nullable=False,
        default="published",
    )

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
    )

    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        nullable=True,
        onupdate=func.now(),
    )

    # --------------------------------------------------
    # RELATIONSHIP WITH PACKAGES
    # --------------------------------------------------

   # model
    packages = relationship("Package", back_populates="destination_obj", passive_deletes="all")

















# # service: check first, give a useful message
# count = db.query(Package).filter(Package.destination_id == item_id).count()
# if count:
#     raise HTTPException(400, f"Cannot delete: {count} package(s) are linked to this destination.")






















