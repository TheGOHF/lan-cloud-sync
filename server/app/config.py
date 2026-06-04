from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path


def _default_server_config_dir() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "lan-cloud-sync"

    return Path.home() / "AppData" / "Local" / "lan-cloud-sync"


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int
    storage_path: Path
    db_path: Path
    tombstone_retention_days: int

    def to_json_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["storage_path"] = str(self.storage_path)
        payload["db_path"] = str(self.db_path)
        return payload

    def with_overrides(self, **overrides: object) -> ServerConfig:
        resolved_overrides = {key: value for key, value in overrides.items() if value is not None}
        return replace(self, **resolved_overrides)


CONFIG_DIR = _default_server_config_dir()
CONFIG_PATH = CONFIG_DIR / "server-config.json"
PID_PATH = CONFIG_DIR / "server.pid"


def default_server_config() -> ServerConfig:
    server_dir = Path(__file__).resolve().parents[1]
    return ServerConfig(
        host="0.0.0.0",
        port=8000,
        storage_path=server_dir / "storage",
        db_path=server_dir / "data.db",
        tombstone_retention_days=30,
    )


def load_server_config(config_path: Path = CONFIG_PATH) -> ServerConfig | None:
    if not config_path.exists():
        return None

    payload = json.loads(config_path.read_text(encoding="utf-8"))
    db_path = Path(payload["db_path"]).expanduser()
    if db_path.suffix == "":
        db_path = db_path / "server-data.db"

    return ServerConfig(
        host=str(payload.get("host", "0.0.0.0")),
        port=int(payload.get("port", 8000)),
        storage_path=Path(payload["storage_path"]).expanduser(),
        db_path=db_path,
        tombstone_retention_days=int(payload.get("tombstone_retention_days", 30)),
    )


def save_server_config(config: ServerConfig, config_path: Path = CONFIG_PATH) -> Path:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        json.dumps(config.to_json_dict(), indent=2),
        encoding="utf-8",
    )
    return config_path


def ensure_server_config(config_path: Path = CONFIG_PATH) -> ServerConfig:
    config = load_server_config(config_path)
    if config is not None:
        return config

    config = default_server_config()
    save_server_config(config, config_path)
    return config


DEFAULT_SERVER_CONFIG = default_server_config()
_runtime_config = ensure_server_config()


def get_server_config() -> ServerConfig:
    return _runtime_config


def set_server_config(config: ServerConfig) -> None:
    global _runtime_config
    _runtime_config = config
