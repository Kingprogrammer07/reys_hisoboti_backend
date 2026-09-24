from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from .. import config, storage
from ..models.activity import ActivityLog
from ..models.entry import Entry
from ..models.outbox import SendQueue
from ..repositories.cargo_repo import CargoRepository
from ..repositories.entry_repo import EntryRepository
from ..repositories.inventory_repo import InventoryRepository
from ..repositories.reys_repo import ReysRepository
from ..schemas.entry import EntryCreate, EntryResponse, PhotoMetadata


class EntryService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.cargo_repo = CargoRepository(session)
        self.entry_repo = EntryRepository(session)
        self.reys_repo = ReysRepository(session)
        self.inv_repo = InventoryRepository(session)

    def _to_response(self, entry: Entry) -> EntryResponse:
        photo_metas: List[PhotoMetadata] = []
        photo_urls: List[str] = []

        for p in entry.photos:
            url: Optional[str] = None
            if p.storage_backend == "r2" and p.storage_key:
                pub = storage.public_url(p.storage_key)
                # Only use external CDN url if it is NOT the raw private S3 API endpoint
                if pub and "r2.cloudflarestorage.com" not in pub:
                    url = pub
            if not url:
                url = f"/api/entries/{entry.id}/photos/{p.idx}"

            meta = PhotoMetadata(
                id=p.id,
                idx=p.idx,
                mime=p.mime,
                size=p.size,
                storage_backend=p.storage_backend,
                storage_key=p.storage_key,
                url=url,
            )
            photo_metas.append(meta)
            photo_urls.append(url)

        dt_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.created_at))

        return EntryResponse(
            id=entry.id,
            reys_id=entry.reys_id,
            box_code=entry.box_code,
            tovar_turi=entry.tovar_turi,
            gross_weight=entry.gross_weight,
            tare_weight=entry.tare_weight,
            net_weight=entry.net_weight,
            coefficient_mode=entry.coefficient_mode,
            created_by=entry.created_by,
            created_at=entry.created_at,
            deleted_at=entry.deleted_at,
            photos=photo_metas,
            # Frontend compatibility fields
            boxCode=entry.box_code,
            grossWeight=entry.gross_weight,
            tareWeight=entry.tare_weight,
            netWeight=entry.net_weight,
            photoUrl=photo_urls[0] if photo_urls else None,
            photoUrls=photo_urls,
            createdAt=dt_str,
        )

    async def list_entries(
        self,
        reys_id: int,
        include_deleted: bool = False,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[EntryResponse]:
        entries = await self.entry_repo.list_by_reys(
            reys_id=reys_id,
            include_deleted=include_deleted,
            limit=limit,
            offset=offset,
        )
        return [self._to_response(e) for e in entries]

    async def get_entry(self, entry_id: int) -> Optional[EntryResponse]:
        entry = await self.entry_repo.get_by_id(entry_id)
        if not entry:
            return None
        return self._to_response(entry)

    async def record_entry(
        self,
        data: EntryCreate,
        photos: Optional[List[Tuple[bytes, str]]] = None,
    ) -> EntryResponse:
        """Validate tare weight, record entry, persist photos, update balances & outbox."""
        # Check reys exists
        reys = await self.reys_repo.get_by_id(data.reys_id)
        if not reys:
            raise ValueError(f"Reys {data.reys_id} topilmadi")

        gross = round(float(data.gross_weight), 3)
        tare = round(float(data.tare_weight or 0.0), 3)

        if gross <= 0:
            raise ValueError("Umumiy og'irlik musbat bo'lishi kerak")
        if tare < 0:
            raise ValueError("Karobka og'irligi manfiy bo'lishi mumkin emas")
        if tare > 10.0:
            raise ValueError("Karobka og'irligi 10 kg dan oshmasligi kerak (ADR-001)")
        if gross > 3.0 and tare > 0.5 * gross:
            raise ValueError("Karobka og'irligi umumiy og'irlikning 50% idan oshmasligi kerak (ADR-002)")
        if tare >= gross:
            raise ValueError("Karobka og'irligi umumiy og'irlikdan kichik bo'lishi kerak")

        net = round(gross - tare, 3)
        if net <= 0:
            raise ValueError("Sof vazn 0 dan katta bo'lishi kerak")

        # 1. Create Entry
        entry = await self.entry_repo.create(
            reys_id=data.reys_id,
            box_code=data.box_code,
            tovar_turi=data.tovar_turi,
            gross_weight=gross,
            tare_weight=tare,
            net_weight=net,
            coefficient_mode=data.coefficient_mode,
            created_by=data.created_by,
        )

        # 2. Persist Photos
        photos_list = photos or []
        reys_code = reys.code if reys else f"reys_{data.reys_id}"
        cargo_code = ""
        if reys and reys.cargo_id:
            cargo_obj = await self.cargo_repo.get_by_id(reys.cargo_id)
            if cargo_obj:
                cargo_code = cargo_obj.code

        for idx, (raw_bytes, raw_mime) in enumerate(photos_list):
            # WebP ga 92% sifat bilan o'girish (iOS HEIC/PNG/JPG barchasini qo'llaydi)
            photo_bytes, mime = storage.optimize_and_convert_to_webp(raw_bytes, quality=92)

            stored_backend = "disk"
            stored_key: Optional[str] = None

            if storage.r2_enabled():
                try:
                    res = storage.put_photo(
                        entry_id=entry.id,
                        idx=idx,
                        data=photo_bytes,
                        mime=mime,
                        cargo_code=cargo_code,
                        reys_code=reys_code,
                        box_code=entry.box_code,
                        quality=92,
                    )
                    if res:
                        stored_backend = "r2"
                        stored_key = res.key
                except Exception as exc:
                    log.warning("R2 saqlashda xatolik (%s), diskka saqlanmoqda", exc)
                    stored_backend = "disk"

            if stored_backend == "disk":
                photo_dir = config.DATA_DIR / "photos" / str(entry.id)
                photo_dir.mkdir(parents=True, exist_ok=True)
                photo_path = photo_dir / f"{idx}.webp"
                photo_path.write_bytes(photo_bytes)
                stored_key = f"photos/{entry.id}/{idx}.webp"

            await self.entry_repo.add_photo(
                entry_id=entry.id,
                idx=idx,
                mime=mime,
                size=len(photo_bytes),
                storage_backend=stored_backend,
                storage_key=stored_key,
            )

        # 3. Upsert Inventory balance
        await self.inv_repo.upsert_inventory(
            reys_id=entry.reys_id,
            tovar_turi=entry.tovar_turi,
            weight_delta=net,
            count_delta=1,
        )

        # 4. Recompute Reys total net weight
        await self.reys_repo.recompute_totals(entry.reys_id)

        # 5. Enqueue to durable Telegram SendQueue
        outbox_item = SendQueue(
            entry_id=entry.id,
            status="pending",
            attempts=0,
            next_at=0,
            created_at=int(time.time()),
        )
        self.session.add(outbox_item)

        # 6. Audit Activity Log
        activity = ActivityLog(
            reys_id=entry.reys_id,
            actor=data.created_by,
            action="reys",
            tovar_turi=entry.tovar_turi,
            weight=gross,
            box_weight=tare,
            net=net,
            coefficient_mode=data.coefficient_mode,
            photos_count=len(photos_list),
            created_at=int(time.time()),
        )
        self.session.add(activity)

        await self.session.flush()
        await self.session.refresh(entry, ["photos"])
        return self._to_response(entry)

    async def delete_entry(self, entry_id: int) -> bool:
        entry = await self.entry_repo.get_by_id(entry_id)
        if not entry:
            return False

        # Soft delete entry
        ok = await self.entry_repo.soft_delete(entry_id)
        if ok:
            # Revert inventory
            await self.inv_repo.upsert_inventory(
                reys_id=entry.reys_id,
                tovar_turi=entry.tovar_turi,
                weight_delta=-entry.net_weight,
                count_delta=-1,
            )
            # Recompute totals
            await self.reys_repo.recompute_totals(entry.reys_id)
        return ok

    async def restore_entry(self, entry_id: int) -> bool:
        entry = await self.entry_repo.get_by_id(entry_id, include_deleted=True)
        if not entry or entry.deleted_at is None:
            return False

        ok = await self.entry_repo.restore(entry_id)
        if ok:
            # Re-apply inventory
            await self.inv_repo.upsert_inventory(
                reys_id=entry.reys_id,
                tovar_turi=entry.tovar_turi,
                weight_delta=entry.net_weight,
                count_delta=1,
            )
            # Recompute totals
            await self.reys_repo.recompute_totals(entry.reys_id)
        return ok
