from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ..sync.config import BASE_PATH
from ..sync.db import init_db, list_local_files
from ..sync.sync_engine import SyncAction, apply_action, get_sync_plan, sync
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    init_db()
    args.handler(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lan-cloud-sync")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--device-id", default="cli-device")
    sync_parser.add_argument("--base-path", type=Path, default=BASE_PATH)
    sync_parser.set_defaults(handler=handle_sync)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--base-path", type=Path, default=BASE_PATH)
    status_parser.set_defaults(handler=handle_status)

    upload_parser = subparsers.add_parser("upload")
    upload_parser.add_argument("file")
    upload_parser.add_argument("--device-id", default="cli-device")
    upload_parser.add_argument("--base-path", type=Path, default=BASE_PATH)
    upload_parser.set_defaults(handler=handle_upload)

    download_parser = subparsers.add_parser("download")
    download_parser.add_argument("file")
    download_parser.add_argument("--base-path", type=Path, default=BASE_PATH)
    download_parser.set_defaults(handler=handle_download)

    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(handler=handle_list)

    return parser


def handle_sync(args: argparse.Namespace) -> None:
    actions = sync(local_base_path=args.base_path, device_id=args.device_id)
    _print_actions(actions)


def handle_status(args: argparse.Namespace) -> None:
    actions = get_sync_plan(local_base_path=args.base_path)
    _print_actions(actions)


def handle_upload(args: argparse.Namespace) -> None:
    relative_path = Path(args.file).as_posix()
    action = SyncAction(action="upload", path=relative_path, reason="manual_cli_upload")
    apply_action(action, local_base_path=args.base_path, device_id=args.device_id)
    print(f"uploaded {relative_path}")


def handle_download(args: argparse.Namespace) -> None:
    relative_path = Path(args.file).as_posix()
    action = SyncAction(action="download", path=relative_path, reason="manual_cli_download")
    apply_action(action, local_base_path=args.base_path, device_id="cli-device")
    print(f"downloaded {relative_path}")


def handle_list(_: argparse.Namespace) -> None:
    for entry in list_local_files():
        conflict_flag = "conflict" if entry.conflict else "ok"
        print(f"{entry.path}\tv{entry.version}\t{entry.hash}\t{conflict_flag}")


def _print_actions(actions: list[SyncAction]) -> None:
    if not actions:
        print("no actions")
        return

    for action in actions:
        print(f"{action.action}\t{action.path}\t{action.reason}")


if __name__ == "__main__":
    main()
