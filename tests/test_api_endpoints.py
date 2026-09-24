import pytest
import httpx


@pytest.mark.asyncio
async def test_cargo_and_reys_api_flow(client: httpx.AsyncClient):
    # 1. Create Cargo via API
    resp = await client.post("/api/cargos", json={"code": "API-CARGO-01"})
    assert resp.status_code == 201
    cargo_data = resp.json()
    assert cargo_data["code"] == "API-CARGO-01"
    cargo_id = cargo_data["id"]

    # 2. List Cargos
    resp = await client.get("/api/cargos")
    assert resp.status_code == 200
    list_data = resp.json()
    assert list_data["total"] >= 1

    # 3. Create Reys via API
    resp = await client.post("/api/reys", json={
        "cargo_id": cargo_id,
        "code": "API-REYS-01",
        "date": "2026-09-24",
        "custom_name": "API Test Reys",
    })
    assert resp.status_code == 201
    reys_data = resp.json()
    assert reys_data["code"] == "API-REYS-01"
    reys_id = reys_data["id"]

    # 4. Create Entry via JSON API
    resp = await client.post("/api/entries/json", json={
        "reys_id": reys_id,
        "box_code": "BOX-API-01",
        "tovar_turi": "mandarin",
        "gross_weight": 20.0,
        "tare_weight": 2.0,
        "coefficient_mode": "none",
        "created_by": "operator",
    })
    assert resp.status_code == 201
    entry_data = resp.json()
    assert entry_data["net_weight"] == 18.0
    assert entry_data["boxCode"] == "BOX-API-01"

    # 5. List Entries for Reys
    resp = await client.get(f"/api/reys/{reys_id}/entries")
    assert resp.status_code == 200
    entries_list = resp.json()
    assert entries_list["total"] == 1
    assert entries_list["items"][0]["net_weight"] == 18.0


@pytest.mark.asyncio
async def test_cors_headers(client: httpx.AsyncClient):
    # Test request with Origin from React dev server
    resp = await client.get("/api/cargos", headers={"Origin": "http://localhost:5173"})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert resp.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_uzbek_error_messages_on_api(client: httpx.AsyncClient):
    # 1. 404 Cargo Not Found in Uzbek
    resp = await client.get("/api/cargos/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Kargo topilmadi"

    # 2. 404 Reys Not Found in Uzbek
    resp = await client.get("/api/reys/999999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "Reys topilmadi"

    # 3. 400 Duplicate Cargo error in Uzbek
    resp1 = await client.post("/api/cargos", json={"code": "DUPLICATE-UZBEK"})
    assert resp1.status_code == 201
    resp2 = await client.post("/api/cargos", json={"code": "DUPLICATE-UZBEK"})
    assert resp2.status_code == 400
    assert "allaqachon mavjud" in resp2.json()["detail"]


@pytest.mark.asyncio
async def test_auth_endpoints(client: httpx.AsyncClient):
    from app import config
    # 1. Login with wrong PIN -> 401
    resp_bad = await client.post("/api/auth/login", json={"pin": "wrong_pin_9999"})
    assert resp_bad.status_code == 401
    assert "noto'g'ri" in resp_bad.json()["detail"]

    # 2. Login with correct PIN -> 200
    resp_ok = await client.post("/api/auth/login", json={"pin": config.ADMIN_PASSWORD})
    assert resp_ok.status_code == 200
    data = resp_ok.json()
    assert data["ok"] is True
    assert data["user"] == "admin"
    assert "token" in data
    token = data["token"]

    # 3. Check /api/auth/me with Bearer token
    resp_me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_me.status_code == 200
    me_data = resp_me.json()
    assert me_data["authenticated"] is True
    assert me_data["user"] == "admin"

    # 4. Logout
    resp_logout = await client.post("/api/auth/logout")
    assert resp_logout.status_code == 200
    assert resp_logout.json()["ok"] is True

