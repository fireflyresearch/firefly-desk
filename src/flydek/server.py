# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import flydek
from flydek.api.catalog import router as catalog_router
from flydek.api.chat import router as chat_router
from flydek.api.health import router as health_router


def create_app() -> FastAPI:
    """Create and configure the Firefly Desk FastAPI application."""
    app = FastAPI(
        title="Firefly Desk",
        version=flydek.__version__,
        description="Backoffice as Agent",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(catalog_router)

    return app
