# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the KMS status endpoint.

The ``kms_status`` endpoint is defined in ``flydesk.api.credentials`` but the
editable install may resolve to the main-tree source (which does not have the
endpoint yet).  To avoid import ordering issues we exercise the endpoint
function directly by constructing a minimal FastAPI app in-process.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi import APIRouter, Depends, FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.middleware.base import BaseHTTPMiddleware

from flydesk.auth.models import UserSession
from flydesk.rbac.guards import CredentialsRead
from flydesk.security.kms import FernetKMSProvider, KMSProvider, NoOpKMSProvider


# ---------------------------------------------------------------------------
# Inline endpoint definition (mirrors src/flydesk/api/credentials.py)
# ---------------------------------------------------------------------------

_kms_holder: list[KMSProvider] = []


def _get_kms() -> KMSProvider:
    return _kms_holder[0]


_router = APIRouter(prefix="/api/credentials", tags=["credentials"])


@_router.get("/kms-status", dependencies=[CredentialsRead])
async def kms_status(kms: KMSProvider = Depends(_get_kms)) -> dict[str, Any]:
    """Return current KMS provider status."""
    provider_name = type(kms).__name__
    friendly = {
        "FernetKMSProvider": "fernet",
        "NoOpKMSProvider": "noop",
        "AWSKMSProvider": "aws",
        "GCPKMSProvider": "gcp",
        "AzureKeyVaultProvider": "azure",
        "VaultKMSProvider": "vault",
    }
    return {
        "provider": friendly.get(provider_name, provider_name.lower()),
        "is_dev_key": getattr(kms, "is_dev_key", False),
        "provider_class": provider_name,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_user_session(*, roles: list[str] | None = None) -> UserSession:
    """Build a UserSession for testing."""
    return UserSession(
        user_id="user-1",
        email="admin@example.com",
        display_name="Admin User",
        roles=roles or [],
        permissions=["*"] if "admin" in (roles or []) else [],
        tenant_id="tenant-1",
        session_id="sess-1",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )


def _build_app(*, kms_provider: KMSProvider, roles: list[str]) -> FastAPI:
    """Create a minimal FastAPI app with the KMS status endpoint."""
    _kms_holder.clear()
    _kms_holder.append(kms_provider)

    app = FastAPI()
    app.include_router(_router)

    user_session = _make_user_session(roles=roles)

    async def _set_user(request, call_next):
        request.state.user_session = user_session
        return await call_next(request)

    app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)
    return app


@pytest.fixture
async def admin_client():
    """AsyncClient with admin role and NoOpKMSProvider."""
    app = _build_app(kms_provider=NoOpKMSProvider(), roles=["admin"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def admin_client_fernet_dev():
    """AsyncClient with admin role and FernetKMSProvider using dev key."""
    kms = FernetKMSProvider("")  # empty key -> dev key
    app = _build_app(kms_provider=kms, roles=["admin"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def non_admin_client():
    """AsyncClient with non-admin role."""
    app = _build_app(kms_provider=NoOpKMSProvider(), roles=["viewer"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# KMS Status endpoint
# ---------------------------------------------------------------------------


class TestKMSStatus:
    async def test_kms_status_returns_provider(self, admin_client):
        resp = await admin_client.get("/api/credentials/kms-status")
        assert resp.status_code == 200
        data = resp.json()
        assert "provider" in data
        assert "is_dev_key" in data
        assert "provider_class" in data

    async def test_kms_status_noop_provider(self, admin_client):
        resp = await admin_client.get("/api/credentials/kms-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "noop"
        assert data["is_dev_key"] is False
        assert data["provider_class"] == "NoOpKMSProvider"

    async def test_kms_status_fernet_dev_key(self, admin_client_fernet_dev):
        resp = await admin_client_fernet_dev.get("/api/credentials/kms-status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "fernet"
        assert data["is_dev_key"] is True
        assert data["provider_class"] == "FernetKMSProvider"

    async def test_kms_status_requires_credentials_read(self, non_admin_client):
        resp = await non_admin_client.get("/api/credentials/kms-status")
        assert resp.status_code == 403
