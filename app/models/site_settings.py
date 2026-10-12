from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, text
from sqlalchemy.sql import func

from app.db.database import Base


class SiteSettings(Base):
    """Singleton table - always exactly one row (id=1)."""

    __tablename__ = "site_settings"

    id = Column(Integer, primary_key=True, index=True)

    # ============================================================
    # Website / marketing settings
    # ============================================================

    offer_banner_text = Column(String(300), nullable=True)

    homepage_headline = Column(String(200), nullable=True)

    trust_line = Column(String(200), nullable=True)

    # ============================================================
    # Top Info Bar
    # ============================================================

    # Controls whether the Top Info Bar is displayed
    # on the public website.
    top_bar_enabled = Column(
        Boolean,
        default=True,
        nullable=False,
        server_default="1",
    )

    # Locations shown in the Top Info Bar (example: Hyderabad, Bengaluru)
    top_bar_location_1 = Column(String(80), nullable=True)
    top_bar_location_2 = Column(String(80), nullable=True)

    # Trust / traveller metric (example: 5000+ successful travelers)
    top_bar_traveller_text = Column(String(100), nullable=True)

    # Social links 1-4 (column sizes match the database)
    top_bar_social_1_name = Column(String(30), nullable=True)
    top_bar_social_1_url = Column(String(500), nullable=True)

    top_bar_social_2_name = Column(String(30), nullable=True)
    top_bar_social_2_url = Column(String(500), nullable=True)

    top_bar_social_3_name = Column(String(30), nullable=True)
    top_bar_social_3_url = Column(String(500), nullable=True)

    top_bar_social_4_name = Column(String(30), nullable=True)
    top_bar_social_4_url = Column(String(500), nullable=True)

    # ============================================================
    # Contact information
    # ============================================================

    phone_number = Column(String(30), nullable=True)

    whatsapp_number = Column(String(30), nullable=True)

    email_address = Column(String(255), nullable=True)

    company_address = Column(Text, nullable=True)

    # When true, the landmark note (see frontend constants/address.js) is
    # shown under the address in the Contact section and the footer.
    show_address_landmark = Column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("0"),
    )

    address_landmark = Column(String(200), nullable=True)

    address_url = Column(String(500), nullable=True)

    # ============================================================
    # Last updated timestamp
    # ============================================================

    updated_at = Column(
        DateTime(timezone=True),
        onupdate=func.now(),
        server_default=func.now(),
    )