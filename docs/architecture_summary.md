# LAN Cloud Sync: Architecture Summary

This summary is based only on facts visible in the current repository. If more than one interpretation is possible, that is stated explicitly.

## 1. Main System Components

### Client side

- CLI entry point in `client/app/cli/main.py`.
- Sync engine in `client/app/sync/sync_engine.py`.
- File watcher and polling loop in `client/app/sync/watcher.py`.
- Network client in `client/app/sync/network.py`.
- Local sync-state database in `client/app/sync/db.py`.
- Local file scan and hashing utilities in `client/app/sync/file_utils.py`.
- Client configuration constants in `client/app/sync/config.py`.

### Server side

- FastAPI application in `server/app/main.py`.
- HTTP API routes in `server/app/api/routes.py`.
- DB session layer in `server/app/db/session.py`.
- File metadata model in `server/app/models/file.py`.
- Metadata logic in `server/app/services/file_service.py`.
- Physical storage logic in `server/app/services/storage_service.py`.
- Hashing logic in `server/app/services/hashing.py`.

### Shared part

- Shared API schemas in `shared/schemas.py`.

### Persistent storage

- Server metadata DB: `server/data.db`.
- Server file storage: `server/storage/`.
- Client local state DB: `client/data/sync_state.db`.
- Client working folder: configured by `BASE_PATH` in `client/app/sync/config.py`.

## 2. Client and Server Roles

### Client role

- Watches the local sync folder for file changes.
- Periodically polls the server for remote changes.
- Scans local files and calculates hashes.
- Reads previous sync state from local SQLite.
- Builds a sync plan by comparing local files, server metadata, and local DB state.
- Executes sync actions: upload, download, remote delete, local delete, local tombstone update, conflict handling.

### Server role

- Exposes HTTP endpoints for file list, upload, download, and delete.
- Stores physical file content under `server/storage/`.
- Stores metadata and version state in SQLite.
- Computes hashes for uploaded and storage-resident files.
- Reconciles metadata with physical storage when listing files.

### Interpretation note

- The current code clearly implements a client-server file sync design.
- It can also be described as a polling-based sync system with local file watching.
- Both descriptions are consistent with the repository.

## 3. Module Interactions

### Client-side interaction chain

- `client/app/cli/main.py`
  calls `sync()`, `get_sync_plan()`, `apply_action()`, `watch_forever()`, and local DB listing functions.
- `client/app/sync/watcher.py`
  triggers `run_sync_cycle()`, which calls `get_sync_plan()` and `apply_actions()` from `sync_engine.py`.
- `client/app/sync/sync_engine.py`
  reads local files via `file_utils.py`,
  reads and writes local state via `db.py`,
  calls server operations via `network.py`.
- `client/app/sync/network.py`
  exchanges data with server routes and validates responses with models from `shared/schemas.py`.

### Server-side interaction chain

- `server/app/main.py`
  initializes DB and mounts `routes.py`.
- `server/app/api/routes.py`
  uses DB sessions from `db/session.py`,
  uses metadata logic from `file_service.py`,
  uses storage operations from `storage_service.py`,
  uses hashing from `hashing.py`,
  returns models from `shared/schemas.py`.
- `server/app/services/file_service.py`
  reads and writes `FileRecord` rows,
  calls `storage_service.py` to inspect physical storage,
  calls `hashing.py` to compute file hashes.

### Cross-boundary interaction

- Client `network.py` talks to server `routes.py` over HTTP.
- Shared request/response structure is represented by schemas in `shared/schemas.py`.

## 4. Main Data Flows

### A. Change detection

There are two direct change detection paths on the client.

1. Local filesystem events
- `watcher.py` uses `watchdog.Observer`.
- `SyncEventHandler.on_any_event()` receives file events.
- Events are debounced with `threading.Timer`.
- Debounced execution calls `run_sync_cycle()`.

2. Remote change polling
- `watcher.py` starts a daemon `Thread`.
- That thread runs `_poll_remote_changes()`.
- On each interval it calls `run_sync_cycle()`.

### B. Metadata transfer

1. Client requests metadata
- `sync_engine.get_sync_plan()` calls `network.get_files()`.
- `network.get_files()` sends `GET /files`.

2. Server prepares metadata
- `routes.get_files()` calls `file_service.list_files()`.
- `list_files()` reconciles DB state with physical files in storage.
- The server returns a list of `FileMetadataResponse`.

3. Client consumes metadata
- `sync_engine.get_sync_plan()` builds `server_index` from returned metadata.
- That metadata is compared with:
  local filesystem state from `scan_local_folder()`;
  local DB state from `list_local_files()`.

### C. File transfer

1. Upload flow
- `sync_engine.apply_action()` decides on `upload`.
- `network.upload_file()` sends `POST /upload` using `MultipartUploadStream`.
- Server route `upload_file()` stores the file via `save_upload_file()`.
- The server calculates SHA-256 and updates metadata via `create_or_update_file()`.
- The server returns `UploadFileResponse`.

2. Download flow
- `sync_engine.apply_action()` decides on `download` or `conflict_download`.
- `network.download_file()` sends `GET /download?path=...`.
- Server route `download_file()` reads the file from storage and streams it via `StreamingResponse`.
- Client writes the streamed bytes to the local path.

3. Delete flow
- `sync_engine.apply_action()` decides on `delete_remote`.
- `network.delete_file()` sends `DELETE /files`.
- Server route `delete_file()` marks metadata as deleted through `soft_delete_file()`.
- Server then physically removes the stored file via `delete_stored_file()`.

### D. Local state update

After action execution, the client updates its local SQLite state.

1. After upload
- `upsert_local_file()` stores returned `hash`, `version`, `last_synced`, `deleted=False`.

2. After download
- Client recalculates local hash from the downloaded file.
- `upsert_local_file()` stores the new local state using remote version metadata.

3. After conflict
- `_save_conflict_copy()` stores a preserved local copy as a separate `_conflict` file.
- That conflict copy is inserted into local DB with `conflict=True`.
- The downloaded remote version then overwrites the original path and updates normal local state.

4. After delete or tombstone handling
- `delete_remote`, `delete_local`, and `mark_local_deleted` all end by writing `deleted=True` into local DB state.

## 5. Architectural Shape

- The client is the orchestrator of sync decisions.
- The server is the source of remote metadata and the holder of canonical remote file storage.
- The client does not receive pushed updates from the server.
- Based on current code, remote visibility is achieved through polling plus full metadata fetch.

## 6. Multiple Valid Interpretations

- The project can be described as:
  a file sync client-server application;
  or a polling-based sync architecture with local watcher triggers.
  Both are directly supported by the code.
- The server metadata can be interpreted as the remote system of record for synchronized files because versioning and delete state are stored there.
  However, the server also reconciles DB state from the physical storage on `GET /files`, so the code shows a mixed model where storage and metadata are kept aligned dynamically.
