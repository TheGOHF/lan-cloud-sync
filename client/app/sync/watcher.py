from __future__ import annotations

import logging
from pathlib import Path
from threading import Lock

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .config import BASE_PATH
from .db import init_db
from .sync_engine import apply_actions, get_sync_plan


logger = logging.getLogger(__name__)


class SyncEventHandler(FileSystemEventHandler):
    def __init__(self, *, local_base_path: Path, device_id: str) -> None:
        self.local_base_path = local_base_path
        self.device_id = device_id
        self._lock = Lock()

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return

        logger.info("Watcher event: %s %s", event.event_type, event.src_path)
        self._run_sync_cycle()

    def _run_sync_cycle(self) -> None:
        if not self._lock.acquire(blocking=False):
            logger.debug("Sync already running, skip duplicate watcher event")
            return

        try:
            actions = get_sync_plan(local_base_path=self.local_base_path)
            if not actions:
                logger.debug("No watcher actions to apply")
                return

            apply_actions(
                actions,
                local_base_path=self.local_base_path,
                device_id=self.device_id,
            )
        finally:
            self._lock.release()


def start_watcher(
    local_base_path: Path = BASE_PATH,
    device_id: str = "unknown-device",
) -> Observer:
    init_db()
    local_base_path.mkdir(parents=True, exist_ok=True)

    observer = Observer()
    handler = SyncEventHandler(local_base_path=local_base_path, device_id=device_id)
    observer.schedule(handler, str(local_base_path), recursive=True)
    observer.start()
    logger.info("Started watcher for %s", local_base_path)
    return observer
