# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Export REST API endpoints."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.exports.models import ExportFormat, ExportRecord, ExportStatus, ExportTemplate
from flydesk.exports.repository import ExportRepository
from flydesk.exports.service import ExportService
from flydesk.models.base import Base


class _InMemoryStorage:
    """A minimal in-memory file storage for tests."""

    def __init__(self):
        self._files: dict[str, bytes] = {}

    async def store(self, filename: str, content: bytes, content_type: str) -> str:
        path = f"/test-storage/{filename}"
        self._files[path] = content
        return path

    async def retrieve(self, storage_path: str) -> bytes:
        if storage_path not in self._files:
            raise FileNotFoundError(storage_path)
        return self._files[storage_path]

    async def delete(self, storage_path: str) -> None:
        self._files.pop(storage_path, None)


@pytest.fixture
async def client():
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_DEV_MODE": "true",
        "FLYDESK_AGENT_NAME": "Ember",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.exports import get_export_repo, get_export_service, get_export_storage
        from flydesk.server import create_app

        app = create_app()

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        export_repo = ExportRepository(session_factory)
        storage = _InMemoryStorage()
        export_service = ExportService(export_repo, storage)

        app.dependency_overrides[get_export_repo] = lambda: export_repo
        app.dependency_overrides[get_export_service] = lambda: export_service
        app.dependency_overrides[get_export_storage] = lambda: storage

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        await engine.dispose()


SOURCE_TABLE = {
    "columns": ["id", "name", "email"],
    "rows": [
        ["1", "Alice", "alice@example.com"],
        ["2", "Bob", "bob@example.com"],
    ],
}


class TestExportAPI:
    async def test_create_csv_export(self, client):
        """POST /api/exports creates a CSV export and returns completed record."""
        response = await client.post(
            "/api/exports",
            json={
                "format": "csv",
                "title": "User Report",
                "source_data": SOURCE_TABLE,
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["format"] == "csv"
        assert body["title"] == "User Report"
        assert body["status"] == "completed"
        assert body["row_count"] == 2
        assert body["file_size"] is not None
        assert body["file_size"] > 0
        assert body["id"] is not None

    async def test_create_json_export(self, client):
        """POST /api/exports creates a JSON export end-to-end."""
        response = await client.post(
            "/api/exports",
            json={
                "format": "json",
                "title": "JSON Report",
                "source_data": SOURCE_TABLE,
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["format"] == "json"
        assert body["status"] == "completed"
        assert body["row_count"] == 2

    async def test_list_exports(self, client):
        """GET /api/exports returns the user's exports."""
        # Create two exports
        await client.post(
            "/api/exports",
            json={"format": "csv", "title": "Export 1", "source_data": SOURCE_TABLE},
        )
        await client.post(
            "/api/exports",
            json={"format": "json", "title": "Export 2", "source_data": SOURCE_TABLE},
        )

        response = await client.get("/api/exports")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 2

    async def test_get_export_by_id(self, client):
        """GET /api/exports/{id} returns details of a specific export."""
        create_resp = await client.post(
            "/api/exports",
            json={"format": "csv", "title": "Detail Test", "source_data": SOURCE_TABLE},
        )
        export_id = create_resp.json()["id"]

        response = await client.get(f"/api/exports/{export_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == export_id
        assert body["title"] == "Detail Test"

    async def test_get_export_not_found(self, client):
        """GET /api/exports/{id} returns 404 for unknown exports."""
        response = await client.get("/api/exports/nonexistent")
        assert response.status_code == 404

    async def test_download_export(self, client):
        """GET /api/exports/{id}/download returns the export file content."""
        create_resp = await client.post(
            "/api/exports",
            json={"format": "csv", "title": "Download Test", "source_data": SOURCE_TABLE},
        )
        export_id = create_resp.json()["id"]

        response = await client.get(f"/api/exports/{export_id}/download")
        assert response.status_code == 200
        assert "text/csv" in response.headers["content-type"]
        content = response.text
        assert "id" in content
        assert "Alice" in content
        assert "Bob" in content

    async def test_delete_export(self, client):
        """DELETE /api/exports/{id} removes the export."""
        create_resp = await client.post(
            "/api/exports",
            json={"format": "csv", "title": "To Delete", "source_data": SOURCE_TABLE},
        )
        export_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"/api/exports/{export_id}")
        assert delete_resp.status_code == 204

        # Verify it's gone
        get_resp = await client.get(f"/api/exports/{export_id}")
        assert get_resp.status_code == 404

    async def test_delete_export_not_found(self, client):
        """DELETE /api/exports/{id} returns 404 for unknown exports."""
        response = await client.delete("/api/exports/nonexistent")
        assert response.status_code == 404


class TestTemplateAPI:
    async def test_create_template(self, client):
        """POST /api/exports/templates creates a template (admin)."""
        response = await client.post(
            "/api/exports/templates",
            json={
                "name": "Standard Report",
                "format": "csv",
                "column_mapping": {"id": "ID", "name": "Name"},
                "header_text": "My Header",
            },
        )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Standard Report"
        assert body["format"] == "csv"
        assert body["column_mapping"] == {"id": "ID", "name": "Name"}
        assert body["header_text"] == "My Header"
        assert body["id"] is not None

    async def test_list_templates(self, client):
        """GET /api/exports/templates returns all templates."""
        await client.post(
            "/api/exports/templates",
            json={"name": "Template A", "format": "csv"},
        )
        await client.post(
            "/api/exports/templates",
            json={"name": "Template B", "format": "json"},
        )

        response = await client.get("/api/exports/templates")
        assert response.status_code == 200
        body = response.json()
        assert isinstance(body, list)
        assert len(body) == 2

    async def test_delete_template(self, client):
        """DELETE /api/exports/templates/{id} removes the template."""
        create_resp = await client.post(
            "/api/exports/templates",
            json={"name": "Deletable", "format": "csv"},
        )
        template_id = create_resp.json()["id"]

        delete_resp = await client.delete(f"/api/exports/templates/{template_id}")
        assert delete_resp.status_code == 204

        # Verify it's gone from the list
        list_resp = await client.get("/api/exports/templates")
        ids = [t["id"] for t in list_resp.json()]
        assert template_id not in ids

    async def test_delete_template_not_found(self, client):
        """DELETE /api/exports/templates/{id} returns 404 for unknown templates."""
        response = await client.delete("/api/exports/templates/nonexistent")
        assert response.status_code == 404
