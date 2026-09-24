from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db_session
from ..repositories.bin_repo import RecycleBinRepository
from ..schemas.bin import RecycleBinItem, RecycleBinListResponse, RestoreRequest

router = APIRouter(prefix="/api/bin", tags=["recycle_bin"])


def get_repo(session: AsyncSession = Depends(get_db_session)) -> RecycleBinRepository:
    return RecycleBinRepository(session)


@router.get("", response_model=RecycleBinListResponse)
async def list_recycle_bin(
    repo: RecycleBinRepository = Depends(get_repo),
):
    """List all deleted cargos, reyslar, and entries with remaining retention days."""
    raw_items = await repo.list_deleted_items()
    items = [RecycleBinItem.model_validate(i) for i in raw_items]
    return RecycleBinListResponse(items=items, total=len(items))


@router.post("/restore")
async def restore_item(
    data: RestoreRequest,
    repo: RecycleBinRepository = Depends(get_repo),
):
    """Restore a deleted item back to active status."""
    ok = await repo.restore_item(data.entity_type, data.entity_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail=f"{data.entity_type} ID {data.entity_id} topilmadi yoki savatchada emas",
        )
    return {"ok": True, "message": f"{data.entity_type} muvaffaqiyatli tiklandi"}


@router.post("/purge")
async def purge_expired_items(
    retention_days: int = 30,
    repo: RecycleBinRepository = Depends(get_repo),
):
    """Permanently delete items older than retention_days (ADR-003)."""
    count = await repo.purge_expired(retention_days=retention_days)
    return {"ok": True, "purged_count": count, "message": f"{count} ta eskirgan yozuv tozalandi"}
