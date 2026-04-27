from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from pprint import pformat
import sys
import tempfile
from types import SimpleNamespace
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from client.app.sync.file_utils import scan_local_folder
from client.app.sync.sync_engine import SyncAction, build_sync_plan
from shared.schemas import FileMetadataResponse


RESULTS_PATH = REPO_ROOT / "coursework_tests" / "test_results.txt"


@dataclass
class CourseworkTestCase:
    case_id: str
    functional_requirement: str
    test_requirement: str
    tested_method: str
    input_data: Any
    expected_output: Any
    actual_output: Any = None
    outputs_match: bool = False
    completed_successfully: bool = False
    error_message: str | None = None


def main() -> int:
    test_cases = [
        run_tp_1_1(),
        run_tp_1_2(),
        run_tp_1_3(),
        run_tp_1_4(),
        run_tp_2_1(),
        run_tp_2_2(),
        run_tp_2_3(),
    ]

    write_results_file(test_cases, RESULTS_PATH)

    total = len(test_cases)
    passed = sum(1 for test_case in test_cases if test_case.outputs_match and test_case.completed_successfully)
    failed = total - passed
    print(f"Coursework tests: total={total}, passed={passed}, failed={failed}")
    print(f"Detailed report: {RESULTS_PATH}")
    return 0 if failed == 0 else 1


def run_tp_1_1() -> CourseworkTestCase:
    return run_build_sync_plan_case(
        case_id="TP-1.1",
        test_requirement="ТТ-1.1: скачивание файла, который существует только на удаленной стороне",
        local_index={},
        server_index={
            "a.txt": build_remote_state(
                path="a.txt",
                version=1,
                file_hash="remote-hash-a",
                deleted=False,
            )
        },
        local_db_index={},
        expected_output=[("download", "a.txt")],
    )


def run_tp_1_2() -> CourseworkTestCase:
    return run_build_sync_plan_case(
        case_id="TP-1.2",
        test_requirement="ТТ-1.2: загрузка файла, который существует только локально",
        local_index={"a.txt": {"hash": "local-hash-a", "mtime": 100.0}},
        server_index={},
        local_db_index={},
        expected_output=[("upload", "a.txt")],
    )


def run_tp_1_3() -> CourseworkTestCase:
    return run_build_sync_plan_case(
        case_id="TP-1.3",
        test_requirement="ТТ-1.3: удаление удаленного файла, если он был синхронизирован ранее, есть на сервере, но отсутствует локально",
        local_index={},
        server_index={
            "a.txt": build_remote_state(
                path="a.txt",
                version=2,
                file_hash="remote-hash-a",
                deleted=False,
            )
        },
        local_db_index={
            "a.txt": build_local_db_state(
                path="a.txt",
                version=1,
                file_hash="remote-hash-a",
                deleted=False,
            )
        },
        expected_output=[("delete_remote", "a.txt")],
    )


def run_tp_1_4() -> CourseworkTestCase:
    return run_build_sync_plan_case(
        case_id="TP-1.4",
        test_requirement="ТТ-1.4: удаление локального файла, если удаленное состояние помечено как tombstone",
        local_index={"a.txt": {"hash": "local-hash-a", "mtime": 100.0}},
        server_index={
            "a.txt": build_remote_state(
                path="a.txt",
                version=3,
                file_hash="remote-hash-a",
                deleted=True,
            )
        },
        local_db_index={
            "a.txt": build_local_db_state(
                path="a.txt",
                version=2,
                file_hash="remote-hash-a",
                deleted=False,
            )
        },
        expected_output=[("delete_local", "a.txt")],
    )


def run_tp_2_1() -> CourseworkTestCase:
    return run_scan_case(
        case_id="TP-2.1",
        test_requirement='ТТ-2.1: игнорирование временных файлов Microsoft Word с префиксом "~$"',
        files_to_create=["~$doc.docx", "report.txt"],
        expected_output=["report.txt"],
    )


def run_tp_2_2() -> CourseworkTestCase:
    return run_scan_case(
        case_id="TP-2.2",
        test_requirement='ТТ-2.2: игнорирование ярлыков с расширением ".lnk"',
        files_to_create=["storage.lnk", "report.txt"],
        expected_output=["report.txt"],
    )


def run_tp_2_3() -> CourseworkTestCase:
    return run_scan_case(
        case_id="TP-2.3",
        test_requirement="ТТ-2.3: включение обычных пользовательских файлов",
        files_to_create=["docs/report.txt", "notes.txt"],
        expected_output=["docs/report.txt", "notes.txt"],
    )


def run_build_sync_plan_case(
    *,
    case_id: str,
    test_requirement: str,
    local_index: dict[str, dict[str, float | str]],
    server_index: dict[str, FileMetadataResponse],
    local_db_index: dict[str, Any],
    expected_output: list[tuple[str, str]],
) -> CourseworkTestCase:
    test_case = CourseworkTestCase(
        case_id=case_id,
        functional_requirement="ФТ-1",
        test_requirement=test_requirement,
        tested_method="client.app.sync.sync_engine.build_sync_plan",
        input_data={
            "local_index": local_index,
            "server_index": serialize_remote_index(server_index),
            "local_db_index": serialize_local_db_index(local_db_index),
        },
        expected_output=expected_output,
    )

    try:
        actions = build_sync_plan(
            local_index=local_index,
            server_index=server_index,
            local_db_index=local_db_index,
        )
        test_case.actual_output = normalize_sync_actions(actions)
        test_case.outputs_match = test_case.actual_output == expected_output
        test_case.completed_successfully = True
    except Exception as exc:
        test_case.actual_output = f"Exception: {exc}"
        test_case.error_message = str(exc)
        test_case.outputs_match = False
        test_case.completed_successfully = False

    return test_case


def run_scan_case(
    *,
    case_id: str,
    test_requirement: str,
    files_to_create: list[str],
    expected_output: list[str],
) -> CourseworkTestCase:
    test_case = CourseworkTestCase(
        case_id=case_id,
        functional_requirement="ФТ-2",
        test_requirement=test_requirement,
        tested_method="client.app.sync.file_utils.scan_local_folder",
        input_data={"files_to_create": files_to_create},
        expected_output=expected_output,
    )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_path = Path(temp_dir)
            for relative_path in files_to_create:
                file_path = base_path / relative_path
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text("test-data", encoding="utf-8")

            scanned_files = scan_local_folder(base_path)
            test_case.actual_output = sorted(scanned_files.keys())
            test_case.outputs_match = test_case.actual_output == sorted(expected_output)
            test_case.completed_successfully = True
    except Exception as exc:
        test_case.actual_output = f"Exception: {exc}"
        test_case.error_message = str(exc)
        test_case.outputs_match = False
        test_case.completed_successfully = False

    return test_case


def normalize_sync_actions(actions: list[SyncAction]) -> list[tuple[str, str]]:
    return sorted((action.action, action.path) for action in actions)


def build_remote_state(
    *,
    path: str,
    version: int,
    file_hash: str,
    deleted: bool,
) -> FileMetadataResponse:
    return FileMetadataResponse(
        path=path,
        version=version,
        hash=file_hash,
        updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        deleted=deleted,
    )


def build_local_db_state(
    *,
    path: str,
    version: int,
    file_hash: str,
    deleted: bool,
) -> Any:
    return SimpleNamespace(
        path=path,
        version=version,
        hash=file_hash,
        deleted=deleted,
    )


def serialize_remote_index(server_index: dict[str, FileMetadataResponse]) -> dict[str, dict[str, Any]]:
    return {
        path: {
            "path": record.path,
            "version": record.version,
            "hash": record.hash,
            "updated_at": record.updated_at.isoformat(),
            "deleted": record.deleted,
        }
        for path, record in server_index.items()
    }


def serialize_local_db_index(local_db_index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        path: {
            "path": record.path,
            "version": record.version,
            "hash": record.hash,
            "deleted": record.deleted,
        }
        for path, record in local_db_index.items()
    }


def write_results_file(test_cases: list[CourseworkTestCase], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for test_case in test_cases if test_case.outputs_match and test_case.completed_successfully)
    failed = len(test_cases) - passed

    lines: list[str] = []
    lines.append("Результаты курсового тестирования LAN Cloud Sync")
    lines.append("=" * 60)
    lines.append("")

    for test_case in test_cases:
        lines.append(f"Идентификатор тестового примера: {test_case.case_id}")
        lines.append(f"Функциональное требование: {test_case.functional_requirement}")
        lines.append(f"Тестовое требование: {test_case.test_requirement}")
        lines.append(f"Проверяемый метод: {test_case.tested_method}")
        lines.append("Входные данные:")
        lines.append(indent_block(pformat(test_case.input_data, width=100)))
        lines.append("Ожидаемый результат:")
        lines.append(indent_block(pformat(test_case.expected_output, width=100)))
        lines.append("Фактический результат:")
        lines.append(indent_block(pformat(test_case.actual_output, width=100)))
        lines.append(
            "Сравнение результатов: "
            + ("совпадение" if test_case.outputs_match else "несовпадение")
        )
        lines.append(
            "Статус выполнения: "
            + ("успешно" if test_case.completed_successfully else "неуспешно")
        )
        if test_case.error_message:
            lines.append(f"Сообщение об ошибке: {test_case.error_message}")
        lines.append("-" * 60)

    lines.append("Сводка")
    lines.append(f"Всего тестов: {len(test_cases)}")
    lines.append(f"Успешно: {passed}")
    lines.append(f"Неуспешно: {failed}")
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")


def indent_block(text: str) -> str:
    return "\n".join(f"  {line}" for line in text.splitlines())


if __name__ == "__main__":
    raise SystemExit(main())
