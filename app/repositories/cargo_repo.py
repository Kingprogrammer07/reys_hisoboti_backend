from __future__ import annotations

import time
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.cargo import Cargo
from ..models.reys import Reys


class CargoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, cargo_id: int, include_deleted: bool = False) -> Optional[Cargo]:
        stmt = (
            select(Cargo)
            .where(Cargo.id == cargo_id)
            .options(selectinload(Cargo.reyslar))
        )
        if not include_deleted:
            stmt = stmt.where(Cargo.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str, include_deleted: bool = False) -> Optional[Cargo]:
        stmt = select(Cargo).where(func.lower(Cargo.code) == code.strip().lower())
        if not include_deleted:
            stmt = stmt.where(Cargo.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, include_deleted: bool = False) -> List[Cargo]:
        stmt = select(Cargo).options(selectinload(Cargo.reyslar)).order_by(Cargo.id.desc())
        if not include_deleted:
            stmt = stmt.where(Cargo.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, code: str) -> Cargo:
        now = int(time.time())
        cargo = Cargo(
            code=code.strip().upper(),
            created_at=now,
        )
        self.session.add(cargo)
        await self.session.flush()
        await self.session.refresh(cargo)
        return cargo

    async def update(self, cargo: Cargo, code: Optional[str] = None) -> Cargo:
        if code is not None:
            cargo.code = code.strip().upper()
        await self.session.flush()
        await self.session.refresh(cargo)
        return cargo

    async def soft_delete(self, cargo_id: int) -> bool:
        cargo = await self.get_by_id(cargo_id, include_deleted=False)
        if not cargo:
            return False
        now = int(time.time())
        cargo.deleted_at = now
        # Also cascade soft-delete to associated active reyslar
        for reys in cargo.reyslar:
            if reys.deleted_at is None:
                reys.deleted_at = now
        await self.session.flush()
        return True

    async def restore(self, cargo_id: int) -> bool:
        cargo = await self.get_by_id(cargo_id, include_deleted=True)
        if not cargo or cargo.deleted_at is None:
            return False
        cascade_deleted_at = cargo.deleted_at
        cargo.deleted_at = None
        # Un-delete associated reyslar that were deleted along with the cargo
        for reys in cargo.reyslar:
            if reys.deleted_at == cascade_deleted_at:
                reys.deleted_at = None
        await self.session.flush()
        return True
