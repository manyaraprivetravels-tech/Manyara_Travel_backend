"""
Image uploads via Cloudinary.

Every image field on the site (packages, destinations, blog covers,
happy moments, testimonial photos) goes through save_image() below and gets
back {url, public_id}.

Changes from the previous version (all backwards compatible):
  * save_image() takes optional `folder` and `verify` arguments.
  * The file is read with a size cap, so an oversized upload is rejected
    without loading the whole thing into memory.
  * verify=True checks the bytes really are a JPEG/PNG/WebP image
    (content_type comes from the client and can be faked).
  * The blocking Cloudinary call runs in a thread pool so uploads don't
    stall other requests.

  * save_video() uploads blog videos (admin only, larger size limit).

Requires Pillow:  pip install pillow
"""

import io
import logging

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from app.core.config import settings

logger = logging.getLogger("app.uploads")

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp" , "image/avif"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP","AVIF"}
ALLOWED_VIDEO_CONTENT_TYPES = {"video/mp4", "video/webm", "video/quicktime"}

# Videos are bigger than photos. Override with MAX_VIDEO_UPLOAD_MB in .env / Settings.
DEFAULT_MAX_VIDEO_UPLOAD_MB = 50

_configured = False


def _ensure_configured() -> None:
    global _configured
    if _configured:
        return
    if not (
        settings.CLOUDINARY_CLOUD_NAME
        and settings.CLOUDINARY_API_KEY
        and settings.CLOUDINARY_API_SECRET
    ):
        raise HTTPException(
            status_code=500,
            detail=(
                "Image uploads aren't configured yet - set CLOUDINARY_CLOUD_NAME, "
                "CLOUDINARY_API_KEY, and CLOUDINARY_API_SECRET in .env (see .env.example)."
            ),
        )
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )
    _configured = True


def _verify_is_image(contents: bytes) -> None:
    """Raises 400 unless the bytes are really a JPEG, PNG or WebP image."""
    try:
        with Image.open(io.BytesIO(contents)) as img:
            image_format = img.format
            img.verify()
    except (
        UnidentifiedImageError,
        Image.DecompressionBombError,
        OSError,
        ValueError,
        SyntaxError,
    ):
        raise HTTPException(status_code=400, detail="That file isn't a valid image.")

    if image_format not in ALLOWED_IMAGE_FORMATS:
        raise HTTPException(
            status_code=400, detail="Only JPEG, PNG,WebP or AVIF images are allowed."
        )


async def save_image(
    file: UploadFile,
    folder: str | None = None,
    verify: bool = False,
) -> dict:
    """Uploads to Cloudinary and returns {url, public_id}.

    folder: Cloudinary folder (defaults to settings.CLOUDINARY_UPLOAD_FOLDER).
    verify: also check the bytes are a real image (use for public endpoints).
    """
    _ensure_configured()

    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400, detail="Only JPEG, PNG,WebP or AVIF images are allowed."
        )

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024

    # Read one byte past the limit so we can tell "too big" without
    # loading a huge file into memory.
    contents = await file.read(max_bytes + 1)

    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"Image is too large - max {settings.MAX_UPLOAD_MB}MB.",
        )

    if verify:
        _verify_is_image(contents)

    try:
        result = await run_in_threadpool(
            cloudinary.uploader.upload,
            contents,
            folder=folder or settings.CLOUDINARY_UPLOAD_FOLDER,
            resource_type="image",
            # Cloudinary auto-generates a unique public_id unless we pass one,
            # which is exactly what we want here (no filename collisions).
        )
    except Exception as exc:
        logger.error("Cloudinary upload failed: %s", exc)
        raise HTTPException(
            status_code=502, detail="Image upload failed - please try again."
        )

    return {"url": result["secure_url"], "public_id": result["public_id"]}


async def save_video(file: UploadFile, folder: str | None = None) -> dict:
    """Uploads a video (MP4 / WebM / MOV) to Cloudinary and returns {url, public_id}.

    Admin use only (blog videos). Photos keep using save_image().
    """
    _ensure_configured()

    if file.content_type not in ALLOWED_VIDEO_CONTENT_TYPES:
        raise HTTPException(
            status_code=400, detail="Only MP4, WebM, or MOV videos are allowed."
        )

    max_mb = getattr(settings, "MAX_VIDEO_UPLOAD_MB", DEFAULT_MAX_VIDEO_UPLOAD_MB)
    max_bytes = max_mb * 1024 * 1024

    contents = await file.read(max_bytes + 1)

    if len(contents) > max_bytes:
        raise HTTPException(
            status_code=400, detail=f"Video is too large - max {max_mb}MB."
        )

    try:
        result = await run_in_threadpool(
            cloudinary.uploader.upload,
            contents,
            folder=f"{folder or settings.CLOUDINARY_UPLOAD_FOLDER}/videos",
            resource_type="video",
        )
    except Exception as exc:
        logger.error("Cloudinary video upload failed: %s", exc)
        raise HTTPException(
            status_code=502, detail="Video upload failed - please try again."
        )

    return {"url": result["secure_url"], "public_id": result["public_id"]}


def delete_image(public_id: str, resource_type: str = "image") -> None:
    """Best-effort cleanup - e.g. when an admin replaces a package's cover photo.

    Pass resource_type="video" to delete a video.
    """
    if not public_id:
        return
    _ensure_configured()
    try:
        cloudinary.uploader.destroy(public_id, resource_type=resource_type)
    except Exception as exc:
        logger.warning("Cloudinary delete failed for %s: %s", public_id, exc)
