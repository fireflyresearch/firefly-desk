# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the multi-file upload endpoint (POST /documents/import-files)."""

from __future__ import annotations

import io
import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.knowledge.models import DocumentType, KnowledgeDocument
from flydesk.knowledge.queue import IndexingQueueProducer


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


def _sample_document(doc_id: str = "doc-1") -> KnowledgeDocument:
    return KnowledgeDocument(
        id=doc_id,
        title="Imported File",
        content="file content",
        source="upload",
        tags=[],
        metadata={},
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_indexer():
    indexer = AsyncMock()
    indexer.index_document = AsyncMock(return_value=[])
    indexer.delete_document = AsyncMock(return_value=None)
    return indexer


@pytest.fixture
def mock_doc_store():
    store = AsyncMock()
    store.list_documents = AsyncMock(return_value=[])
    store.get_document = AsyncMock(return_value=None)
    store.update_document = AsyncMock(return_value=None)
    return store


@pytest.fixture
def mock_importer():
    importer = AsyncMock()
    importer.import_url = AsyncMock(return_value=_sample_document("url-1"))
    importer.import_file = AsyncMock(return_value=_sample_document("file-1"))
    return importer


@pytest.fixture
def mock_producer():
    producer = AsyncMock(spec=IndexingQueueProducer)
    producer.enqueue = AsyncMock(return_value=None)
    return producer


@pytest.fixture
def mock_graph():
    from flydesk.knowledge.graph import EntityGraph

    graph = AsyncMock()
    graph.list_entities = AsyncMock(return_value=[])
    graph.get_entity_neighborhood = AsyncMock(return_value=EntityGraph())
    graph.upsert_entity = AsyncMock(return_value=None)
    graph.delete_entity = AsyncMock(return_value=True)
    graph.get_stats = AsyncMock(
        return_value={
            "entity_count": 0,
            "relation_count": 0,
            "entity_types": {},
            "relation_types": {},
        }
    )
    return graph


@pytest.fixture
async def admin_client(mock_indexer, mock_doc_store, mock_importer, mock_graph, mock_producer):
    """AsyncClient with an admin user session and mocked dependencies."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.knowledge import (
            get_indexing_producer,
            get_knowledge_doc_store,
            get_knowledge_graph,
            get_knowledge_importer,
            get_knowledge_indexer,
        )
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_knowledge_indexer] = lambda: mock_indexer
        app.dependency_overrides[get_knowledge_doc_store] = lambda: mock_doc_store
        app.dependency_overrides[get_knowledge_importer] = lambda: mock_importer
        app.dependency_overrides[get_knowledge_graph] = lambda: mock_graph
        app.dependency_overrides[get_indexing_producer] = lambda: mock_producer

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
# Tests: Multi-file upload
# ---------------------------------------------------------------------------

ENDPOINT = "/api/knowledge/documents/import-files"


class TestImportMultipleFilesEmpty:
    """Uploading zero files should return 422 (FastAPI rejects empty required list)."""

    async def test_no_files_field_returns_422(self, admin_client):
        """Omitting the 'files' form field entirely -> 422 validation error."""
        response = await admin_client.post(ENDPOINT)
        assert response.status_code == 422

    async def test_empty_files_body_returns_422(self, admin_client):
        """Sending multipart with no file parts -> 422 validation error."""
        response = await admin_client.post(ENDPOINT, data={})
        assert response.status_code == 422


class TestImportSingleFile:
    """Uploading exactly one file."""

    async def test_single_file_success(self, admin_client, mock_importer):
        mock_importer.import_file.return_value = _sample_document("single-1")
        response = await admin_client.post(
            ENDPOINT,
            files=[("files", ("readme.md", io.BytesIO(b"# Hello"), "text/markdown"))],
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["documents"]) == 1
        assert data["documents"][0]["filename"] == "readme.md"
        assert data["documents"][0]["document_id"] == "single-1"
        assert data["documents"][0]["status"] == "indexed"
        assert data["errors"] == []

    async def test_single_file_with_tags(self, admin_client, mock_importer):
        mock_importer.import_file.return_value = _sample_document("tagged-1")
        response = await admin_client.post(
            ENDPOINT,
            files=[("files", ("doc.txt", io.BytesIO(b"content"), "text/plain"))],
            data={"tags": "ops, internal"},
        )
        assert response.status_code == 201
        call_kwargs = mock_importer.import_file.call_args
        assert call_kwargs.kwargs["tags"] == ["ops", "internal"]


class TestImportMultipleFiles:
    """Uploading three files at once."""

    async def test_three_files_success(self, admin_client, mock_importer):
        # Return different documents for each call
        docs = [_sample_document(f"doc-{i}") for i in range(3)]
        mock_importer.import_file.side_effect = docs

        files = [
            ("files", (f"file{i}.txt", io.BytesIO(f"content {i}".encode()), "text/plain"))
            for i in range(3)
        ]
        response = await admin_client.post(ENDPOINT, files=files)
        assert response.status_code == 201
        data = response.json()
        assert len(data["documents"]) == 3
        assert data["errors"] == []
        assert mock_importer.import_file.await_count == 3

        # Verify each result matches
        for i in range(3):
            assert data["documents"][i]["filename"] == f"file{i}.txt"
            assert data["documents"][i]["document_id"] == f"doc-{i}"


class TestImportMixedSuccessFailure:
    """Some files succeed and some fail -- failures should not block others."""

    async def test_mixed_results(self, admin_client, mock_importer):
        good_doc = _sample_document("good-1")
        mock_importer.import_file.side_effect = [
            good_doc,
            RuntimeError("Unsupported file type"),
            _sample_document("good-2"),
        ]

        files = [
            ("files", ("good1.pdf", io.BytesIO(b"pdf bytes"), "application/pdf")),
            ("files", ("bad.xyz", io.BytesIO(b"bad bytes"), "application/octet-stream")),
            ("files", ("good2.md", io.BytesIO(b"# doc"), "text/markdown")),
        ]
        response = await admin_client.post(ENDPOINT, files=files)
        assert response.status_code == 201
        data = response.json()

        assert len(data["documents"]) == 2
        assert len(data["errors"]) == 1
        assert data["errors"][0]["filename"] == "bad.xyz"
        assert "Unsupported file type" in data["errors"][0]["error"]

        # Verify the importer was called for all three files
        assert mock_importer.import_file.await_count == 3

    async def test_all_files_fail(self, admin_client, mock_importer):
        mock_importer.import_file.side_effect = ValueError("parse error")

        files = [
            ("files", ("a.bin", io.BytesIO(b"\x00\x01"), "application/octet-stream")),
            ("files", ("b.bin", io.BytesIO(b"\x00\x02"), "application/octet-stream")),
        ]
        response = await admin_client.post(ENDPOINT, files=files)
        assert response.status_code == 201
        data = response.json()
        assert len(data["documents"]) == 0
        assert len(data["errors"]) == 2


class TestImportFilesCallsImporter:
    """Verify the importer is called with the correct arguments."""

    async def test_importer_receives_correct_args(self, admin_client, mock_importer):
        mock_importer.import_file.return_value = _sample_document("arg-1")
        file_content = b"Hello, World!"
        response = await admin_client.post(
            ENDPOINT,
            files=[("files", ("hello.txt", io.BytesIO(file_content), "text/plain"))],
            data={"tags": "greeting"},
        )
        assert response.status_code == 201
        mock_importer.import_file.assert_awaited_once_with(
            filename="hello.txt",
            content=file_content,
            content_type="text/plain",
            tags=["greeting"],
        )

    async def test_no_tags_passes_none(self, admin_client, mock_importer):
        mock_importer.import_file.return_value = _sample_document("notag-1")
        response = await admin_client.post(
            ENDPOINT,
            files=[("files", ("doc.txt", io.BytesIO(b"data"), "text/plain"))],
        )
        assert response.status_code == 201
        call_kwargs = mock_importer.import_file.call_args
        assert call_kwargs.kwargs["tags"] is None


class TestExistingSingleFileEndpointUnchanged:
    """The existing single-file endpoint should still work."""

    async def test_single_file_endpoint_still_works(self, admin_client, mock_importer):
        mock_importer.import_file.return_value = _sample_document("compat-1")
        response = await admin_client.post(
            "/api/knowledge/documents/import-file",
            files={"file": ("readme.md", io.BytesIO(b"# Hello"), "text/markdown")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "compat-1"
