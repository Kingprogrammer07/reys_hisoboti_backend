from __future__ import annotations

from typing import Optional
from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SendQueue(Base):
    """Durable Telegram send queue model."""
    __tablename__ = "send_queue"

    entry_id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_at: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False, index=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_attempt_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    last_error_at: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[int] = mapped_column(BigInteger, nullable=False)
