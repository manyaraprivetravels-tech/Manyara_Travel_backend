import time
from collections import defaultdict, deque

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.core.config import settings
from app.core.deps import require_admin_or_creator
from app.services import upload_service

router = APIRouter(prefix="/uploads", tags=["Uploads"])


@router.post("/image", dependencies=[Depends(require_admin_or_creator)])
async def upload_image(file: UploadFile = File(...)):
    """Returns {url, public_id} - used by every admin image field on the site."""
    return await upload_service.save_image(file)


@router.post("/video", dependencies=[Depends(require_admin_or_creator)])
async def upload_video(file: UploadFile = File(...)):
    """Returns {url, public_id} - used for videos inside blog posts (admin only)."""
    return await upload_service.save_video(file)


WINDOW_SECONDS = 60
MAX_UPLOADS_PER_WINDOW = 5

_hits: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # Behind a proxy (Render, Railway, Nginx...) the real IP is in this header.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _enforce_rate_limit(request: Request) -> None:
    ip = _client_ip(request)
    now = time.monotonic()
    hits = _hits[ip]

    while hits and now - hits[0] > WINDOW_SECONDS:
        hits.popleft()

    if len(hits) >= MAX_UPLOADS_PER_WINDOW:
        raise HTTPException(
            status_code=429,
            detail="Too many uploads. Please wait a minute and try again.",
        )

    hits.append(now)


@router.post("/review-image")
async def upload_review_image(request: Request, file: UploadFile = File(...)):
    """Public upload for review photos. Returns {url, public_id}."""
    _enforce_rate_limit(request)

    return await upload_service.save_image(
        file,
        folder=f"{settings.CLOUDINARY_UPLOAD_FOLDER}/reviews",
        verify=True,
    )

