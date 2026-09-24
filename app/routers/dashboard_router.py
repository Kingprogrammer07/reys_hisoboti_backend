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


_stats_cache: tuple[float, Dict[str, Any]] | None = None


def invalidate_dashboard_cache() -> None:
    global _stats_cache
    _stats_cache = None


@router.get("/api/dashboard/stats")
async def get_dashboard_stats(session: AsyncSession = Depends(get_db_session)) -> Dict[str, Any]:
    global _stats_cache
    now_mono = time.monotonic()
    if _stats_cache is not None and (now_mono - _stats_cache[0]) < 3.0:
        return _stats_cache[1]

    # Calculate Tashkent today timestamp (UTC+5)
    now_ts = int(time.time())
    now_dt = datetime.datetime.fromtimestamp(now_ts, tz=datetime.timezone(datetime.timedelta(hours=5)))
    today_start_dt = now_dt.replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_ts = int(today_start_dt.timestamp())

    # Combined single query for 5 high-level metrics
    metrics_stmt = select(
        select(func.coalesce(func.sum(Entry.net_weight), 0.0)).where(Entry.deleted_at.is_(None)).scalar_subquery().label("total_net_weight"),
        select(func.count(Entry.id)).where(Entry.deleted_at.is_(None)).scalar_subquery().label("total_entries_count"),
        select(func.count(Cargo.id)).where(Cargo.deleted_at.is_(None)).scalar_subquery().label("cargos_count"),
        select(func.count(Reys.id)).where(Reys.deleted_at.is_(None)).scalar_subquery().label("reys_count"),
        select(func.coalesce(func.sum(Entry.net_weight), 0.0)).where(
            Entry.deleted_at.is_(None),
            Entry.created_at >= today_start_ts,
        ).scalar_subquery().label("today_added_kg"),
    )
    metrics_row = (await session.execute(metrics_stmt)).one()

    total_net_weight = round(float(metrics_row.total_net_weight or 0.0), 2)
    total_entries_count = int(metrics_row.total_entries_count or 0)
    cargos_count = int(metrics_row.cargos_count or 0)
    reys_count = int(metrics_row.reys_count or 0)
    today_added_kg = round(float(metrics_row.today_added_kg or 0.0), 2)

    # Total gross & tare weights
    weights_stmt = select(
        func.coalesce(func.sum(Entry.gross_weight), 0.0).label("gross"),
        func.coalesce(func.sum(Entry.tare_weight), 0.0).label("tare"),
    ).where(Entry.deleted_at.is_(None))
    weights_row = (await session.execute(weights_stmt)).one()
    total_gross_weight = round(float(weights_row.gross or 0.0), 2)
    total_karobka_weight = round(float(weights_row.tare or 0.0), 2)

    # Today entries count
    today_entries_stmt = select(func.count(Entry.id)).where(
        Entry.deleted_at.is_(None),
        Entry.created_at >= today_start_ts,
    )
    today_entries_count = int((await session.execute(today_entries_stmt)).scalar() or 0)

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

    # 6. Cargos statistics breakdown
    cargos_stmt = (
        select(Cargo)
        .options(selectinload(Cargo.reyslar).selectinload(Reys.entries))
        .where(Cargo.deleted_at.is_(None))
        .order_by(Cargo.id.desc())
    )
    cargos_res = await session.execute(cargos_stmt)
    cargos_list = cargos_res.scalars().all()
    cargos_stats = []
    for c in cargos_list:
        active_reyslar = [r for r in c.reyslar if r.deleted_at is None]
        c_toza = 0.0
        c_karobka = 0.0
        for r in active_reyslar:
            r_entries = [e for e in r.entries if e.deleted_at is None]
            r_toza = sum(e.net_weight for e in r_entries) if r_entries else r.toza_kg
            r_karobka = sum(e.tare_weight for e in r_entries) if r_entries else r.karobka_plus_kg
            c_toza += r_toza
            c_karobka += r_karobka

        c_toza = round(c_toza, 2)
        c_karobka = round(c_karobka, 2)
        c_gross = round(c_toza + c_karobka, 2)
        all_entries = [e for r in active_reyslar for e in r.entries if e.deleted_at is None]
        c_entries_count = len(all_entries)
        latest_date = max([r.date for r in active_reyslar], default=None)
        share_pct = round((c_toza / total_net_weight * 100) if total_net_weight > 0 else 0, 1)

        cargos_stats.append({
            "id": c.id,
            "code": c.code,
            "created_at": c.created_at,
            "reys_count": len(active_reyslar),
            "total_toza_kg": c_toza,
            "total_karobka_plus_kg": c_karobka,
            "total_gross_kg": c_gross,
            "entries_count": c_entries_count,
            "latest_date": latest_date,
            "share_percentage": share_pct,
        })

    # 7. Recent reyslar (top 5)
    recent_reys_stmt = (
        select(Reys)
        .options(selectinload(Reys.cargo), selectinload(Reys.entries))
        .where(Reys.deleted_at.is_(None))
        .order_by(Reys.id.desc())
        .limit(5)
    )
    recent_reys_res = await session.execute(recent_reys_stmt)
    recent_reys_items = recent_reys_res.scalars().all()
    recent_reyslar = []
    for r in recent_reys_items:
        r_entries = [e for e in r.entries if e.deleted_at is None]
        r_toza = round(sum(e.net_weight for e in r_entries) if r_entries else r.toza_kg, 2)
        r_karobka = round(sum(e.tare_weight for e in r_entries) if r_entries else r.karobka_plus_kg, 2)
        recent_reyslar.append({
            "id": r.id,
            "code": r.code,
            "cargo_id": r.cargo_id,
            "cargo_code": r.cargo.code if r.cargo else "-",
            "custom_name": r.custom_name,
            "date": r.date,
            "toza_kg": r_toza,
            "karobka_plus_kg": r_karobka,
            "total_gross_kg": round(r_toza + r_karobka, 2),
            "entries_count": len(r_entries),
        })

    # 8. Recent activities (latest 10 entries)
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

    result = {
        "status": "success",
        "total_net_weight": total_net_weight,
        "total_gross_weight": total_gross_weight,
        "total_karobka_weight": total_karobka_weight,
        "total_entries_count": total_entries_count,
        "cargos_count": cargos_count,
        "reys_count": reys_count,
        "active_tovar_types_count": len(inventory_items),
        "today_added_kg": today_added_kg,
        "today_entries_count": today_entries_count,
        "cargos_stats": cargos_stats,
        "recent_reyslar": recent_reyslar,
        "inventory": inventory_items,
        "recent_activities": activities,
    }
    _stats_cache = (now_mono, result)
    return result


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
