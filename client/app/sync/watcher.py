from __future__ import annotations

import logging
from pathlib import Path
from threading import Event, Lock, Thread, Timer

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .config import BASE_PATH, LOCAL_EVENT_DEBOUNCE_SECONDS, POLL_INTERVAL_SECONDS
from .db import init_db
from .sync_engine import apply_actions, get_sync_plan


logger = logging.getLogger(__name__)


class SyncEventHandler(FileSystemEventHandler):
    def __init__(
        self,
        *,
        local_base_path: Path,
        device_id: str,
        sync_lock: Lock,
    ) -> None:
        self.local_base_path = local_base_path
        self.device_id = device_id
        self._lock = sync_lock
        self._timer_lock = Lock()
        self._debounce_timer: Timer | None = None

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return

        logger.info("Watcher event: %s %s", event.event_type, event.src_path)
        self._schedule_sync()

    def stop(self) -> None:
        with self._timer_lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()
                self._debounce_timer = None

    def _schedule_sync(self) -> None:
        with self._timer_lock:
            if self._debounce_timer is not None:
                self._debounce_timer.cancel()

            self._debounce_timer = Timer(
                LOCAL_EVENT_DEBOUNCE_SECONDS,
                self._run_scheduled_sync,
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _run_scheduled_sync(self) -> None:
        run_sync_cycle(
            local_base_path=self.local_base_path,
            device_id=self.device_id,
            sync_lock=self._lock,
        )

        with self._timer_lock:
            self._debounce_timer = None


def start_watcher(
    local_base_path: Path = BASE_PATH,
    device_id: str = "unknown-device",
) -> Observer:
    init_db()
    local_base_path.mkdir(parents=True, exist_ok=True)

    observer = Observer()
    sync_lock = Lock()
    handler = SyncEventHandler(
        local_base_path=local_base_path,
        device_id=device_id,
        sync_lock=sync_lock,
    )
    observer.schedule(handler, str(local_base_path), recursive=True)
    observer.start()
    logger.info("Started watcher for %s", local_base_path)
    return observer


def watch_forever(
    local_base_path: Path = BASE_PATH,
    device_id: str = "unknown-device",
    poll_interval: int = POLL_INTERVAL_SECONDS,
) -> None:
    init_db()
    local_base_path.mkdir(parents=True, exist_ok=True)

    sync_lock = Lock()
    stop_event = Event()
    observer = Observer()
    handler = SyncEventHandler(
        local_base_path=local_base_path,
        device_id=device_id,
        sync_lock=sync_lock,
    )
    observer.schedule(handler, str(local_base_path), recursive=True)
    observer.start()

    poller = Thread(
        target=_poll_remote_changes,
        kwargs={
            "local_base_path": local_base_path,
            "device_id": device_id,
            "poll_interval": poll_interval,
            "stop_event": stop_event,
            "sync_lock": sync_lock,
        },
        daemon=True,
    )
    poller.start()

    logger.info("Watching %s with poll interval %ss", local_base_path, poll_interval)
    run_sync_cycle(local_base_path=local_base_path, device_id=device_id, sync_lock=sync_lock)

    try:
        while observer.is_alive():
            observer.join(timeout=1)
    except KeyboardInterrupt:
        logger.info("Stopping watcher")
    finally:
        stop_event.set()
        handler.stop()
        observer.stop()
        observer.join()
        poller.join(timeout=2)


def run_sync_cycle(*, local_base_path: Path, device_id: str, sync_lock: Lock) -> None:
    if not sync_lock.acquire(blocking=False):
        logger.debug("Sync already running, skip duplicate trigger")
        return

    try:
        actions = get_sync_plan(local_base_path=local_base_path)
        if not actions:
            logger.debug("No sync actions to apply")
            return

        apply_actions(
            actions,
            local_base_path=local_base_path,
            device_id=device_id,
        )
    finally:
        sync_lock.release()


def _poll_remote_changes(
    *,
    local_base_path: Path,
    device_id: str,
    poll_interval: int,
    stop_event: Event,
    sync_lock: Lock,
) -> None:
    while not stop_event.wait(poll_interval):
        try:
            run_sync_cycle(
                local_base_path=local_base_path,
                device_id=device_id,
                sync_lock=sync_lock,
            )
        except Exception:
            logger.exception("Polling sync failed")
