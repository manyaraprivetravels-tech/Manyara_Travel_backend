from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SiteSettingsUpdate(BaseModel):
    # ============================================================
    # Website / marketing settings
    # ============================================================

    offer_banner_text: Optional[str] = None
    homepage_headline: Optional[str] = None
    trust_line: Optional[str] = None

    # ============================================================
    # Top Info Bar
    # ============================================================

    # Show / hide the Top Info Bar on the public website
    top_bar_enabled: Optional[bool] = None

    # Locations displayed in the Top Info Bar
    # Example: Hyderabad / Bengaluru
    top_bar_location_1: Optional[str] = None
    top_bar_location_2: Optional[str] = None

    # Example: 5000+ successful travelers
    top_bar_traveller_text: Optional[str] = None

    # Social media links 1-4 (platform name + profile URL)
    top_bar_social_1_name: Optional[str] = None
    top_bar_social_1_url: Optional[str] = None

    top_bar_social_2_name: Optional[str] = None
    top_bar_social_2_url: Optional[str] = None

    top_bar_social_3_name: Optional[str] = None
    top_bar_social_3_url: Optional[str] = None

    top_bar_social_4_name: Optional[str] = None
    top_bar_social_4_url: Optional[str] = None

    # ============================================================
    # Contact information
    # ============================================================

    email_address: Optional[str] = None
    phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    company_address: Optional[str] = None

    # Show the landmark note under the address (Contact section + footer).
    # None = not sent, so the saved value is left unchanged.
    address_landmark: Optional[str] = None
    show_address_landmark: Optional[bool] = None

    address_url: Optional[str] = None


class SiteSettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # ============================================================
    # Website / marketing settings
    # ============================================================

    offer_banner_text: Optional[str] = None
    homepage_headline: Optional[str] = None
    trust_line: Optional[str] = None

    # ============================================================
    # Top Info Bar
    # ============================================================

    top_bar_enabled: Optional[bool] = None

    top_bar_location_1: Optional[str] = None
    top_bar_location_2: Optional[str] = None

    top_bar_traveller_text: Optional[str] = None

    top_bar_social_1_name: Optional[str] = None
    top_bar_social_1_url: Optional[str] = None

    top_bar_social_2_name: Optional[str] = None
    top_bar_social_2_url: Optional[str] = None

    top_bar_social_3_name: Optional[str] = None
    top_bar_social_3_url: Optional[str] = None

    top_bar_social_4_name: Optional[str] = None
    top_bar_social_4_url: Optional[str] = None

    # ============================================================
    # Contact information
    # ============================================================

    email_address: Optional[str] = None
    phone_number: Optional[str] = None
    whatsapp_number: Optional[str] = None
    company_address: Optional[str] = None
    address_landmark: Optional[str] = None
    show_address_landmark: bool = False
    address_url: Optional[str] = None

    # ============================================================
    # Metadata
    # ============================================================

    updated_at: Optional[datetime] = None
    