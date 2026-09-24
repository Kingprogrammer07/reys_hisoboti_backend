import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.cargo import CargoCreate
from app.schemas.entry import EntryCreate
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
