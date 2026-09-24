from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session
from ..schemas.reys import (
    ReysAdjust,
    ReysCreate,
    ReysListResponse,
    ReysResponse,
    ReysUpdate,
)
from ..services.reys_service import ReysService

router = APIRouter(prefix="/api/reys", tags=["reys"])


def get_service(session: AsyncSession = Depends(get_db_session)) -> ReysService:
    return ReysService(session)


@router.get("", response_model=ReysListResponse)
async def list_reys(
    cargo_id: Optional[int] = Query(None, description="Kargo bo'yicha filter"),
    include_deleted: bool = Query(False, description="O'chirilganlarni ham ko'rsatish"),
    service: ReysService = Depends(get_service),
):
    items = await service.list_reys(cargo_id=cargo_id, include_deleted=include_deleted)
    return ReysListResponse(items=items, total=len(items))


@router.post("", response_model=ReysResponse, status_code=status.HTTP_201_CREATED)
async def create_reys(
    data: ReysCreate,
    service: ReysService = Depends(get_service),
):
    try:
        return await service.create_reys(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{reys_id}", response_model=ReysResponse)
async def get_reys(
    reys_id: int,
    service: ReysService = Depends(get_service),
):
    reys = await service.get_reys(reys_id)
    if not reys:
        raise HTTPException(status_code=404, detail="Reys topilmadi")
    return reys


@router.put("/{reys_id}", response_model=ReysResponse)
async def update_reys(
    reys_id: int,
    data: ReysUpdate,
    service: ReysService = Depends(get_service),
):
    try:
        return await service.update_reys(reys_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{reys_id}")
async def delete_reys(
    reys_id: int,
    service: ReysService = Depends(get_service),
):
    ok = await service.delete_reys(reys_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Reys topilmadi yoki allaqachon o'chirilgan")
    return {"ok": True, "message": "Reys savatchaga ko'chirildi"}


@router.post("/{reys_id}/restore", response_model=ReysResponse)
async def restore_reys(
    reys_id: int,
    service: ReysService = Depends(get_service),
):
    ok = await service.restore_reys(reys_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Reys topilmadi yoki savatchada emas")
    reys = await service.get_reys(reys_id)
    return reys


@router.post("/{reys_id}/adjust", response_model=ReysResponse)
async def adjust_reys(
    reys_id: int,
    data: ReysAdjust,
    service: ReysService = Depends(get_service),
):
    try:
        return await service.adjust_reys(reys_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
