# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""CLI entry point for seeding example domain data.

Usage::

    # Seed the banking example domain
    flydesk-seed banking

    # Remove the banking example domain
    flydesk-seed banking --remove

This command is intended for development and demos only.
Production deployments should never ship with example seed data.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from flydesk.config import get_config
from flydesk.db import create_engine_from_url, create_session_factory
from flydesk.models import Base

logger = logging.getLogger(__name__)


async def _run_seed(domain: str, *, remove: bool = False) -> None:
    config = get_config()
    engine = create_engine_from_url(config.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = create_session_factory(engine)

    if domain == "banking":
        if remove:
            from flydesk.seeds.banking import unseed_banking_catalog

            repo = _make_catalog_repo(session_factory)
            await unseed_banking_catalog(repo)
            logger.info("Banking seed data removed.")
        else:
            from flydesk.seeds.banking import seed_banking_catalog

            repo = _make_catalog_repo(session_factory)
            await seed_banking_catalog(repo)
            logger.info("Banking seed data loaded.")
    else:
        logger.error("Unknown domain: %s. Available: banking", domain)
        sys.exit(1)

    await engine.dispose()


def _make_catalog_repo(session_factory):  # noqa: ANN001, ANN202
    from flydesk.catalog.repository import CatalogRepository

    return CatalogRepository(session_factory)


def main() -> None:
    """CLI entry point for ``flydesk-seed``."""
    parser = argparse.ArgumentParser(
        prog="flydesk-seed",
        description="Seed or remove example domain data for Firefly Desk.",
    )
    parser.add_argument(
        "domain",
        choices=["banking"],
        help="The example domain to seed (currently only 'banking').",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        default=False,
        help="Remove previously seeded data instead of adding it.",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose logging.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s  %(name)s  %(message)s",
    )

    asyncio.run(_run_seed(args.domain, remove=args.remove))


if __name__ == "__main__":
    main()
