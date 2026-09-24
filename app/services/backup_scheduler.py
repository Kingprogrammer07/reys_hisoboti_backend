"""Background worker that executes scheduled database backups and Telegram delivery.

Runs periodically according to config.BACKUP_INTERVAL_HOURS.
Safely cleans up retention archives (> 30 days) and reports status.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Dict, Optional

from .. import config
from . import backup_service

log = logging.getLogger("reys.backup_scheduler")

_scheduler_task: Optional[asyncio.Task] = None
_last_backup_info: Dict[str, Any] = {
    "last_run": None,
    "last_file": None,
    "last_status": "none",
    "last_error": None,
}


async def run_backup_job() -> Dict[str, Any]:
    """Execute a single backup run: create dump, cleanup old, and send to Telegram."""
    global _last_backup_info
    log.info("Starting scheduled backup job...")
    now_dt = datetime.datetime.now()

    try:
        dest_path, stats = await backup_service.create_backup()
        file_size = dest_path.stat().st_size

        # Cleanup files older than 30 days
        cleaned = backup_service.cleanup_old_backups()
        if cleaned > 0:
            log.info("Deleted %d expired backup archives.", cleaned)

        # Format Uzbek caption
        caption = backup_service.format_telegram_caption(
            stats=stats,
            file_size_bytes=file_size,
            filename=dest_path.name,
            dt=now_dt,
        )

        # Send to Telegram backup channel (e.g. 1002982052676 / -1002982052676)
        sent, send_err = await backup_service.send_backup_to_telegram(
            file_path=dest_path,
            caption=caption,
        )

        _last_backup_info = {
            "last_run": now_dt.isoformat(),
            "last_file": dest_path.name,
            "last_status": "success" if sent else "telegram_failed",
            "last_error": send_err,
            "file_size": file_size,
            "telegram_sent": sent,
            "stats": stats,
        }
        log.info("Backup job completed: %s (Telegram sent: %s, error: %s)", dest_path.name, sent, send_err)
        return _last_backup_info

    except Exception as exc:
        log.error("Scheduled backup job encountered error: %s", exc, exc_info=True)
        _last_backup_info = {
            "last_run": now_dt.isoformat(),
            "last_file": None,
            "last_status": "failed",
            "last_error": str(exc),
        }
        return _last_backup_info


async def _scheduler_loop():
    """Continuous loop checking interval and executing backups."""
    log.info(
        "Backup scheduler loop started. Interval: %d hours, Target channel: %s",
        config.BACKUP_INTERVAL_HOURS,
        config.BACKUP_CHANNEL_ID,
    )

    interval_seconds = max(3600, config.BACKUP_INTERVAL_HOURS * 3600)

    # Initial delay before the first scheduled run so the server starts smoothly
    await asyncio.sleep(60)

    while True:
        try:
            await run_backup_job()
        except asyncio.CancelledError:
            log.info("Backup scheduler received cancellation request.")
            break
        except Exception as exc:
            log.error("Unexpected error in backup scheduler loop: %s", exc)

        try:
            await asyncio.sleep(interval_seconds)
        except asyncio.CancelledError:
            break


def start_backup_scheduler() -> None:
    """Start background scheduler task if not already running."""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(_scheduler_loop())
        log.info("Backup scheduler task created.")


def stop_backup_scheduler() -> None:
    """Stop background scheduler task gracefully."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        log.info("Backup scheduler task cancelled.")


def get_last_backup_info() -> Dict[str, Any]:
    """Return status metadata about recent backup runs."""
    return _last_backup_info
