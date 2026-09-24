"""Database Failover and Bi-directional Synchronization Worker.

Manages seamless transition between Neon PostgreSQL (Primary) and local SQLite (Fallback).
Features:
1. Continuous Neon Health Check & Circuit Breaker.
2. Instant fallback to local SQLite (data/reys.db) when Neon or internet is down.
3. Full two-way synchronization:
   - Replicates offline records from SQLite -> Neon when Neon recovers.
   - Mirrors Neon -> SQLite hot standby so local database always has fresh state.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from .. import config
from ..database import Base, async_session_factory, engine
from ..models import ActivityLog, Cargo, CustomType, Entry, EntryPhoto, Inventory, Reys

log = logging.getLogger("reys.db_sync")

_sqlite_engine = None
_sqlite_session_factory = None
_db_sync_task: Optional[asyncio.Task] = None
_current_active_mode = "postgres" if config.DATABASE_BACKEND == "postgres" else "sqlite"
_is_neon_online = True


def get_sqlite_fallback_factory() -> async_sessionmaker[AsyncSession]:
    """Get or initialize the local SQLite fallback engine and session factory."""
    global _sqlite_engine, _sqlite_session_factory
    if _sqlite_session_factory is None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        sqlite_path = (config.DATA_DIR / "reys.db").as_posix()
        _sqlite_engine = create_async_engine(
            f"sqlite+aiosqlite:///{sqlite_path}",
            connect_args={"check_same_thread": False},
        )
        _sqlite_session_factory = async_sessionmaker(
            bind=_sqlite_engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _sqlite_session_factory


async def init_sqlite_tables():
    """Ensure all tables exist in the local SQLite fallback database."""
    factory = get_sqlite_fallback_factory()
    assert _sqlite_engine is not None
    async with _sqlite_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def check_neon_health() -> bool:
    """Perform a fast ping to Neon PostgreSQL."""
    if not (config.DATABASE_BACKEND == "postgres" and config.DATABASE_URL):
        return False
    try:
        async with asyncio.timeout(3.0):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def get_database_status() -> Dict[str, Any]:
    return {
        "configured_backend": config.DATABASE_BACKEND,
        "active_mode": _current_active_mode,
        "neon_online": _is_neon_online,
        "fallback_available": True,
    }


async def sync_sqlite_to_neon() -> Dict[str, int]:
    """Replicate all records created offline in SQLite into Neon PostgreSQL."""
    sqlite_factory = get_sqlite_fallback_factory()
    neon_factory = async_session_factory

    stats = {"cargos": 0, "reyslar": 0, "entries": 0, "photos": 0, "inventory": 0}

    async with sqlite_factory() as s_session, neon_factory() as n_session:
        # 1. Cargos
        cargos = (await s_session.execute(select(Cargo))).scalars().all()
        for c in cargos:
            await n_session.merge(Cargo(
                id=c.id,
                code=c.code,
                created_at=c.created_at,
                deleted_at=c.deleted_at,
            ))
            stats["cargos"] += 1
        await n_session.commit()

        # 2. Reyslar
        reyslar = (await s_session.execute(select(Reys))).scalars().all()
        for r in reyslar:
            await n_session.merge(Reys(
                id=r.id,
                cargo_id=r.cargo_id,
                code=r.code,
                custom_name=r.custom_name,
                date=r.date,
                toza_kg=r.toza_kg,
                karobka_plus_kg=r.karobka_plus_kg,
                adjustment_diff_kg=r.adjustment_diff_kg,
                original_toza_kg=r.original_toza_kg,
                original_karobka_plus_kg=r.original_karobka_plus_kg,
                created_at=r.created_at,
                deleted_at=r.deleted_at,
            ))
            stats["reyslar"] += 1
        await n_session.commit()

        # 3. Entries
        entries = (await s_session.execute(select(Entry))).scalars().all()
        for e in entries:
            await n_session.merge(Entry(
                id=e.id,
                reys_id=e.reys_id,
                box_code=e.box_code,
                tovar_turi=e.tovar_turi,
                gross_weight=e.gross_weight,
                tare_weight=e.tare_weight,
                net_weight=e.net_weight,
                coefficient_mode=e.coefficient_mode,
                created_by=e.created_by,
                created_at=e.created_at,
                deleted_at=e.deleted_at,
            ))
            stats["entries"] += 1
        await n_session.commit()

        # 4. Entry Photos
        photos = (await s_session.execute(select(EntryPhoto))).scalars().all()
        for p in photos:
            await n_session.merge(EntryPhoto(
                id=p.id,
                entry_id=p.entry_id,
                idx=p.idx,
                mime=p.mime,
                size=p.size,
                storage_backend=p.storage_backend,
                storage_key=p.storage_key,
                telegram_file_id=p.telegram_file_id,
                created_at=p.created_at,
            ))
            stats["photos"] += 1
        await n_session.commit()

        # 5. Inventory
        inv_items = (await s_session.execute(select(Inventory))).scalars().all()
        for item in inv_items:
            await n_session.merge(Inventory(
                id=item.id,
                reys_id=item.reys_id,
                tovar_turi=item.tovar_turi,
                weight=item.weight,
                package_count=getattr(item, "package_count", 0),
                box_coefficient=getattr(item, "box_coefficient", 1.0),
                updated_at=item.updated_at,
            ))
            stats["inventory"] += 1
        await n_session.commit()

    log.info("Successfully synced SQLite backlog to Neon: %s", stats)
    return stats


async def sync_neon_to_sqlite():
    """Mirror Neon PostgreSQL state to local SQLite hot standby."""
    if not (config.DATABASE_BACKEND == "postgres" and _is_neon_online):
        return

    sqlite_factory = get_sqlite_fallback_factory()
    neon_factory = async_session_factory

    try:
        async with neon_factory() as n_session, sqlite_factory() as s_session:
            # 1. Cargos
            cargos = (await n_session.execute(select(Cargo))).scalars().all()
            for c in cargos:
                await s_session.merge(Cargo(id=c.id, code=c.code, created_at=c.created_at, deleted_at=c.deleted_at))
            await s_session.commit()

            # 2. Reyslar
            reyslar = (await n_session.execute(select(Reys))).scalars().all()
            for r in reyslar:
                await s_session.merge(Reys(
                    id=r.id, cargo_id=r.cargo_id, code=r.code, custom_name=r.custom_name,
                    date=r.date, toza_kg=r.toza_kg, karobka_plus_kg=r.karobka_plus_kg,
                    adjustment_diff_kg=r.adjustment_diff_kg, original_toza_kg=r.original_toza_kg,
                    original_karobka_plus_kg=r.original_karobka_plus_kg, created_at=r.created_at, deleted_at=r.deleted_at
                ))
            await s_session.commit()

            # 3. Entries
            entries = (await n_session.execute(select(Entry))).scalars().all()
            for e in entries:
                await s_session.merge(Entry(
                    id=e.id, reys_id=e.reys_id, box_code=e.box_code, tovar_turi=e.tovar_turi,
                    gross_weight=e.gross_weight, tare_weight=e.tare_weight, net_weight=e.net_weight,
                    coefficient_mode=e.coefficient_mode, created_by=e.created_by, created_at=e.created_at, deleted_at=e.deleted_at
                ))
            await s_session.commit()

            # 4. Entry Photos
            photos = (await n_session.execute(select(EntryPhoto))).scalars().all()
            for p in photos:
                await s_session.merge(EntryPhoto(
                    id=p.id, entry_id=p.entry_id, idx=p.idx, mime=p.mime, size=p.size,
                    storage_backend=p.storage_backend, storage_key=p.storage_key, telegram_file_id=p.telegram_file_id, created_at=p.created_at
                ))
            await s_session.commit()

            # 5. Inventory
            inv_items = (await n_session.execute(select(Inventory))).scalars().all()
            for item in inv_items:
                await s_session.merge(Inventory(
                    id=item.id,
                    reys_id=item.reys_id,
                    tovar_turi=item.tovar_turi,
                    weight=item.weight,
                    package_count=getattr(item, "package_count", 0),
                    box_coefficient=getattr(item, "box_coefficient", 1.0),
                    updated_at=item.updated_at,
                ))
            await s_session.commit()
    except Exception as exc:
        log.warning("Could not mirror Neon to SQLite hot standby: %s", exc)


async def _db_monitor_loop():
    """Background task monitoring Neon health and triggering automatic failover/sync."""
    global _is_neon_online, _current_active_mode
    log.info("Database failover & sync monitor started.")

    await init_sqlite_tables()
    await asyncio.sleep(10)

    while True:
        try:
            if config.DATABASE_BACKEND == "postgres":
                is_healthy = await check_neon_health()

                if not is_healthy and _is_neon_online:
                    # Neon just went down -> Failover to SQLite
                    _is_neon_online = False
                    _current_active_mode = "sqlite"
                    log.warning("⚠️ Neon PostgreSQL aloqasi uzildi! Tizim zaxira SQLite rejimiga o'tdi.")

                elif is_healthy and not _is_neon_online:
                    # Neon recovered -> Sync SQLite backlog back to Neon!
                    log.info("🟢 Neon PostgreSQL aloqasi qayta tiklandi! Oflayn ma'lumotlar Neonga sinxronlanmoqda...")
                    try:
                        await sync_sqlite_to_neon()
                        _is_neon_online = True
                        _current_active_mode = "postgres"
                        log.info("✅ Neon bilan sinxronizatsiya tugadi. Asosiy PostgreSQL rejimiga qaytildi.")
                    except Exception as exc:
                        log.error("Neon ga sinxronizatsiya qilishda xatolik: %s", exc)

                elif is_healthy and _is_neon_online:
                    # Periodic hot standby mirror (every 5 mins)
                    await sync_neon_to_sqlite()

        except asyncio.CancelledError:
            log.info("DB sync monitor loop cancelled.")
            break
        except Exception as exc:
            log.error("Error in DB sync monitor loop: %s", exc)

        try:
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            break


def start_db_sync_worker() -> None:
    global _db_sync_task
    if _db_sync_task is None or _db_sync_task.done():
        _db_sync_task = asyncio.create_task(_db_monitor_loop())
        log.info("DB sync background monitor started.")


def stop_db_sync_worker() -> None:
    global _db_sync_task
    if _db_sync_task and not _db_sync_task.done():
        _db_sync_task.cancel()
        log.info("DB sync background monitor stopped.")
