from __future__ import annotations

import argparse
import atexit
import os
import sys

import uvicorn

from server.app.config import PID_PATH, ensure_server_config
from server.app.db.session import get_session_factory, init_db
from server.app.services.file_service import prune_tombstones


def main() -> None:
    config = ensure_server_config()
    parser = build_parser()
    args = parser.parse_args()
    args.handler(args, config)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="lan-cloud-sync-server")
    subparsers = parser.add_subparsers(dest="command", required=True)

    serve_parser = subparsers.add_parser("serve")
    serve_parser.set_defaults(handler=handle_serve)

    prune_parser = subparsers.add_parser("prune-tombstones")
    prune_parser.add_argument("--older-than-days", type=int)
    prune_parser.set_defaults(handler=handle_prune_tombstones)

    config_parser = subparsers.add_parser("config")
    config_parser.set_defaults(handler=handle_config)

    return parser


def _acquire_pid_lock() -> None:
    pid = os.getpid()
    if PID_PATH.exists():
        try:
            existing = int(PID_PATH.read_text().strip())
            if existing == pid:
                PID_PATH.write_text(str(pid))
                return
            os.kill(existing, 0)
            print(f"Сервер уже запущен (PID {existing}). Используй stop_server.bat сначала.")
            sys.exit(1)
        except (OSError, ValueError):
            pass
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(pid))
    atexit.register(lambda: PID_PATH.unlink(missing_ok=True))


def handle_serve(_: argparse.Namespace, config) -> None:
    _acquire_pid_lock()
    uvicorn.run(
        "server.app.main:app",
        host=config.host,
        port=config.port,
    )


def handle_prune_tombstones(args: argparse.Namespace, config) -> None:
    init_db()
    older_than_days = (
        args.older_than_days
        if args.older_than_days is not None
        else config.tombstone_retention_days
    )
    with get_session_factory()() as session:
        deleted_count = prune_tombstones(session, older_than_days=older_than_days)

    print(f"pruned server tombstones: {deleted_count}")


def handle_config(_: argparse.Namespace, config) -> None:
    print(f"host={config.host}")
    print(f"port={config.port}")
    print(f"storage_path={config.storage_path}")
    print(f"db_path={config.db_path}")
    print(f"tombstone_retention_days={config.tombstone_retention_days}")


if __name__ == "__main__":
    main()
