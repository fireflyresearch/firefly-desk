# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Cloud Import API (browse + import)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.knowledge.document_source import (
    DriveInfo,
    DriveItem,
    StorageContainer,
    StorageObject,
)
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


def _sample_source(
    source_id: str = "src-1",
    source_type: str = "s3",
    category: str = "blob",
) -> DocumentSource:
    return DocumentSource(
        id=source_id,
        source_type=source_type,
        category=category,
        display_name="My Source",
        auth_method="credentials",
        has_config=True,
        config_summary={"bucket": "my-bucket"},
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
    repo.get = AsyncMock(return_value=None)
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
# Browse root -- blob storage
# ---------------------------------------------------------------------------


class TestBrowseRootBlob:
    async def test_browse_root_blob(self, admin_client, mock_repo):
        """Browsing a blob source returns containers."""
        mock_repo.get_decrypted_config.return_value = {"bucket": "b", "region": "us-east-1"}
        row = MagicMock()
        row.source_type = "s3"
        mock_repo.get_row.return_value = row

        mock_adapter = AsyncMock()
        mock_adapter.list_containers = AsyncMock(
            return_value=[
                StorageContainer(name="bucket-a"),
                StorageContainer(name="bucket-b", region="eu-west-1"),
            ]
        )
        mock_adapter.aclose = AsyncMock()

        # Make isinstance checks work for BlobStorageProvider
        from flydesk.knowledge.document_source import BlobStorageProvider

        mock_adapter.__class__ = type(
            "MockBlob", (), {
                "validate_credentials": AsyncMock(),
                "list_containers": AsyncMock(),
                "list_objects": AsyncMock(),
                "get_object_content": AsyncMock(),
                "aclose": AsyncMock(),
            }
        )

        with patch(
            "flydesk.api.cloud_import.DocumentSourceFactory.create",
            return_value=mock_adapter,
        ), patch(
            "flydesk.api.cloud_import._ensure_adapters_loaded",
        ):
            response = await admin_client.get("/api/import/src-1/browse")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "bucket-a"
        assert data[0]["name"] == "bucket-a"
        assert data[0]["type"] == "container"
        assert data[1]["id"] == "bucket-b"


# ---------------------------------------------------------------------------
# Browse root -- drive
# ---------------------------------------------------------------------------


class TestBrowseRootDrive:
    async def test_browse_root_drive(self, admin_client, mock_repo):
        """Browsing a drive source returns drives."""
        mock_repo.get_decrypted_config.return_value = {"client_id": "x", "tenant_id": "t"}
        row = MagicMock()
        row.source_type = "onedrive"
        mock_repo.get_row.return_value = row

        mock_adapter = AsyncMock()
        mock_adapter.list_drives = AsyncMock(
            return_value=[
                DriveInfo(id="drive-1", name="Personal Drive", type="personal"),
                DriveInfo(id="drive-2", name="Shared Drive", type="business"),
            ]
        )
        mock_adapter.aclose = AsyncMock()

        # Ensure isinstance(adapter, DriveProvider) is True but
        # isinstance(adapter, BlobStorageProvider) is False
        from flydesk.knowledge.document_source import DriveProvider

        mock_adapter.__class__ = type(
            "MockDrive", (), {
                "validate_credentials": AsyncMock(),
                "list_drives": AsyncMock(),
                "list_items": AsyncMock(),
                "get_file_content": AsyncMock(),
                "aclose": AsyncMock(),
            }
        )

        with patch(
            "flydesk.api.cloud_import.DocumentSourceFactory.create",
            return_value=mock_adapter,
        ), patch(
            "flydesk.api.cloud_import._ensure_adapters_loaded",
        ):
            response = await admin_client.get("/api/import/src-1/browse")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "drive-1"
        assert data[0]["name"] == "Personal Drive"
        assert data[0]["type"] == "drive"
        assert data[1]["id"] == "drive-2"


# ---------------------------------------------------------------------------
# Browse contents
# ---------------------------------------------------------------------------


class TestBrowseContents:
    async def test_browse_contents_blob(self, admin_client, mock_repo):
        """Browsing contents of a blob container returns files."""
        mock_repo.get_decrypted_config.return_value = {"bucket": "b"}
        row = MagicMock()
        row.source_type = "s3"
        mock_repo.get_row.return_value = row

        mock_adapter = AsyncMock()
        mock_adapter.list_objects = AsyncMock(
            return_value=[
                StorageObject(
                    key="docs/readme.md",
                    size=1024,
                    last_modified="2026-01-15T10:00:00Z",
                    content_type="text/markdown",
                ),
                StorageObject(
                    key="data.json",
                    size=512,
                    last_modified="2026-01-14T09:00:00Z",
                    content_type="application/json",
                ),
            ]
        )
        mock_adapter.aclose = AsyncMock()

        mock_adapter.__class__ = type(
            "MockBlob", (), {
                "validate_credentials": AsyncMock(),
                "list_containers": AsyncMock(),
                "list_objects": AsyncMock(),
                "get_object_content": AsyncMock(),
                "aclose": AsyncMock(),
            }
        )

        with patch(
            "flydesk.api.cloud_import.DocumentSourceFactory.create",
            return_value=mock_adapter,
        ), patch(
            "flydesk.api.cloud_import._ensure_adapters_loaded",
        ):
            response = await admin_client.get("/api/import/src-1/browse/my-bucket?prefix=docs/")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "docs/readme.md"
        assert data[0]["name"] == "readme.md"
        assert data[0]["type"] == "file"
        assert data[0]["size"] == 1024
        assert data[0]["mime_type"] == "text/markdown"
        assert data[0]["path"] == "docs/readme.md"
        assert data[1]["name"] == "data.json"

    async def test_browse_contents_drive(self, admin_client, mock_repo):
        """Browsing contents of a drive returns folders and files."""
        mock_repo.get_decrypted_config.return_value = {"client_id": "x"}
        row = MagicMock()
        row.source_type = "google_drive"
        mock_repo.get_row.return_value = row

        mock_adapter = AsyncMock()
        mock_adapter.list_items = AsyncMock(
            return_value=[
                DriveItem(
                    id="folder-1",
                    name="Reports",
                    path="/Reports",
                    is_folder=True,
                ),
                DriveItem(
                    id="file-1",
                    name="summary.pdf",
                    path="/summary.pdf",
                    is_folder=False,
                    size=2048,
                    modified_at="2026-01-10T08:00:00Z",
                    mime_type="application/pdf",
                ),
            ]
        )
        mock_adapter.aclose = AsyncMock()

        mock_adapter.__class__ = type(
            "MockDrive", (), {
                "validate_credentials": AsyncMock(),
                "list_drives": AsyncMock(),
                "list_items": AsyncMock(),
                "get_file_content": AsyncMock(),
                "aclose": AsyncMock(),
            }
        )

        with patch(
            "flydesk.api.cloud_import.DocumentSourceFactory.create",
            return_value=mock_adapter,
        ), patch(
            "flydesk.api.cloud_import._ensure_adapters_loaded",
        ):
            response = await admin_client.get(
                "/api/import/src-1/browse/drive-1?folder_id=root"
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "folder-1"
        assert data[0]["name"] == "Reports"
        assert data[0]["type"] == "folder"
        assert data[1]["id"] == "file-1"
        assert data[1]["name"] == "summary.pdf"
        assert data[1]["type"] == "file"
        assert data[1]["size"] == 2048
        assert data[1]["mime_type"] == "application/pdf"


# ---------------------------------------------------------------------------
# Import files
# ---------------------------------------------------------------------------


class TestImportFiles:
    async def test_import_files_accepted(self, admin_client, mock_repo):
        """POST import returns 202 with file count."""
        mock_repo.get.return_value = _sample_source()

        response = await admin_client.post(
            "/api/import/src-1/import",
            json={
                "items": [
                    {
                        "container_or_drive": "my-bucket",
                        "key_or_item_id": "docs/readme.md",
                        "name": "readme.md",
                    },
                    {
                        "container_or_drive": "my-bucket",
                        "key_or_item_id": "data.json",
                        "name": "data.json",
                    },
                ],
                "tags": ["imported"],
                "workspace_ids": ["ws-1"],
            },
        )

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"
        assert data["total"] == 2
        assert "2 file(s)" in data["message"]
        assert "My Source" in data["message"]

    async def test_import_files_empty_list(self, admin_client, mock_repo):
        """POST import with empty items returns 202 with zero total."""
        mock_repo.get.return_value = _sample_source()

        response = await admin_client.post(
            "/api/import/src-1/import",
            json={"items": []},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["total"] == 0

    async def test_import_not_found(self, admin_client, mock_repo):
        """POST import for nonexistent source returns 404."""
        mock_repo.get.return_value = None

        response = await admin_client.post(
            "/api/import/no-such/import",
            json={"items": []},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Browse not found
# ---------------------------------------------------------------------------


class TestBrowseNotFound:
    async def test_browse_root_not_found(self, admin_client, mock_repo):
        """Browsing a nonexistent source returns 404."""
        mock_repo.get_decrypted_config.return_value = None

        response = await admin_client.get("/api/import/no-such/browse")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    async def test_browse_contents_not_found(self, admin_client, mock_repo):
        """Browsing contents of a nonexistent source returns 404."""
        mock_repo.get_decrypted_config.return_value = None

        response = await admin_client.get("/api/import/no-such/browse/bucket-x")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
