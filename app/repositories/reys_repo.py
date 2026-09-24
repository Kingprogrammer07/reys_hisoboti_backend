from __future__ import annotations

import time
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.entry import Entry
from ..models.reys import Reys


class ReysRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, reys_id: int, include_deleted: bool = False) -> Optional[Reys]:
        stmt = (
            select(Reys)
            .where(Reys.id == reys_id)
            .options(
                selectinload(Reys.entries),
                selectinload(Reys.inventory),
            )
        )
        if not include_deleted:
            stmt = stmt.where(Reys.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str, include_deleted: bool = False) -> Optional[Reys]:
        stmt = select(Reys).where(func.lower(Reys.code) == code.strip().lower())
        if not include_deleted:
            stmt = stmt.where(Reys.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(
        self,
        cargo_id: Optional[int] = None,
        include_deleted: bool = False,
    ) -> List[Reys]:
        stmt = select(Reys).order_by(Reys.id.desc())
        if cargo_id is not None:
            stmt = stmt.where(Reys.cargo_id == cargo_id)
        if not include_deleted:
            stmt = stmt.where(Reys.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        code: str,
        date: str,
        cargo_id: Optional[int] = None,
        custom_name: Optional[str] = None,
    ) -> Reys:
        now = int(time.time())
        reys = Reys(
            cargo_id=cargo_id,
            code=code.strip().upper(),
            date=date.strip(),
            custom_name=custom_name.strip() if custom_name else None,
            toza_kg=0.0,
            karobka_plus_kg=0.0,
            adjustment_diff_kg=0.0,
            created_at=now,
        )
        self.session.add(reys)
        await self.session.flush()
        await self.session.refresh(reys)
        return reys

    async def update(
        self,
        reys: Reys,
        code: Optional[str] = None,
        date: Optional[str] = None,
        custom_name: Optional[str] = None,
        cargo_id: Optional[int] = None,
    ) -> Reys:
        if code is not None:
            reys.code = code.strip().upper()
        if date is not None:
            reys.date = date.strip()
        if custom_name is not None:
            reys.custom_name = custom_name.strip() or None
        if cargo_id is not None:
            reys.cargo_id = cargo_id if cargo_id > 0 else None
        await self.session.flush()
        await self.session.refresh(reys)
        return reys

    async def soft_delete(self, reys_id: int) -> bool:
        reys = await self.get_by_id(reys_id, include_deleted=False)
        if not reys:
            return False
        now = int(time.time())
        reys.deleted_at = now
        # Also cascade to entries
        for entry in reys.entries:
            if entry.deleted_at is None:
                entry.deleted_at = now
        await self.session.flush()
        return True

    async def restore(self, reys_id: int) -> bool:
        reys = await self.get_by_id(reys_id, include_deleted=True)
        if not reys or reys.deleted_at is None:
            return False
        reys.deleted_at = None
        for entry in reys.entries:
            entry.deleted_at = None
        await self.session.flush()
        return True

    async def recompute_totals(self, reys_id: int) -> Reys:
        """Sum net_weight of active entries and update toza_kg."""
        reys = await self.get_by_id(reys_id, include_deleted=True)
        if not reys:
            raise ValueError(f"Reys {reys_id} not found")

        stmt = select(func.coalesce(func.sum(Entry.net_weight), 0.0)).where(
            Entry.reys_id == reys_id,
            Entry.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        total_net = float(result.scalar_one())
        
        reys.toza_kg = round(total_net, 3)
        await self.session.flush()
        await self.session.refresh(reys)
        return reys
