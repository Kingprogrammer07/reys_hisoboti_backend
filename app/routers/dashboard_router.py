from __future__ import annotations

import datetime
import time
from typing import Any, Dict, List
from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import require_session
from ..database import get_db_session
from ..models.cargo import Cargo
from ..models.entry import Entry, EntryPhoto
from ..models.inventory import Inventory
from ..models.reys import Reys

router = APIRouter(tags=["dashboard"], dependencies=[Depends(require_session)])


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

    # Combined single query for high-level metrics.
    metrics_stmt = select(
        select(func.coalesce(func.sum(Entry.net_weight), 0.0)).where(Entry.deleted_at.is_(None)).scalar_subquery().label("total_net_weight"),
        select(func.coalesce(func.sum(Entry.gross_weight), 0.0)).where(Entry.deleted_at.is_(None)).scalar_subquery().label("total_gross_weight"),
        select(func.coalesce(func.sum(Entry.tare_weight), 0.0)).where(Entry.deleted_at.is_(None)).scalar_subquery().label("total_karobka_weight"),
        select(func.count(Entry.id)).where(Entry.deleted_at.is_(None)).scalar_subquery().label("total_entries_count"),
        select(func.count(Cargo.id)).where(Cargo.deleted_at.is_(None)).scalar_subquery().label("cargos_count"),
        select(func.count(Reys.id)).where(Reys.deleted_at.is_(None)).scalar_subquery().label("reys_count"),
        select(func.coalesce(func.sum(Entry.net_weight), 0.0)).where(
            Entry.deleted_at.is_(None),
            Entry.created_at >= today_start_ts,
        ).scalar_subquery().label("today_added_kg"),
        select(func.count(Entry.id)).where(
            Entry.deleted_at.is_(None),
            Entry.created_at >= today_start_ts,
        ).scalar_subquery().label("today_entries_count"),
    )
    metrics_row = (await session.execute(metrics_stmt)).one()

    total_net_weight = round(float(metrics_row.total_net_weight or 0.0), 2)
    total_gross_weight = round(float(metrics_row.total_gross_weight or 0.0), 2)
    total_karobka_weight = round(float(metrics_row.total_karobka_weight or 0.0), 2)
    total_entries_count = int(metrics_row.total_entries_count or 0)
    cargos_count = int(metrics_row.cargos_count or 0)
    reys_count = int(metrics_row.reys_count or 0)
    today_added_kg = round(float(metrics_row.today_added_kg or 0.0), 2)
    today_entries_count = int(metrics_row.today_entries_count or 0)

    # 5. Inventory summary (group by tovar_turi). Use inventory_v2 so transfers
    # such as "adashgan yuklar" are reflected without changing total reys weight.
    inv_stmt = (
        select(
            Inventory.tovar_turi,
            func.coalesce(func.sum(Inventory.weight), 0.0).label("balance_weight"),
            func.coalesce(func.sum(Inventory.package_count), 0).label("package_count"),
        )
        .group_by(Inventory.tovar_turi)
        .order_by(func.sum(Inventory.weight).desc())
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
    reys_totals = (
        select(
            Reys.id.label("reys_id"),
            Reys.cargo_id.label("cargo_id"),
            Reys.date.label("date"),
            func.coalesce(func.sum(Entry.net_weight), Reys.toza_kg, 0.0).label("toza_kg"),
            func.coalesce(func.sum(Entry.tare_weight), Reys.karobka_plus_kg, 0.0).label("karobka_kg"),
            func.count(Entry.id).label("entries_count"),
        )
        .outerjoin(Entry, and_(Entry.reys_id == Reys.id, Entry.deleted_at.is_(None)))
        .where(Reys.deleted_at.is_(None))
        .group_by(Reys.id)
        .subquery()
    )
    cargos_stmt = (
        select(
            Cargo.id,
            Cargo.code,
            Cargo.created_at,
            func.count(reys_totals.c.reys_id).label("reys_count"),
            func.coalesce(func.sum(reys_totals.c.toza_kg), 0.0).label("total_toza_kg"),
            func.coalesce(func.sum(reys_totals.c.karobka_kg), 0.0).label("total_karobka_plus_kg"),
            func.coalesce(func.sum(reys_totals.c.entries_count), 0).label("entries_count"),
            func.max(reys_totals.c.date).label("latest_date"),
        )
        .outerjoin(reys_totals, reys_totals.c.cargo_id == Cargo.id)
        .where(Cargo.deleted_at.is_(None))
        .group_by(Cargo.id)
        .order_by(Cargo.id.desc())
    )
    cargos_res = await session.execute(cargos_stmt)
    cargos_stats = []
    for c in cargos_res.all():
        c_toza = round(float(c.total_toza_kg or 0.0), 2)
        c_karobka = round(float(c.total_karobka_plus_kg or 0.0), 2)
        c_gross = round(c_toza + c_karobka, 2)
        share_pct = round((c_toza / total_net_weight * 100) if total_net_weight > 0 else 0, 1)

        cargos_stats.append({
            "id": c.id,
            "code": c.code,
            "created_at": c.created_at,
            "reys_count": int(c.reys_count or 0),
            "total_toza_kg": c_toza,
            "total_karobka_plus_kg": c_karobka,
            "total_gross_kg": c_gross,
            "entries_count": int(c.entries_count or 0),
            "latest_date": c.latest_date,
            "share_percentage": share_pct,
        })

    # 7. Recent reyslar (top 5)
    recent_reys_stmt = (
        select(
            Reys.id,
            Reys.code,
            Reys.cargo_id,
            Cargo.code.label("cargo_code"),
            Reys.custom_name,
            Reys.date,
            func.coalesce(func.sum(Entry.net_weight), Reys.toza_kg, 0.0).label("toza_kg"),
            func.coalesce(func.sum(Entry.tare_weight), Reys.karobka_plus_kg, 0.0).label("karobka_plus_kg"),
            func.count(Entry.id).label("entries_count"),
        )
        .outerjoin(Cargo, Cargo.id == Reys.cargo_id)
        .outerjoin(Entry, and_(Entry.reys_id == Reys.id, Entry.deleted_at.is_(None)))
        .where(Reys.deleted_at.is_(None))
        .group_by(Reys.id, Cargo.code)
        .order_by(Reys.id.desc())
        .limit(5)
    )
    recent_reys_res = await session.execute(recent_reys_stmt)
    recent_reyslar = []
    for r in recent_reys_res.all():
        r_toza = round(float(r.toza_kg or 0.0), 2)
        r_karobka = round(float(r.karobka_plus_kg or 0.0), 2)
        recent_reyslar.append({
            "id": r.id,
            "code": r.code,
            "cargo_id": r.cargo_id,
            "cargo_code": r.cargo_code or "-",
            "custom_name": r.custom_name,
            "date": r.date,
            "toza_kg": r_toza,
            "karobka_plus_kg": r_karobka,
            "total_gross_kg": round(r_toza + r_karobka, 2),
            "entries_count": int(r.entries_count or 0),
        })

    # 8. Recent activities (latest 10 entries)
    recent_stmt = (
        select(
            Entry.id,
            Entry.reys_id,
            Entry.box_code,
            Entry.tovar_turi,
            Entry.gross_weight,
            Entry.tare_weight,
            Entry.net_weight,
            Entry.created_by,
            Entry.created_at,
            func.count(EntryPhoto.id).label("photos_count"),
        )
        .outerjoin(EntryPhoto, EntryPhoto.entry_id == Entry.id)
        .where(Entry.deleted_at.is_(None))
        .group_by(Entry.id)
        .order_by(Entry.created_at.desc(), Entry.id.desc())
        .limit(10)
    )
    recent_res = await session.execute(recent_stmt)
    activities = []
    for e in recent_res.all():
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
            "photos_count": int(e.photos_count or 0),
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
        select(
            Entry.id,
            Entry.reys_id,
            Entry.box_code,
            Entry.tovar_turi,
            Entry.gross_weight,
            Entry.tare_weight,
            Entry.net_weight,
            Entry.created_by,
            Entry.created_at,
            func.count(EntryPhoto.id).label("photos_count"),
        )
        .outerjoin(EntryPhoto, EntryPhoto.entry_id == Entry.id)
        .where(Entry.deleted_at.is_(None))
        .group_by(Entry.id)
        .order_by(Entry.created_at.desc(), Entry.id.desc())
        .limit(limit)
    )
    recent_res = await session.execute(recent_stmt)
    results = []
    for e in recent_res.all():
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
            "photos_count": int(e.photos_count or 0),
            "created_at": dt_str,
        })
    return results
