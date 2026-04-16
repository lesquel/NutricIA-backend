"""Learning loop domain public API."""

from app.learning_loop.domain.entities import ScanCorrection, UserFoodProfile
from app.learning_loop.domain.errors import (
    CorrectionValidationError,
    LearningLoopError,
    ProfileNotFoundError,
)

__all__ = [
    "ScanCorrection",
    "UserFoodProfile",
    "CorrectionValidationError",
    "LearningLoopError",
    "ProfileNotFoundError",
]
