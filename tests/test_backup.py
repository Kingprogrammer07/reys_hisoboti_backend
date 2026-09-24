import datetime
import os
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app import config
from app.config import _parse_chat_id
from app.server import app
from app.services import backup_service, backup_scheduler


def test_parse_chat_id_normalization():
    # User's channel ID: 1002982052676 -> should normalize to -1002982052676
    assert _parse_chat_id("1002982052676") == -1002982052676
    assert _parse_chat_id("-1002982052676") == -1002982052676
    assert _parse_chat_id("1002982052676") == -1002982052676
    assert _parse_chat_id("") is None
    assert _parse_chat_id("@mychannel") == "@mychannel"


def test_generate_backup_filename():
    dt = datetime.datetime(2026, 9, 24, 21, 17)
    filename = backup_service.generate_backup_filename(dt)
    assert filename == "hisobot_backup_2026-09-24_21-17.dump"
    assert filename.startswith("hisobot_backup_")
    assert filename.endswith(".dump")


def test_format_telegram_caption():
    stats = {
        "cargos": 5,
        "reyslar": 12,
        "entries": 340,
        "photos": 680,
        "inventory": 20,
        "custom_types": 4,
        "backend": "postgres",
    }
    caption = backup_service.format_telegram_caption(
        stats=stats,
        file_size_bytes=1024 * 1024 * 2,  # 2 MB
        filename="hisobot_backup_2026-09-24_21-17.dump",
        dt=datetime.datetime(2026, 9, 24, 21, 17),
    )

    assert "MANDARIN REYS HISOBOTI — ZAXIRA NUSXASI" in caption
    assert "hisobot_backup_2026-09-24_21-17.dump" in caption
    assert "PostgreSQL (Neon)" in caption
    assert "2.00 MB" in caption
    assert "Kargolar: 5 ta" in caption
    assert "Reyslar: 12 ta" in caption
    assert "Partiyalar (yozuvlar): 340 ta" in caption
    assert "Rasmlar havolalari: 680 ta" in caption
    assert "Zaxira muvaffaqiyatli olindi" in caption


@pytest.mark.asyncio
async def test_create_and_cleanup_backup(tmp_path: Path):
    # Temporarily set BACKUP_DIR to tmp_path
    orig_backup_dir = config.BACKUP_DIR
    orig_backend = config.DATABASE_BACKEND
    config.BACKUP_DIR = tmp_path
    config.DATABASE_BACKEND = "sqlite"

    try:
        # Create backup
        dest_path, stats = await backup_service.create_backup()
        assert dest_path.exists()
        assert dest_path.name.startswith("hisobot_backup_")
        assert dest_path.name.endswith(".dump")
        assert dest_path.stat().st_size > 0
        assert "cargos" in stats

        # Test cleanup with retention 0 days (simulate old file)
        # Set file modification time to 10 days ago
        old_time = datetime.datetime.now().timestamp() - (10 * 86400)
        os.utime(dest_path, (old_time, old_time))

        deleted_count = backup_service.cleanup_old_backups(retention_days=1)
        assert deleted_count == 1
        assert not dest_path.exists()

    finally:
        config.BACKUP_DIR = orig_backup_dir
        config.DATABASE_BACKEND = orig_backend


@pytest.mark.asyncio
async def test_backup_api_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Test /api/backup/stats
        stats_resp = await client.get("/api/backup/stats")
        assert stats_resp.status_code == 200
        data = stats_resp.json()
        assert data["status"] == "success"
        assert "stats" in data
        assert "scheduler" in data
        assert data["backup_channel"] == "-1002982052676"

        # 2. Test /api/backup/download
        dl_resp = await client.get("/api/backup/download")
        assert dl_resp.status_code == 200
        assert "application/octet-stream" in dl_resp.headers["content-type"]
        assert "hisobot_backup_" in dl_resp.headers["content-disposition"]
        assert len(dl_resp.content) > 0
