# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Knowledge Admin REST API."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydek.auth.models import UserSession
from flydek.knowledge.models import DocumentChunk, KnowledgeDocument


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


def _sample_document(doc_id: str = "doc-1") -> KnowledgeDocument:
    return KnowledgeDocument(
        id=doc_id,
        title="Troubleshooting Guide",
        content="Step 1: Check the logs. Step 2: Restart the service.",
        source="internal-wiki",
        tags=["ops", "troubleshooting"],
        metadata={"author": "admin"},
    )


def _sample_chunk(chunk_id: str = "chunk-1", doc_id: str = "doc-1") -> DocumentChunk:
    return DocumentChunk(
        chunk_id=chunk_id,
        document_id=doc_id,
        content="Step 1: Check the logs.",
        chunk_index=0,
    )


@pytest.fixture
def mock_indexer():
    """Return an AsyncMock that mimics KnowledgeIndexer."""
    indexer = AsyncMock()
    indexer.index_document = AsyncMock(return_value=[])
    indexer.delete_document = AsyncMock(return_value=None)
    return indexer


@pytest.fixture
def mock_doc_store():
    """Return an AsyncMock that mimics KnowledgeDocumentStore."""
    store = AsyncMock()
    store.list_documents = AsyncMock(return_value=[])
    store.get_document = AsyncMock(return_value=None)
    return store


@pytest.fixture
async def admin_client(mock_indexer, mock_doc_store):
    """AsyncClient with an admin user session and mocked dependencies."""
    env = {
        "FLYDEK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDEK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDEK_OIDC_CLIENT_ID": "test",
        "FLYDEK_OIDC_CLIENT_SECRET": "test",
        "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydek.api.knowledge import get_knowledge_doc_store, get_knowledge_indexer
        from flydek.server import create_app

        app = create_app()
        app.dependency_overrides[get_knowledge_indexer] = lambda: mock_indexer
        app.dependency_overrides[get_knowledge_doc_store] = lambda: mock_doc_store

        admin_session = _make_user_session(roles=["admin"])

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def non_admin_client(mock_indexer, mock_doc_store):
    """AsyncClient with a non-admin user session."""
    env = {
        "FLYDEK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDEK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDEK_OIDC_CLIENT_ID": "test",
        "FLYDEK_OIDC_CLIENT_SECRET": "test",
        "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydek.api.knowledge import get_knowledge_doc_store, get_knowledge_indexer
        from flydek.server import create_app

        app = create_app()
        app.dependency_overrides[get_knowledge_indexer] = lambda: mock_indexer
        app.dependency_overrides[get_knowledge_doc_store] = lambda: mock_doc_store

        viewer_session = _make_user_session(roles=["viewer"])

        async def _set_user(request, call_next):
            request.state.user_session = viewer_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# List Documents
# ---------------------------------------------------------------------------


class TestListDocuments:
    async def test_list_documents_empty(self, admin_client, mock_doc_store):
        mock_doc_store.list_documents.return_value = []
        response = await admin_client.get("/api/knowledge/documents")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_documents_returns_items(self, admin_client, mock_doc_store):
        mock_doc_store.list_documents.return_value = [_sample_document()]
        response = await admin_client.get("/api/knowledge/documents")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "doc-1"
        assert data[0]["title"] == "Troubleshooting Guide"

    async def test_list_documents_excludes_content(self, admin_client, mock_doc_store):
        """List endpoint should return metadata only, not full content."""
        mock_doc_store.list_documents.return_value = [_sample_document()]
        response = await admin_client.get("/api/knowledge/documents")
        data = response.json()
        assert "content" not in data[0]


# ---------------------------------------------------------------------------
# Create (Index) Document
# ---------------------------------------------------------------------------


class TestCreateDocument:
    async def test_create_document_returns_201(self, admin_client, mock_indexer):
        doc = _sample_document()
        chunks = [_sample_chunk()]
        mock_indexer.index_document.return_value = chunks
        response = await admin_client.post(
            "/api/knowledge/documents", json=doc.model_dump()
        )
        assert response.status_code == 201
        mock_indexer.index_document.assert_awaited_once()

    async def test_create_document_returns_body(self, admin_client, mock_indexer):
        doc = _sample_document()
        chunks = [_sample_chunk()]
        mock_indexer.index_document.return_value = chunks
        response = await admin_client.post(
            "/api/knowledge/documents", json=doc.model_dump()
        )
        data = response.json()
        assert data["document_id"] == "doc-1"
        assert data["chunks_created"] == 1


# ---------------------------------------------------------------------------
# Delete Document
# ---------------------------------------------------------------------------


class TestDeleteDocument:
    async def test_delete_document_success(
        self, admin_client, mock_indexer, mock_doc_store
    ):
        mock_doc_store.get_document.return_value = _sample_document()
        response = await admin_client.delete("/api/knowledge/documents/doc-1")
        assert response.status_code == 204
        mock_indexer.delete_document.assert_awaited_once_with("doc-1")

    async def test_delete_document_not_found(self, admin_client, mock_doc_store):
        mock_doc_store.get_document.return_value = None
        response = await admin_client.delete("/api/knowledge/documents/no-such")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Admin-only access
# ---------------------------------------------------------------------------


class TestKnowledgeAdminGuard:
    async def test_non_admin_cannot_list_documents(self, non_admin_client):
        response = await non_admin_client.get("/api/knowledge/documents")
        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    async def test_non_admin_cannot_create_document(self, non_admin_client):
        doc = _sample_document()
        response = await non_admin_client.post(
            "/api/knowledge/documents", json=doc.model_dump()
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_delete_document(self, non_admin_client):
        response = await non_admin_client.delete("/api/knowledge/documents/doc-1")
        assert response.status_code == 403
