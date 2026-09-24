from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ReysCreate(BaseModel):
    cargo_id: Optional[int] = Field(None, description="Parent Cargo ID")
    code: str = Field(..., min_length=1, max_length=60, description="Reys kodi (masalan: REYS-001)")
    date: str = Field(..., min_length=8, max_length=20, description="Reys sanasi (YYYY-MM-DD)")
    custom_name: Optional[str] = Field(None, max_length=100, description="Ixtiyoriy reys nomi")


class ReysUpdate(BaseModel):
    cargo_id: Optional[int] = None
    code: Optional[str] = Field(None, min_length=1, max_length=60)
    date: Optional[str] = Field(None, min_length=8, max_length=20)
    custom_name: Optional[str] = Field(None, max_length=100)


class ReysAdjust(BaseModel):
    actual_toza_kg: float = Field(..., ge=0.0, description="Faktik tarozidagi toza vazn (A)")
    actual_karobka_plus_kg: float = Field(0.0, ge=0.0, description="Faktik karobka qo'shimcha vazni")


class ReysResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cargo_id: Optional[int] = None
    code: str
    custom_name: Optional[str] = None
    date: str
    toza_kg: float
    karobka_plus_kg: float
    adjustment_diff_kg: float
    original_toza_kg: Optional[float] = None
    original_karobka_plus_kg: Optional[float] = None
    created_at: int
    deleted_at: Optional[int] = None


class ReysListResponse(BaseModel):
    items: List[ReysResponse]
    total: int
