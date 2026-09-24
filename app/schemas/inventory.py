from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class InventoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reys_id: int
    tovar_turi: str
    weight: float
    package_count: int
    box_coefficient: float
    updated_at: int


class InventoryListResponse(BaseModel):
    items: List[InventoryResponse]
    total: int


class CustomTypeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60, description="Yangi tovar turi nomi")


class CustomTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    created_at: int
    deleted_at: Optional[int] = None
