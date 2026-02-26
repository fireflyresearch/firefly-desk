# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Document Source admin API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.knowledge.document_source_repository import DocumentSource


# ---------------------------------------------------------------------------
# Helpers
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


def _sample_source(source_id: str = "src-1") -> DocumentSource:
    return DocumentSource(
        id=source_id,
        source_type="s3",
        category="blob",
        display_name="My S3 Bucket",
        auth_method="credentials",
        has_config=True,
        config_summary={"bucket": "my-bucket", "region": "us-east-1"},
        is_active=True,
        sync_enabled=False,
        sync_cron=None,
        last_sync_at=None,
        created_at="2026-01-15T10:00:00",
        updated_at="2026-01-15T10:00:00",
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo():
    """Return an AsyncMock that mimics DocumentSourceRepository."""
    repo = AsyncMock()
    repo.create = AsyncMock(return_value=_sample_source())
    repo.get = AsyncMock(return_value=None)
    repo.list_all = AsyncMock(return_value=[])
    repo.update = AsyncMock(return_value=None)
    repo.delete = AsyncMock(return_value=None)
    repo.get_decrypted_config = AsyncMock(return_value=None)
    repo.get_row = AsyncMock(return_value=None)
    return repo


@pytest.fixture
async def admin_client(mock_repo):
    """AsyncClient with an admin user session and mocked DocumentSourceRepository."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.deps import get_document_source_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_document_source_repo] = lambda: mock_repo

        # Inject admin user_session into request state via middleware
        admin_session = _make_user_session(roles=["admin"])

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class TestListDocumentSources:
    async def test_list_empty(self, admin_client, mock_repo):
        mock_repo.list_all.return_value = []
        response = await admin_client.get("/api/admin/document-sources")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_returns_sources(self, admin_client, mock_repo):
        mock_repo.list_all.return_value = [_sample_source(), _sample_source("src-2")]
        response = await admin_client.get("/api/admin/document-sources")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "src-1"
        assert data[0]["source_type"] == "s3"
        assert data[0]["category"] == "blob"
        assert data[1]["id"] == "src-2"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateDocumentSource:
    async def test_create_source(self, admin_client, mock_repo):
        response = await admin_client.post(
            "/api/admin/document-sources",
            json={
                "source_type": "s3",
                "display_name": "My S3 Bucket",
                "config": {"bucket": "my-bucket", "region": "us-east-1"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "src-1"
        assert data["source_type"] == "s3"
        assert data["display_name"] == "My S3 Bucket"
        mock_repo.create.assert_awaited_once()

    async def test_create_drive_source(self, admin_client, mock_repo):
        drive_src = DocumentSource(
            id="src-3",
            source_type="google_drive",
            category="drive",
            display_name="Team Drive",
            auth_method="oauth",
            has_config=True,
            config_summary={"folder_id": "abc123"},
            is_active=True,
            sync_enabled=True,
            sync_cron="0 */6 * * *",
            last_sync_at=None,
            created_at="2026-01-15T10:00:00",
            updated_at="2026-01-15T10:00:00",
        )
        mock_repo.create.return_value = drive_src
        response = await admin_client.post(
            "/api/admin/document-sources",
            json={
                "source_type": "google_drive",
                "display_name": "Team Drive",
                "auth_method": "oauth",
                "config": {"folder_id": "abc123"},
                "sync_enabled": True,
                "sync_cron": "0 */6 * * *",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["category"] == "drive"
        assert data["sync_enabled"] is True


# ---------------------------------------------------------------------------
# Get
# ---------------------------------------------------------------------------


class TestGetDocumentSource:
    async def test_get_found(self, admin_client, mock_repo):
        mock_repo.get.return_value = _sample_source()
        response = await admin_client.get("/api/admin/document-sources/src-1")
        assert response.status_code == 200
        assert response.json()["id"] == "src-1"

    async def test_get_not_found(self, admin_client, mock_repo):
        mock_repo.get.return_value = None
        response = await admin_client.get("/api/admin/document-sources/no-such")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteDocumentSource:
    async def test_delete_source(self, admin_client, mock_repo):
        mock_repo.get.return_value = _sample_source()
        response = await admin_client.delete("/api/admin/document-sources/src-1")
        assert response.status_code == 204
        mock_repo.delete.assert_awaited_once_with("src-1")

    async def test_delete_not_found(self, admin_client, mock_repo):
        mock_repo.get.return_value = None
        response = await admin_client.delete("/api/admin/document-sources/no-such")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Test connectivity
# ---------------------------------------------------------------------------


class TestConnectivity:
    async def test_connectivity_success(self, admin_client, mock_repo):
        mock_repo.get_decrypted_config.return_value = {"bucket": "b", "region": "us-east-1"}
        row = MagicMock()
        row.source_type = "s3"
        mock_repo.get_row.return_value = row

        mock_adapter = AsyncMock()
        mock_adapter.validate_credentials.return_value = True

        with patch(
            "flydesk.api.document_sources.DocumentSourceFactory.create",
            return_value=mock_adapter,
        ), patch(
            "flydesk.api.document_sources.DocumentSourceFactory.registered_types",
            return_value=["s3"],
        ):
            response = await admin_client.post("/api/admin/document-sources/src-1/test")

        assert response.status_code == 200
        data = response.json()
        assert data["reachable"] is True
        assert data["error"] is None

    async def test_connectivity_not_found(self, admin_client, mock_repo):
        mock_repo.get_decrypted_config.return_value = None
        response = await admin_client.post("/api/admin/document-sources/no-such/test")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Sync (stub)
# ---------------------------------------------------------------------------


class TestSync:
    async def test_sync_triggered(self, admin_client, mock_repo):
        mock_repo.get.return_value = _sample_source()
        response = await admin_client.post("/api/admin/document-sources/src-1/sync")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "triggered"
        assert data["source_id"] == "src-1"

    async def test_sync_not_found(self, admin_client, mock_repo):
        mock_repo.get.return_value = None
        response = await admin_client.post("/api/admin/document-sources/no-such/sync")
        assert response.status_code == 404
