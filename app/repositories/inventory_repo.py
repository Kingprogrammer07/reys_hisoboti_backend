from __future__ import annotations

import time
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.inventory import CustomType, Inventory


class InventoryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_reys_and_type(self, reys_id: int, tovar_turi: str) -> Optional[Inventory]:
        stmt = select(Inventory).where(
            Inventory.reys_id == reys_id,
            func.lower(Inventory.tovar_turi) == tovar_turi.strip().lower(),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_reys(self, reys_id: int) -> List[Inventory]:
        stmt = (
            select(Inventory)
            .where(Inventory.reys_id == reys_id)
            .order_by(Inventory.tovar_turi.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_inventory(
        self,
        reys_id: int,
        tovar_turi: str,
        weight_delta: float,
        count_delta: int = 1,
        box_coefficient: float = 1.0,
    ) -> Inventory:
        now = int(time.time())
        inv = await self.get_by_reys_and_type(reys_id, tovar_turi)
        if inv is None:
            inv = Inventory(
                reys_id=reys_id,
                tovar_turi=tovar_turi.strip().lower(),
                weight=round(weight_delta, 3),
                package_count=max(0, count_delta),
                box_coefficient=box_coefficient,
                updated_at=now,
            )
            self.session.add(inv)
        else:
            inv.weight = round(inv.weight + weight_delta, 3)
            inv.package_count = max(0, inv.package_count + count_delta)
            if box_coefficient > 0:
                inv.box_coefficient = box_coefficient
            inv.updated_at = now
        await self.session.flush()
        await self.session.refresh(inv)
        return inv

    async def list_custom_types(self) -> List[CustomType]:
        stmt = (
            select(CustomType)
            .where(CustomType.deleted_at.is_(None))
            .order_by(CustomType.name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def add_custom_type(self, name: str) -> CustomType:
        now = int(time.time())
        clean_name = name.strip().lower()
        stmt = select(CustomType).where(CustomType.name == clean_name)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.deleted_at = None
            await self.session.flush()
            return existing
        ct = CustomType(name=clean_name, created_at=now)
        self.session.add(ct)
        await self.session.flush()
        await self.session.refresh(ct)
        return ct

    async def delete_custom_type(self, name: str) -> bool:
        clean_name = name.strip().lower()
        stmt = select(CustomType).where(CustomType.name == clean_name)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if not existing or existing.deleted_at is not None:
            return False
        existing.deleted_at = int(time.time())
        await self.session.flush()
        return True
