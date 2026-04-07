# LAN Cloud Sync: Features Inventory

This document is based only on facts visible in the current repository. It does not include abstract recommendations and does not infer features that are not present in code.

## 1. Implemented System Features

### Server-side features

- FastAPI server application exists in `server/app/main.py`.
- HTTP API for file metadata listing is implemented:
  `GET /files`.
- HTTP API for file upload is implemented:
  `POST /upload`.
- HTTP API for file download is implemented:
  `GET /download`.
- HTTP API for file deletion is implemented:
  `DELETE /files`.
- Server stores file metadata in SQLite `server/data.db`.
- Server stores physical files in `server/storage/`.
- Server computes SHA-256 for uploaded files.
- Server increments file version on content change.
- Server increments file version on delete.
- Server stores delete state using `deleted` flag.
- Server stores `device_id` of the last modifying side.
- Server validates relative paths and rejects absolute paths or `..`.
- Server streams downloads in chunks.
- Server removes physical file from storage on delete.
- Server reconciles DB metadata with actual storage content when `GET /files` is called.
  This includes:
  creating metadata rows for storage files not present in DB,
  marking DB rows deleted when physical files are missing,
  restoring deleted DB rows if matching storage files exist again.

### Client-side features

- CLI client exists in `client/app/cli/main.py`.
- CLI commands implemented:
  `sync`, `status`, `upload`, `download`, `list`, `watch`.
- Client stores local sync state in SQLite `client/data/sync_state.db`.
- Client scans local sync folder recursively.
- Client computes SHA-256 for local files.
- Client captures file `mtime` during local scan.
- Client requests remote metadata from the server.
- Client uploads local files to the server.
- Client downloads remote files from the server.
- Client sends delete requests to the server.
- Client builds a sync plan by comparing:
  local filesystem state,
  remote metadata,
  local DB state.
- Client supports these sync actions:
  `upload`,
  `download`,
  `delete_remote`,
  `delete_local`,
  `mark_local_deleted`,
  `conflict_download`.
- Client persists local tombstone state with `deleted=True`.
- Client handles conflict by:
  saving the local version as a separate `_conflict` file,
  then downloading the remote version to the original path.
- Client supports initial sync cycle on watcher start.
- Client watches local filesystem changes with `watchdog`.
- Client debounces local file events using `threading.Timer`.
- Client polls the server periodically in a background thread.
- Client prevents overlapping sync cycles with a `Lock`.

### Operational and support features

- Start scripts exist for server and client watcher in `scripts/`.
- Stop scripts exist for server and client watcher in `scripts/`.
- Status-check script exists in `scripts/check_status.bat`.
- Log files are written through script-level stdout/stderr redirection into `logs/`.

## 2. Missing or Incomplete Features Based on the Current Repository

Only items directly supported by code or TODO comments are listed here.

### Features explicitly incomplete in code

- Real delta sync is not implemented.
  Evidence:
  `client/app/sync/network.py` has `updated_since`,
  but server `GET /files` does not accept or process it.
- Pagination for server file listing is not implemented.
  Evidence:
  TODO in `server/app/services/file_service.py`.
- Updated-since filtering on server file listing is not implemented.
  Evidence:
  TODO in `server/app/services/file_service.py`.
- Separate persistence of server delta checkpoints is not implemented.
  Evidence:
  TODO in `client/app/sync/sync_engine.py`.
- Conflict policy extraction is not implemented as a separate mechanism.
  Evidence:
  TODO in `client/app/sync/sync_engine.py`.
- Additional multi-device merge rules are not implemented.
  Evidence:
  TODO in `client/app/sync/sync_engine.py`.
- Upload-time hash calculation during streaming write is not implemented.
  Evidence:
  TODO in `server/app/services/storage_service.py`;
  hash is calculated after the file is already written.

### Features not found in the repository

- No GUI is present in the repository.
  Evidence:
  the active client interface is CLI;
  no GUI code or GUI library usage was found.
- No web frontend is present in the repository.
- No WebSocket or other push-based remote update channel was found.
- No authentication or authorization layer was found in server routes.
- No user/account model was found.
- No explicit test suite was found in the repository tree.
- No `.env`-based or separate config file system was found;
  configuration is stored in code constants and start scripts.

### Scope note

- The absence list above is limited to what can be checked directly from the repository.
- It does not claim that these features are required by every coursework format.

## 3. Minimal GUI for Defense: Needed or Not

### Fact-based assessment

- The current repository already provides an executable interaction surface through CLI commands and start/stop/status scripts.
- The current repository does not contain any GUI implementation.
- The implemented system behavior that can be demonstrated from code is:
  server start,
  client watcher start,
  local file change detection,
  upload/download/delete behavior,
  conflict copy creation,
  local sync-state listing.

### Conclusion based only on the repository

- A minimal GUI is not technically required for the system to run, because the implemented interface is CLI-based and operational scripts already exist.
- A minimal GUI would be an additional feature, not an already implemented part of the system.
- If the defense format expects visual interaction, the current repository does not provide that layer.

### What is directly missing for GUI support

- No GUI entry point.
- No GUI framework usage.
- No view layer for file list, sync status, conflict state, or server connection state.
- No event wiring from sync engine to any visual components.
