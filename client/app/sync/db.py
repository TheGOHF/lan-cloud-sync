from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from sqlalchemy import Boolean, DateTime, Integer, String, create_engine, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from .config import ClientConfig, get_client_config


class Base(DeclarativeBase):
    pass


class LocalFileEntry(Base):
    __tablename__ = "local_files"

    path: Mapped[str] = mapped_column(String, primary_key=True)
    hash: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    last_synced: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    conflict: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


_engine_cache: dict[Path, Engine] = {}
_session_factory_cache: dict[Path, sessionmaker[Session]] = {}


def init_db(config: ClientConfig | None = None) -> None:
    engine = get_engine(config)
    Base.metadata.create_all(bind=engine)
    _ensure_deleted_column(engine)


def get_local_file(path: str, config: ClientConfig | None = None) -> LocalFileEntry | None:
    with get_session_factory(config)() as session:
        return session.get(LocalFileEntry, path)


def upsert_local_file(
    *,
    path: str,
    file_hash: str,
    version: int,
    last_synced: datetime,
    conflict: bool,
    deleted: bool,
    config: ClientConfig | None = None,
) -> LocalFileEntry:
    session_factory = get_session_factory(config)

    with session_factory.begin() as session:
        entry = session.get(LocalFileEntry, path)
        if entry is None:
            entry = LocalFileEntry(
                path=path,
                hash=file_hash,
                version=version,
                last_synced=last_synced,
                conflict=conflict,
                deleted=deleted,
            )
            session.add(entry)
        else:
            entry.hash = file_hash
            entry.version = version
            entry.last_synced = last_synced
            entry.conflict = conflict
            entry.deleted = deleted

    with session_factory() as session:
        refreshed = session.get(LocalFileEntry, path)
        if refreshed is None:
            raise RuntimeError(f"Failed to persist local state for {path}.")
        return refreshed


def list_local_files(config: ClientConfig | None = None) -> Sequence[LocalFileEntry]:
    with get_session_factory(config)() as session:
        return session.execute(
            select(LocalFileEntry).order_by(LocalFileEntry.path.asc())
        ).scalars().all()


def get_latest_sync_time(config: ClientConfig | None = None) -> datetime | None:
    entries = list_local_files(config)
    if not entries:
        return None

    return max(entry.last_synced for entry in entries)


def get_engine(config: ClientConfig | None = None) -> Engine:
    resolved_config = config or get_client_config()
    db_path = resolved_config.local_db_path.resolve()
    engine = _engine_cache.get(db_path)
    if engine is not None:
        return engine

    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    _engine_cache[db_path] = engine
    return engine


def get_session_factory(config: ClientConfig | None = None) -> sessionmaker[Session]:
    resolved_config = config or get_client_config()
    db_path = resolved_config.local_db_path.resolve()
    session_factory = _session_factory_cache.get(db_path)
    if session_factory is not None:
        return session_factory

    session_factory = sessionmaker(
        bind=get_engine(resolved_config),
        autoflush=False,
        autocommit=False,
        class_=Session,
    )
    _session_factory_cache[db_path] = session_factory
    return session_factory


def _ensure_deleted_column(engine: Engine) -> None:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns("local_files")}
    if "deleted" in columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text("ALTER TABLE local_files ADD COLUMN deleted BOOLEAN NOT NULL DEFAULT 0")
        )
