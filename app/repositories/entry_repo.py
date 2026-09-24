from __future__ import annotations

import time
from typing import List, Optional
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.entry import Entry, EntryPhoto


class EntryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, entry_id: int, include_deleted: bool = False) -> Optional[Entry]:
        stmt = (
            select(Entry)
            .where(Entry.id == entry_id)
            .options(selectinload(Entry.photos))
        )
        if not include_deleted:
            stmt = stmt.where(Entry.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_box_code(
        self,
        reys_id: int,
        box_code: str,
        include_deleted: bool = False,
    ) -> Optional[Entry]:
        stmt = select(Entry).where(
            Entry.reys_id == reys_id,
            func.lower(Entry.box_code) == box_code.strip().lower(),
        ).options(selectinload(Entry.photos))
        if not include_deleted:
            stmt = stmt.where(Entry.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_reys(
        self,
        reys_id: int,
        include_deleted: bool = False,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Entry]:
        stmt = (
            select(Entry)
            .where(Entry.reys_id == reys_id)
            .options(selectinload(Entry.photos))
            .order_by(Entry.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if not include_deleted:
            stmt = stmt.where(Entry.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        reys_id: int,
        box_code: str,
        tovar_turi: str,
        gross_weight: float,
        tare_weight: float,
        net_weight: float,
        coefficient_mode: str = "none",
        created_by: str = "operator",
    ) -> Entry:
        now = int(time.time())
        entry = Entry(
            reys_id=reys_id,
            box_code=box_code.strip(),
            tovar_turi=tovar_turi.strip().lower(),
            gross_weight=round(gross_weight, 3),
            tare_weight=round(tare_weight, 3),
            net_weight=round(net_weight, 3),
            coefficient_mode=coefficient_mode.strip().lower(),
            created_by=created_by.strip(),
            created_at=now,
        )
        self.session.add(entry)
        await self.session.flush()
        await self.session.refresh(entry)
        return entry

    async def add_photo(
        self,
        entry_id: int,
        idx: int,
        mime: str,
        size: int,
        storage_backend: str = "disk",
        storage_key: Optional[str] = None,
        telegram_file_id: Optional[str] = None,
    ) -> EntryPhoto:
        now = int(time.time())
        photo = EntryPhoto(
            entry_id=entry_id,
            idx=idx,
            mime=mime,
            size=size,
            storage_backend=storage_backend,
            storage_key=storage_key,
            telegram_file_id=telegram_file_id,
            created_at=now,
        )
        self.session.add(photo)
        await self.session.flush()
        await self.session.refresh(photo)
        return photo

    async def soft_delete(self, entry_id: int) -> bool:
        entry = await self.get_by_id(entry_id, include_deleted=False)
        if not entry:
            return False
        entry.deleted_at = int(time.time())
        await self.session.flush()
        return True

    async def restore(self, entry_id: int) -> bool:
        entry = await self.get_by_id(entry_id, include_deleted=True)
        if not entry or entry.deleted_at is None:
            return False
        entry.deleted_at = None
        await self.session.flush()
        return True
