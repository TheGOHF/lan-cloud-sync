from __future__ import annotations

import json
import os
import socket
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from uuid import uuid4


def _default_client_config_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "lan-cloud-sync"

    return Path.home() / "AppData" / "Local" / "lan-cloud-sync"


@dataclass(frozen=True)
class ClientConfig:
    server_url: str
    base_path: Path
    local_db_path: Path
    chunk_size: int
    poll_interval_seconds: int
    local_event_debounce_seconds: int
    device_id: str

    def to_json_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["base_path"] = str(self.base_path)
        payload["local_db_path"] = str(self.local_db_path)
        return payload

    def with_overrides(self, **overrides: object) -> ClientConfig:
        resolved_overrides = {key: value for key, value in overrides.items() if value is not None}
        return replace(self, **resolved_overrides)


CONFIG_DIR = _default_client_config_dir()
CONFIG_PATH = CONFIG_DIR / "client-config.json"


def default_client_config() -> ClientConfig:
    config_dir = _default_client_config_dir()
    default_base_path = Path.home() / "lan-cloud-sync"
    default_device_name = socket.gethostname().strip() or "device"
    return ClientConfig(
        server_url="http://127.0.0.1:8000",
        base_path=default_base_path,
        local_db_path=config_dir / "sync_state.db",
        chunk_size=1024 * 1024,
        poll_interval_seconds=5,
        local_event_debounce_seconds=2,
        device_id=f"{default_device_name}-{uuid4().hex[:8]}",
    )


def load_client_config(config_path: Path = CONFIG_PATH) -> ClientConfig | None:
    if not config_path.exists():
        return None

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    return ClientConfig(
        server_url=str(payload["server_url"]),
        base_path=Path(payload["base_path"]).expanduser(),
        local_db_path=Path(payload["local_db_path"]).expanduser(),
        chunk_size=int(payload["chunk_size"]),
        poll_interval_seconds=int(payload["poll_interval_seconds"]),
        local_event_debounce_seconds=int(payload["local_event_debounce_seconds"]),
        device_id=str(payload["device_id"]),
    )


def save_client_config(config: ClientConfig, config_path: Path = CONFIG_PATH) -> Path:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config.to_json_dict(), indent=2),
        encoding="utf-8",
    )
    return config_path


def ensure_client_config(config_path: Path = CONFIG_PATH) -> ClientConfig:
    config = load_client_config(config_path)
    if config is not None:
        return config

    config = default_client_config()
    save_client_config(config, config_path)
    return config


DEFAULT_CLIENT_CONFIG = default_client_config()
_runtime_config = DEFAULT_CLIENT_CONFIG


def get_client_config() -> ClientConfig:
    return _runtime_config


def set_client_config(config: ClientConfig) -> None:
    global _runtime_config
    _runtime_config = config


# Retained temporarily for backward compatibility with older import-based code paths.
BASE_PATH = DEFAULT_CLIENT_CONFIG.base_path
LOCAL_DB_PATH = DEFAULT_CLIENT_CONFIG.local_db_path
SERVER_URL = DEFAULT_CLIENT_CONFIG.server_url
CHUNK_SIZE = DEFAULT_CLIENT_CONFIG.chunk_size
POLL_INTERVAL_SECONDS = DEFAULT_CLIENT_CONFIG.poll_interval_seconds
LOCAL_EVENT_DEBOUNCE_SECONDS = DEFAULT_CLIENT_CONFIG.local_event_debounce_seconds
