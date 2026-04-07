# LAN Cloud Sync: Сущности предметной области для UML-диаграммы классов

Документ составлен только по сущностям, которые реально существуют в текущем репозитории. Если сущность реализована не как класс, а как структура данных или модульная конструкция, это указано отдельно.

## 1. Ключевые классы и структуры данных

### FileRecord

- Имя: `FileRecord`
- Вид: SQLAlchemy ORM class
- Расположение: `server/app/models/file.py`
- Назначение:
  представляет удалённые метаданные файла, хранящиеся на сервере.
- Основные поля:
  `id`, `path`, `version`, `hash`, `updated_at`, `device_id`, `deleted`
- Замечание для UML:
  это одна из основных доменных сущностей, потому что серверное versioning и delete state хранятся именно здесь.

### LocalFileEntry

- Имя: `LocalFileEntry`
- Вид: SQLAlchemy ORM class
- Расположение: `client/app/sync/db.py`
- Назначение:
  представляет сохранённое клиентом локальное состояние синхронизации файла.
- Основные поля:
  `path`, `hash`, `version`, `last_synced`, `conflict`, `deleted`
- Замечание для UML:
  это основная доменная сущность, потому что sync decisions сравнивают remote metadata, local files и этот локальный snapshot.

### SyncAction

- Имя: `SyncAction`
- Вид: `dataclass`
- Расположение: `client/app/sync/sync_engine.py`
- Назначение:
  представляет запланированную операцию синхронизации, создаваемую sync engine.
- Основные поля:
  `action`, `path`, `reason`, `conflict_path`
- Замечание для UML:
  это важная control/data сущность, потому что клиентский sync flow построен вокруг создания и применения этих действий.

### FileMetadataResponse

- Имя: `FileMetadataResponse`
- Вид: Pydantic model
- Расположение: `shared/schemas.py`
- Назначение:
  представляет серверные метаданные файла, возвращаемые клиенту.
- Основные поля:
  `path`, `version`, `hash`, `updated_at`, `deleted`
- Замечание для UML:
  эта сущность важна, если UML-диаграмма должна включать integration DTO между клиентом и сервером.

### UploadFileResponse

- Имя: `UploadFileResponse`
- Вид: Pydantic model
- Расположение: `shared/schemas.py`
- Назначение:
  представляет серверный ответ после загрузки файла.
- Основные поля:
  `path`, `version`, `hash`
- Замечание для UML:
  второстепенная по сравнению с `FileMetadataResponse`, но всё равно является частью наблюдаемого data contract.

### DeleteFileResponse

- Имя: `DeleteFileResponse`
- Вид: Pydantic model
- Расположение: `shared/schemas.py`
- Назначение:
  представляет серверный ответ после удаления.
- Основные поля:
  `path`, `version`, `deleted`
- Замечание для UML:
  второстепенный integration DTO.

### LocalFileState

- Имя: `LocalFileState`
- Вид: `TypedDict`
- Расположение: `client/app/sync/file_utils.py`
- Назначение:
  представляет временное состояние локального файла, полученное при сканировании, до сравнения с серверными метаданными и локальной БД.
- Основные поля:
  `hash`, `mtime`
- Замечание для UML:
  это не persistent class, но реальная структура данных, участвующая в планировании синхронизации.

### MultipartUploadStream

- Имя: `MultipartUploadStream`
- Вид: обычный class
- Расположение: `client/app/sync/network.py`
- Назначение:
  формирует multipart upload bytes для передачи файла от клиента к серверу.
- Основные поля / ответственности:
  `local_path`, `remote_path`, `device_id`, `boundary`, `_sha256`,
  итерация по upload payload,
  вычисляемый `digest`
- Замечание для UML:
  это скорее transport/helper class, чем доменная сущность.

### SyncEventHandler

- Имя: `SyncEventHandler`
- Вид: class, наследующий `FileSystemEventHandler`
- Расположение: `client/app/sync/watcher.py`
- Назначение:
  реагирует на локальные события файловой системы и планирует sync cycles.
- Основные поля / ответственности:
  `local_base_path`, `device_id`, `_lock`, `_timer_lock`, `_debounce_timer`,
  приём событий,
  debounce scheduling,
  запуск sync cycle
- Замечание для UML:
  это application-service/helper class, а не core business entity.

### NetworkError

- Имя: `NetworkError`
- Вид: exception class
- Расположение: `client/app/sync/network.py`
- Назначение:
  оборачивает ошибки request-layer в клиентский тип исключения.
- Основная ответственность:
  представлять сбой сетевого запроса в клиентском sync layer.
- Замечание для UML:
  обычно не нужен в учебной UML class diagram, если моделирование ошибок не является частью задания.

### Base (server)

- Имя: `Base`
- Вид: SQLAlchemy `DeclarativeBase`
- Расположение: `server/app/db/base.py`
- Назначение:
  базовый класс для ORM models на стороне сервера.
- Основная ответственность:
  persistence infrastructure, а не доменное поведение.
- Замечание для UML:
  чисто техническая инфраструктура.

### Base (client)

- Имя: `Base`
- Вид: SQLAlchemy `DeclarativeBase`
- Расположение: `client/app/sync/db.py`
- Назначение:
  базовый класс для ORM models на стороне клиента.
- Основная ответственность:
  persistence infrastructure, а не доменное поведение.
- Замечание для UML:
  чисто техническая инфраструктура.

## 2. Важные модульные структуры доменной логики

Это не классы, но они несут важную business responsibility и могут быть показаны на UML-диаграмме как service classes только если формат курса допускает service-style элементы.

### sync_engine module

- Имя: `client.app.sync.sync_engine`
- Вид: module with functions
- Назначение:
  центральная логика принятия sync decisions.
- Основные ответственности:
  build sync plan,
  сравнение local state / remote state / local DB state,
  применение upload/download/delete/conflict actions.
- Основные функции:
  `sync`, `get_sync_plan`, `build_sync_plan`, `apply_actions`, `apply_action`
- Замечание для UML:
  если диаграмма должна фокусироваться только на domain classes, этот модуль должен остаться вне class diagram.
  если service classes допустимы, его можно смоделировать как `SyncEngine`-like service, но это уже будет интерпретацией, так как в коде это module, а не class.

### file_service module

- Имя: `server.app.services.file_service`
- Вид: module with functions
- Назначение:
  серверная логика управления метаданными.
- Основные ответственности:
  создание и обновление remote file metadata,
  soft delete,
  согласование DB state со storage,
  преобразование DB rows в response schemas.
- Основные функции:
  `create_or_update_file`, `get_file_by_path`, `list_files`, `soft_delete_file`, `to_file_metadata_response`
- Замечание для UML:
  та же проблема интерпретации, что и с `sync_engine`: это функциональный service module, а не class.

### storage_service module

- Имя: `server.app.services.storage_service`
- Вид: module with functions
- Назначение:
  обработка физического хранения файлов на сервере.
- Основные ответственности:
  нормализация путей,
  сохранение upload,
  поиск файла,
  list storage files,
  физическое удаление файла,
  потоковая отдача чанков файла.
- Основные функции:
  `save_upload_file`, `normalize_relative_path`, `build_storage_path`, `get_existing_file_path`, `list_storage_files`, `delete_stored_file`, `iter_file_chunks`
- Замечание для UML:
  это infrastructure/service logic, а не логика доменных сущностей.

### network module

- Имя: `client.app.sync.network`
- Вид: module with functions plus helper classes
- Назначение:
  транспортный слой клиента для общения с сервером.
- Основные ответственности:
  запрос метаданных,
  upload файлов,
  download файлов,
  отправка delete requests.
- Основные функции:
  `get_files`, `upload_file`, `download_file`, `delete_file`
- Замечание для UML:
  лучше рассматривать как transport/service layer, а не как доменную модель.

### watcher module

- Имя: `client.app.sync.watcher`
- Вид: module with functions plus event handler class
- Назначение:
  наблюдение за локальными событиями и опрос удалённого состояния.
- Основные ответственности:
  запуск observer,
  debounce событий,
  запуск sync cycles,
  polling удалённых изменений.
- Основные функции:
  `start_watcher`, `watch_forever`, `run_sync_cycle`, `_poll_remote_changes`
- Замечание для UML:
  это operational/application layer, а не core domain model.

## 3. Какие сущности стоит включить в учебную UML class diagram

### Рекомендуемые как основные UML classes

Эти сущности лучше всего подходят для учебной class diagram, потому что несут устойчивый предметный смысл.

- `FileRecord`
  удалённые метаданные файла и состояние версий на сервере.
- `LocalFileEntry`
  локальное сохранённое состояние синхронизации на клиенте.
- `SyncAction`
  явное представление запланированных операций синхронизации.
- `FileMetadataResponse`
  полезна, если UML-диаграмма допускает integration DTO между подсистемами.

### Рекомендуемые как опциональные UML classes

Добавлять их стоит, если диаграмма должна показывать transport contracts и runtime interaction structures, а не только persistent domain objects.

- `UploadFileResponse`
- `DeleteFileResponse`
- `LocalFileState`
- `MultipartUploadStream`
- `SyncEventHandler`

### Лучше считать второстепенными или техническими

Эти сущности есть в коде, но в основном относятся к технической инфраструктуре, а не к core subject-area model.

- `NetworkError`
- клиентский `Base`
- серверный `Base`
- модульные service layers вроде `sync_engine`, `file_service`, `storage_service`, `network`, `watcher`

## 4. Рекомендуемый объём UML для курсовой

### Минимальная предметно-ориентированная диаграмма

Если курс ожидает компактную class diagram с акцентом на business entities, наиболее сильный набор такой:

- `FileRecord`
- `LocalFileEntry`
- `SyncAction`
- `FileMetadataResponse`

Возможные связи для показа:

- `SyncAction` создаётся из сравнения `LocalFileEntry`, `LocalFileState` и `FileMetadataResponse`.
- `FileMetadataResponse` получается из `FileRecord`.
- `LocalFileEntry` и `FileRecord` представляют сходное sync-related состояние на разных сторонах системы.

### Расширенная диаграмма

Если курс допускает более широкую application-level class diagram, можно добавить:

- `UploadFileResponse`
- `DeleteFileResponse`
- `LocalFileState`
- `MultipartUploadStream`
- `SyncEventHandler`

## 5. Замечания по интерпретации

- `sync_engine` и `file_service` являются центральными для доменной логики, но в текущем репозитории они реализованы как модули с функциями, а не как классы.
- Если UML class diagram должна оставаться строго class-based, их нельзя искусственно превращать в классы.
- Если формат курса допускает service blocks или stereotype classes для модулей, их можно представить таким образом, но это уже будет моделирующей интерпретацией, а не прямым отражением кода.
