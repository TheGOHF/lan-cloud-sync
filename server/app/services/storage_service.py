from __future__ import annotations

from collections.abc import Iterator
import shutil
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile


BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"
CHUNK_SIZE = 1024 * 1024


def save_upload_file(*, file: UploadFile, relative_path: str) -> tuple[str, Path]:
    normalized_path = normalize_relative_path(relative_path)
    destination = build_storage_path(normalized_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("wb") as output:
        shutil.copyfileobj(file.file, output)

    # TODO: Compute SHA-256 during write to avoid a second disk read on upload.
    return normalized_path, destination


def normalize_relative_path(relative_path: str) -> str:
    normalized_path = relative_path.replace("\\", "/")
    path_obj = Path(normalized_path)

    if path_obj.is_absolute() or ".." in path_obj.parts:
        raise ValueError("Invalid file path.")

    normalized_parts = [part for part in path_obj.parts if part not in ("", ".")]
    if not normalized_parts:
        raise ValueError("Invalid file path.")

    return "/".join(normalized_parts)


def build_storage_path(relative_path: str) -> Path:
    normalized_path = normalize_relative_path(relative_path)
    return STORAGE_DIR.joinpath(*normalized_path.split("/"))


def get_existing_file_path(relative_path: str) -> Path:
    file_path = build_storage_path(relative_path)

    if not file_path.is_file():
        raise FileNotFoundError(relative_path)

    return file_path


def iter_file_chunks(file_path: Path) -> Iterator[bytes]:
    file_obj: BinaryIO = file_path.open("rb")
    try:
        while chunk := file_obj.read(CHUNK_SIZE):
            yield chunk
    finally:
        file_obj.close()
