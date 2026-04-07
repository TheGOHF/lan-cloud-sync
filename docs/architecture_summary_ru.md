# LAN Cloud Sync: Краткое описание архитектуры

Документ составлен только по фактам, видимым в текущем репозитории. Если возможны разные интерпретации, это указано явно.

## 1. Основные компоненты системы

### Клиентская часть

- CLI entry point в `client/app/cli/main.py`.
- Sync engine в `client/app/sync/sync_engine.py`.
- File watcher и polling loop в `client/app/sync/watcher.py`.
- Network client в `client/app/sync/network.py`.
- Локальная sync-state база в `client/app/sync/db.py`.
- Утилиты локального сканирования и хеширования в `client/app/sync/file_utils.py`.
- Клиентские конфигурационные константы в `client/app/sync/config.py`.

### Серверная часть

- FastAPI application в `server/app/main.py`.
- HTTP API routes в `server/app/api/routes.py`.
- Слой DB session в `server/app/db/session.py`.
- Модель file metadata в `server/app/models/file.py`.
- Логика работы с метаданными в `server/app/services/file_service.py`.
- Логика физического storage в `server/app/services/storage_service.py`.
- Логика хеширования в `server/app/services/hashing.py`.

### Общая часть

- Общие API schemas в `shared/schemas.py`.

### Постоянное хранение

- Серверная metadata DB: `server/data.db`.
- Серверное файловое storage: `server/storage/`.
- Клиентская local state DB: `client/data/sync_state.db`.
- Клиентская рабочая папка: задаётся через `BASE_PATH` в `client/app/sync/config.py`.

## 2. Роли клиента и сервера

### Роль клиента

- Следит за изменениями в локальной папке синхронизации.
- Периодически опрашивает сервер на предмет удалённых изменений.
- Сканирует локальные файлы и считает хеши.
- Читает предыдущее состояние синхронизации из локальной SQLite.
- Строит sync plan, сравнивая локальные файлы, серверные метаданные и локальное состояние в БД.
- Выполняет sync actions: upload, download, remote delete, local delete, обновление tombstone и обработку конфликтов.

### Роль сервера

- Предоставляет HTTP endpoints для списка файлов, загрузки, скачивания и удаления.
- Хранит физическое содержимое файлов в `server/storage/`.
- Хранит метаданные и состояние версий в SQLite.
- Считает хеши для загруженных файлов и файлов, уже лежащих в storage.
- Согласует метаданные с физическим storage при выдаче списка файлов.

### Замечание по интерпретации

- Текущий код явно реализует client-server file sync design.
- Его также можно описать как polling-based sync system с local file watching.
- Оба описания согласуются с содержимым репозитория.

## 3. Взаимодействие модулей

### Цепочка взаимодействия на стороне клиента

- `client/app/cli/main.py`
  вызывает `sync()`, `get_sync_plan()`, `apply_action()`, `watch_forever()` и функции вывода локального состояния БД.
- `client/app/sync/watcher.py`
  запускает `run_sync_cycle()`, который вызывает `get_sync_plan()` и `apply_actions()` из `sync_engine.py`.
- `client/app/sync/sync_engine.py`
  читает локальные файлы через `file_utils.py`,
  читает и пишет локальное состояние через `db.py`,
  вызывает серверные операции через `network.py`.
- `client/app/sync/network.py`
  обменивается данными с серверными routes и валидирует ответы через модели из `shared/schemas.py`.

### Цепочка взаимодействия на стороне сервера

- `server/app/main.py`
  инициализирует БД и подключает `routes.py`.
- `server/app/api/routes.py`
  использует DB sessions из `db/session.py`,
  использует metadata logic из `file_service.py`,
  использует storage operations из `storage_service.py`,
  использует hashing из `hashing.py`,
  возвращает модели из `shared/schemas.py`.
- `server/app/services/file_service.py`
  читает и пишет строки `FileRecord`,
  вызывает `storage_service.py` для проверки физического storage,
  вызывает `hashing.py` для вычисления хешей файлов.

### Взаимодействие через границу клиент-сервер

- Клиентский `network.py` общается с серверным `routes.py` по HTTP.
- Общая структура request/response представлена схемами в `shared/schemas.py`.

## 4. Основные потоки данных

### A. Обнаружение изменений

На клиенте есть два прямых пути обнаружения изменений.

1. Локальные события файловой системы
- `watcher.py` использует `watchdog.Observer`.
- `SyncEventHandler.on_any_event()` получает файловые события.
- События проходят debounce через `threading.Timer`.
- После debounce вызывается `run_sync_cycle()`.

2. Опрос удалённых изменений
- `watcher.py` запускает daemon `Thread`.
- Этот поток выполняет `_poll_remote_changes()`.
- На каждом интервале он вызывает `run_sync_cycle()`.

### B. Передача метаданных

1. Клиент запрашивает метаданные
- `sync_engine.get_sync_plan()` вызывает `network.get_files()`.
- `network.get_files()` отправляет `GET /files`.

2. Сервер готовит метаданные
- `routes.get_files()` вызывает `file_service.list_files()`.
- `list_files()` согласует состояние БД с физическими файлами в storage.
- Сервер возвращает список `FileMetadataResponse`.

3. Клиент использует метаданные
- `sync_engine.get_sync_plan()` строит `server_index` из полученных метаданных.
- Эти метаданные сравниваются с:
  локальным состоянием файловой системы из `scan_local_folder()`;
  локальным состоянием БД из `list_local_files()`.

### C. Передача файлов

1. Сценарий upload
- `sync_engine.apply_action()` выбирает `upload`.
- `network.upload_file()` отправляет `POST /upload` через `MultipartUploadStream`.
- Серверный route `upload_file()` сохраняет файл через `save_upload_file()`.
- Сервер вычисляет SHA-256 и обновляет метаданные через `create_or_update_file()`.
- Сервер возвращает `UploadFileResponse`.

2. Сценарий download
- `sync_engine.apply_action()` выбирает `download` или `conflict_download`.
- `network.download_file()` отправляет `GET /download?path=...`.
- Серверный route `download_file()` читает файл из storage и отдает его через `StreamingResponse`.
- Клиент записывает полученные байты в локальный путь.

3. Сценарий delete
- `sync_engine.apply_action()` выбирает `delete_remote`.
- `network.delete_file()` отправляет `DELETE /files`.
- Серверный route `delete_file()` помечает метаданные удалёнными через `soft_delete_file()`.
- Затем сервер физически удаляет stored file через `delete_stored_file()`.

### D. Обновление локального состояния

После выполнения действия клиент обновляет своё состояние в SQLite.

1. После upload
- `upsert_local_file()` сохраняет возвращённые `hash`, `version`, `last_synced`, `deleted=False`.

2. После download
- Клиент заново считает локальный hash из скачанного файла.
- `upsert_local_file()` сохраняет новое локальное состояние с использованием удалённой версии.

3. После конфликта
- `_save_conflict_copy()` сохраняет локальную копию как отдельный `_conflict` file.
- Эта conflict copy записывается в локальную БД с `conflict=True`.
- Затем скачанная удалённая версия перезаписывает исходный путь и обновляет обычное локальное состояние.

4. После удаления или обработки tombstone
- `delete_remote`, `delete_local` и `mark_local_deleted` завершаются записью `deleted=True` в локальное состояние БД.

## 5. Архитектурная форма

- Клиент является оркестратором sync decisions.
- Сервер является источником удалённых метаданных и держателем канонического remote file storage.
- Клиент не получает push-updates от сервера.
- По текущему коду видимость удалённых изменений достигается через polling и полный запрос списка метаданных.

## 6. Несколько допустимых интерпретаций

- Проект можно описать как:
  клиент-серверное приложение синхронизации файлов;
  или polling-based sync architecture с local watcher triggers.
  Обе формулировки напрямую поддерживаются кодом.
- Серверные метаданные можно интерпретировать как remote system of record для синхронизируемых файлов, потому что versioning и delete state хранятся там.
  Однако сервер также согласует состояние БД с физическим storage при `GET /files`, поэтому код показывает смешанную модель, где storage и metadata динамически поддерживаются согласованными.
