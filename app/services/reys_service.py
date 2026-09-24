from __future__ import annotations

import time
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.activity import ActivityLog
from ..models.reys import Reys
from ..repositories.entry_repo import EntryRepository
from ..repositories.reys_repo import ReysRepository
from ..schemas.reys import ReysAdjust, ReysCreate, ReysResponse, ReysUpdate


class ReysService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ReysRepository(session)
        self.entry_repo = EntryRepository(session)

    def _to_response(self, reys: Reys) -> ReysResponse:
        return ReysResponse.model_validate(reys)

    async def list_reys(
        self,
        cargo_id: Optional[int] = None,
        include_deleted: bool = False,
    ) -> List[ReysResponse]:
        items = await self.repo.list_all(cargo_id=cargo_id, include_deleted=include_deleted)
        return [self._to_response(r) for r in items]

    async def get_reys(self, reys_id: int) -> Optional[ReysResponse]:
        reys = await self.repo.get_by_id(reys_id)
        if not reys:
            return None
        return self._to_response(reys)

    async def create_reys(self, data: ReysCreate) -> ReysResponse:
        existing = await self.repo.get_by_code(data.code)
        if existing:
            raise ValueError(f"'{data.code}' kodi bilan reys allaqachon mavjud")
        reys = await self.repo.create(
            code=data.code,
            date=data.date,
            cargo_id=data.cargo_id,
            custom_name=data.custom_name,
        )
        return self._to_response(reys)

    async def update_reys(self, reys_id: int, data: ReysUpdate) -> ReysResponse:
        reys = await self.repo.get_by_id(reys_id)
        if not reys:
            raise ValueError("Reys topilmadi")
        if data.code and data.code.strip().upper() != reys.code:
            existing = await self.repo.get_by_code(data.code)
            if existing and existing.id != reys_id:
                raise ValueError(f"'{data.code}' kodi band")
        updated = await self.repo.update(
            reys,
            code=data.code,
            date=data.date,
            custom_name=data.custom_name,
            cargo_id=data.cargo_id,
        )
        return self._to_response(updated)

    async def delete_reys(self, reys_id: int) -> bool:
        return await self.repo.soft_delete(reys_id)

    async def restore_reys(self, reys_id: int) -> bool:
        return await self.repo.restore(reys_id)

    async def adjust_reys(self, reys_id: int, data: ReysAdjust) -> ReysResponse:
        reys = await self.repo.get_by_id(reys_id)
        if not reys:
            raise ValueError("Reys topilmadi")

        if reys.original_toza_kg is None:
            reys.original_toza_kg = reys.toza_kg
        if reys.original_karobka_plus_kg is None:
            reys.original_karobka_plus_kg = reys.karobka_plus_kg

        old_toza = reys.toza_kg
        diff = round(data.actual_toza_kg - old_toza, 3)
        reys.adjustment_diff_kg = diff
        reys.toza_kg = round(data.actual_toza_kg, 3)
        reys.karobka_plus_kg = round(data.actual_karobka_plus_kg, 3)

        # Scale active entries proportionally if old_toza > 0
        if old_toza > 0 and abs(diff) > 0.0001:
            ratio = data.actual_toza_kg / old_toza
            for entry in reys.entries:
                if entry.deleted_at is None:
                    entry.net_weight = round(entry.net_weight * ratio, 3)

        # Audit log entry
        log_entry = ActivityLog(
            reys_id=reys.id,
            actor="admin",
            action="adjust",
            weight=data.actual_toza_kg,
            net=data.actual_toza_kg,
            coefficient=data.actual_karobka_plus_kg,
            created_at=int(time.time()),
        )
        self.session.add(log_entry)

        await self.session.flush()
        await self.session.refresh(reys)
        return self._to_response(reys)
