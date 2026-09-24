from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import BigInteger, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .cargo import Cargo
    from .entry import Entry
    from .inventory import Inventory


class Reys(Base):
    __tablename__ = "reyslar"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    cargo_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cargos.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    custom_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    date: Mapped[str] = mapped_column(String(20), nullable=False)  # YYYY-MM-DD
    toza_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    karobka_plus_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    adjustment_diff_kg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    original_toza_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    original_karobka_plus_kg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    # Relationships
    cargo: Mapped[Optional[Cargo]] = relationship("Cargo", back_populates="reyslar")
    entries: Mapped[List[Entry]] = relationship(
        "Entry",
        back_populates="reys",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Entry.id.desc()",
    )
    inventory: Mapped[List[Inventory]] = relationship(
        "Inventory",
        back_populates="reys",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
