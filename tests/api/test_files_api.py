# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the File Upload API."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.files.extractor import ContentExtractor
from flydesk.files.repository import FileUploadRepository
from flydesk.files.storage import LocalFileStorage
from flydesk.models.base import Base


@pytest.fixture
async def client(tmp_path):
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_DEV_MODE": "true",
        "FLYDESK_AGENT_NAME": "Ember",
        "FLYDESK_FILE_STORAGE_PATH": str(tmp_path / "uploads"),
    }
    with patch.dict(os.environ, env):
        from flydesk.api.files import get_content_extractor, get_file_repo, get_file_storage
        from flydesk.server import create_app

        app = create_app()

        # Create in-memory database and wire dependencies manually
        # (ASGITransport does not trigger lifespan)
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_factory = async_sessionmaker(engine, expire_on_commit=False)

        file_repo = FileUploadRepository(session_factory)
        file_storage = LocalFileStorage(str(tmp_path / "uploads"))
        content_extractor = ContentExtractor()

        app.dependency_overrides[get_file_repo] = lambda: file_repo
        app.dependency_overrides[get_file_storage] = lambda: file_storage
        app.dependency_overrides[get_content_extractor] = lambda: content_extractor

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

        await engine.dispose()


class TestFileUploadAPI:
    async def test_upload_file(self, client):
        """POST /api/chat/upload creates a file and returns metadata."""
        response = await client.post(
            "/api/chat/upload",
            files={"file": ("test.txt", b"Hello, world!", "text/plain")},
            data={"conversation_id": "conv-1"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["filename"] == "test.txt"
        assert body["content_type"] == "text/plain"
        assert body["file_size"] == 13
        assert body["conversation_id"] == "conv-1"
        assert body["extracted_text"] == "Hello, world!"
        assert "id" in body

    async def test_upload_file_without_conversation(self, client):
        """POST /api/chat/upload works without a conversation_id."""
        response = await client.post(
            "/api/chat/upload",
            files={"file": ("data.json", b'{"key": "value"}', "application/json")},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["filename"] == "data.json"
        assert body["conversation_id"] is None

    async def test_get_file_metadata(self, client):
        """GET /api/files/{file_id} returns file metadata."""
        # First upload a file
        upload_resp = await client.post(
            "/api/chat/upload",
            files={"file": ("readme.txt", b"Read me!", "text/plain")},
            data={"conversation_id": "conv-2"},
        )
        file_id = upload_resp.json()["id"]

        # Then retrieve metadata
        response = await client.get(f"/api/files/{file_id}")
        assert response.status_code == 200
        body = response.json()
        assert body["id"] == file_id
        assert body["filename"] == "readme.txt"
        assert body["file_size"] == 8

    async def test_get_file_metadata_not_found(self, client):
        """GET /api/files/{file_id} returns 404 for unknown files."""
        response = await client.get("/api/files/nonexistent")
        assert response.status_code == 404

    async def test_download_file(self, client):
        """GET /api/files/{file_id}/download returns file content."""
        content = b"Download this content"
        upload_resp = await client.post(
            "/api/chat/upload",
            files={"file": ("download.txt", content, "text/plain")},
        )
        file_id = upload_resp.json()["id"]

        response = await client.get(f"/api/files/{file_id}/download")
        assert response.status_code == 200
        assert response.content == content
        assert "text/plain" in response.headers["content-type"]
        assert "download.txt" in response.headers.get("content-disposition", "")

    async def test_download_file_not_found(self, client):
        """GET /api/files/{file_id}/download returns 404 for unknown files."""
        response = await client.get("/api/files/nonexistent/download")
        assert response.status_code == 404

    async def test_delete_file(self, client):
        """DELETE /api/files/{file_id} removes the file."""
        upload_resp = await client.post(
            "/api/chat/upload",
            files={"file": ("todelete.txt", b"bye", "text/plain")},
        )
        file_id = upload_resp.json()["id"]

        # Delete
        delete_resp = await client.delete(f"/api/files/{file_id}")
        assert delete_resp.status_code == 204

        # Verify gone
        get_resp = await client.get(f"/api/files/{file_id}")
        assert get_resp.status_code == 404

    async def test_delete_file_not_found(self, client):
        """DELETE /api/files/{file_id} returns 404 for unknown files."""
        response = await client.delete("/api/files/nonexistent")
        assert response.status_code == 404

    async def test_upload_binary_file(self, client):
        """Uploading a binary file stores it with no extracted text."""
        response = await client.post(
            "/api/chat/upload",
            files={"file": ("photo.png", b"\x89PNG\r\n\x1a\n", "image/png")},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["filename"] == "photo.png"
        assert body["content_type"] == "image/png"
        assert body["extracted_text"] is None
