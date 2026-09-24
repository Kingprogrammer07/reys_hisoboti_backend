from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class RecycleBinItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entity_type: str = Field(..., description="cargo | reys | entry | activity")
    entity_id: int
    title: str
    details: Optional[str] = None
    deleted_at: int
    days_remaining: int = 30


class RecycleBinListResponse(BaseModel):
    items: List[RecycleBinItem]
    total: int


class RestoreRequest(BaseModel):
    entity_type: str = Field(..., description="cargo | reys | entry | activity")
    entity_id: int
