"""Durable Telegram sender.

Saved entries are enqueued in SQLite `send_queue`. A single background worker
drains the queue and forwards photos + caption to the configured Telegram
channel for that entry type. Pending sends survive process restarts and retry
forever with backoff.
"""
from __future__ import annotations

import asyncio
import logging
import time

from aiogram.types import BufferedInputFile, InputMediaPhoto
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from . import config, database, db, storage
from .models.entry import Entry, EntryPhoto
from .models.outbox import SendQueue
from .models.reys import Reys

log = logging.getLogger("reys.outbox")

_bot = None
_wake: asyncio.Event | None = None
_started = False

_BACKOFF = [5, 15, 30, 60, 120, 300, 600, 900]
_OBSHIY_TITLES = {
    "top": "Top",
    "topchiqgan": "Topdan chiqgan",
    "bizda": "Bizda qoladigan",
    "chiqgan": "Bizdan chiqgan",
}


def set_bot(bot) -> None:
    global _bot
    _bot = bot


def notify() -> None:
    if _wake is not None:
        try:
            _wake.set()
        except RuntimeError:
            pass


def _fmt(v) -> str:
    try:
        return f"{round(float(v or 0), 2):g}"
    except (TypeError, ValueError):
        return "0"


def _caption(entry: dict, report_name: str) -> str:
    name = report_name or "Hisobot"
    action = entry["action"]
    if action in _OBSHIY_TITLES:
        head = f"{name} - {_OBSHIY_TITLES[action]}"
        code = (entry.get("tovar_turi") or "").strip()
        coef = float(entry.get("coefficient") or 0)
        net = entry.get("net")
        if net is None:
            net = float(entry.get("weight") or 0) - coef
        weight = f"{_fmt(entry.get('weight'))} - {_fmt(coef)} = {_fmt(net)}" if coef else _fmt(entry.get("weight"))
        body = f"{code + ' - ' if code else ''}{weight} kg"
    elif action == "adjust":
        head = f"{name} - {entry['from_type']} -> {entry['to_type']}"
        body = f"{_fmt(entry['weight'])} kg"
    else:
        coef = float(entry.get("coefficient") or 0)
        net = entry.get("net")
        if net is None:
            net = float(entry.get("weight") or 0) - coef
        head = f"{name} - {entry.get('tovar_turi') or ''}"
        body = f"{_fmt(entry.get('weight'))} - {_fmt(coef)} = {_fmt(net)} kg"
    return f"{head}\n\n{body}"


def _remember_telegram_photo(entry_id: int, idx: int, message) -> None:
    photos = getattr(message, "photo", None) or []
    if not photos:
        return
    photo = photos[-1]
    db.mark_photo_telegram(
        entry_id,
        idx,
        getattr(photo, "file_id", None),
        getattr(photo, "file_unique_id", None),
        getattr(message, "message_id", None),
    )


def _remember_telegram_photo_v2(photo: EntryPhoto, message) -> None:
    photos = getattr(message, "photo", None) or []
    if not photos:
        return
    sent = photos[-1]
    photo.telegram_file_id = getattr(sent, "file_id", None)


def _caption_v2(entry: Entry) -> str:
    reys = entry.reys
    cargo_code = reys.cargo.code if reys and reys.cargo else ""
    report_name = cargo_code or (reys.code if reys else "Reys")
    head = f"{report_name} - {entry.tovar_turi}"
    body = f"{entry.box_code}: {_fmt(entry.gross_weight)} - {_fmt(entry.tare_weight)} = {_fmt(entry.net_weight)} kg"
    return f"{head}\n\n{body}"


async def _photo_blobs_v2(entry: Entry) -> list[tuple[bytes, str, EntryPhoto]]:
    blobs: list[tuple[bytes, str, EntryPhoto]] = []
    for photo in sorted(entry.photos, key=lambda p: p.idx):
        data: bytes | None = None
        if photo.storage_backend == "r2" and photo.storage_key:
            data = await asyncio.to_thread(storage.get_photo, photo.storage_key)
        else:
            photo_path = config.DATA_DIR / "photos" / str(entry.id) / f"{photo.idx}.webp"
            if not photo_path.exists():
                photo_path = config.DATA_DIR / "photos" / str(entry.id) / str(photo.idx)
            if photo_path.exists():
                data = await asyncio.to_thread(photo_path.read_bytes)
        if data is not None:
            blobs.append((data, photo.mime or "image/webp", photo))
    return blobs


async def _get_entry_v2(entry_id: int) -> Entry | None:
    async with database.async_session_factory() as session:
        stmt = (
            select(Entry)
            .options(
                selectinload(Entry.photos),
                selectinload(Entry.reys).selectinload(Reys.cargo),
            )
            .where(Entry.id == entry_id, Entry.deleted_at.is_(None))
        )
        return (await session.execute(stmt)).scalar_one_or_none()


async def _send_one_v2(entry: Entry) -> None:
    chat = config.channel_for_action("reys")
    if chat is None:
        raise RuntimeError("channel not configured for reys")

    caption = _caption_v2(entry)
    blobs = await _photo_blobs_v2(entry)

    async with database.async_session_factory() as session:
        managed_entry = await session.get(
            Entry,
            entry.id,
            options=[selectinload(Entry.photos)],
        )
        photo_by_idx = {p.idx: p for p in (managed_entry.photos if managed_entry else [])}

        if not blobs:
            await _bot.send_message(chat, caption)
        elif len(blobs) == 1:
            data, _mime, photo = blobs[0]
            msg = await _bot.send_photo(chat, BufferedInputFile(data, filename="photo.webp"), caption=caption)
            if photo.idx in photo_by_idx:
                _remember_telegram_photo_v2(photo_by_idx[photo.idx], msg)
        else:
            media = [
                InputMediaPhoto(
                    media=BufferedInputFile(data, filename=f"photo_{i}.webp"),
                    caption=caption if i == 0 else None,
                )
                for i, (data, _mime, _photo) in enumerate(blobs)
            ]
            messages = await _bot.send_media_group(chat, media)
            for i, msg in enumerate(messages or []):
                if i < len(blobs):
                    photo = blobs[i][2]
                    if photo.idx in photo_by_idx:
                        _remember_telegram_photo_v2(photo_by_idx[photo.idx], msg)
        await session.commit()


async def _send_one(entry_id: int) -> None:
    entry = db.get_entry_any(entry_id)
    if entry is not None:
        await _send_one_legacy(entry_id, entry)
        return

    entry_v2 = await _get_entry_v2(entry_id)
    if entry_v2 is None:
        await _mark_send_canceled(entry_id)
        return
    await _send_one_v2(entry_v2)


async def _send_one_legacy(entry_id: int, entry: dict) -> None:
    chat = config.channel_for_action(entry["action"])
    if chat is None:
        raise RuntimeError(f"channel not configured for {entry['action']}")

    caption = _caption(entry, db.report_name(entry["report_id"]) or "")
    blobs = db.photo_blobs(entry_id)

    if not blobs:
        await _bot.send_message(chat, caption)
    elif len(blobs) == 1:
        data, _mime = blobs[0]
        msg = await _bot.send_photo(chat, BufferedInputFile(data, filename="photo.jpg"), caption=caption)
        _remember_telegram_photo(entry_id, 0, msg)
    else:
        media = [
            InputMediaPhoto(
                media=BufferedInputFile(data, filename=f"photo_{i}.jpg"),
                caption=caption if i == 0 else None,
            )
            for i, (data, _mime) in enumerate(blobs)
        ]
        messages = await _bot.send_media_group(chat, media)
        for i, msg in enumerate(messages or []):
            _remember_telegram_photo(entry_id, i, msg)


async def _next_send_job(now: int) -> dict | None:
    try:
        async with database.async_session_factory() as session:
            stmt = (
                select(SendQueue)
                .where(SendQueue.status == "pending", SendQueue.next_at <= now)
                .order_by(SendQueue.created_at, SendQueue.entry_id)
                .limit(1)
            )
            job = (await session.execute(stmt)).scalar_one_or_none()
            if job is not None:
                return {
                    "entry_id": job.entry_id,
                    "attempts": job.attempts,
                    "source": "sqlalchemy",
                }
    except Exception as exc:  # noqa: BLE001
        log.warning("sqlalchemy outbox lookup failed, trying legacy queue: %s", exc)
    legacy = db.next_send_job(now)
    if legacy is not None:
        legacy["source"] = "legacy"
    return legacy


async def _mark_sent(entry_id: int) -> None:
    now = int(time.time())
    try:
        async with database.async_session_factory() as session:
            await session.execute(
                update(SendQueue)
                .where(SendQueue.entry_id == entry_id)
                .values(
                    status="sent",
                    last_error=None,
                    last_attempt_at=now,
                    last_error_at=None,
                )
            )
            await session.commit()
            return
    except Exception as exc:  # noqa: BLE001
        log.warning("sqlalchemy outbox mark_sent failed, trying legacy queue: %s", exc)
    db.mark_sent(entry_id)


async def _mark_send_canceled(entry_id: int, error: str = "entry unavailable") -> None:
    now = int(time.time())
    try:
        async with database.async_session_factory() as session:
            await session.execute(
                update(SendQueue)
                .where(SendQueue.entry_id == entry_id)
                .values(
                    status="canceled",
                    last_error=(error or "")[:500],
                    last_attempt_at=now,
                    last_error_at=now,
                )
            )
            await session.commit()
            return
    except Exception as exc:  # noqa: BLE001
        log.warning("sqlalchemy outbox cancel failed, trying legacy queue: %s", exc)
    db.mark_send_canceled(entry_id, error)


async def _mark_send_retry(entry_id: int, attempts: int, next_at: int, error: str) -> None:
    now = int(time.time())
    try:
        async with database.async_session_factory() as session:
            await session.execute(
                update(SendQueue)
                .where(SendQueue.entry_id == entry_id)
                .values(
                    attempts=attempts,
                    next_at=next_at,
                    last_error=(error or "")[:500],
                    last_attempt_at=now,
                    last_error_at=now,
                )
            )
            await session.commit()
            return
    except Exception as exc:  # noqa: BLE001
        log.warning("sqlalchemy outbox retry mark failed, trying legacy queue: %s", exc)
    db.mark_send_retry(entry_id, attempts, next_at, error)


async def worker() -> None:
    global _wake
    _wake = asyncio.Event()
    log.info("outbox worker started (pending=%s)", db.pending_send_count())
    while True:
        if _bot is None:
            await asyncio.sleep(5)
            continue

        now = int(time.time())
        job = await _next_send_job(now)
        if job is None:
            _wake.clear()
            try:
                await asyncio.wait_for(_wake.wait(), timeout=15)
            except asyncio.TimeoutError:
                pass
            continue

        entry_id = job["entry_id"]
        try:
            await _send_one(entry_id)
            await _mark_sent(entry_id)
            log.info("channel send ok: entry=%s", entry_id)
        except Exception as exc:  # noqa: BLE001
            attempts = job["attempts"] + 1
            retry_after = getattr(exc, "retry_after", None)
            delay = int(retry_after) if retry_after else _BACKOFF[min(attempts - 1, len(_BACKOFF) - 1)]
            await _mark_send_retry(entry_id, attempts, now + delay, str(exc))
            log.warning("channel send failed: entry=%s attempt=%s err=%s retry_in=%ss",
                        entry_id, attempts, exc, delay)
            await asyncio.sleep(1)


def ensure_started() -> None:
    global _started
    if _started:
        return
    _started = True
    asyncio.create_task(worker())
