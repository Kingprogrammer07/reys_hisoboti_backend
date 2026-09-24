from __future__ import annotations

from .bin_router import router as bin_router
from .cargo_router import router as cargo_router
from .entry_router import router as entry_router
from .inventory_router import router as inventory_router
from .reys_router import router as reys_router

__all__ = [
    "cargo_router",
    "reys_router",
    "entry_router",
    "bin_router",
    "inventory_router",
]
