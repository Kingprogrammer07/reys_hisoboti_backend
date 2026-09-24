from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class PhotoMetadata(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    idx: int
    mime: str = "image/jpeg"
    size: int = 0
    storage_backend: str = "disk"
    storage_key: Optional[str] = None
    url: Optional[str] = None


class EntryCreate(BaseModel):
    reys_id: int = Field(..., description="Tegishli Reys ID")
    box_code: str = Field(..., min_length=1, max_length=60, description="Karobka kodi / shtrix-kod")
    tovar_turi: str = Field(..., min_length=1, max_length=60, description="Tovar turi")
    gross_weight: float = Field(..., gt=0.0, description="Og'irlik (Gross weight, W)")
    tare_weight: float = Field(0.0, description="Karobka og'irligi (Tare weight, T)")
    coefficient_mode: str = Field("none", description="none | box | fixed | custom")
    created_by: str = Field("operator", max_length=100)

    @field_validator("tare_weight")
    @classmethod
    def validate_tare_weight(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Karobka og'irligi manfiy bo'lishi mumkin emas")
        if v > 10.0:
            raise ValueError("Karobka og'irligi 10 kg dan oshmasligi kerak (ADR-001)")
        return v


class EntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reys_id: int
    box_code: str
    tovar_turi: str
    gross_weight: float
    tare_weight: float
    net_weight: float
    coefficient_mode: str
    created_by: str
    created_at: int
    deleted_at: Optional[int] = None
    photos: List[PhotoMetadata] = []
    
    # Frontend compatibility fields
    boxCode: Optional[str] = None
    grossWeight: Optional[float] = None
    tareWeight: Optional[float] = None
    netWeight: Optional[float] = None
    photoUrl: Optional[str] = None
    photoUrls: List[str] = []
    createdAt: Optional[str] = None


class EntryListResponse(BaseModel):
    items: List[EntryResponse]
    total: int
