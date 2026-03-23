from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.file_service import (
    create_or_update_file,
    get_file_by_path,
    list_files,
    to_file_metadata_response,
)
from app.services.hashing import calculate_file_sha256
from app.services.storage_service import get_existing_file_path, iter_file_chunks, save_upload_file
from shared.schemas import FileMetadataResponse, UploadFileResponse


router = APIRouter()


@router.get("/files", response_model=list[FileMetadataResponse])
def get_files(db: Session = Depends(get_db)) -> list[FileMetadataResponse]:
    file_records = list_files(db)
    return [to_file_metadata_response(file_record) for file_record in file_records]


@router.post("/upload", response_model=UploadFileResponse)
def upload_file(
    file: UploadFile = File(...),
    path: str = Form(...),
    device_id: str = Form(...),
    db: Session = Depends(get_db),
) -> UploadFileResponse:
    try:
        normalized_path, file_path = save_upload_file(file=file, relative_path=path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    file_hash = calculate_file_sha256(file_path)
    file_record = create_or_update_file(
        db,
        path=normalized_path,
        file_hash=file_hash,
        device_id=device_id,
    )

    return UploadFileResponse(
        path=file_record.path,
        version=file_record.version,
        hash=file_record.hash,
    )


@router.get("/download")
def download_file(
    path: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    file_record = get_file_by_path(db, path=path)

    if file_record is None or file_record.deleted:
        raise HTTPException(status_code=404, detail="File not found.")

    try:
        file_path = get_existing_file_path(file_record.path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="File not found.") from exc

    file_size = file_path.stat().st_size
    encoded_filename = quote(file_path.name)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        "Content-Length": str(file_size),
    }

    return StreamingResponse(
        iter_file_chunks(file_path),
        media_type="application/octet-stream",
        headers=headers,
    )
