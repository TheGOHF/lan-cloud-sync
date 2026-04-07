# LAN Cloud Sync: Project Structure and Architecture

This document is based only on facts visible in the current repository. If a conclusion is not directly proven by code, it is explicitly marked as an assumption.

## 1. Project Entry Points

### Server

- Main application entry point: `server/app/main.py`.
- This module creates the `FastAPI` app, runs `init_db()` on startup, and includes the API router.
- The repository contains an operational start script: `scripts/start_server.bat`.
- That script starts the server with:

```bat
python -m uvicorn server.app.main:app --host 0.0.0.0 --port 8000
```

### Client

- Real client entry point: `client/app/cli/main.py`.
- This module implements a CLI application called `lan-cloud-sync` using `argparse`.
- Supported commands: `sync`, `status`, `upload`, `download`, `list`, `watch`.
- The repository contains an operational start script for the background client: `scripts/start_client_watch.bat`.
- That script starts the client with:

```bat
python -m app.cli.main watch --device-id <device_id>
```

### Other observations

- `client/app/main.py` contains only a docstring and does not look like an active entry point.
- The `scripts/` directory also contains stop/status helper scripts for operational usage.

## 2. Where the Server and Client Parts Are

### Server side

- Root folder: `server/`.
- HTTP API: `server/app/api/routes.py`.
- Database layer: `server/app/db/`.
- Metadata model: `server/app/models/file.py`.
- Server-side file and metadata logic: `server/app/services/file_service.py`.
- Physical file storage logic: `server/app/services/storage_service.py`.

### Client side

- Root folder: `client/`.
- CLI: `client/app/cli/main.py`.
- Network communication: `client/app/sync/network.py`.
- Sync planning and action execution: `client/app/sync/sync_engine.py`.
- Local metadata database: `client/app/sync/db.py`.
- Local file scanning and hashing: `client/app/sync/file_utils.py`.
- File watcher and polling loop: `client/app/sync/watcher.py`.

### Shared part

- Root folder: `shared/`.
- Shared Pydantic response schemas: `shared/schemas.py`.

## 3. Main Modules and Their Purpose

### Server modules

- `server/app/main.py`
  Creates the FastAPI app, initializes the DB, mounts routes.
- `server/app/api/routes.py`
  Defines the HTTP endpoints: `GET /files`, `POST /upload`, `GET /download`, `DELETE /files`.
- `server/app/db/session.py`
  Configures the SQLite engine, session factory, `get_db()`, and `init_db()`.
- `server/app/db/base.py`
  Declares the SQLAlchemy base class.
- `server/app/models/file.py`
  Defines the `files` table with `path`, `version`, `hash`, `updated_at`, `device_id`, `deleted`.
- `server/app/services/file_service.py`
  Implements metadata create/update, soft delete, metadata serialization, and reconciliation between DB state and physical storage.
- `server/app/services/storage_service.py`
  Implements path normalization, upload saving, file listing, chunked reading, and physical delete from storage.
- `server/app/services/hashing.py`
  Calculates file SHA-256 hashes.

### Client modules

- `client/app/cli/main.py`
  CLI wrapper over sync functionality.
- `client/app/sync/config.py`
  Stores client constants such as sync folder path, local DB path, server URL, chunk size, and polling/debounce intervals.
- `client/app/sync/db.py`
  Stores local sync state in SQLite table `local_files`.
- `client/app/sync/file_utils.py`
  Scans the local folder, reads files in chunks, calculates SHA-256, captures `mtime`.
- `client/app/sync/network.py`
  Implements the HTTP client using `requests` for list/upload/download/delete operations.
- `client/app/sync/sync_engine.py`
  Core sync logic: builds the sync plan, detects conflicts, applies upload/download/delete actions, and maintains local tombstones.
- `client/app/sync/watcher.py`
  Integrates `watchdog`, debounces local events with `Timer`, and polls the server in a separate background thread.

## 4. Technologies and Libraries

### Based on `requirements.txt` and imports

- Python
- FastAPI
- Uvicorn
- SQLAlchemy
- Pydantic
- `python-multipart`
- Requests
- Watchdog
- SQLite

### Standard library elements used in the architecture

- `argparse`
- `logging`
- `threading` (`Thread`, `Lock`, `Timer`, `Event`)
- `pathlib`
- `shutil`
- `hashlib`
- `datetime`

## 5. How Network Communication Works

### Protocol and addressing

- The client uses HTTP via `requests`.
- Default client base URL: `http://127.0.0.1:8000` in `client/app/sync/config.py`.
- The server start script binds Uvicorn to `0.0.0.0:8000`.
- Fact from the repo:
  the server is configured to listen on all interfaces,
  but the default client configuration still points to localhost.

### HTTP API

- `GET /files`
  Returns a list of file metadata.
- `POST /upload`
  Accepts a file plus `path` and `device_id` via `multipart/form-data`.
- `GET /download?path=...`
  Streams binary file content back to the client.
- `DELETE /files?path=...&device_id=...`
  Marks a file as deleted and removes it from server storage.

### Data transfer details

- Upload is streamed as manually constructed multipart data via `MultipartUploadStream`.
- Download is streamed in chunks of `1 MiB`.
- Server download responses are also chunked via `iter_file_chunks`.
- Client network failures are wrapped into `NetworkError`.

### Observation about delta sync

- `client/app/sync/network.py` supports an optional `updated_since` parameter in `get_files()`.
- The server route `GET /files` does not accept that parameter.
- `server/app/services/file_service.py` contains a TODO about adding pagination and updated-since filters.
- `client/app/sync/sync_engine.py` contains a TODO about re-enabling delta sync after server support exists.
- Therefore, based on the current code, metadata sync is full-list based, not delta based.

## 6. How File Sync Is Implemented

### High-level flow

- The client builds three state views:
  local filesystem state from `scan_local_folder()`,
  remote server state from `GET /files`,
  local sync-state DB from `local_files`.
- `build_sync_plan()` compares those views using `path`, `hash`, `version`, `deleted`, and sometimes `mtime`.
- The output is a list of `SyncAction` objects.

### Supported actions

- `upload`
  Send local file to the server.
- `download`
  Download server file to local storage.
- `delete_remote`
  Send a delete request to the server.
- `delete_local`
  Remove the local file because the server marked it deleted.
- `mark_local_deleted`
  Keep a tombstone only in the local DB.
- `conflict_download`
  Save the current local file as `<name>_conflict<suffix>`, then download the server version.

### State resolution behavior

- If a file exists locally but not on the server, the client plans `upload`.
- If a file exists on the server but not locally:
  if local DB history says it previously existed and was not deleted, the client plans `delete_remote`;
  otherwise it plans `download`.
- If the server marks a file as deleted:
  the client either deletes the local file, records a local tombstone, or re-uploads the file if it was recreated locally.
- If both local and remote changed compared with the last local DB snapshot, the client creates a conflict action.

### Versioning

- Server metadata has an integer `version`.
- Version is incremented on content change or delete.
- The client stores the last known version in its local DB and uses it during comparisons.

### Change detection

- Both server and client use SHA-256 hashes.
- The client also uses local `mtime` in one specific case:
  when local and remote content differ, but the local DB has no previous record for that file.
  In that case, upload vs download is decided by comparing local `mtime` and remote `updated_at`.

### File storage

- Physical server files are stored under `server/storage/`.
- The server builds storage paths from normalized relative paths.
- Path normalization rejects absolute paths and `..`.

## 7. Metadata Storage, Logging, Configuration, Multithreading

### Metadata storage

Yes, there are two separate metadata stores.

- Server DB: `server/data.db` (SQLite).
  Table `files` stores:
  `id`, `path`, `version`, `hash`, `updated_at`, `device_id`, `deleted`.
- Client DB: `client/data/sync_state.db` (SQLite).
  Table `local_files` stores:
  `path`, `hash`, `version`, `last_synced`, `conflict`, `deleted`.

### Logging

- The code uses Python `logging`.
- Explicit `logging.basicConfig(...)` is configured in `client/app/cli/main.py`.
- `watcher.py` and `sync_engine.py` use `logger.info`, `logger.warning`, `logger.debug`, and `logger.exception`.
- No explicit `logging.basicConfig(...)` was found on the server side.
- The repository contains operational log files:
  `logs/server.log`, `logs/client-watch.log`, `logs/check-status.log`.
- Those log files are produced by bat scripts through stdout/stderr redirection.
- No dedicated database-backed operation journal or event log module was found.

### Configuration

- Client runtime configuration is stored as code constants in `client/app/sync/config.py`.
- Main values:
  `BASE_PATH`, `LOCAL_DB_PATH`, `SERVER_URL`, `CHUNK_SIZE`, `POLL_INTERVAL_SECONDS`, `LOCAL_EVENT_DEBOUNCE_SECONDS`.
- Server paths for DB and storage are also hardcoded in code:
  `server/app/db/session.py` and `server/app/services/storage_service.py`.
- No `.env`, YAML, JSON, or dedicated settings layer was found in the repository.

### Multithreading

Yes, the client uses multithreading explicitly.

- `watchdog.Observer` runs filesystem watching.
- `threading.Timer` is used for debounce of local events.
- A daemon `Thread` is used for periodic remote polling.
- A `Lock` prevents overlapping sync cycles.
- An `Event` is used to stop the polling loop.

### Limitation note

- Both SQLite engine configurations use `check_same_thread=False`.
- That is a direct fact from the code.
- Any stronger claim about full thread safety of the whole application would be an assumption.

## 8. Overall Architectural Picture

- The repository is split into client, server, and shared schemas.
- The server exposes a small HTTP API for list, upload, download, and delete operations.
- The server stores:
  physical file content in `server/storage/`,
  metadata and versions in SQLite `server/data.db`.
- The client stores:
  synced working files under `BASE_PATH`,
  its own sync state in SQLite `client/data/sync_state.db`.
- Sync is implemented as a combination of:
  local file watching,
  periodic server polling,
  comparison of local filesystem, server metadata list, and local sync-state DB.
- Conflicts are handled by preserving the local version as a separate `_conflict` file, then downloading the remote version.
- Deletes are represented with soft-delete metadata plus physical delete from server storage.
- Based on the current code, a real delta-sync API is not implemented yet.

## What Is Marked as Assumption

- It is reasonable to describe the project as a LAN client-server file sync system because:
  the server is launched on `0.0.0.0:8000`,
  and the repository name and structure point in that direction.
  However, the default client `SERVER_URL` is still `127.0.0.1`, so real multi-host LAN usage would require configuration change.
- No server-side background job queue, message broker, WebSocket channel, or push-based sync mechanism was found in the code.
  That is a reliable negative observation about the current repository, not a claim about future plans.
