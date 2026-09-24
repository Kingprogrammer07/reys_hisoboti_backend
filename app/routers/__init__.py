from __future__ import annotations

from .backup_router import router as backup_router
from .bin_router import router as bin_router
from .cargo_router import router as cargo_router
from .dashboard_router import router as dashboard_router
from .entry_router import router as entry_router
from .inventory_router import router as inventory_router
from .reys_router import router as reys_router

__all__ = [
    "cargo_router",
    "reys_router",
    "entry_router",
    "bin_router",
    "inventory_router",
    "backup_router",
    "dashboard_router",
]

