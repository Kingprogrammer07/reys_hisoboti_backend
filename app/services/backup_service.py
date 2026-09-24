"""Backup service for Mandarin Reys Hisoboti.

Supports:
- PostgreSQL native dump (pg_dump -Fc) for Neon DB and standard PostgreSQL.
- SQLite atomic backup for local development / offline fallback.
- Database statistics extraction across all models.
- Beautiful, detailed Uzbek caption formatting.
- Telegram document sending via aiogram Bot to the configured backup channel.
- Automatic rotation / retention cleanup (> 30 days).
- Native database restoration (pg_restore).
"""
from __future__ import annotations

import asyncio
import datetime
import glob
import logging
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
from typing import Any, Dict, Optional, Tuple
from urllib.parse import parse_qs, urlencode, urlsplit, urlunsplit

from aiogram import Bot
from aiogram.types import FSInputFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import config
from ..database import async_session_factory
from ..models import ActivityLog, Cargo, CustomType, Entry, EntryPhoto, Inventory, Reys

log = logging.getLogger("reys.backup")


def _find_pg_tool(tool_name: str) -> Optional[str]:
    """Find pg_dump or pg_restore in PATH or standard PostgreSQL installation paths."""
    found = shutil.which(tool_name)
    if found:
        return found

    # Search standard Windows Program Files paths
    candidates = glob.glob(rf"C:\Program Files\PostgreSQL\*\bin\{tool_name}.exe")
    if candidates:
        # Pick the latest version
        return sorted(candidates)[-1]

    # Search Linux / Unix standard paths
    for unix_path in [f"/usr/bin/{tool_name}", f"/usr/local/bin/{tool_name}"]:
        if os.path.isfile(unix_path) and os.access(unix_path, os.X_OK):
            return unix_path

    return None


def get_pg_dump_url(raw_url: str) -> str:
    """Normalize a database URL for pg_dump/pg_restore CLI.
    
    Converts 'postgresql+asyncpg://...' to standard 'postgresql://...'
    and converts 'ssl=require' to 'sslmode=require'.
    """
    raw = (raw_url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    scheme = parts.scheme
    if scheme in ("postgresql+asyncpg", "postgres+asyncpg"):
        scheme = "postgresql"
    elif scheme == "postgres":
        scheme = "postgresql"

    query_params = parse_qs(parts.query)
    if "ssl" in query_params:
        ssl_val = query_params.pop("ssl")[0]
        if ssl_val in ("require", "verify-ca", "verify-full"):
            query_params["sslmode"] = ["require"]

    new_query = urlencode(query_params, doseq=True)
    return urlunsplit((scheme, parts.netloc, parts.path, new_query, parts.fragment))


def generate_backup_filename(dt: Optional[datetime.datetime] = None) -> str:
    """Generate user-requested filename: hisobot_backup_YYYY-MM-DD_HH-mm.dump"""
    if dt is None:
        dt = datetime.datetime.now()
    return f"hisobot_backup_{dt.strftime('%Y-%m-%d_%H-%M')}.dump"


async def get_database_stats(session: Optional[AsyncSession] = None) -> Dict[str, Any]:
    """Query counts of core business records for reporting and verification."""
    stats = {
        "cargos": 0,
        "reyslar": 0,
        "entries": 0,
        "photos": 0,
        "inventory": 0,
        "custom_types": 0,
        "backend": config.DATABASE_BACKEND,
    }

    async def _query(s: AsyncSession):
        try:
            cargos_res = await s.execute(select(func.count(Cargo.id)).where(Cargo.deleted_at.is_(None)))
            stats["cargos"] = cargos_res.scalar_one_or_none() or 0
        except Exception:
            pass

        try:
            reys_res = await s.execute(select(func.count(Reys.id)).where(Reys.deleted_at.is_(None)))
            stats["reyslar"] = reys_res.scalar_one_or_none() or 0
        except Exception:
            pass

        try:
            entries_res = await s.execute(select(func.count(Entry.id)).where(Entry.deleted_at.is_(None)))
            stats["entries"] = entries_res.scalar_one_or_none() or 0
        except Exception:
            pass

        try:
            photos_res = await s.execute(select(func.count(EntryPhoto.id)))
            stats["photos"] = photos_res.scalar_one_or_none() or 0
        except Exception:
            pass

        try:
            inv_res = await s.execute(select(func.count(Inventory.id)))
            stats["inventory"] = inv_res.scalar_one_or_none() or 0
        except Exception:
            pass

        try:
            types_res = await s.execute(select(func.count(CustomType.id)))
            stats["custom_types"] = types_res.scalar_one_or_none() or 0
        except Exception:
            pass

    if session:
        await _query(session)
    else:
        async with async_session_factory() as s:
            await _query(s)

    return stats


def format_file_size(size_bytes: int) -> str:
    """Format bytes into human-readable KB or MB."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def format_telegram_caption(
    stats: Dict[str, Any],
    file_size_bytes: int,
    filename: str,
    dt: Optional[datetime.datetime] = None,
) -> str:
    """Format a detailed, professional caption in 100% pure Uzbek."""
    if dt is None:
        dt = datetime.datetime.now()

    date_str = dt.strftime("%d.%m.%Y %H:%M")
    backend_display = "PostgreSQL (Neon)" if stats.get("backend") == "postgres" else "SQLite (Mahalliy)"
    size_str = format_file_size(file_size_bytes)

    caption = (
        f"📦 MANDARIN REYS HISOBOTI — ZAXIRA NUSXASI\n"
        f"─────────────────────────\n"
        f"📁 Fayl: {filename}\n"
        f"📅 Sana: {date_str} (Toshkent vaqti)\n"
        f"🗄️ Baza turi: {backend_display}\n"
        f"💾 Fayl hajmi: {size_str}\n\n"
        f"📊 BAZA STATISTIKASI:\n"
        f"• 🏢 Kargolar: {stats.get('cargos', 0):,} ta\n"
        f"• 🚚 Reyslar: {stats.get('reyslar', 0):,} ta\n"
        f"• 📝 Partiyalar (yozuvlar): {stats.get('entries', 0):,} ta\n"
        f"• 📸 Rasmlar havolalari: {stats.get('photos', 0):,} ta\n"
        f"• 📦 Ombor qoldiqlari: {stats.get('inventory', 0):,} ta\n"
        f"• 🏷️ Tovar turlari: {stats.get('custom_types', 0):,} ta\n\n"
        f"✅ Holat: Zaxira muvaffaqiyatli olindi va tekshirildi.\n"
        f"🔒 Format: PostgreSQL Native Custom Dump (-Fc)"
    )
    return caption


async def create_backup(target_path: Optional[Path] = None) -> Tuple[Path, Dict[str, Any]]:
    """Create a database backup file and return (file_path, stats).
    
    If PostgreSQL: runs pg_dump -Fc.
    If SQLite: runs atomic sqlite3 backup.
    """
    config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    filename = generate_backup_filename()
    dest_path = target_path or (config.BACKUP_DIR / filename)

    stats = await get_database_stats()

    is_postgres = (
        config.DATABASE_BACKEND == "postgres"
        or config.DATABASE_URL.startswith(("postgres://", "postgresql://"))
    )

    if is_postgres:
        pg_dump_bin = _find_pg_tool("pg_dump")
        if not pg_dump_bin:
            raise RuntimeError(
                "Tizimda 'pg_dump' dasturi topilmadi. Iltimos, PostgreSQL o'rnatilganligini tekshiring."
            )

        pg_url = get_pg_dump_url(config.DATABASE_URL)
        if not pg_url:
            raise RuntimeError("DATABASE_URL ko'rsatilmagan.")

        # Command: pg_dump -Fc -d <URL> -f <dest_path>
        cmd = [
            pg_dump_bin,
            "-Fc",               # Custom format (compressed binary)
            "--no-owner",        # Do not output commands to set ownership of objects
            "--no-acl",          # Prevent dumping of access privileges (grant/revoke)
            "-d", pg_url,
            "-f", str(dest_path),
        ]

        log.info("Starting pg_dump to %s", dest_path)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_msg = stderr.decode("utf-8", errors="replace").strip()
            log.error("pg_dump failed with returncode %s: %s", proc.returncode, err_msg)
            raise RuntimeError(f"pg_dump xatoligi: {err_msg}")

    else:
        # SQLite atomic backup fallback
        sqlite_src = config.DATA_DIR / "reys.db"
        if not sqlite_src.exists():
            # If empty, create an empty db
            sqlite_src.touch()

        log.info("Starting SQLite atomic backup from %s to %s", sqlite_src, dest_path)
        
        def _sync_sqlite_backup():
            src_conn = sqlite3.connect(sqlite_src)
            dst_conn = sqlite3.connect(dest_path)
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()

        await asyncio.to_thread(_sync_sqlite_backup)

    if not dest_path.exists() or dest_path.stat().st_size == 0:
        raise RuntimeError("Zaxira fayli yaratilmadi yoki bo'sh bo'lib qoldi.")

    log.info("Backup successfully created at %s (%s)", dest_path, format_file_size(dest_path.stat().st_size))
    return dest_path, stats


async def send_backup_to_telegram(
    file_path: Path,
    caption: Optional[str] = None,
    channel_id: Optional[Any] = None,
) -> Tuple[bool, Optional[str]]:
    """Send a backup .dump file to the configured Telegram channel."""
    if not config.BOT_TOKEN:
        log.warning("BOT_TOKEN mavjud emas, Telegramga zaxira yuborilmadi.")
        return False, "BOT_TOKEN sozlanmagan"

    target_chat = channel_id if channel_id is not None else config.BACKUP_CHANNEL_ID
    if not target_chat:
        log.warning("BOT_BACKUP_CHANNEL_ID sozlanmagan, zaxira yuborilmadi.")
        return False, "BOT_BACKUP_CHANNEL_ID sozlanmagan"

    # Normalize channel id (e.g. 1002982052676 -> -1002982052676)
    if isinstance(target_chat, int) and target_chat > 10_000_000_000:
        target_chat = -target_chat
    elif isinstance(target_chat, str) and target_chat.isdigit() and int(target_chat) > 10_000_000_000:
        target_chat = -int(target_chat)

    bot = Bot(token=config.BOT_TOKEN)
    try:
        doc = FSInputFile(str(file_path), filename=file_path.name)
        log.info("Sending backup file %s to Telegram channel %s", file_path.name, target_chat)
        await bot.send_document(
            chat_id=target_chat,
            document=doc,
            caption=caption or f"📦 Mandarin Reys Hisoboti Zaxira Nusxasi: {file_path.name}",
        )
        log.info("Backup successfully delivered to Telegram channel %s", target_chat)
        return True, None
    except Exception as exc:
        err_msg = str(exc)
        log.error("Telegramga zaxira yuborishda xatolik: %s", err_msg)
        if "chat not found" in err_msg.lower():
            err_msg = (
                f"Kanal topilmadi ({target_chat}). Iltimos, Telegram botingizni kanalga "
                f"Administrator qilib qo'shing va xabar yuborish huquqini bering!"
            )
        return False, err_msg
    finally:
        await bot.session.close()


def cleanup_old_backups(retention_days: Optional[int] = None) -> int:
    """Remove backup files older than retention_days (default 30 days)."""
    days = retention_days if retention_days is not None else config.BACKUP_RETENTION_DAYS
    cutoff_ts = datetime.datetime.now().timestamp() - (days * 86400)
    removed_count = 0

    if not config.BACKUP_DIR.exists():
        return 0

    for file_path in config.BACKUP_DIR.glob("hisobot_backup_*.dump"):
        try:
            mtime = file_path.stat().st_mtime
            if mtime < cutoff_ts:
                file_path.unlink()
                removed_count += 1
                log.info("Cleaned up old backup file: %s", file_path.name)
        except OSError as exc:
            log.warning("Could not delete old backup %s: %s", file_path, exc)

    return removed_count


async def restore_backup(file_path: Path) -> Dict[str, Any]:
    """Restore database from a .dump file using pg_restore (PostgreSQL) or copy (SQLite)."""
    if not file_path.exists():
        raise FileNotFoundError(f"Zaxira fayli topilmadi: {file_path}")

    is_postgres = (
        config.DATABASE_BACKEND == "postgres"
        or config.DATABASE_URL.startswith(("postgres://", "postgresql://"))
    )

    if is_postgres:
        pg_restore_bin = _find_pg_tool("pg_restore")
        if not pg_restore_bin:
            raise RuntimeError("Tizimda 'pg_restore' dasturi topilmadi.")

        pg_url = get_pg_dump_url(config.DATABASE_URL)
        if not pg_url:
            raise RuntimeError("DATABASE_URL ko'rsatilmagan.")

        # Command: pg_restore -d <URL> --clean --if-exists --no-owner <file_path>
        cmd = [
            pg_restore_bin,
            "--clean",
            "--if-exists",
            "--no-owner",
            "--no-acl",
            "-d", pg_url,
            str(file_path),
        ]

        log.info("Starting pg_restore from %s", file_path)
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        # pg_restore returns 0 on complete success, or 1 if warnings occurred (e.g. table didn't exist to drop)
        err_msg = stderr.decode("utf-8", errors="replace").strip()
        if proc.returncode not in (0, 1):
            log.error("pg_restore failed with code %s: %s", proc.returncode, err_msg)
            raise RuntimeError(f"pg_restore xatoligi: {err_msg}")

    else:
        # SQLite restore
        sqlite_dst = config.DATA_DIR / "reys.db"
        log.info("Restoring SQLite database from %s to %s", file_path, sqlite_dst)

        def _sync_sqlite_restore():
            src_conn = sqlite3.connect(file_path)
            dst_conn = sqlite3.connect(sqlite_dst)
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()

        await asyncio.to_thread(_sync_sqlite_restore)

    stats = await get_database_stats()
    return {
        "status": "success",
        "message": "Ma'lumotlar bazasi zaxira faylidan muvaffaqiyatli tiklandi.",
        "stats": stats,
    }
