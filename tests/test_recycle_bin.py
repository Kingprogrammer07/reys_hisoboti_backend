import pytest
import time
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.bin_repo import RecycleBinRepository
from app.schemas.cargo import CargoCreate
from app.services.cargo_service import CargoService


@pytest.mark.asyncio
async def test_recycle_bin_retention_and_restoration(db_session: AsyncSession):
    cargo_service = CargoService(db_session)
    bin_repo = RecycleBinRepository(db_session)

    cargo = await cargo_service.create_cargo(CargoCreate(code="CARGO-BIN-TEST"))

    # Soft delete cargo
    await cargo_service.delete_cargo(cargo.id)

    # List bin items
    deleted_items = await bin_repo.list_deleted_items()
    assert len(deleted_items) >= 1
    found = next((i for i in deleted_items if i["entity_type"] == "cargo" and i["entity_id"] == cargo.id), None)
    assert found is not None
    assert found["days_remaining"] == 30

    # Restore from bin
    restored = await bin_repo.restore_item("cargo", cargo.id)
    assert restored is True

    # Check it is no longer in bin
    deleted_items_after = await bin_repo.list_deleted_items()
    assert all(not (i["entity_type"] == "cargo" and i["entity_id"] == cargo.id) for i in deleted_items_after)
