from __future__ import annotations

from pathlib import Path


CLIENT_ROOT = Path(__file__).resolve().parents[2]
BASE_PATH = Path.home() / "lan-cloud-sync"
LOCAL_DB_PATH = CLIENT_ROOT / "data" / "sync_state.db"
SERVER_URL = "http://127.0.0.1:8000"
CHUNK_SIZE = 1024 * 1024
POLL_INTERVAL_SECONDS = 5
LOCAL_EVENT_DEBOUNCE_SECONDS = 2
