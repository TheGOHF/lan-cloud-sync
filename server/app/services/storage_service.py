from __future__ import annotations

from collections.abc import Iterator
import shutil
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

from server.app.config import get_server_config

CHUNK_SIZE = 1024 * 1024


def get_storage_dir() -> Path:
    return get_server_config().storage_path.resolve()


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
    return get_storage_dir().joinpath(*normalized_path.split("/"))


def get_existing_file_path(relative_path: str) -> Path:
    file_path = build_storage_path(relative_path)

    if not file_path.is_file():
        raise FileNotFoundError(relative_path)

    return file_path


def list_storage_files() -> list[str]:
    relative_paths: list[str] = []
    storage_dir = get_storage_dir()

    if not storage_dir.exists():
        return relative_paths

    for file_path in storage_dir.rglob("*"):
        if file_path.is_file():
            relative_paths.append(file_path.relative_to(storage_dir).as_posix())

    return sorted(relative_paths)


def delete_stored_file(relative_path: str) -> None:
    file_path = build_storage_path(relative_path)
    if file_path.exists():
        file_path.unlink()
        _remove_empty_parent_directories(file_path.parent)


def iter_file_chunks(file_path: Path) -> Iterator[bytes]:
    file_obj: BinaryIO = file_path.open("rb")
    try:
        while chunk := file_obj.read(CHUNK_SIZE):
            yield chunk
    finally:
        file_obj.close()


def _remove_empty_parent_directories(directory: Path) -> None:
    storage_dir = get_storage_dir()
    while directory != storage_dir and directory.exists():
        try:
            directory.rmdir()
        except OSError:
            return

        directory = directory.parent
