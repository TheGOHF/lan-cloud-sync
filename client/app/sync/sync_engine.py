from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .config import BASE_PATH
from .db import (
    LocalFileEntry,
    get_latest_sync_time,
    get_local_file,
    init_db,
    list_local_files,
    upsert_local_file,
)
from .file_utils import LocalFileState, calculate_file_hash, scan_local_folder
from .network import download_file, get_files, upload_file
from shared.schemas import FileMetadataResponse


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SyncAction:
    action: str
    path: str
    reason: str
    conflict_path: str | None = None


def sync(local_base_path: Path = BASE_PATH, device_id: str = "unknown-device") -> list[SyncAction]:
    init_db()
    actions = get_sync_plan(local_base_path=local_base_path)
    apply_actions(actions, local_base_path=local_base_path, device_id=device_id)
    return actions


def get_sync_plan(local_base_path: Path = BASE_PATH) -> list[SyncAction]:
    local_base_path.mkdir(parents=True, exist_ok=True)

    # TODO: Re-enable delta sync once the server supports updated_since filtering explicitly.
    server_files = get_files()
    server_index = {file_record.path: file_record for file_record in server_files}
    local_index = scan_local_folder(local_base_path)
    local_db_index = {entry.path: entry for entry in list_local_files()}

    return build_sync_plan(
        local_index=local_index,
        server_index=server_index,
        local_db_index=local_db_index,
    )


def build_sync_plan(
    *,
    local_index: dict[str, LocalFileState],
    server_index: dict[str, FileMetadataResponse],
    local_db_index: dict[str, LocalFileEntry],
) -> list[SyncAction]:
    actions: list[SyncAction] = []

    for path in sorted(set(local_index) | set(server_index)):
        local_state = local_index.get(path)
        remote_state = server_index.get(path)
        local_record = local_db_index.get(path)

        if remote_state is None and local_state is not None:
            actions.append(SyncAction(action="upload", path=path, reason="missing_on_server"))
            continue

        if remote_state is None:
            continue

        if remote_state.deleted:
            logger.info("Skip deleted remote file: %s", path)
            continue

        if local_state is None:
            actions.append(SyncAction(action="download", path=path, reason="missing_locally"))
            continue

        if local_state["hash"] == remote_state.hash:
            logger.debug("No changes for %s at version %s", path, remote_state.version)
            continue

        if local_record is None:
            remote_timestamp = _to_timestamp(remote_state.updated_at)
            if local_state["mtime"] > remote_timestamp:
                actions.append(
                    SyncAction(
                        action="upload",
                        path=path,
                        reason=f"local_newer_than_remote_v{remote_state.version}",
                    )
                )
            else:
                actions.append(
                    SyncAction(
                        action="download",
                        path=path,
                        reason=f"remote_v{remote_state.version}_newer_or_equal",
                    )
                )
            continue

        local_changed = local_state["hash"] != local_record.hash
        remote_changed = (
            remote_state.version != local_record.version
            or remote_state.hash != local_record.hash
        )

        if local_changed and remote_changed:
            actions.append(
                SyncAction(
                    action="conflict_download",
                    path=path,
                    reason="local_and_remote_changed",
                    conflict_path=_build_conflict_relative_path(path),
                )
            )
            continue

        if local_changed:
            actions.append(
                SyncAction(
                    action="upload",
                    path=path,
                    reason=f"local_changed_since_v{local_record.version}",
                )
            )
            continue

        if remote_changed:
            actions.append(
                SyncAction(
                    action="download",
                    path=path,
                    reason=f"remote_changed_to_v{remote_state.version}",
                )
            )

    return actions


def apply_actions(
    actions: list[SyncAction],
    *,
    local_base_path: Path = BASE_PATH,
    device_id: str,
) -> None:
    for action in actions:
        apply_action(action, local_base_path=local_base_path, device_id=device_id)


def apply_action(action: SyncAction, *, local_base_path: Path, device_id: str) -> None:
    local_path = local_base_path / Path(action.path)

    if action.action == "upload":
        logger.info("Upload %s (%s)", action.path, action.reason)
        response = upload_file(local_path=local_path, remote_path=action.path, device_id=device_id)
        upsert_local_file(
            path=action.path,
            file_hash=response.hash,
            version=response.version,
            last_synced=datetime.now(timezone.utc),
            conflict=False,
        )
        return

    if action.action == "download":
        logger.info("Download %s (%s)", action.path, action.reason)
        download_file(remote_path=action.path, local_path=local_path)
        remote_record = _get_remote_record(action.path)
        upsert_local_file(
            path=action.path,
            file_hash=calculate_file_hash(local_path),
            version=remote_record.version,
            last_synced=datetime.now(timezone.utc),
            conflict=False,
        )
        return

    if action.action == "conflict_download":
        logger.warning("Conflict for %s, preserving local copy", action.path)
        _save_conflict_copy(action=action, local_base_path=local_base_path)
        download_file(remote_path=action.path, local_path=local_path)
        remote_record = _get_remote_record(action.path)
        upsert_local_file(
            path=action.path,
            file_hash=calculate_file_hash(local_path),
            version=remote_record.version,
            last_synced=datetime.now(timezone.utc),
            conflict=False,
        )
        return

    logger.warning("Unknown sync action for %s: %s", action.path, action.action)


def _to_timestamp(value: datetime) -> float:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc).timestamp()

    return value.timestamp()


def _build_conflict_relative_path(path: str) -> str:
    path_obj = Path(path)
    return path_obj.with_name(f"{path_obj.stem}_conflict{path_obj.suffix}").as_posix()


def _save_conflict_copy(*, action: SyncAction, local_base_path: Path) -> None:
    if action.conflict_path is None:
        return

    source_path = local_base_path / Path(action.path)
    conflict_path = local_base_path / Path(action.conflict_path)
    conflict_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, conflict_path)

    source_record = get_local_file(action.path)
    upsert_local_file(
        path=action.conflict_path,
        file_hash=calculate_file_hash(conflict_path),
        version=source_record.version if source_record is not None else 0,
        last_synced=datetime.now(timezone.utc),
        conflict=True,
    )


def _get_remote_record(path: str) -> FileMetadataResponse:
    for file_record in get_files():
        if file_record.path == path:
            return file_record

    raise FileNotFoundError(path)


# TODO: Persist server delta checkpoints separately from file rows to reduce GET /files load.
# TODO: Extract conflict policies before adding delete propagation and multi-device merge rules.
