# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Catalog Tags, System-Tag Associations, and System-Document API endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.catalog.models import SystemDocument, SystemTag


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


def _sample_tag(tag_id: str = "tag-1") -> SystemTag:
    return SystemTag(
        id=tag_id,
        name="Backend",
        color="#FF0000",
        description="Backend systems",
    )


def _sample_document_link(
    system_id: str = "sys-1", document_id: str = "doc-1"
) -> SystemDocument:
    return SystemDocument(
        system_id=system_id,
        document_id=document_id,
        role="reference",
    )


@pytest.fixture
def mock_repo():
    """Return an AsyncMock that mimics CatalogRepository with tag/document methods."""
    repo = AsyncMock()
    # System methods (needed for endpoint routing)
    repo.create_system = AsyncMock(return_value=None)
    repo.get_system = AsyncMock(return_value=None)
    repo.list_systems = AsyncMock(return_value=([], 0))
    repo.update_system = AsyncMock(return_value=None)
    repo.delete_system = AsyncMock(return_value=None)
    repo.create_endpoint = AsyncMock(return_value=None)
    repo.get_endpoint = AsyncMock(return_value=None)
    repo.list_endpoints = AsyncMock(return_value=[])
    repo.delete_endpoint = AsyncMock(return_value=None)
    # Tag methods
    repo.create_tag = AsyncMock(return_value=None)
    repo.list_tags = AsyncMock(return_value=[])
    repo.update_tag = AsyncMock(return_value=None)
    repo.delete_tag = AsyncMock(return_value=None)
    # Tag association methods
    repo.assign_tag = AsyncMock(return_value=None)
    repo.remove_tag = AsyncMock(return_value=None)
    repo.list_system_tags = AsyncMock(return_value=[])
    # Document methods
    repo.link_document = AsyncMock(return_value=None)
    repo.unlink_document = AsyncMock(return_value=None)
    repo.list_system_documents = AsyncMock(return_value=[])
    return repo


@pytest.fixture
async def admin_client(mock_repo):
    """AsyncClient with an admin user session and mocked CatalogRepository."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.catalog import get_catalog_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_catalog_repo] = lambda: mock_repo

        from flydesk.api.deps import get_audit_logger
        app.dependency_overrides[get_audit_logger] = lambda: AsyncMock()

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
# Tag CRUD
# ---------------------------------------------------------------------------


class TestListTags:
    async def test_list_tags_empty(self, admin_client, mock_repo):
        mock_repo.list_tags.return_value = []
        response = await admin_client.get("/api/catalog/tags")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_tags_returns_items(self, admin_client, mock_repo):
        mock_repo.list_tags.return_value = [_sample_tag()]
        response = await admin_client.get("/api/catalog/tags")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["name"] == "Backend"
        assert data[0]["color"] == "#FF0000"


class TestCreateTag:
    async def test_create_tag_returns_201(self, admin_client, mock_repo):
        response = await admin_client.post(
            "/api/catalog/tags",
            json={"name": "Frontend", "color": "#00FF00", "description": "UI systems"},
        )
        assert response.status_code == 201
        mock_repo.create_tag.assert_awaited_once()

    async def test_create_tag_returns_body(self, admin_client, mock_repo):
        response = await admin_client.post(
            "/api/catalog/tags",
            json={"name": "Frontend", "color": "#00FF00"},
        )
        data = response.json()
        assert data["name"] == "Frontend"
        assert data["color"] == "#00FF00"
        assert "id" in data  # UUID was generated

    async def test_create_tag_minimal_body(self, admin_client, mock_repo):
        response = await admin_client.post(
            "/api/catalog/tags",
            json={"name": "Minimal"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Minimal"
        assert data["color"] is None
        assert data["description"] is None


class TestUpdateTag:
    async def test_update_tag_success(self, admin_client, mock_repo):
        response = await admin_client.put(
            "/api/catalog/tags/tag-1",
            json={"name": "Updated", "color": "#0000FF", "description": "Updated desc"},
        )
        assert response.status_code == 200
        mock_repo.update_tag.assert_awaited_once()
        data = response.json()
        assert data["id"] == "tag-1"
        assert data["name"] == "Updated"
        assert data["color"] == "#0000FF"


class TestDeleteTag:
    async def test_delete_tag_success(self, admin_client, mock_repo):
        response = await admin_client.delete("/api/catalog/tags/tag-1")
        assert response.status_code == 204
        mock_repo.delete_tag.assert_awaited_once_with("tag-1")


# ---------------------------------------------------------------------------
# System-Tag Associations
# ---------------------------------------------------------------------------


class TestListSystemTags:
    async def test_list_system_tags_empty(self, admin_client, mock_repo):
        mock_repo.list_system_tags.return_value = []
        response = await admin_client.get("/api/catalog/systems/sys-1/tags")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_system_tags_returns_items(self, admin_client, mock_repo):
        mock_repo.list_system_tags.return_value = [_sample_tag()]
        response = await admin_client.get("/api/catalog/systems/sys-1/tags")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "tag-1"
        assert data[0]["name"] == "Backend"


class TestAssignSystemTag:
    async def test_assign_tag_success(self, admin_client, mock_repo):
        response = await admin_client.post(
            "/api/catalog/systems/sys-1/tags",
            json={"tag_id": "tag-1"},
        )
        assert response.status_code == 200
        mock_repo.assign_tag.assert_awaited_once_with("sys-1", "tag-1")
        data = response.json()
        assert data["system_id"] == "sys-1"
        assert data["tag_id"] == "tag-1"


class TestRemoveSystemTag:
    async def test_remove_tag_success(self, admin_client, mock_repo):
        response = await admin_client.delete(
            "/api/catalog/systems/sys-1/tags/tag-1"
        )
        assert response.status_code == 204
        mock_repo.remove_tag.assert_awaited_once_with("sys-1", "tag-1")


# ---------------------------------------------------------------------------
# System-Document Links
# ---------------------------------------------------------------------------


class TestListSystemDocuments:
    async def test_list_documents_empty(self, admin_client, mock_repo):
        mock_repo.list_system_documents.return_value = []
        response = await admin_client.get("/api/catalog/systems/sys-1/documents")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_documents_returns_items(self, admin_client, mock_repo):
        mock_repo.list_system_documents.return_value = [_sample_document_link()]
        response = await admin_client.get("/api/catalog/systems/sys-1/documents")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["system_id"] == "sys-1"
        assert data[0]["document_id"] == "doc-1"
        assert data[0]["role"] == "reference"


class TestLinkSystemDocument:
    async def test_link_document_success(self, admin_client, mock_repo):
        response = await admin_client.post(
            "/api/catalog/systems/sys-1/documents",
            json={"document_id": "doc-1", "role": "api_spec"},
        )
        assert response.status_code == 200
        mock_repo.link_document.assert_awaited_once_with("sys-1", "doc-1", "api_spec")
        data = response.json()
        assert data["system_id"] == "sys-1"
        assert data["document_id"] == "doc-1"
        assert data["role"] == "api_spec"

    async def test_link_document_default_role(self, admin_client, mock_repo):
        response = await admin_client.post(
            "/api/catalog/systems/sys-1/documents",
            json={"document_id": "doc-2"},
        )
        assert response.status_code == 200
        mock_repo.link_document.assert_awaited_once_with("sys-1", "doc-2", "reference")
        data = response.json()
        assert data["role"] == "reference"


class TestUnlinkSystemDocument:
    async def test_unlink_document_success(self, admin_client, mock_repo):
        response = await admin_client.delete(
            "/api/catalog/systems/sys-1/documents/doc-1"
        )
        assert response.status_code == 204
        mock_repo.unlink_document.assert_awaited_once_with("sys-1", "doc-1")
