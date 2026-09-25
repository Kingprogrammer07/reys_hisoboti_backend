import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.cargo import CargoCreate, CargoUpdate
from app.schemas.entry import EntryCreate
from app.schemas.reys import ReysAdjust, ReysCreate, ReysUpdate
from app.services.cargo_service import CargoService
from app.services.entry_service import EntryService
from app.services.reys_service import ReysService


@pytest.mark.asyncio
async def test_cargo_crud_and_uniqueness(db_session: AsyncSession):
    service = CargoService(db_session)

    # 1. Create Cargo
    cargo = await service.create_cargo(CargoCreate(code="CARGO-TEST-01"))
    assert cargo.id > 0
    assert cargo.code == "CARGO-TEST-01"

    # 2. Duplicate code should raise ValueError
    with pytest.raises(ValueError, match="allaqachon mavjud"):
        await service.create_cargo(CargoCreate(code="CARGO-TEST-01"))

    # 3. Update Cargo
    updated = await service.update_cargo(cargo.id, CargoUpdate(code="CARGO-TEST-01-RENAMED"))
    assert updated.code == "CARGO-TEST-01-RENAMED"

    # 4. Soft Delete Cargo
    del_ok = await service.delete_cargo(cargo.id)
    assert del_ok is True

    # Active list should not include deleted cargo
    active_cargos = await service.list_cargos(include_deleted=False)
    assert all(c.id != cargo.id for c in active_cargos)

    # 5. Restore Cargo
    rest_ok = await service.restore_cargo(cargo.id)
    assert rest_ok is True
    restored = await service.get_cargo(cargo.id)
    assert restored is not None
    assert restored.deleted_at is None


@pytest.mark.asyncio
async def test_cargo_restore_restores_reys_deleted_by_cascade(db_session: AsyncSession):
    cargo_service = CargoService(db_session)
    reys_service = ReysService(db_session)

    cargo = await cargo_service.create_cargo(CargoCreate(code="CARGO-CASCADE-RESTORE"))
    reys = await reys_service.create_reys(ReysCreate(
        cargo_id=cargo.id,
        code="REYS-CASCADE-RESTORE",
        date="2026-09-24",
    ))

    assert await cargo_service.delete_cargo(cargo.id) is True
    deleted_reys = await reys_service.repo.get_by_id(reys.id, include_deleted=True)
    assert deleted_reys is not None
    assert deleted_reys.deleted_at is not None

    assert await cargo_service.restore_cargo(cargo.id) is True
    restored_reys = await reys_service.repo.get_by_id(reys.id, include_deleted=True)
    assert restored_reys is not None
    assert restored_reys.deleted_at is None


@pytest.mark.asyncio
async def test_reys_crud_and_adjustment(db_session: AsyncSession):
    cargo_service = CargoService(db_session)
    reys_service = ReysService(db_session)

    cargo = await cargo_service.create_cargo(CargoCreate(code="CARGO-REYS-TEST"))

    # 1. Create Reys
    reys = await reys_service.create_reys(ReysCreate(
        cargo_id=cargo.id,
        code="REYS-001",
        date="2026-09-24",
        custom_name="Birinchi Reys",
    ))
    assert reys.id > 0
    assert reys.cargo_id == cargo.id
    assert reys.toza_kg == 0.0

    # 2. Adjust Reys
    adjusted = await reys_service.adjust_reys(
        reys.id,
        ReysAdjust(actual_toza_kg=1250.5, actual_karobka_plus_kg=55.0),
    )
    assert adjusted.toza_kg == 1250.5
    assert adjusted.karobka_plus_kg == 55.0
    assert adjusted.original_toza_kg == 0.0
    assert adjusted.adjustment_diff_kg == 1250.5

    # 3. Check cargo reflects updated reys totals
    cargo_detail = await cargo_service.get_cargo(cargo.id)
    assert cargo_detail.reys_count == 1
    assert cargo_detail.total_toza_kg == 1250.5
    assert cargo_detail.total_karobka_plus_kg == 55.0


@pytest.mark.asyncio
async def test_proportional_entry_scaling(db_session: AsyncSession):
    """Test proportional weight scaling when adjusting a reys with existing entries."""
    cargo_service = CargoService(db_session)
    reys_service = ReysService(db_session)
    entry_service = EntryService(db_session)

    cargo = await cargo_service.create_cargo(CargoCreate(code="CARGO-SCALE-TEST"))
    reys = await reys_service.create_reys(ReysCreate(
        cargo_id=cargo.id,
        code="REYS-SCALE-01",
        date="2026-09-24",
    ))

    # Add 2 entries: 10 kg net and 20 kg net (total = 30 kg)
    e1 = await entry_service.record_entry(EntryCreate(
        reys_id=reys.id,
        box_code="BOX-S1",
        tovar_turi="mandarin",
        gross_weight=11.0,
        tare_weight=1.0,
    ))
    assert e1.net_weight == 10.0

    e2 = await entry_service.record_entry(EntryCreate(
        reys_id=reys.id,
        box_code="BOX-S2",
        tovar_turi="mandarin",
        gross_weight=22.0,
        tare_weight=2.0,
    ))
    assert e2.net_weight == 20.0

    current_reys = await reys_service.get_reys(reys.id)
    assert current_reys.toza_kg == 30.0

    # Adjust reys to 60.0 kg (2x multiplier)
    adjusted = await reys_service.adjust_reys(
        reys.id,
        ReysAdjust(actual_toza_kg=60.0, actual_karobka_plus_kg=5.0),
    )
    assert adjusted.toza_kg == 60.0

    # Verify that entries scaled proportionally (10 -> 20, 20 -> 40)
    scaled_e1 = await entry_service.get_entry(e1.id)
    scaled_e2 = await entry_service.get_entry(e2.id)
    assert scaled_e1.net_weight == 20.0
    assert scaled_e2.net_weight == 40.0
