from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from server.app.models.file import FileRecord
from server.app.services.hashing import calculate_file_sha256
from server.app.services.storage_service import build_storage_path, list_storage_files
from shared.schemas import FileMetadataResponse


def create_or_update_file(
    db: Session,
    *,
    path: str,
    file_hash: str,
    device_id: str,
) -> FileRecord:
    with db.begin():
        file_record = db.execute(
            select(FileRecord).where(FileRecord.path == path)
        ).scalar_one_or_none()

        if file_record is None:
            file_record = FileRecord(
                path=path,
                version=1,
                hash=file_hash,
                updated_at=datetime.now(timezone.utc),
                device_id=device_id,
                deleted=False,
            )
            db.add(file_record)
        elif file_record.hash != file_hash or file_record.deleted:
            file_record.version += 1
            file_record.hash = file_hash
            file_record.updated_at = datetime.now(timezone.utc)
            file_record.device_id = device_id
            file_record.deleted = False

    db.refresh(file_record)
    return file_record


def get_file_by_path(db: Session, *, path: str) -> Optional[FileRecord]:
    return db.query(FileRecord).filter(FileRecord.path == path).first()


def list_files(
    db: Session,
    *,
    updated_since: datetime | None = None,
) -> Sequence[FileRecord]:
    _reconcile_storage_files(db)
    _reconcile_missing_storage_files(db)

    query = db.query(FileRecord)
    if updated_since is not None:
        query = query.filter(FileRecord.updated_at > updated_since)

    return query.order_by(FileRecord.path.asc()).all()


def soft_delete_file(
    db: Session,
    *,
    path: str,
    device_id: str,
) -> Optional[FileRecord]:
    with db.begin():
        file_record = db.execute(
            select(FileRecord).where(FileRecord.path == path)
        ).scalar_one_or_none()

        if file_record is None:
            return None

        if file_record.deleted:
            return file_record

        file_record.version += 1
        file_record.updated_at = datetime.now(timezone.utc)
        file_record.device_id = device_id
        file_record.deleted = True

    db.refresh(file_record)
    return file_record


def to_file_metadata_response(file_record: FileRecord) -> FileMetadataResponse:
    return FileMetadataResponse(
        path=file_record.path,
        version=file_record.version,
        hash=file_record.hash,
        updated_at=file_record.updated_at,
        deleted=file_record.deleted,
    )


def _reconcile_missing_storage_files(db: Session) -> None:
    with db.begin():
        file_records = db.execute(select(FileRecord)).scalars().all()
        now = datetime.now(timezone.utc)

        for file_record in file_records:
            if file_record.deleted:
                continue

            if build_storage_path(file_record.path).is_file():
                continue

            file_record.version += 1
            file_record.updated_at = now
            file_record.deleted = True


def _reconcile_storage_files(db: Session) -> None:
    with db.begin():
        now = datetime.now(timezone.utc)

        for relative_path in list_storage_files():
            file_path = build_storage_path(relative_path)
            file_hash = calculate_file_sha256(file_path)
            file_record = db.execute(
                select(FileRecord).where(FileRecord.path == relative_path)
            ).scalar_one_or_none()

            if file_record is None:
                db.add(
                    FileRecord(
                        path=relative_path,
                        version=1,
                        hash=file_hash,
                        updated_at=now,
                        device_id="server",
                        deleted=False,
                    )
                )
                continue

            if file_record.deleted:
                file_record.version += 1
                file_record.hash = file_hash
                file_record.updated_at = now
                file_record.device_id = "server"
                file_record.deleted = False
                continue

            if file_record.hash != file_hash:
                file_record.version += 1
                file_record.hash = file_hash
                file_record.updated_at = now
                file_record.device_id = "server"
