from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .reys import Reys


class Inventory(Base):
    __tablename__ = "inventory_v2"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reys_id: Mapped[int] = mapped_column(
        ForeignKey("reyslar.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tovar_turi: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    package_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    box_coefficient: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    updated_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relationship
    reys: Mapped[Reys] = relationship("Reys", back_populates="inventory")


class CustomType(Base):
    __tablename__ = "custom_types_v2"

    name: Mapped[str] = mapped_column(String(60), primary_key=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
