"""Learning loop presentation — FastAPI router."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.dependencies import DB, CurrentUser
from app.learning_loop.application.get_scan_metrics_use_case import (
    GetScanMetricsUseCase,
)
from app.learning_loop.infrastructure.repositories import (
    ScanCorrectionRepositoryImpl,
    UserFoodProfileRepositoryImpl,
)
from app.learning_loop.presentation import (
    ScanMetricsResponse,
    UserFoodProfileResponse,
)

router = APIRouter(tags=["learning_loop"])


def _get_admin_emails() -> set[str]:
    return {e.strip().lower() for e in settings.admin_emails.split(",") if e.strip()}


@router.get(
    "/users/me/food-profile",
    response_model=UserFoodProfileResponse,
    summary="Get current user's food profile",
)
async def get_my_food_profile(
    user: CurrentUser,
    db: DB,
) -> UserFoodProfileResponse:
    """Return the user's evolving food profile, or 404 if not yet built."""
    repo = UserFoodProfileRepositoryImpl(db)
    profile = await repo.get_by_user(user.id)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Food profile not yet built. Log some meals first.",
        )
    return UserFoodProfileResponse(
        user_id=str(profile.user_id),
        frequent_foods=profile.frequent_foods,
        avoided_tags=profile.avoided_tags,
        avg_daily_macros=profile.avg_daily_macros,
        updated_at=profile.updated_at.isoformat(),
    )


@router.get(
    "/admin/metrics/scan-confidence",
    response_model=ScanMetricsResponse,
    summary="Admin: scan confidence metrics",
)
async def get_scan_confidence_metrics(
    user: CurrentUser,
    db: DB,
    days: int = 30,
) -> ScanMetricsResponse:
    """Return scan correction metrics. Admin-only endpoint."""
    admin_emails = _get_admin_emails()
    if user.email.lower() not in admin_emails:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required.",
        )

    repo = ScanCorrectionRepositoryImpl(db)
    use_case = GetScanMetricsUseCase(repo)
    result = await use_case.execute(user_id=None, days=days)

    return ScanMetricsResponse(
        avg_confidence=result["avg_confidence"],
        count_low_confidence=result["count_low_confidence"],
        correction_rate=result["correction_rate"],
        days=result["days"],
    )
