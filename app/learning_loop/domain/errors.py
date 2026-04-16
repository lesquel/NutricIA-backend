"""Learning loop domain errors."""

from __future__ import annotations


class LearningLoopError(Exception):
    """Base error for the learning_loop domain."""


class ProfileNotFoundError(LearningLoopError):
    """Raised when a user food profile cannot be found."""


class CorrectionValidationError(LearningLoopError):
    """Raised when a scan correction fails validation."""
