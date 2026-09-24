from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class ActivityLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    reys_id: int
    actor: str
    action: str
    tovar_turi: Optional[str] = None
    from_type: Optional[str] = None
    to_type: Optional[str] = None
    weight: Optional[float] = None
    coefficient: Optional[float] = None
    net: Optional[float] = None
    box_weight: Optional[float] = None
    coefficient_mode: Optional[str] = None
    photos_count: int = 0
    created_at: int
    deleted_at: Optional[int] = None

    # Frontend compatibility
    report_id: Optional[int] = None
    gross_weight: Optional[float] = None
    net_weight: Optional[float] = None
    boxes_count: Optional[int] = None
    created_by: Optional[str] = None
    status: str = "completed"


class ActivityLogListResponse(BaseModel):
    items: List[ActivityLogResponse]
    total: int
