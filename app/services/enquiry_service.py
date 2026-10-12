
from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload, contains_eager

from app.models.enquiry import Enquiry
from app.models.package import Package
from app.models.package_batch import PackageBatch
from app.schemas.enquiry import EnquiryCreate


def create_enquiry(
    db: Session,
    enquiry_data: EnquiryCreate,
) -> Enquiry:
    # ---------------------------------------------------------
    # Validate selected package
    # ---------------------------------------------------------
    package = None

    if enquiry_data.package_id is not None:
        package = (
            db.query(Package)
            .filter(Package.id == enquiry_data.package_id)
            .first()
        )

        if not package:
            raise HTTPException(
                status_code=404,
                detail="Selected package not found.",
            )

    # ---------------------------------------------------------
    # Validate selected seasoned/trip if provided
    # ---------------------------------------------------------
    seasoned = None

    if enquiry_data.seasoned_id is not None:
        seasoned = (
            db.query(PackageBatch)
            .filter(PackageBatch.id == enquiry_data.seasoned_id)
            .first()
        )

        if not seasoned:
            raise HTTPException(
                status_code=404,
                detail="Selected trip/seasoned not found.",
            )

        # If a seasoned/trip is selected, make sure it belongs
        # to the selected package.
        if (
            enquiry_data.package_id is not None
            and seasoned.package_id != enquiry_data.package_id
        ):
            raise HTTPException(
                status_code=400,
                detail="Selected trip does not belong to the selected package.",
            )

    # ---------------------------------------------------------
    # Validate custom enquiry
    # ---------------------------------------------------------
    package_type = enquiry_data.package_type.strip().lower()

    if package_type == "custom":
        # Custom enquiries must not point to an existing package.
        if enquiry_data.package_id is not None:
            raise HTTPException(
                status_code=400,
                detail="Custom enquiries cannot have a package selected.",
            )

        # Custom enquiry must have a destination.
        if not enquiry_data.destination:
            raise HTTPException(
                status_code=400,
                detail="Destination is required for a custom enquiry.",
            )

        destination = enquiry_data.destination.strip()

        if not destination:
            raise HTTPException(
                status_code=400,
                detail="Destination is required for a custom enquiry.",
            )

    else:
        # -----------------------------------------------------
        # Normal package enquiry
        # -----------------------------------------------------
        destination = (
            enquiry_data.destination.strip()
            if enquiry_data.destination
            else None
        )

    # ---------------------------------------------------------
    # Create enquiry
    # ---------------------------------------------------------
    enquiry = Enquiry(
        package_id=enquiry_data.package_id,
        seasoned_id=enquiry_data.seasoned_id,
        package_type=package_type,
        destination=destination,
        name=enquiry_data.name.strip(),
        phone=enquiry_data.phone.strip(),
        adults=enquiry_data.adults,
        kids=enquiry_data.kids,
        nights=enquiry_data.nights,
        travel_date=enquiry_data.travel_date,
        message=(
            enquiry_data.message.strip()
            if enquiry_data.message
            else None
        ),
    )

    db.add(enquiry)
    db.commit()
    db.refresh(enquiry)

    return enquiry


def get_all_enquiries(
    db: Session,
):
    enquiries = (
        db.query(Enquiry)
        .options(
            joinedload(Enquiry.package),
            joinedload(Enquiry.batch),
        )
        .order_by(Enquiry.created_at.desc())
        .all()
    )

    return [
        {
            "id": enquiry.id,
            "package_id": enquiry.package_id,
            "seasoned_id": enquiry.seasoned_id,
            "package_type": enquiry.package_type,
            "destination": enquiry.destination,
            "package_title": (
                enquiry.package.title
                if enquiry.package
                else None
            ),
            "name": enquiry.name,
            "phone": enquiry.phone,
            "adults": enquiry.adults,
            "kids": enquiry.kids,
            "nights": enquiry.nights,
            "travel_date": enquiry.travel_date,
            "message": enquiry.message,
            "created_at": enquiry.created_at,
            "updated_at": enquiry.updated_at,
        }
        for enquiry in enquiries
    ]



def get_enquiries_admin_paged(
    db: Session,
    skip: int = 0,
    limit: int = 10,
    search: Optional[str] = None,
    package_type: Optional[str] = None,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
) -> dict:
    """
    Admin endpoint (paginated + filtered), newest first.

    Returns {"items": [...], "total": <count after filters>}.
    """

    # Join Package once: needed for searching by package title,
    # and contains_eager reuses it to load enquiry.package
    # (so package_title works without extra queries).
    query = (
        db.query(Enquiry)
        .outerjoin(Package, Enquiry.package_id == Package.id)
        .options(contains_eager(Enquiry.package))
    )

    # ---------------------------------------------------------
    # Search: name, phone, destination, message, package title
    # ---------------------------------------------------------

    if search and search.strip():
        like = f"%{search.strip()}%"

        query = query.filter(
            or_(
                Enquiry.name.ilike(like),
                Enquiry.phone.ilike(like),
                Enquiry.destination.ilike(like),
                Enquiry.message.ilike(like),
                Package.title.ilike(like),
            )
        )

    # ---------------------------------------------------------
    # Package type filter (pilgrimage, beach, custom, ...)
    # ---------------------------------------------------------

    if package_type and package_type != "all":
        query = query.filter(
            Enquiry.package_type == package_type.strip().lower()
        )

    # ---------------------------------------------------------
    # Date received (created_at), inclusive of both days
    # ---------------------------------------------------------

    if date_from:
        query = query.filter(
            Enquiry.created_at >= datetime.combine(date_from, time.min)
        )

    if date_to:
        query = query.filter(
            Enquiry.created_at
            < datetime.combine(date_to + timedelta(days=1), time.min)
        )

    # ---------------------------------------------------------
    # Total BEFORE offset/limit
    # ---------------------------------------------------------

    total = query.count()

    items = (
        query
        .order_by(
            Enquiry.created_at.desc(),
            Enquiry.id.desc(),  # stable tiebreaker for paging
        )
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "items": items,
        "total": total,
    }


def get_enquiry_stats_admin(db: Session) -> dict:
    """
    Counts for the admin summary cards.
    created_at is stored in UTC, so rolling windows are used
    instead of "today" to avoid timezone confusion.
    """

    now = datetime.utcnow()

    total = db.query(func.count(Enquiry.id)).scalar() or 0

    last_24h = (
        db.query(func.count(Enquiry.id))
        .filter(Enquiry.created_at >= now - timedelta(hours=24))
        .scalar()
        or 0
    )

    last_7_days = (
        db.query(func.count(Enquiry.id))
        .filter(Enquiry.created_at >= now - timedelta(days=7))
        .scalar()
        or 0
    )

    custom = (
        db.query(func.count(Enquiry.id))
        .filter(Enquiry.package_type == "custom")
        .scalar()
        or 0
    )

    return {
        "total": total,
        "last_24h": last_24h,
        "last_7_days": last_7_days,
        "custom": custom,
    }












def get_enquiry_by_id(
    db: Session,
    enquiry_id: int,
):
    return (
        db.query(Enquiry)
        .options(
            joinedload(Enquiry.package),
            joinedload(Enquiry.batch),
        )
        .filter(Enquiry.id == enquiry_id)
        .first()
    )



def delete_enquiry(
    db: Session,
    enquiry_id: int,
):
    enquiry = get_enquiry_by_id(
        db,
        enquiry_id,
    )

    if not enquiry:
        return None

    db.delete(enquiry)
    db.commit()

    return enquiry
