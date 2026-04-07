# LAN Cloud Sync: Domain Entities for UML Class Diagram

This document is based only on entities that exist in the current repository. If an entity is implemented not as a class but as a data structure or a module-level construct, that is stated explicitly.

## 1. Key Classes and Data Structures

### FileRecord

- Name: `FileRecord`
- Kind: SQLAlchemy ORM class
- Location: `server/app/models/file.py`
- Purpose:
  represents remote file metadata stored on the server.
- Main fields:
  `id`, `path`, `version`, `hash`, `updated_at`, `device_id`, `deleted`
- Notes for UML:
  this is one of the core domain entities because server-side versioning and delete state are stored here.

### LocalFileEntry

- Name: `LocalFileEntry`
- Kind: SQLAlchemy ORM class
- Location: `client/app/sync/db.py`
- Purpose:
  represents the client's persisted local sync state for a file.
- Main fields:
  `path`, `hash`, `version`, `last_synced`, `conflict`, `deleted`
- Notes for UML:
  this is a core domain entity because sync decisions compare remote metadata, local files, and this local state snapshot.

### SyncAction

- Name: `SyncAction`
- Kind: `dataclass`
- Location: `client/app/sync/sync_engine.py`
- Purpose:
  represents a planned sync operation produced by the sync engine.
- Main fields:
  `action`, `path`, `reason`, `conflict_path`
- Notes for UML:
  this is a core control/data entity because the client sync flow is built around generating and applying these actions.

### FileMetadataResponse

- Name: `FileMetadataResponse`
- Kind: Pydantic model
- Location: `shared/schemas.py`
- Purpose:
  represents server metadata returned to the client for a file.
- Main fields:
  `path`, `version`, `hash`, `updated_at`, `deleted`
- Notes for UML:
  this is important if the UML diagram is meant to include integration DTOs between client and server.

### UploadFileResponse

- Name: `UploadFileResponse`
- Kind: Pydantic model
- Location: `shared/schemas.py`
- Purpose:
  represents the server response after file upload.
- Main fields:
  `path`, `version`, `hash`
- Notes for UML:
  secondary compared with `FileMetadataResponse`, but still part of the observable data contract.

### DeleteFileResponse

- Name: `DeleteFileResponse`
- Kind: Pydantic model
- Location: `shared/schemas.py`
- Purpose:
  represents the server response after delete.
- Main fields:
  `path`, `version`, `deleted`
- Notes for UML:
  secondary integration DTO.

### LocalFileState

- Name: `LocalFileState`
- Kind: `TypedDict`
- Location: `client/app/sync/file_utils.py`
- Purpose:
  represents transient scanned local file state before it is compared with server metadata and local DB state.
- Main fields:
  `hash`, `mtime`
- Notes for UML:
  not a persistent class, but a real data structure used in planning sync decisions.

### MultipartUploadStream

- Name: `MultipartUploadStream`
- Kind: regular class
- Location: `client/app/sync/network.py`
- Purpose:
  produces multipart upload bytes for file transfer from client to server.
- Main fields / responsibilities:
  `local_path`, `remote_path`, `device_id`, `boundary`, `_sha256`,
  iteration over upload payload,
  calculated `digest`
- Notes for UML:
  this is more of a transport/helper class than a domain entity.

### SyncEventHandler

- Name: `SyncEventHandler`
- Kind: class inheriting `FileSystemEventHandler`
- Location: `client/app/sync/watcher.py`
- Purpose:
  reacts to local filesystem events and schedules sync cycles.
- Main fields / responsibilities:
  `local_base_path`, `device_id`, `_lock`, `_timer_lock`, `_debounce_timer`,
  event reception,
  debounce scheduling,
  starting a sync cycle
- Notes for UML:
  this is an application-service/helper class, not a core business entity.

### NetworkError

- Name: `NetworkError`
- Kind: exception class
- Location: `client/app/sync/network.py`
- Purpose:
  wraps request-layer failures into a client-specific error type.
- Main responsibility:
  represent network request failure in the client sync layer.
- Notes for UML:
  usually not necessary in a course UML class diagram unless error modeling is part of the assignment.

### Base (server)

- Name: `Base`
- Kind: SQLAlchemy `DeclarativeBase`
- Location: `server/app/db/base.py`
- Purpose:
  base class for ORM models on the server side.
- Main responsibility:
  persistence infrastructure, not domain behavior.
- Notes for UML:
  technical infrastructure only.

### Base (client)

- Name: `Base`
- Kind: SQLAlchemy `DeclarativeBase`
- Location: `client/app/sync/db.py`
- Purpose:
  base class for ORM models on the client side.
- Main responsibility:
  persistence infrastructure, not domain behavior.
- Notes for UML:
  technical infrastructure only.

## 2. Important Module-Level Domain Structures

These are not classes, but they carry important business responsibility and may be shown in a UML diagram as service classes only if the course format allows service-style elements.

### sync_engine module

- Name: `client.app.sync.sync_engine`
- Kind: module with functions
- Purpose:
  central sync decision logic.
- Main responsibilities:
  build sync plan,
  compare local state / remote state / local DB state,
  apply upload/download/delete/conflict actions.
- Main functions:
  `sync`, `get_sync_plan`, `build_sync_plan`, `apply_actions`, `apply_action`
- UML note:
  if the diagram must focus on domain classes only, this should stay outside the class diagram.
  if service classes are allowed, it can be modeled as a `SyncEngine`-like service, but that would be an interpretation because in code it is a module, not a class.

### file_service module

- Name: `server.app.services.file_service`
- Kind: module with functions
- Purpose:
  server-side metadata management logic.
- Main responsibilities:
  create/update remote file metadata,
  soft delete,
  reconcile DB state with storage,
  convert DB rows to response schemas.
- Main functions:
  `create_or_update_file`, `get_file_by_path`, `list_files`, `soft_delete_file`, `to_file_metadata_response`
- UML note:
  same interpretation issue as with `sync_engine`: it is a functional service module, not a class.

### storage_service module

- Name: `server.app.services.storage_service`
- Kind: module with functions
- Purpose:
  physical file storage handling on the server.
- Main responsibilities:
  path normalization,
  save upload,
  locate file,
  list storage files,
  delete physical file,
  stream file chunks.
- Main functions:
  `save_upload_file`, `normalize_relative_path`, `build_storage_path`, `get_existing_file_path`, `list_storage_files`, `delete_stored_file`, `iter_file_chunks`
- UML note:
  infrastructure/service logic rather than domain entity logic.

### network module

- Name: `client.app.sync.network`
- Kind: module with functions plus helper classes
- Purpose:
  client-side transport layer for server communication.
- Main responsibilities:
  request metadata,
  upload files,
  download files,
  send delete requests.
- Main functions:
  `get_files`, `upload_file`, `download_file`, `delete_file`
- UML note:
  better treated as transport/service layer than domain model.

### watcher module

- Name: `client.app.sync.watcher`
- Kind: module with functions plus event handler class
- Purpose:
  local event watching and remote polling.
- Main responsibilities:
  start observer,
  debounce events,
  run sync cycles,
  poll remote changes.
- Main functions:
  `start_watcher`, `watch_forever`, `run_sync_cycle`, `_poll_remote_changes`
- UML note:
  operational/application layer, not core domain model.

## 3. Which Entities Should Be Included in a Course UML Class Diagram

### Recommended as primary UML classes

These are the most suitable entities for a course class diagram because they carry stable business meaning.

- `FileRecord`
  remote file metadata and version state on the server.
- `LocalFileEntry`
  local persisted sync state on the client.
- `SyncAction`
  explicit representation of planned synchronization operations.
- `FileMetadataResponse`
  useful if the UML diagram is allowed to include integration DTOs between subsystems.

### Recommended as optional UML classes

Include these if the diagram is expected to show transport contracts and runtime interaction structures, not just persistent domain objects.

- `UploadFileResponse`
- `DeleteFileResponse`
- `LocalFileState`
- `MultipartUploadStream`
- `SyncEventHandler`

### Better treated as secondary or technical

These exist in the code, but they are mostly technical infrastructure rather than core subject-area entities.

- `NetworkError`
- client `Base`
- server `Base`
- module-level service layers such as `sync_engine`, `file_service`, `storage_service`, `network`, `watcher`

## 4. Suggested UML Scope for Coursework

### Minimal domain-focused diagram

If the course expects a compact class diagram focused on business entities, the strongest set is:

- `FileRecord`
- `LocalFileEntry`
- `SyncAction`
- `FileMetadataResponse`

Possible relationships to show:

- `SyncAction` is created from comparison of `LocalFileEntry`, `LocalFileState`, and `FileMetadataResponse`.
- `FileMetadataResponse` is derived from `FileRecord`.
- `LocalFileEntry` and `FileRecord` represent similar sync-related state on different sides of the system.

### Extended diagram

If the course allows a broader application-level class diagram, add:

- `UploadFileResponse`
- `DeleteFileResponse`
- `LocalFileState`
- `MultipartUploadStream`
- `SyncEventHandler`

## 5. Interpretation Notes

- `sync_engine` and `file_service` are central to the domain logic, but in the current repository they are implemented as modules with functions, not as classes.
- If a UML class diagram must stay strictly class-based, they should not be invented as classes.
- If the course allows service blocks or stereotyped classes for modules, they may be represented that way, but that would be a modeling interpretation rather than a direct mirror of the code.
