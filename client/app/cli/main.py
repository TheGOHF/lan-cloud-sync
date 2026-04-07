from __future__ import annotations

import argparse
import logging
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ..sync.config import ClientConfig, ensure_client_config, set_client_config
from ..sync.db import init_db, list_local_files
from ..sync.watcher import watch_forever
from ..sync.sync_engine import SyncAction, apply_action, get_sync_plan, sync
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    base_config = ensure_client_config()
    parser = build_parser(base_config)
    args = parser.parse_args()
    config = resolve_cli_config(args, base_config)
    set_client_config(config)
    init_db(config)
    args.handler(args, config)


def build_parser(config: ClientConfig) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lan-cloud-sync")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync")
    sync_parser.add_argument("--device-id")
    sync_parser.add_argument("--base-path", type=Path)
    sync_parser.set_defaults(handler=handle_sync)

    status_parser = subparsers.add_parser("status")
    status_parser.add_argument("--base-path", type=Path)
    status_parser.set_defaults(handler=handle_status)

    upload_parser = subparsers.add_parser("upload")
    upload_parser.add_argument("file")
    upload_parser.add_argument("--device-id")
    upload_parser.add_argument("--base-path", type=Path)
    upload_parser.set_defaults(handler=handle_upload)

    download_parser = subparsers.add_parser("download")
    download_parser.add_argument("file")
    download_parser.add_argument("--base-path", type=Path)
    download_parser.set_defaults(handler=handle_download)

    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(handler=handle_list)

    watch_parser = subparsers.add_parser("watch")
    watch_parser.add_argument("--device-id")
    watch_parser.add_argument("--base-path", type=Path)
    watch_parser.add_argument("--poll-interval", type=int)
    watch_parser.set_defaults(handler=handle_watch)

    parser.set_defaults(default_config=config)

    return parser


def handle_sync(args: argparse.Namespace, config: ClientConfig) -> None:
    actions = sync(local_base_path=config.base_path, device_id=config.device_id, config=config)
    _print_actions(actions)


def handle_status(args: argparse.Namespace, config: ClientConfig) -> None:
    actions = get_sync_plan(local_base_path=config.base_path, config=config)
    _print_actions(actions)


def handle_upload(args: argparse.Namespace, config: ClientConfig) -> None:
    relative_path = Path(args.file).as_posix()
    action = SyncAction(action="upload", path=relative_path, reason="manual_cli_upload")
    apply_action(action, local_base_path=config.base_path, device_id=config.device_id, config=config)
    print(f"uploaded {relative_path}")


def handle_download(args: argparse.Namespace, config: ClientConfig) -> None:
    relative_path = Path(args.file).as_posix()
    action = SyncAction(action="download", path=relative_path, reason="manual_cli_download")
    apply_action(action, local_base_path=config.base_path, device_id=config.device_id, config=config)
    print(f"downloaded {relative_path}")


def handle_list(_: argparse.Namespace, config: ClientConfig) -> None:
    for entry in list_local_files(config):
        conflict_flag = "conflict" if entry.conflict else "ok"
        print(f"{entry.path}\tv{entry.version}\t{entry.hash}\t{conflict_flag}")


def handle_watch(args: argparse.Namespace, config: ClientConfig) -> None:
    watch_forever(
        local_base_path=config.base_path,
        device_id=config.device_id,
        poll_interval=config.poll_interval_seconds,
        config=config,
    )


def resolve_cli_config(args: argparse.Namespace, base_config: ClientConfig) -> ClientConfig:
    poll_interval = getattr(args, "poll_interval", None)
    return base_config.with_overrides(
        base_path=getattr(args, "base_path", None),
        device_id=getattr(args, "device_id", None),
        poll_interval_seconds=poll_interval,
    )


def _print_actions(actions: list[SyncAction]) -> None:
    if not actions:
        print("no actions")
        return

    for action in actions:
        print(f"{action.action}\t{action.path}\t{action.reason}")


if __name__ == "__main__":
    main()
