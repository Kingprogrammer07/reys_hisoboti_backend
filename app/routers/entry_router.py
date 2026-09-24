from __future__ import annotations

from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from .. import config, storage
from ..database import get_db_session
from ..schemas.entry import EntryCreate, EntryListResponse, EntryResponse
from ..services.entry_service import EntryService

router = APIRouter(tags=["entries"])


def get_service(session: AsyncSession = Depends(get_db_session)) -> EntryService:
    return EntryService(session)


@router.get("/api/reys/{reys_id}/entries", response_model=EntryListResponse)
async def list_entries(
    reys_id: int,
    include_deleted: bool = Query(False),
    limit: int = Query(1000, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    service: EntryService = Depends(get_service),
):
    items = await service.list_entries(
        reys_id=reys_id,
        include_deleted=include_deleted,
        limit=limit,
        offset=offset,
    )
    return EntryListResponse(items=items, total=len(items))


@router.post("/api/reys/{reys_id}/entries", response_model=EntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry(
    reys_id: int,
    box_code: str = Form(..., description="Karobka kodi"),
    tovar_turi: str = Form(..., description="Tovar turi"),
    gross_weight: float = Form(..., description="Og'irlik (W)"),
    tare_weight: float = Form(0.0, description="Karobka og'irligi (T)"),
    coefficient_mode: str = Form("none"),
    created_by: str = Form("operator"),
    photos: List[UploadFile] = File(default=[]),
    service: EntryService = Depends(get_service),
):
    payload = EntryCreate(
        reys_id=reys_id,
        box_code=box_code,
        tovar_turi=tovar_turi,
        gross_weight=gross_weight,
        tare_weight=tare_weight,
        coefficient_mode=coefficient_mode,
        created_by=created_by,
    )

    photo_tuples = []
    for p in photos:
        if p.filename:
            content = await p.read()
            mime = p.content_type or "image/jpeg"
            photo_tuples.append((content, mime))

    try:
        return await service.record_entry(payload, photos=photo_tuples)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/entries/json", response_model=EntryResponse, status_code=status.HTTP_201_CREATED)
async def create_entry_json(
    data: EntryCreate,
    service: EntryService = Depends(get_service),
):
    """Direct JSON entry creation without photo binaries."""
    try:
        return await service.record_entry(data, photos=[])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/entries/{entry_id}", response_model=EntryResponse)
async def get_entry(
    entry_id: int,
    service: EntryService = Depends(get_service),
):
    entry = await service.get_entry(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Yozuv topilmadi")
    return entry


@router.delete("/api/entries/{entry_id}")
async def delete_entry(
    entry_id: int,
    service: EntryService = Depends(get_service),
):
    ok = await service.delete_entry(entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Yozuv topilmadi yoki allaqachon o'chirilgan")
    return {"ok": True, "message": "Yozuv savatchaga ko'chirildi"}


@router.post("/api/entries/{entry_id}/restore", response_model=EntryResponse)
async def restore_entry(
    entry_id: int,
    service: EntryService = Depends(get_service),
):
    ok = await service.restore_entry(entry_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Yozuv topilmadi yoki savatchada emas")
    entry = await service.get_entry(entry_id)
    return entry


@router.get("/api/entries/{entry_id}/photos/{idx}")
async def get_entry_photo(
    entry_id: int,
    idx: int,
    service: EntryService = Depends(get_service),
):
    """Serve photo from Cloudflare R2 or local disk."""
    entry = await service.entry_repo.get_by_id(entry_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Yozuv topilmadi")

    target_photo = None
    for p in entry.photos:
        if p.idx == idx:
            target_photo = p
            break

    if not target_photo:
        raise HTTPException(status_code=404, detail="Rasm topilmadi")

    if target_photo.storage_backend == "r2" and target_photo.storage_key:
        try:
            raw_bytes = storage.get_photo(target_photo.storage_key)
            return Response(content=raw_bytes, media_type=target_photo.mime)
        except Exception:
            pass

    # Disk fallback
    photo_path = config.DATA_DIR / "photos" / str(entry_id) / str(idx)
    if photo_path.exists():
        return FileResponse(path=str(photo_path), media_type=target_photo.mime)

    raise HTTPException(status_code=404, detail="Rasm fayli mavjud emas")
