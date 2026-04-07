from __future__ import annotations

from collections.abc import Iterator
import hashlib
from pathlib import Path
from typing import TypedDict

from .config import get_client_config


class LocalFileState(TypedDict):
    hash: str
    mtime: float


def iter_file_chunks(file_path: Path, chunk_size: int | None = None) -> Iterator[bytes]:
    resolved_chunk_size = chunk_size or get_client_config().chunk_size
    with file_path.open("rb") as file_obj:
        while chunk := file_obj.read(resolved_chunk_size):
            yield chunk


def calculate_file_hash(file_path: Path) -> str:
    sha256 = hashlib.sha256()

    for chunk in iter_file_chunks(file_path):
        sha256.update(chunk)

    return sha256.hexdigest()


def scan_local_folder(base_path: Path) -> dict[str, LocalFileState]:
    local_files: dict[str, LocalFileState] = {}

    if not base_path.exists():
        return local_files

    for file_path in base_path.rglob("*"):
        if not file_path.is_file():
            continue

        relative_path = file_path.relative_to(base_path).as_posix()
        stat_result = file_path.stat()
        local_files[relative_path] = {
            "hash": calculate_file_hash(file_path),
            "mtime": stat_result.st_mtime,
        }

    return local_files
