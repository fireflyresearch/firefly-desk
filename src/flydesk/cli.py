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
import sys


def serve(args: argparse.Namespace) -> None:
    """Start the Firefly Desk backend server."""
    import uvicorn

    uvicorn.run(
        "flydesk.server:create_app",
        factory=True,
        host="0.0.0.0",
        port=args.port,
        reload=args.reload,
    )


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


def main() -> None:
    """Entry point for the flydesk CLI."""
    parser = argparse.ArgumentParser(
        prog="flydesk",
        description="Firefly Desk -- Backoffice as Agent",
    )
    subparsers = parser.add_subparsers(dest="command")

    # serve
    serve_parser = subparsers.add_parser("serve", help="Start the backend server")
    serve_parser.add_argument("--port", type=int, default=8000, help="Port to listen on")
    serve_parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    serve_parser.set_defaults(func=serve)

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

    args.func(args)


if __name__ == "__main__":
    main()
