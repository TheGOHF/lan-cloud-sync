from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
import sys

from PySide6.QtCore import QObject, QThread, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ..sync.config import ClientConfig, ensure_client_config, save_client_config, set_client_config
from ..sync.db import init_db, list_local_files
from ..sync.sync_engine import SyncAction, sync
from ..sync.watcher import SyncWatcherService


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class SyncWorker(QObject):
    finished = Signal(list)
    failed = Signal(str)

    def __init__(self, config: ClientConfig) -> None:
        super().__init__()
        self.config = config

    def run(self) -> None:
        try:
            actions = sync(
                local_base_path=self.config.base_path,
                device_id=self.config.device_id,
                config=self.config,
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return

        rendered_actions = [
            f"{action.action}\t{action.path}\t{action.reason}"
            for action in actions
        ]
        self.finished.emit(rendered_actions)


class GuiEventBridge(QObject):
    message = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("LAN Cloud Sync")
        self.resize(980, 700)

        self.config = ensure_client_config()
        set_client_config(self.config)
        init_db(self.config)

        self.watcher_service: SyncWatcherService | None = None
        self.sync_thread: QThread | None = None
        self.sync_worker: SyncWorker | None = None
        self.last_sync_status: str = "idle"
        self.last_sync_time: datetime | None = None
        self.last_error_message: str | None = None
        self.event_bridge = GuiEventBridge()
        self.event_bridge.message.connect(self.handle_watcher_event)

        self.server_url_input = QLineEdit()
        self.sync_folder_input = QLineEdit()
        self.device_id_input = QLineEdit()
        self.status_label = QLabel()
        self.file_table = QTableWidget(0, 4)
        self.log_output = QPlainTextEdit()
        self.save_button = QPushButton("Save settings")
        self.sync_button = QPushButton("Sync now")
        self.start_watcher_button = QPushButton("Start watcher")
        self.stop_watcher_button = QPushButton("Stop watcher")

        self._build_ui()
        self._bind_events()
        self.load_config_into_form()
        self.refresh_file_list()
        self.append_log("GUI ready")

    def _build_ui(self) -> None:
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        settings_layout = QGridLayout()

        settings_layout.addWidget(QLabel("Server URL"), 0, 0)
        settings_layout.addWidget(self.server_url_input, 0, 1, 1, 2)

        settings_layout.addWidget(QLabel("Sync folder"), 1, 0)
        settings_layout.addWidget(self.sync_folder_input, 1, 1)
        browse_button = QPushButton("Browse...")
        browse_button.clicked.connect(self.choose_sync_folder)
        settings_layout.addWidget(browse_button, 1, 2)

        settings_layout.addWidget(QLabel("Device ID"), 2, 0)
        settings_layout.addWidget(self.device_id_input, 2, 1, 1, 2)

        button_row = QHBoxLayout()
        button_row.addWidget(self.save_button)
        button_row.addWidget(self.sync_button)
        button_row.addWidget(self.start_watcher_button)
        button_row.addWidget(self.stop_watcher_button)
        button_row.addStretch(1)

        self.file_table.setHorizontalHeaderLabels(["Path", "Version", "Hash", "State"])
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.verticalHeader().setVisible(False)
        self.file_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.file_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.log_output.setReadOnly(True)

        root_layout.addLayout(settings_layout)
        root_layout.addLayout(button_row)
        root_layout.addWidget(self.status_label)
        root_layout.addWidget(QLabel("Local sync database"))
        root_layout.addWidget(self.file_table, stretch=2)
        root_layout.addWidget(QLabel("Events and errors"))
        root_layout.addWidget(self.log_output, stretch=1)

        self._update_watcher_controls()

    def _bind_events(self) -> None:
        self.save_button.clicked.connect(self.save_settings)
        self.sync_button.clicked.connect(self.run_sync_now)
        self.start_watcher_button.clicked.connect(self.start_watcher)
        self.stop_watcher_button.clicked.connect(self.stop_watcher)

    def load_config_into_form(self) -> None:
        self.server_url_input.setText(self.config.server_url)
        self.sync_folder_input.setText(str(self.config.base_path))
        self.device_id_input.setText(self.config.device_id)

    def read_form_config(self) -> ClientConfig:
        server_url = self.server_url_input.text().strip()
        sync_folder = self.sync_folder_input.text().strip()
        device_id = self.device_id_input.text().strip()

        if not server_url:
            raise ValueError("Server URL is required.")
        if not sync_folder:
            raise ValueError("Sync folder is required.")
        if not device_id:
            raise ValueError("Device ID is required.")

        return self.config.with_overrides(
            server_url=server_url,
            base_path=Path(sync_folder).expanduser(),
            device_id=device_id,
        )

    def choose_sync_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Choose Sync Folder",
            self.sync_folder_input.text() or str(self.config.base_path),
        )
        if selected:
            self.sync_folder_input.setText(selected)

    def save_settings(self) -> None:
        try:
            new_config = self.read_form_config()
            save_client_config(new_config)
            set_client_config(new_config)
            init_db(new_config)
            self.config = new_config
        except Exception as exc:
            self._set_sync_failed(str(exc))
            self.append_log(f"[ERROR] {self._short_error_message(str(exc))}")
            QMessageBox.critical(self, "Save settings", str(exc))
            return

        self.append_log("Settings saved")
        if self.watcher_service is not None and self.watcher_service.is_running:
            self.append_log("Watcher is still using the previous settings until restarted")
        self.refresh_file_list()

    def run_sync_now(self) -> None:
        if self.sync_thread is not None and self.sync_thread.isRunning():
            self.append_log("Sync already running")
            return

        try:
            self.config = self.read_form_config()
            set_client_config(self.config)
            init_db(self.config)
        except Exception as exc:
            self._set_sync_failed(str(exc))
            self.append_log(f"[ERROR] {self._short_error_message(str(exc))}")
            QMessageBox.critical(self, "Sync now", str(exc))
            return

        self.sync_button.setEnabled(False)
        self.last_error_message = None
        self.append_log("Starting sync")
        self._update_watcher_controls()

        self.sync_thread = QThread(self)
        self.sync_worker = SyncWorker(self.config)
        self.sync_worker.moveToThread(self.sync_thread)
        self.sync_thread.started.connect(self.sync_worker.run)
        self.sync_worker.finished.connect(self._handle_sync_finished)
        self.sync_worker.failed.connect(self._handle_sync_failed)
        self.sync_worker.finished.connect(self.sync_thread.quit)
        self.sync_worker.failed.connect(self.sync_thread.quit)
        self.sync_thread.finished.connect(self._cleanup_sync_thread)
        self.sync_thread.start()

    def start_watcher(self) -> None:
        if self.watcher_service is not None and self.watcher_service.is_running:
            self.append_log("Watcher already running")
            self._update_watcher_controls()
            return

        try:
            self.config = self.read_form_config()
            set_client_config(self.config)
            init_db(self.config)
            self.watcher_service = SyncWatcherService(
                self.config,
                local_base_path=self.config.base_path,
                device_id=self.config.device_id,
                event_sink=self.emit_watcher_event,
            )
            self.watcher_service.start()
        except Exception as exc:
            self._set_sync_failed(str(exc))
            self.append_log(f"[ERROR] {self._short_error_message(str(exc))}")
            QMessageBox.critical(self, "Start watcher", str(exc))
            self._update_watcher_controls()
            return

        self.refresh_file_list()
        self._update_watcher_controls()

    def stop_watcher(self) -> None:
        if self.watcher_service is None:
            self._update_watcher_controls()
            return

        try:
            self.watcher_service.stop()
        except Exception as exc:
            self._set_sync_failed(str(exc))
            self.append_log(f"[ERROR] {self._short_error_message(str(exc))}")
            QMessageBox.critical(self, "Stop watcher", str(exc))
            return

        self.refresh_file_list()
        self._update_watcher_controls()

    def refresh_file_list(self) -> None:
        try:
            entries = [entry for entry in list_local_files(self.config) if not entry.deleted]
        except Exception as exc:
            self.append_log(f"[ERROR] {self._short_error_message(str(exc))}")
            return

        self.file_table.setRowCount(len(entries))
        for row_index, entry in enumerate(entries):
            state = "conflict" if entry.conflict else "ok"
            values = [
                entry.path,
                str(entry.version),
                entry.hash,
                state,
            ]
            for column_index, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.file_table.setItem(row_index, column_index, item)

        self.file_table.resizeColumnsToContents()

    def emit_watcher_event(self, message: str) -> None:
        self.event_bridge.message.emit(message)

    def handle_watcher_event(self, message: str) -> None:
        if message == "Sync cycle completed":
            self._set_sync_success()
            self.append_log("[OK] Synced successfully")
            self.refresh_file_list()
            return

        if message.startswith("Sync cycle failed:"):
            error_message = self._short_error_message(message.partition(":")[2].strip())
            self._set_sync_failed(error_message)
            self.append_log(f"[ERROR] {error_message}")
            self.refresh_file_list()
            return

        self.append_log(message)

    def append_log(self, message: str) -> None:
        self.log_output.appendPlainText(message)
        self.log_output.verticalScrollBar().setValue(self.log_output.verticalScrollBar().maximum())
        self._update_watcher_controls()

    def _update_watcher_controls(self) -> None:
        watcher_running = self.watcher_service is not None and self.watcher_service.is_running
        last_sync_text = f"Last sync: {self.last_sync_status}"
        if self.last_sync_time is not None:
            last_sync_text = (
                f"{last_sync_text} at {self.last_sync_time.astimezone().strftime('%Y-%m-%d %H:%M:%S')}"
            )

        self.status_label.setText(
            f"Watcher: {'running' if watcher_running else 'stopped'} | {last_sync_text}"
        )
        self.start_watcher_button.setEnabled(not watcher_running)
        self.stop_watcher_button.setEnabled(watcher_running)

    def _handle_sync_finished(self, rendered_actions: list[str]) -> None:
        self._set_sync_success()
        if rendered_actions:
            for line in rendered_actions:
                self.append_log(f"Sync: {line}")

        self.append_log("[OK] Synced successfully")
        self.refresh_file_list()
        self.sync_button.setEnabled(True)

    def _handle_sync_failed(self, error_message: str) -> None:
        short_message = self._short_error_message(error_message)
        self._set_sync_failed(short_message)
        self.append_log(f"[ERROR] {short_message}")
        QMessageBox.critical(self, "Sync failed", error_message)
        self.sync_button.setEnabled(True)

    def _cleanup_sync_thread(self) -> None:
        if self.sync_worker is not None:
            self.sync_worker.deleteLater()
        if self.sync_thread is not None:
            self.sync_thread.deleteLater()
        self.sync_worker = None
        self.sync_thread = None

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if self.sync_thread is not None and self.sync_thread.isRunning():
            QMessageBox.information(self, "LAN Cloud Sync", "Sync is still running.")
            event.ignore()
            return

        if self.watcher_service is not None and self.watcher_service.is_running:
            self.watcher_service.stop()

        event.accept()

    def _set_sync_success(self) -> None:
        self.last_sync_status = "success"
        self.last_sync_time = datetime.now().astimezone()
        self.last_error_message = None
        self._update_watcher_controls()

    def _set_sync_failed(self, error_message: str) -> None:
        self.last_sync_status = "failed"
        self.last_sync_time = datetime.now().astimezone()
        self.last_error_message = error_message
        self._update_watcher_controls()

    def _short_error_message(self, message: str) -> str:
        return " ".join(message.splitlines()).strip() or "Unknown error"


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
