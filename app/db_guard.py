"""Database size guard for Neon/Postgres storage safety.

SQLite is still the active local backend today. The guard exposes the same
status shape now, and becomes fully actionable when DATABASE_BACKEND=postgres.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from . import config

log = logging.getLogger("reys.db_guard")


@dataclass(frozen=True)
class DatabaseSizeStatus:
    backend: str
    size_bytes: int | None
    warn_bytes: int
    pre_cleanup_bytes: int
    cleanup_bytes: int
    target_bytes: int
    level: str
    message: str | None
    cleanup_needed: bool

    def as_dict(self) -> dict:
        return {
            "backend": self.backend,
            "size_bytes": self.size_bytes,
            "warn_bytes": self.warn_bytes,
            "pre_cleanup_bytes": self.pre_cleanup_bytes,
            "cleanup_bytes": self.cleanup_bytes,
            "target_bytes": self.target_bytes,
            "level": self.level,
            "message": self.message,
            "cleanup_needed": self.cleanup_needed,
        }


def _threshold_status(size: int | None) -> tuple[str, str | None, bool]:
    if size is None:
        return "unknown", None, False
    mb = round(size / 1024 / 1024, 1)
    if size >= config.DB_SIZE_CLEANUP_BYTES:
        return "cleanup", f"Baza hajmi {mb} MB. Eski ma'lumotlar auto-cleanupga tayyor.", True
    if size >= config.DB_SIZE_PRE_CLEANUP_BYTES:
        left = max(0, config.DB_SIZE_CLEANUP_BYTES - size)
        left_mb = round(left / 1024 / 1024, 1)
        return "danger", f"Baza hajmi {mb} MB. Auto-cleanup boshlanishiga taxminan {left_mb} MB qoldi.", False
    if size >= config.DB_SIZE_WARN_BYTES:
        return "warning", f"Baza hajmi {mb} MB'dan oshdi.", False
    return "ok", None, False


def _sqlite_size() -> int | None:
    path = config.DATA_DIR / "reys.db"
    if not path.exists():
        return 0
    total = path.stat().st_size
    wal = path.with_name(path.name + "-wal")
    shm = path.with_name(path.name + "-shm")
    for extra in (wal, shm):
        if extra.exists():
            total += extra.stat().st_size
    return total


def _postgres_size() -> int | None:
    if not config.DATABASE_URL:
        return None
    try:
        import psycopg
    except ModuleNotFoundError:
        log.info("psycopg is not installed; postgres size unavailable")
        return None
    try:
        with psycopg.connect(config.DATABASE_URL, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_database_size(current_database())")
                row = cur.fetchone()
                return int(row[0]) if row else None
    except Exception as exc:  # noqa: BLE001
        log.warning("postgres size check failed: %s", exc)
        return None


def database_size_bytes() -> int | None:
    if config.DATABASE_BACKEND == "postgres":
        return _postgres_size()
    return _sqlite_size()


def status() -> DatabaseSizeStatus:
    size = database_size_bytes()
    level, message, cleanup_needed = _threshold_status(size)
    return DatabaseSizeStatus(
        backend=config.DATABASE_BACKEND,
        size_bytes=size,
        warn_bytes=config.DB_SIZE_WARN_BYTES,
        pre_cleanup_bytes=config.DB_SIZE_PRE_CLEANUP_BYTES,
        cleanup_bytes=config.DB_SIZE_CLEANUP_BYTES,
        target_bytes=config.DB_SIZE_TARGET_BYTES,
        level=level,
        message=message,
        cleanup_needed=cleanup_needed,
    )


def maybe_cleanup() -> dict:
    """Placeholder for the future Postgres cleanup policy.

    We intentionally do not delete data yet: the product rules for what counts
    as safe-to-delete will be added with the upcoming backend logic changes.
    """
    current = status()
    return {
        "ok": True,
        "cleanup_ran": False,
        "reason": "cleanup policy not enabled yet",
        "status": current.as_dict(),
    }
