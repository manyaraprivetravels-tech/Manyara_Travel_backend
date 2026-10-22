from fastapi import (
    APIRouter,
    Depends,
    status,
)

from sqlalchemy.orm import Session

from app.db.database import get_db

from app.schemas.testimonial import (
    TestimonialCreate,
    TestimonialUpdate,
    TestimonialOut,
    TestimonialPublicCreate,
)

from app.services import testimonial_service

from app.core.deps import require_admin_or_creator

from app.models.user import User

router = APIRouter(
    prefix="/testimonials",
    tags=["Testimonials"],
)




@router.get(
    "",
    response_model=list[TestimonialOut],
)
def list_published(
    db: Session = Depends(get_db),
):
    return testimonial_service.get_published_testimonials(db)



@router.post(
    "",
    response_model=TestimonialOut,
    status_code=status.HTTP_201_CREATED,
)
def create_public(
    payload: TestimonialPublicCreate,
    db: Session = Depends(get_db),
):
    return testimonial_service.create_public_testimonial(
        db,
        payload,
    )



@router.get(
    "/admin/all",
    response_model=list[TestimonialOut],
    dependencies=[Depends(require_admin_or_creator)],
)
def list_all(
    db: Session = Depends(get_db),
):
    return testimonial_service.get_all_testimonials_admin(db)



@router.post(
    "/admin",
    response_model=TestimonialOut,
    status_code=status.HTTP_201_CREATED,
)
def create(
    payload: TestimonialCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin_or_creator),
):
    return testimonial_service.create_testimonial(
        db,
        payload,
        current_user.id,
    )




@router.put(
    "/admin/{item_id}",
    response_model=TestimonialOut,
    dependencies=[Depends(require_admin_or_creator)],
)
def update(
    item_id: int,
    payload: TestimonialUpdate,
    db: Session = Depends(get_db),
):
    return testimonial_service.update_testimonial(
        db,
        item_id,
        payload,
    )



@router.delete(
    "/admin/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin_or_creator)],
)
def delete(
    item_id: int,
    db: Session = Depends(get_db),
):
    testimonial_service.delete_testimonial(
        db,
        item_id,
    )

    return None




@router.get(
    "/{slug}",
    response_model=TestimonialOut,
)
def get_by_slug(
    slug: str,
    db: Session = Depends(get_db),
):
    return testimonial_service.get_published_testimonial_by_slug(
        db,
        slug,
    )
