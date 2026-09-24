from __future__ import annotations

import datetime
import time
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database import get_db_session
from ..models.cargo import Cargo
from ..models.entry import Entry
from ..models.reys import Reys

router = APIRouter(tags=["dashboard"])


@router.get("/api/dashboard/stats")
async def get_dashboard_stats(session: AsyncSession = Depends(get_db_session)) -> Dict[str, Any]:
    # 1. Total net weight across all active entries
    net_weight_res = await session.execute(
        select(func.coalesce(func.sum(Entry.net_weight), 0.0)).where(Entry.deleted_at.is_(None))
    )
    total_net_weight = round(float(net_weight_res.scalar_one_or_none() or 0.0), 2)

    # 2. Total entries count
    entries_count_res = await session.execute(
        select(func.count(Entry.id)).where(Entry.deleted_at.is_(None))
    )
    total_entries_count = int(entries_count_res.scalar_one_or_none() or 0)

    # 3. Active Cargos and Reys counts
    cargos_count_res = await session.execute(
        select(func.count(Cargo.id)).where(Cargo.deleted_at.is_(None))
    )
    cargos_count = int(cargos_count_res.scalar_one_or_none() or 0)

    reys_count_res = await session.execute(
        select(func.count(Reys.id)).where(Reys.deleted_at.is_(None))
    )
    reys_count = int(reys_count_res.scalar_one_or_none() or 0)

    # 4. Today's added net weight (Tashkent timezone UTC+5)
    now_ts = int(time.time())
    now_dt = datetime.datetime.fromtimestamp(now_ts, tz=datetime.timezone(datetime.timedelta(hours=5)))
    today_start_dt = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_ts = int(today_start_dt.timestamp())

    today_weight_res = await session.execute(
        select(func.coalesce(func.sum(Entry.net_weight), 0.0)).where(
            Entry.deleted_at.is_(None),
            Entry.created_at >= today_start_ts,
        )
    )
    today_added_kg = round(float(today_weight_res.scalar_one_or_none() or 0.0), 2)

    # 5. Inventory summary (group by tovar_turi)
    inv_stmt = (
        select(
            Entry.tovar_turi,
            func.coalesce(func.sum(Entry.net_weight), 0.0).label("balance_weight"),
            func.count(Entry.id).label("package_count"),
        )
        .where(Entry.deleted_at.is_(None))
        .group_by(Entry.tovar_turi)
        .order_by(func.sum(Entry.net_weight).desc())
    )
    inv_res = await session.execute(inv_stmt)
    inventory_items = []
    for idx, row in enumerate(inv_res.all()):
        inventory_items.append({
            "id": idx + 1,
            "tovar_turi": row.tovar_turi.capitalize(),
            "balance_weight": round(float(row.balance_weight), 2),
            "package_count": row.package_count,
            "box_coefficient": 1.0,
        })

    # 6. Recent activities (latest 10 entries)
    recent_stmt = (
        select(Entry)
        .options(selectinload(Entry.photos))
        .where(Entry.deleted_at.is_(None))
        .order_by(Entry.created_at.desc(), Entry.id.desc())
        .limit(10)
    )
    recent_res = await session.execute(recent_stmt)
    recent_entries = recent_res.scalars().all()
    activities = []
    for e in recent_entries:
        dt_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(e.created_at))
        activities.append({
            "id": e.id,
            "reys_id": e.reys_id,
            "box_code": e.box_code,
            "tovar_turi": e.tovar_turi.capitalize(),
            "gross_weight": e.gross_weight,
            "coefficient": e.tare_weight,
            "net_weight": e.net_weight,
            "created_by": e.created_by,
            "photos_count": len(e.photos) if e.photos else 0,
            "created_at": dt_str,
        })

    return {
        "status": "success",
        "total_net_weight": total_net_weight,
        "total_entries_count": total_entries_count,
        "cargos_count": cargos_count,
        "reys_count": reys_count,
        "active_tovar_types_count": len(inventory_items),
        "today_added_kg": today_added_kg,
        "inventory": inventory_items,
        "recent_activities": activities,
    }


@router.get("/api/activities")
async def get_all_activities(
    limit: int = 100,
    session: AsyncSession = Depends(get_db_session),
) -> List[Dict[str, Any]]:
    recent_stmt = (
        select(Entry)
        .options(selectinload(Entry.photos))
        .where(Entry.deleted_at.is_(None))
        .order_by(Entry.created_at.desc(), Entry.id.desc())
        .limit(limit)
    )
    recent_res = await session.execute(recent_stmt)
    entries = recent_res.scalars().all()
    results = []
    for e in entries:
        dt_str = time.strftime("%Y-%m-%d %H:%M", time.localtime(e.created_at))
        results.append({
            "id": e.id,
            "reys_id": e.reys_id,
            "box_code": e.box_code,
            "tovar_turi": e.tovar_turi.capitalize(),
            "gross_weight": e.gross_weight,
            "coefficient": e.tare_weight,
            "net_weight": e.net_weight,
            "created_by": e.created_by,
            "photos_count": len(e.photos) if e.photos else 0,
            "created_at": dt_str,
        })
    return results
