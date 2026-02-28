"""Use case: Scan food image with AI."""

import io
import logging

from PIL import Image

from app.config import settings
from app.meals.infrastructure.ai_providers import get_analyzer
from app.meals.presentation import ScanResult

logger = logging.getLogger(__name__)


async def scan_food(image_bytes: bytes, mime_type: str = "image/jpeg") -> ScanResult:
    """Compress image if needed and send to AI for analysis."""
    processed = _compress_image(image_bytes)
    analyzer = get_analyzer()
    return await analyzer.analyze(processed, mime_type)


def _compress_image(image_bytes: bytes) -> bytes:
    """Resize and compress image to stay under size limits."""
    if len(image_bytes) <= settings.max_image_bytes:
        return image_bytes

    img = Image.open(io.BytesIO(image_bytes))

    # Resize keeping aspect ratio
    max_px = settings.max_image_size_px
    img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)

    # Save with reduced quality
    if img.mode == "RGBA":
        img = img.convert("RGB")

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=80, optimize=True)
    return buffer.getvalue()
