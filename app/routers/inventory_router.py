from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session
from ..repositories.inventory_repo import InventoryRepository
from ..schemas.inventory import (
    CustomTypeCreate,
    CustomTypeResponse,
    InventoryListResponse,
    InventoryResponse,
)

router = APIRouter(tags=["inventory"])


def get_repo(session: AsyncSession = Depends(get_db_session)) -> InventoryRepository:
    return InventoryRepository(session)


@router.get("/api/reys/{reys_id}/inventory", response_model=InventoryListResponse)
async def list_inventory(
    reys_id: int,
    repo: InventoryRepository = Depends(get_repo),
):
    items = await repo.list_by_reys(reys_id)
    responses = [InventoryResponse.model_validate(i) for i in items]
    return InventoryListResponse(items=responses, total=len(responses))


@router.get("/api/custom-types", response_model=List[CustomTypeResponse])
async def list_custom_types(
    repo: InventoryRepository = Depends(get_repo),
):
    items = await repo.list_custom_types()
    return [CustomTypeResponse.model_validate(i) for i in items]


@router.post("/api/custom-types", response_model=CustomTypeResponse, status_code=status.HTTP_201_CREATED)
async def add_custom_type(
    data: CustomTypeCreate,
    repo: InventoryRepository = Depends(get_repo),
):
    ct = await repo.add_custom_type(data.name)
    return CustomTypeResponse.model_validate(ct)


@router.delete("/api/custom-types/{name}")
async def delete_custom_type(
    name: str,
    repo: InventoryRepository = Depends(get_repo),
):
    ok = await repo.delete_custom_type(name)
    if not ok:
        raise HTTPException(status_code=404, detail="Tovar turi topilmadi")
    return {"ok": True, "message": "Tovar turi o'chirildi"}
