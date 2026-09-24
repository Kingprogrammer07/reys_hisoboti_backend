from __future__ import annotations

import time
from typing import Any, Dict, List
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.activity import ActivityLog
from ..models.cargo import Cargo
from ..models.entry import Entry
from ..models.reys import Reys


class RecycleBinRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_deleted_items(self) -> List[Dict[str, Any]]:
        now = int(time.time())
        items: List[Dict[str, Any]] = []

        # 1. Deleted Cargos
        cargo_stmt = select(Cargo).where(Cargo.deleted_at.is_not(None)).order_by(Cargo.deleted_at.desc())
        cargos = (await self.session.execute(cargo_stmt)).scalars().all()
        for c in cargos:
            del_at = c.deleted_at or now
            days_left = max(0, 30 - int((now - del_at) / 86400))
            items.append({
                "entity_type": "cargo",
                "entity_id": c.id,
                "title": f"Kargo: {c.code}",
                "details": f"Yaratilgan: {time.strftime('%Y-%m-%d', time.localtime(c.created_at))}",
                "deleted_at": del_at,
                "days_remaining": days_left,
            })

        # 2. Deleted Reyslar
        reys_stmt = select(Reys).where(Reys.deleted_at.is_not(None)).order_by(Reys.deleted_at.desc())
        reyslar = (await self.session.execute(reys_stmt)).scalars().all()
        for r in reyslar:
            del_at = r.deleted_at or now
            days_left = max(0, 30 - int((now - del_at) / 86400))
            items.append({
                "entity_type": "reys",
                "entity_id": r.id,
                "title": f"Reys: {r.code} ({r.custom_name or 'Nomsiz'})",
                "details": f"Sana: {r.date}, Toza: {r.toza_kg} kg",
                "deleted_at": del_at,
                "days_remaining": days_left,
            })

        # 3. Deleted Entries
        entry_stmt = select(Entry).where(Entry.deleted_at.is_not(None)).order_by(Entry.deleted_at.desc()).limit(100)
        entries = (await self.session.execute(entry_stmt)).scalars().all()
        for e in entries:
            del_at = e.deleted_at or now
            days_left = max(0, 30 - int((now - del_at) / 86400))
            items.append({
                "entity_type": "entry",
                "entity_id": e.id,
                "title": f"Karobka: {e.box_code} ({e.tovar_turi})",
                "details": f"Toza vazn: {e.net_weight} kg, Karobka: {e.tare_weight} kg",
                "deleted_at": del_at,
                "days_remaining": days_left,
            })

        # Sort all items by deleted_at descending
        items.sort(key=lambda x: x["deleted_at"], reverse=True)
        return items

    async def restore_item(self, entity_type: str, entity_id: int) -> bool:
        if entity_type == "cargo":
            stmt = select(Cargo).where(Cargo.id == entity_id)
            cargo = (await self.session.execute(stmt)).scalar_one_or_none()
            if cargo and cargo.deleted_at:
                cargo.deleted_at = None
                await self.session.flush()
                return True
        elif entity_type == "reys":
            stmt = select(Reys).where(Reys.id == entity_id)
            reys = (await self.session.execute(stmt)).scalar_one_or_none()
            if reys and reys.deleted_at:
                reys.deleted_at = None
                await self.session.flush()
                return True
        elif entity_type == "entry":
            stmt = select(Entry).where(Entry.id == entity_id)
            entry = (await self.session.execute(stmt)).scalar_one_or_none()
            if entry and entry.deleted_at:
                entry.deleted_at = None
                await self.session.flush()
                return True
        return False

    async def purge_expired(self, retention_days: int = 30) -> int:
        """Permanently delete items older than retention_days (ADR-003)."""
        threshold = int(time.time()) - (retention_days * 86400)
        purged = 0

        # Purge entries
        res1 = await self.session.execute(
            delete(Entry).where(Entry.deleted_at.is_not(None), Entry.deleted_at < threshold)
        )
        purged += res1.rowcount or 0

        # Purge reyslar
        res2 = await self.session.execute(
            delete(Reys).where(Reys.deleted_at.is_not(None), Reys.deleted_at < threshold)
        )
        purged += res2.rowcount or 0

        # Purge cargos
        res3 = await self.session.execute(
            delete(Cargo).where(Cargo.deleted_at.is_not(None), Cargo.deleted_at < threshold)
        )
        purged += res3.rowcount or 0

        await self.session.flush()
        return purged
