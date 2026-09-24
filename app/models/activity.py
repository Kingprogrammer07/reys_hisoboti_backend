from __future__ import annotations

from typing import Optional
from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class ActivityLog(Base):
    __tablename__ = "activity_logs_v2"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reys_id: Mapped[int] = mapped_column(
        ForeignKey("reyslar.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)  # 'reys', 'adjust', 'top', etc.
    tovar_turi: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    from_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    to_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    coefficient: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    net: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    box_weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    coefficient_mode: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    photos_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
