"""API Router for Database Backup & Restore.

Endpoints:
- GET  /api/backup/stats: Database record counts and scheduler status.
- GET  /api/backup/download: Generate fresh .dump and download to browser.
- POST /api/backup/send-telegram: Trigger immediate backup and Telegram delivery.
- POST /api/backup/restore: Upload a .dump file and restore database.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from .. import config
from ..services import backup_scheduler, backup_service

log = logging.getLogger("reys.backup_router")

router = APIRouter(prefix="/api/backup", tags=["backup"])


@router.get("/stats")
async def get_backup_status() -> Dict[str, Any]:
    """Return database record counts, backup scheduler status, and local files."""
    try:
        db_stats = await backup_service.get_database_stats()
        scheduler_info = backup_scheduler.get_last_backup_info()

        # List local backup files
        files_list: List[Dict[str, Any]] = []
        if config.BACKUP_DIR.exists():
            for f in sorted(config.BACKUP_DIR.glob("hisobot_backup_*.dump"), reverse=True):
                files_list.append({
                    "filename": f.name,
                    "size_bytes": f.stat().st_size,
                    "size_formatted": backup_service.format_file_size(f.stat().st_size),
                    "created_at": f.stat().st_mtime,
                })

        return {
            "status": "success",
            "stats": db_stats,
            "scheduler": scheduler_info,
            "backup_channel": str(config.BACKUP_CHANNEL_ID),
            "interval_hours": config.BACKUP_INTERVAL_HOURS,
            "retention_days": config.BACKUP_RETENTION_DAYS,
            "files": files_list[:10],  # Latest 10 files
        }
    except Exception as exc:
        log.error("Failed to retrieve backup stats: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Zaxira statistikasini olishda xatolik: {exc}",
        )


@router.get("/download")
async def download_backup_dump():
    """Create a fresh database dump and stream it as a file download."""
    try:
        dest_path, _ = await backup_service.create_backup()
        return FileResponse(
            path=str(dest_path),
            filename=dest_path.name,
            media_type="application/octet-stream",
        )
    except Exception as exc:
        log.error("Failed to generate backup download: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Zaxira faylini yaratishda xatolik: {exc}",
        )


@router.post("/send-telegram")
async def send_backup_now() -> Dict[str, Any]:
    """Manually trigger backup creation and delivery to Telegram channel."""
    try:
        result = await backup_scheduler.run_backup_job()
        if result.get("last_status") == "failed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Telegramga zaxira yuborishda xatolik: {result.get('last_error')}",
            )
        return {
            "status": "success",
            "message": "Zaxira nusxasi muvaffaqiyatli yaratildi va Telegram kanalga yuborildi.",
            "data": result,
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.error("Failed to trigger backup to Telegram: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Telegramga zaxira yuborishda xatolik: {exc}",
        )


@router.post("/restore")
async def restore_from_dump(file: UploadFile = File(...)) -> Dict[str, Any]:
    """Restore database from an uploaded .dump file."""
    if not file.filename or not file.filename.endswith(".dump"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Faqat '.dump' formatidagi zaxira fayllarini tiklash mumkin.",
        )

    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    temp_path = config.BACKUP_DIR / f"temp_restore_{int(time.time())}.dump"

    try:
        # Save uploaded file
        with open(temp_path, "wb") as buffer:
            while chunk := await file.read(64 * 1024):
                buffer.write(chunk)

        # Restore
        res = await backup_service.restore_backup(temp_path)
        return res

    except Exception as exc:
        log.error("Restore failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ma'lumotlar bazasini tiklashda xatolik: {exc}",
        )
    finally:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
