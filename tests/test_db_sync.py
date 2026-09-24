import pytest
from httpx import ASGITransport, AsyncClient

from app.server import app
from app.services import db_sync_worker


@pytest.mark.asyncio
async def test_init_sqlite_and_status():
    await db_sync_worker.init_sqlite_tables()
    status = db_sync_worker.get_database_status()
    assert "active_mode" in status
    assert "fallback_available" in status
    assert status["fallback_available"] is True


@pytest.mark.asyncio
async def test_system_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/system/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "database" in data
        assert "storage" in data
        assert "backup" in data
