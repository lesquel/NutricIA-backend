"""Learning loop domain ports (Protocol interfaces)."""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from app.learning_loop.domain.entities import ScanCorrection, UserFoodProfile


@runtime_checkable
class UserFoodProfileRepositoryPort(Protocol):
    async def get_by_user(self, user_id: uuid.UUID) -> UserFoodProfile | None: ...

    async def upsert(self, profile: UserFoodProfile) -> UserFoodProfile: ...


@runtime_checkable
class ScanCorrectionRepositoryPort(Protocol):
    async def create(self, correction: ScanCorrection) -> ScanCorrection: ...

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        limit: int,
    ) -> list[ScanCorrection]: ...

    async def list_all(self, limit: int) -> list[ScanCorrection]: ...
