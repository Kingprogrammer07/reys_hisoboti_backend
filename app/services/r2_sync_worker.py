"""Background worker that continuously syncs disk-stored photos to Cloudflare R2.

When R2 experiences temporary outages or network disconnects, photos are safely
persisted on local disk in WebP format. Once R2 connectivity is restored, this
worker automatically:
1. Pushes local disk photos to their designated R2 path (with Cargo/Reys hierarchy).
2. Updates database records (storage_backend='r2', storage_key=r2_key).
3. Safely deletes the local files from disk, freeing up storage.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .. import config, storage
from ..database import async_session_factory
from ..models.entry import Entry, EntryPhoto
from ..models.reys import Reys

log = logging.getLogger("reys.r2_sync")

_sync_task: Optional[asyncio.Task] = None


async def sync_pending_disk_photos(batch_size: int = 50) -> Dict[str, Any]:
    """Find photos stored on disk, upload them to R2, and clean up disk."""
    if not storage.r2_enabled():
        return {"synced": 0, "remaining": 0, "message": "R2 hozirda yoqilmagan"}

    synced_count = 0
    failed_count = 0

    async with async_session_factory() as session:
        # Find photos currently marked as 'disk'
        stmt = (
            select(EntryPhoto)
            .where(EntryPhoto.storage_backend == "disk")
            .options(
                selectinload(EntryPhoto.entry).selectinload(Entry.reys).selectinload(Reys.cargo)
            )
            .limit(batch_size)
        )
        result = await session.execute(stmt)
        disk_photos = result.scalars().all()

        if not disk_photos:
            return {"synced": 0, "remaining": 0, "message": "Diskda sinxronlanmagan rasmlar yo'q"}

        log.info("Found %d disk photos pending R2 sync. Starting sync...", len(disk_photos))

        for p in disk_photos:
            entry = p.entry
            if not entry:
                continue

            # Determine local path
            possible_paths = [
                config.DATA_DIR / "photos" / str(p.entry_id) / f"{p.idx}.webp",
                config.DATA_DIR / "photos" / str(p.entry_id) / str(p.idx),
            ]
            local_file: Optional[Path] = None
            for path in possible_paths:
                if path.exists():
                    local_file = path
                    break

            if not local_file:
                log.warning("Disk photo file not found on disk for entry %s idx %s", p.entry_id, p.idx)
                continue

            # Extract hierarchy context
            reys = entry.reys
            reys_code = reys.code if reys else f"reys_{entry.reys_id}"
            cargo_code = reys.cargo.code if (reys and getattr(reys, "cargo", None)) else ""

            try:
                data = local_file.read_bytes()
                # Upload to R2 with hierarchical folder routing
                res = storage.put_photo(
                    entry_id=p.entry_id,
                    idx=p.idx,
                    data=data,
                    mime=p.mime or "image/webp",
                    cargo_code=cargo_code,
                    reys_code=reys_code,
                    box_code=entry.box_code,
                    quality=92,
                )

                if res:
                    # Update database record to R2
                    p.storage_backend = "r2"
                    p.storage_key = res.key
                    p.size = res.size
                    p.mime = "image/webp"

                    # Remove local file to reclaim disk space
                    try:
                        local_file.unlink()
                        # If entry directory is now empty, remove it
                        parent_dir = local_file.parent
                        if parent_dir.exists() and not any(parent_dir.iterdir()):
                            parent_dir.rmdir()
                    except OSError as exc:
                        log.warning("Could not delete local photo file %s: %s", local_file, exc)

                    synced_count += 1
                    log.info("Successfully synced photo to R2: %s (disk file cleaned)", res.key)
                else:
                    failed_count += 1
            except Exception as exc:
                log.error("Failed to sync photo to R2 for entry %s: %s", p.entry_id, exc)
                failed_count += 1

        if synced_count > 0:
            await session.commit()

    return {
        "synced": synced_count,
        "failed": failed_count,
        "message": f"{synced_count} ta rasm R2 ga muvaffaqiyatli ko'chirildi va diskdan tozalandi.",
    }


async def _r2_sync_loop():
    """Background periodic loop to sync disk photos to R2."""
    log.info("R2 auto-sync worker started.")
    # Initial wait so application finishes boot
    await asyncio.sleep(15)

    while True:
        try:
            if storage.r2_enabled():
                await sync_pending_disk_photos(batch_size=30)
        except asyncio.CancelledError:
            log.info("R2 sync worker cancelled.")
            break
        except Exception as exc:
            log.error("Unexpected error in R2 sync loop: %s", exc)

        try:
            # Check every 45 seconds
            await asyncio.sleep(45)
        except asyncio.CancelledError:
            break


def start_r2_sync_worker() -> None:
    global _sync_task
    if _sync_task is None or _sync_task.done():
        _sync_task = asyncio.create_task(_r2_sync_loop())
        log.info("R2 auto-sync background task started.")


def stop_r2_sync_worker() -> None:
    global _sync_task
    if _sync_task and not _sync_task.done():
        _sync_task.cancel()
        log.info("R2 auto-sync background task stopped.")
