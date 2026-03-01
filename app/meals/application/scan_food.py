"""Use case: Scan food image with AI."""

import io
import logging

from PIL import Image

from app.config import settings
from app.meals.infrastructure.ai_providers import analyze_food
from app.meals.presentation import ScanResult

logger = logging.getLogger(__name__)


async def scan_food(image_bytes: bytes, mime_type: str = "image/jpeg") -> ScanResult:
    """Prepare image and send to AI for analysis."""
    processed, processed_mime_type = _prepare_image_for_ai(image_bytes, mime_type)
    return await analyze_food(processed, processed_mime_type)


def _prepare_image_for_ai(image_bytes: bytes, mime_type: str) -> tuple[bytes, str]:
    """Normalize image for multimodal providers and keep payload under limits.

    Returns image bytes and the effective MIME type.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        # Fallback to original content if PIL cannot decode it.
        return image_bytes, mime_type

    max_px = settings.max_image_size_px
    img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)

    if img.mode not in ("RGB",):
        img = img.convert("RGB")

    quality = 85
    while True:
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        output = buffer.getvalue()

        if len(output) <= settings.max_image_bytes or quality <= 45:
            return output, "image/jpeg"

        quality -= 10
