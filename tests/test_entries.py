import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.cargo import CargoCreate
from app.schemas.entry import EntryAdjustmentCreate, EntryCreate
from app.schemas.reys import ReysCreate
from app.services.cargo_service import CargoService
from app.services.entry_service import EntryService
from app.services.reys_service import ReysService


@pytest.mark.asyncio
async def test_entry_validations_and_lifecycle(db_session: AsyncSession):
    cargo_service = CargoService(db_session)
    reys_service = ReysService(db_session)
    entry_service = EntryService(db_session)

    cargo = await cargo_service.create_cargo(CargoCreate(code="CARGO-ENTRY-TEST"))
    reys = await reys_service.create_reys(ReysCreate(
        cargo_id=cargo.id,
        code="REYS-ENTRY-01",
        date="2026-09-24",
    ))

    # 1. ADR-001: Tare > 10 kg should fail
    with pytest.raises(ValueError, match="10 kg dan oshmasligi kerak"):
        await entry_service.record_entry(EntryCreate(
            reys_id=reys.id,
            box_code="BOX-FAIL-01",
            tovar_turi="mandarin",
            gross_weight=25.0,
            tare_weight=11.0,
        ))

    # 2. ADR-002: Tare > 50% gross weight should fail
    with pytest.raises(ValueError, match="50% idan oshmasligi kerak"):
        await entry_service.record_entry(EntryCreate(
            reys_id=reys.id,
            box_code="BOX-FAIL-02",
            tovar_turi="mandarin",
            gross_weight=6.0,
            tare_weight=4.0,  # 4.0 > 3.0 (50% of 6.0)
        ))

    # 3. Valid entry creation
    entry = await entry_service.record_entry(
        EntryCreate(
            reys_id=reys.id,
            box_code="BOX-VALID-01",
            tovar_turi="mandarin",
            gross_weight=15.0,
            tare_weight=1.5,
        ),
        photos=[(b"fake_jpeg_photo_bytes_123", "image/jpeg")],
    )
    assert entry.id > 0
    assert entry.gross_weight == 15.0
    assert entry.tare_weight == 1.5
    assert entry.net_weight == 13.5
    assert len(entry.photos) == 1
    assert entry.photoUrls is not None and len(entry.photoUrls) == 1

    # 4. Reys total toza_kg should be updated
    updated_reys = await reys_service.get_reys(reys.id)
    assert updated_reys.toza_kg == 13.5

    # 5. Delete entry should revert reys total
    await entry_service.delete_entry(entry.id)
    reverted_reys = await reys_service.get_reys(reys.id)
    assert reverted_reys.toza_kg == 0.0

    # 6. Restore entry should restore reys total
    await entry_service.restore_entry(entry.id)
    restored_reys = await reys_service.get_reys(reys.id)
    assert restored_reys.toza_kg == 13.5


@pytest.mark.asyncio
async def test_entry_photo_r2_failure_falls_back_to_disk(db_session: AsyncSession, monkeypatch):
    cargo_service = CargoService(db_session)
    reys_service = ReysService(db_session)
    entry_service = EntryService(db_session)

    cargo = await cargo_service.create_cargo(CargoCreate(code="CARGO-R2-FALLBACK"))
    reys = await reys_service.create_reys(ReysCreate(
        cargo_id=cargo.id,
        code="REYS-R2-FALLBACK",
        date="2026-09-24",
    ))

    from app import storage

    monkeypatch.setattr(storage, "r2_enabled", lambda: True)

    def fail_put_photo(*args, **kwargs):
        raise RuntimeError("r2 down")

    monkeypatch.setattr(storage, "put_photo", fail_put_photo)

    entry = await entry_service.record_entry(
        EntryCreate(
            reys_id=reys.id,
            box_code="BOX-R2-FALLBACK",
            tovar_turi="mandarin",
            gross_weight=10.0,
            tare_weight=1.0,
        ),
        photos=[(b"not-really-an-image", "image/jpeg")],
    )

    assert entry.photos is not None
    assert len(entry.photos) == 1
    assert entry.photos[0].storage_backend == "disk"


@pytest.mark.asyncio
async def test_adjust_inventory_moves_weight_without_changing_reys_total(db_session: AsyncSession):
    cargo_service = CargoService(db_session)
    reys_service = ReysService(db_session)
    entry_service = EntryService(db_session)

    cargo = await cargo_service.create_cargo(CargoCreate(code="CARGO-ADJUST-TEST"))
    reys = await reys_service.create_reys(ReysCreate(
        cargo_id=cargo.id,
        code="REYS-ADJUST-TEST",
        date="2026-09-24",
    ))

    await entry_service.record_entry(EntryCreate(
        reys_id=reys.id,
        box_code="BOX-ADJUST-SOURCE",
        tovar_turi="mandarin",
        gross_weight=110.0,
        tare_weight=10.0,
    ))

    res = await entry_service.adjust_inventory(EntryAdjustmentCreate(
        reys_id=reys.id,
        from_type="mandarin",
        to_type="apelsin",
        weight=25.0,
    ))

    assert res.balances["mandarin"] == 75.0
    assert res.balances["apelsin"] == 25.0

    unchanged_reys = await reys_service.get_reys(reys.id)
    assert unchanged_reys.toza_kg == 100.0
