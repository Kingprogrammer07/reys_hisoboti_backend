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
