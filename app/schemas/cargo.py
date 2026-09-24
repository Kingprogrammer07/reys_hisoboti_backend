from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field

from .reys import ReysResponse


class CargoCreate(BaseModel):
    code: str = Field(..., min_length=1, max_length=60, description="Kargo kodi (masalan: CARGO-2026-001)")


class CargoUpdate(BaseModel):
    code: Optional[str] = Field(None, min_length=1, max_length=60)


class CargoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    created_at: int
    deleted_at: Optional[int] = None
    reys_count: int = 0
    total_toza_kg: float = 0.0
    total_karobka_plus_kg: float = 0.0
    reyslar: List[ReysResponse] = []


class CargoListResponse(BaseModel):
    items: List[CargoResponse]
    total: int
