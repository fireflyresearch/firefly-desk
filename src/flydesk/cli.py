# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Firefly Desk CLI -- management commands."""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------

def serve(args: argparse.Namespace) -> None:
    """Start the Firefly Desk backend server."""
    import uvicorn

    uvicorn.run(
        "flydesk.server:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


# ---------------------------------------------------------------------------
# dev
# ---------------------------------------------------------------------------

def dev(args: argparse.Namespace) -> None:
    """Start backend and frontend together for development."""
    procs: list[subprocess.Popen] = []

    def _cleanup(signum=None, frame=None) -> None:
        for p in procs:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, _cleanup)
    signal.signal(signal.SIGTERM, _cleanup)

    # Backend
    backend_cmd = [
        sys.executable, "-m", "uvicorn",
        "flydesk.server:create_app",
        "--factory",
        "--reload",
        "--host", "127.0.0.1",
        "--port", str(args.port),
    ]
    print(f"[flydesk] Starting backend on http://127.0.0.1:{args.port}")
    procs.append(subprocess.Popen(
        backend_cmd,
        preexec_fn=os.setsid,
    ))

    # Frontend
    if not args.no_frontend:
        frontend_cmd = [
            "npm", "--prefix", "frontend",
            "run", "dev", "--",
            "--port", str(args.frontend_port),
        ]
        print(f"[flydesk] Starting frontend on http://localhost:{args.frontend_port}")
        procs.append(subprocess.Popen(
            frontend_cmd,
            preexec_fn=os.setsid,
        ))

    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        _cleanup()


# ---------------------------------------------------------------------------
# db
# ---------------------------------------------------------------------------

def db_upgrade(args: argparse.Namespace) -> None:
    """Run alembic upgrade."""
    subprocess.run(["alembic", "upgrade", args.revision], check=True)


def db_downgrade(args: argparse.Namespace) -> None:
    """Run alembic downgrade."""
    subprocess.run(["alembic", "downgrade", args.revision], check=True)


def db_revision(args: argparse.Namespace) -> None:
    """Create a new alembic revision."""
    subprocess.run(
        ["alembic", "revision", "--autogenerate", "-m", args.message],
        check=True,
    )


def db_current(args: argparse.Namespace) -> None:
    """Show current alembic revision."""
    subprocess.run(["alembic", "current"], check=True)


def db_history(args: argparse.Namespace) -> None:
    """Show alembic revision history."""
    subprocess.run(["alembic", "history"], check=True)


def db_stamp(args: argparse.Namespace) -> None:
    """Stamp the database with a specific revision."""
    subprocess.run(["alembic", "stamp", args.revision], check=True)


# ---------------------------------------------------------------------------
# status / version
# ---------------------------------------------------------------------------

def status(args: argparse.Namespace) -> None:
    """Show current configuration and service status."""
    try:
        from flydesk import __version__
        from flydesk.config import get_config

        config = get_config()
        db_display = config.database_url.split("@")[-1] if "@" in config.database_url else config.database_url
        print(f"Firefly Desk v{__version__}")
        print(f"  Mode:     {'development' if config.dev_mode else 'production'}")
        print(f"  Database: {db_display}")
        print(f"  Agent:    {config.agent_name}")
        print(f"  Title:    {config.app_title}")
    except Exception as exc:
        print(f"[!!] Failed to load config: {exc}", file=sys.stderr)
        sys.exit(1)


def version(args: argparse.Namespace) -> None:
    """Print version and exit."""
    from flydesk import __version__

    print(f"flydesk {__version__}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point for the flydesk CLI."""
    parser = argparse.ArgumentParser(
        prog="flydesk",
        description="Firefly Desk -- Backoffice as Agent",
    )
    subparsers = parser.add_subparsers(dest="command")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start the backend server")
    serve_parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    serve_parser.set_defaults(func=serve)

    # dev
    dev_parser = subparsers.add_parser("dev", help="Start backend + frontend for development")
    dev_parser.add_argument("--port", type=int, default=8000, help="Backend port")
    dev_parser.add_argument("--frontend-port", type=int, default=5173, help="Frontend port")
    dev_parser.add_argument("--no-frontend", action="store_true", help="Skip starting the frontend")
    dev_parser.set_defaults(func=dev)

    # db
    db_parser = subparsers.add_parser("db", help="Database migration commands (Alembic)")
    db_sub = db_parser.add_subparsers(dest="db_command")

    up_parser = db_sub.add_parser("upgrade", help="Upgrade database schema")
    up_parser.add_argument("revision", nargs="?", default="head", help="Target revision (default: head)")
    up_parser.set_defaults(func=db_upgrade)

    down_parser = db_sub.add_parser("downgrade", help="Downgrade database schema")
    down_parser.add_argument("revision", nargs="?", default="-1", help="Target revision (default: -1)")
    down_parser.set_defaults(func=db_downgrade)

    rev_parser = db_sub.add_parser("revision", help="Create a new migration revision")
    rev_parser.add_argument("-m", "--message", required=True, help="Revision message")
    rev_parser.set_defaults(func=db_revision)

    cur_parser = db_sub.add_parser("current", help="Show current revision")
    cur_parser.set_defaults(func=db_current)

    hist_parser = db_sub.add_parser("history", help="Show revision history")
    hist_parser.set_defaults(func=db_history)

    stamp_parser = db_sub.add_parser("stamp", help="Stamp database with a revision")
    stamp_parser.add_argument("revision", help="Revision to stamp")
    stamp_parser.set_defaults(func=db_stamp)

    # status
    status_parser = subparsers.add_parser("status", help="Show service status")
    status_parser.set_defaults(func=status)

    # version
    version_parser = subparsers.add_parser("version", help="Print version")
    version_parser.set_defaults(func=version)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Handle 'flydesk db' with no subcommand
    if args.command == "db" and not getattr(args, "db_command", None):
        db_parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
