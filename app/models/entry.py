from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base

if TYPE_CHECKING:
    from .reys import Reys


class Entry(Base):
    __tablename__ = "entries"
    __table_args__ = (
        Index("ix_entries_reys_deleted_id", "reys_id", "deleted_at", "id"),
        Index("ix_entries_deleted_created", "deleted_at", "created_at"),
        Index("ix_entries_type_deleted", "tovar_turi", "deleted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    reys_id: Mapped[int] = mapped_column(
        ForeignKey("reyslar.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    box_code: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    tovar_turi: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    gross_weight: Mapped[float] = mapped_column(Float, nullable=False)  # Og'irlik
    tare_weight: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)  # Karobka og'irligi
    net_weight: Mapped[float] = mapped_column(Float, nullable=False)  # Toza vazn
    coefficient_mode: Mapped[str] = mapped_column(String(20), default="none", nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), default="operator", nullable=False)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
    deleted_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    # Relationships
    reys: Mapped[Reys] = relationship("Reys", back_populates="entries")
    photos: Mapped[List[EntryPhoto]] = relationship(
        "EntryPhoto",
        back_populates="entry",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="EntryPhoto.idx.asc()",
    )


class EntryPhoto(Base):
    __tablename__ = "entry_photos_v2"
    __table_args__ = (
        Index("ix_entry_photos_entry_idx", "entry_id", "idx"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entry_id: Mapped[int] = mapped_column(
        ForeignKey("entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    mime: Mapped[str] = mapped_column(String(50), default="image/jpeg", nullable=False)
    size: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(20), default="disk", nullable=False)  # 'r2' | 'disk'
    storage_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    telegram_file_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Relationship
    entry: Mapped[Entry] = relationship("Entry", back_populates="photos")
