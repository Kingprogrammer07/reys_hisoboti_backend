from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_session
from ..database import get_db_session
from ..schemas.cargo import CargoCreate, CargoListResponse, CargoResponse, CargoUpdate
from ..services.cargo_service import CargoService

router = APIRouter(prefix="/api/cargos", tags=["cargos"], dependencies=[Depends(require_session)])


def get_service(session: AsyncSession = Depends(get_db_session)) -> CargoService:
    return CargoService(session)


@router.get("", response_model=CargoListResponse)
async def list_cargos(
    include_deleted: bool = Query(False, description="O'chirilganlarni ham ko'rsatish"),
    service: CargoService = Depends(get_service),
):
    items = await service.list_cargos(include_deleted=include_deleted)
    return CargoListResponse(items=items, total=len(items))


@router.post("", response_model=CargoResponse, status_code=status.HTTP_201_CREATED)
async def create_cargo(
    data: CargoCreate,
    service: CargoService = Depends(get_service),
):
    try:
        return await service.create_cargo(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{cargo_id}", response_model=CargoResponse)
async def get_cargo(
    cargo_id: int,
    service: CargoService = Depends(get_service),
):
    cargo = await service.get_cargo(cargo_id)
    if not cargo:
        raise HTTPException(status_code=404, detail="Kargo topilmadi")
    return cargo


@router.put("/{cargo_id}", response_model=CargoResponse)
async def update_cargo(
    cargo_id: int,
    data: CargoUpdate,
    service: CargoService = Depends(get_service),
):
    try:
        return await service.update_cargo(cargo_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{cargo_id}")
async def delete_cargo(
    cargo_id: int,
    service: CargoService = Depends(get_service),
):
    ok = await service.delete_cargo(cargo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Kargo topilmadi yoki allaqachon o'chirilgan")
    return {"ok": True, "message": "Kargo savatchaga ko'chirildi"}


@router.post("/{cargo_id}/restore", response_model=CargoResponse)
async def restore_cargo(
    cargo_id: int,
    service: CargoService = Depends(get_service),
):
    ok = await service.restore_cargo(cargo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Kargo topilmadi yoki savatchada emas")
    cargo = await service.get_cargo(cargo_id)
    return cargo
