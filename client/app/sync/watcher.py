from __future__ import annotations

import logging
from pathlib import Path
from time import sleep
from threading import Event, Lock, Thread, Timer
from typing import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .config import ClientConfig, get_client_config
from .db import init_db
from .sync_engine import apply_actions, get_sync_plan


logger = logging.getLogger(__name__)


WatcherEventSink = Callable[[str], None]


class SyncEventHandler(FileSystemEventHandler):
    def __init__(
        self,
        *,
        local_base_path: Path,
        device_id: str,
        sync_lock: Lock,
        config: ClientConfig,
        event_sink: WatcherEventSink | None = None,
    ) -> None:
        self.local_base_path = local_base_path
        self.device_id = device_id
        self.config = config
        self.event_sink = event_sink
        self._lock = sync_lock
        self._timer_lock = Lock()
        self._debounce_timer: Timer | None = None

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return

        _emit_event(
            self.event_sink,
            logging.INFO,
            "Watcher event: %s %s",
            event.event_type,
            event.src_path,
        )
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
                self.config.local_event_debounce_seconds,
                self._run_scheduled_sync,
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _run_scheduled_sync(self) -> None:
        try:
            run_sync_cycle(
                local_base_path=self.local_base_path,
                device_id=self.device_id,
                sync_lock=self._lock,
                config=self.config,
                event_sink=self.event_sink,
            )
        except Exception:
            pass

        with self._timer_lock:
            self._debounce_timer = None


class SyncWatcherService:
    def __init__(
        self,
        config: ClientConfig,
        *,
        local_base_path: Path | None = None,
        device_id: str | None = None,
        poll_interval: int | None = None,
        event_sink: WatcherEventSink | None = None,
    ) -> None:
        self.config = config
        self.local_base_path = local_base_path or config.base_path
        self.device_id = device_id or config.device_id
        self.poll_interval = (
            poll_interval if poll_interval is not None else config.poll_interval_seconds
        )
        self.event_sink = event_sink
        self.sync_lock = Lock()
        self.stop_event = Event()
        self._state_lock = Lock()
        self._observer: Observer | None = None
        self._poller: Thread | None = None
        self._handler: SyncEventHandler | None = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        with self._state_lock:
            if not self._is_running:
                return False

            return self._observer is not None and self._observer.is_alive()

    @property
    def observer(self) -> Observer | None:
        return self._observer

    @property
    def poller(self) -> Thread | None:
        return self._poller

    def start(self) -> None:
        with self._state_lock:
            if self._is_running:
                return

            init_db(self.config)
            self.local_base_path.mkdir(parents=True, exist_ok=True)
            self.stop_event.clear()

            observer = Observer()
            handler = SyncEventHandler(
                local_base_path=self.local_base_path,
                device_id=self.device_id,
                sync_lock=self.sync_lock,
                config=self.config,
                event_sink=self.event_sink,
            )
            observer.schedule(handler, str(self.local_base_path), recursive=True)
            observer.start()

            poller = Thread(
                target=_poll_remote_changes,
                kwargs={
                    "local_base_path": self.local_base_path,
                    "device_id": self.device_id,
                    "poll_interval": self.poll_interval,
                    "stop_event": self.stop_event,
                    "sync_lock": self.sync_lock,
                    "config": self.config,
                    "event_sink": self.event_sink,
                },
                daemon=True,
            )
            poller.start()

            self._observer = observer
            self._poller = poller
            self._handler = handler
            self._is_running = True

        try:
            _emit_event(
                self.event_sink,
                logging.INFO,
                "Watching %s with poll interval %ss",
                self.local_base_path,
                self.poll_interval,
            )
            run_sync_cycle(
                local_base_path=self.local_base_path,
                device_id=self.device_id,
                sync_lock=self.sync_lock,
                config=self.config,
                event_sink=self.event_sink,
            )
        except Exception:
            self.stop()
            raise

    def stop(self) -> None:
        with self._state_lock:
            if not self._is_running:
                return

            self._is_running = False
            observer = self._observer
            poller = self._poller
            handler = self._handler
            self._observer = None
            self._poller = None
            self._handler = None
            self.stop_event.set()

        if handler is not None:
            handler.stop()

        if observer is not None:
            observer.stop()
            observer.join()

        if poller is not None:
            poller.join(timeout=2)

        _emit_event(self.event_sink, logging.INFO, "Watcher stopped")

    def wait(self, timeout: float = 1.0) -> None:
        while self.is_running:
            observer = self._observer
            if observer is None:
                break

            observer.join(timeout=timeout)
            sleep(0.05)


def start_watcher(
    local_base_path: Path | None = None,
    device_id: str | None = None,
    *,
    config: ClientConfig | None = None,
    poll_interval: int | None = None,
    event_sink: WatcherEventSink | None = None,
) -> SyncWatcherService:
    resolved_config = config or get_client_config()
    service = SyncWatcherService(
        resolved_config,
        local_base_path=local_base_path,
        device_id=device_id,
        poll_interval=poll_interval,
        event_sink=event_sink,
    )
    service.start()
    return service


def watch_forever(
    local_base_path: Path | None = None,
    device_id: str | None = None,
    poll_interval: int | None = None,
    *,
    config: ClientConfig | None = None,
    event_sink: WatcherEventSink | None = None,
) -> None:
    resolved_config = config or get_client_config()
    service = SyncWatcherService(
        resolved_config,
        local_base_path=local_base_path,
        device_id=device_id,
        poll_interval=poll_interval,
        event_sink=event_sink,
    )
    service.start()

    try:
        service.wait()
    except KeyboardInterrupt:
        _emit_event(event_sink, logging.INFO, "Stopping watcher")
    finally:
        service.stop()


def run_sync_cycle(
    *,
    local_base_path: Path,
    device_id: str,
    sync_lock: Lock,
    config: ClientConfig | None = None,
    event_sink: WatcherEventSink | None = None,
) -> None:
    if not sync_lock.acquire(blocking=False):
        logger.debug("Sync already running, skip duplicate trigger")
        return

    try:
        actions = get_sync_plan(local_base_path=local_base_path, config=config)
        if not actions:
            logger.debug("No sync actions to apply")
            _emit_event(event_sink, logging.INFO, "Sync cycle completed")
            return

        apply_actions(
            actions,
            local_base_path=local_base_path,
            device_id=device_id,
            config=config,
        )
        _emit_event(event_sink, logging.INFO, "Sync cycle completed")
    except Exception as exc:
        _emit_event(event_sink, logging.ERROR, "Sync cycle failed: %s", exc)
        raise
    finally:
        sync_lock.release()


def _poll_remote_changes(
    *,
    local_base_path: Path,
    device_id: str,
    poll_interval: int,
    stop_event: Event,
    sync_lock: Lock,
    config: ClientConfig,
    event_sink: WatcherEventSink | None,
) -> None:
    while not stop_event.wait(poll_interval):
        try:
            run_sync_cycle(
                local_base_path=local_base_path,
                device_id=device_id,
                sync_lock=sync_lock,
                config=config,
                event_sink=event_sink,
            )
        except Exception:
            logger.exception("Polling sync failed")


def _emit_event(
    event_sink: WatcherEventSink | None,
    level: int,
    message: str,
    *args: object,
) -> None:
    logger.log(level, message, *args)
    if event_sink is not None:
        event_sink(message % args if args else message)
