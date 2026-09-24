from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .reys import Reys


class Cargo(Base):
    __tablename__ = "cargos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    # Relationships
    reyslar: Mapped[List[Reys]] = relationship(
        "Reys",
        back_populates="cargo",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Reys.id.desc()",
    )
