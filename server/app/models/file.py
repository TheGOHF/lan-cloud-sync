from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FileRecord(Base):
    __tablename__ = "files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    path: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    device_id: Mapped[str] = mapped_column(String, nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
