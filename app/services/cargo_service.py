from __future__ import annotations

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.cargo import Cargo
from ..repositories.cargo_repo import CargoRepository
from ..schemas.cargo import CargoCreate, CargoResponse, CargoUpdate
from ..schemas.reys import ReysResponse


class CargoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CargoRepository(session)

    def _to_response(self, cargo: Cargo) -> CargoResponse:
        active_reyslar = [r for r in cargo.reyslar if r.deleted_at is None]
        total_toza = sum(r.toza_kg for r in active_reyslar)
        total_karobka = sum(r.karobka_plus_kg for r in active_reyslar)
        reys_responses = [ReysResponse.model_validate(r) for r in active_reyslar]

        return CargoResponse(
            id=cargo.id,
            code=cargo.code,
            created_at=cargo.created_at,
            deleted_at=cargo.deleted_at,
            reys_count=len(active_reyslar),
            total_toza_kg=round(total_toza, 3),
            total_karobka_plus_kg=round(total_karobka, 3),
            reyslar=reys_responses,
        )

    async def list_cargos(self, include_deleted: bool = False) -> List[CargoResponse]:
        cargos = await self.repo.list_all(include_deleted=include_deleted)
        return [self._to_response(c) for c in cargos]

    async def get_cargo(self, cargo_id: int) -> Optional[CargoResponse]:
        cargo = await self.repo.get_by_id(cargo_id)
        if not cargo:
            return None
        return self._to_response(cargo)

    async def create_cargo(self, data: CargoCreate) -> CargoResponse:
        existing = await self.repo.get_by_code(data.code)
        if existing:
            raise ValueError(f"'{data.code}' kodi bilan kargo allaqachon mavjud")
        cargo = await self.repo.create(data.code)
        return self._to_response(cargo)

    async def update_cargo(self, cargo_id: int, data: CargoUpdate) -> CargoResponse:
        cargo = await self.repo.get_by_id(cargo_id)
        if not cargo:
            raise ValueError("Kargo topilmadi")
        if data.code and data.code.strip().upper() != cargo.code:
            existing = await self.repo.get_by_code(data.code)
            if existing and existing.id != cargo_id:
                raise ValueError(f"'{data.code}' kodi band")
        updated = await self.repo.update(cargo, code=data.code)
        return self._to_response(updated)

    async def delete_cargo(self, cargo_id: int) -> bool:
        return await self.repo.soft_delete(cargo_id)

    async def restore_cargo(self, cargo_id: int) -> bool:
        return await self.repo.restore(cargo_id)
