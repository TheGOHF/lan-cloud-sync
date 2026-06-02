from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from server.app.config import get_server_config
from server.app.db.base import Base


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine

    db_path = get_server_config().db_path.resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is not None:
        return _session_factory

    _session_factory = sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        class_=Session,
    )
    return _session_factory


def init_db() -> None:
    from server.app.models.file import FileRecord

    Base.metadata.create_all(bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()
