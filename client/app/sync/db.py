from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.sync.config import LOCAL_DB_PATH


class Base(DeclarativeBase):
    pass


class LocalFileEntry(Base):
    __tablename__ = "local_files"

    path: Mapped[str] = mapped_column(String, primary_key=True)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    last_synced: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    conflict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(f"sqlite:///{LOCAL_DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_local_file(path: str) -> LocalFileEntry | None:
    with SessionLocal() as session:
        return session.get(LocalFileEntry, path)


def upsert_local_file(
    *,
    path: str,
    file_hash: str,
    version: int,
    last_synced: datetime,
    conflict: bool,
) -> LocalFileEntry:
    with SessionLocal.begin() as session:
        entry = session.get(LocalFileEntry, path)
        if entry is None:
            entry = LocalFileEntry(
                path=path,
                hash=file_hash,
                version=version,
                last_synced=last_synced,
                conflict=conflict,
            )
            session.add(entry)
        else:
            entry.hash = file_hash
            entry.version = version
            entry.last_synced = last_synced
            entry.conflict = conflict

    with SessionLocal() as session:
        refreshed = session.get(LocalFileEntry, path)
        if refreshed is None:
            raise RuntimeError(f"Failed to persist local state for {path}.")
        return refreshed


def list_local_files() -> Sequence[LocalFileEntry]:
    with SessionLocal() as session:
        return session.execute(
            select(LocalFileEntry).order_by(LocalFileEntry.path.asc())
        ).scalars().all()


def get_latest_sync_time() -> datetime | None:
    entries = list_local_files()
    if not entries:
        return None

    return max(entry.last_synced for entry in entries)
