from __future__ import annotations

import hashlib
from pathlib import Path


def calculate_file_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()

    with file_path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()
