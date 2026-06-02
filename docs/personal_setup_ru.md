# LAN Cloud Sync: личная настройка вместо облачного диска

Этот документ описывает простой бытовой режим: один компьютер работает сервером,
остальные компьютеры запускают фонового клиента и синхронизируют одну выбранную
папку.

## 1. Роли компьютеров

### Серверный компьютер

Запускает FastAPI-сервер и хранит общее файловое хранилище.

Запуск вручную:

```bat
scripts\start_server.bat
```

Скрытый запуск:

```bat
scripts\start_server_hidden.vbs
```

Установка автозапуска при входе в Windows:

```bat
scripts\install_server_autostart.bat
```

Удаление автозапуска:

```bat
scripts\uninstall_server_autostart.bat
```

### Клиентский компьютер

Запускает watcher, который следит за папкой синхронизации и периодически
проверяет сервер.

Первичная настройка через GUI:

```bat
scripts\start_client_gui.bat
```

В поле сервера указывается полный URL, например:

```text
http://192.168.1.127:8000
```

Фоновый запуск watcher:

```bat
scripts\start_client_watch.bat
```

Скрытый запуск:

```bat
scripts\start_client_watch_hidden.vbs
```

Установка автозапуска при входе в Windows:

```bat
scripts\install_client_autostart.bat
```

Удаление автозапуска:

```bat
scripts\uninstall_client_autostart.bat
```

## 2. Где лежат настройки

Клиентская настройка хранится в:

```text
%LOCALAPPDATA%\lan-cloud-sync\client-config.json
```

Основные поля:

- `server_url` - адрес сервера.
- `base_path` - локальная папка синхронизации.
- `local_db_path` - локальная SQLite-БД состояния клиента.
- `device_id` - уникальный ID компьютера.

Серверная настройка хранится в:

```text
%LOCALAPPDATA%\lan-cloud-sync\server-config.json
```

Основные поля:

- `host` - обычно `0.0.0.0`.
- `port` - обычно `8000`.
- `storage_path` - физическое серверное хранилище файлов.
- `db_path` - SQLite-БД серверных метаданных.
- `tombstone_retention_days` - сколько дней хранить записи об удалённых файлах.

По умолчанию сервер продолжает использовать старые пути проекта:

```text
server\storage
server\data.db
```

## 3. Как переназначить серверное хранилище

1. Остановить сервер:

```bat
scripts\stop_server.bat
```

2. Перенести файлы из старого хранилища в новую папку.

3. Открыть:

```text
%LOCALAPPDATA%\lan-cloud-sync\server-config.json
```

4. Изменить `storage_path`, например:

```json
"storage_path": "D:\\LanCloudSync\\storage"
```

5. При желании перенести и `db_path`, например:

```json
"db_path": "D:\\LanCloudSync\\server-data.db"
```

6. Запустить сервер снова:

```bat
scripts\start_server.bat
```

## 4. Очистка tombstone-записей

Tombstone - это запись о том, что файл был удалён. Она нужна, чтобы удаление
распространилось на другие компьютеры. После этого старые tombstone можно
чистить.

Очистить клиентские tombstone старше 30 дней:

```bat
scripts\prune_client_tombstones.bat
```

Очистить клиентские tombstone сразу:

```bat
scripts\prune_client_tombstones.bat 0
```

Очистить серверные tombstone старше 30 дней:

```bat
scripts\prune_server_tombstones.bat
```

Очистить серверные tombstone сразу:

```bat
scripts\prune_server_tombstones.bat 0
```

## 5. Проверка сети

С клиентского компьютера сервер должен открываться в браузере:

```text
http://SERVER_IP:8000/files
```

Если браузер не открывает этот URL, синхронизация тоже не заработает. Сначала
проверяется сеть:

```powershell
ping SERVER_IP
Test-NetConnection SERVER_IP -Port 8000
```

## 6. Рекомендуемый обычный режим

1. Один раз настроить клиента через GUI.
2. На сервере включить `install_server_autostart.bat`.
3. На клиентах включить `install_client_autostart.bat`.
4. Каждый день пользоваться только папкой синхронизации.
5. GUI открывать только для изменения адреса сервера или папки.
