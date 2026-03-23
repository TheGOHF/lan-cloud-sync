from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.file import FileRecord
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


def list_files(db: Session) -> Sequence[FileRecord]:
    # TODO: Add pagination and updated-since filters for large datasets and delta sync.
    return db.query(FileRecord).order_by(FileRecord.path.asc()).all()


def to_file_metadata_response(file_record: FileRecord) -> FileMetadataResponse:
    return FileMetadataResponse(
        path=file_record.path,
        version=file_record.version,
        hash=file_record.hash,
        updated_at=file_record.updated_at,
        deleted=file_record.deleted,
    )
