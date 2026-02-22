# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Knowledge Admin REST API."""

from __future__ import annotations

import io
import os
from dataclasses import asdict
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydek.auth.models import UserSession
from flydek.knowledge.graph import Entity, EntityGraph, Relation
from flydek.knowledge.models import DocumentChunk, DocumentType, KnowledgeDocument


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


def _sample_entity(entity_id: str = "ent-1") -> Entity:
    return Entity(
        id=entity_id,
        entity_type="service",
        name="Auth Service",
        properties={"version": "2.1"},
        source_system="catalog",
        confidence=0.95,
        mention_count=5,
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
    store.update_document = AsyncMock(return_value=None)
    return store


@pytest.fixture
def mock_importer():
    """Return an AsyncMock that mimics KnowledgeImporter."""
    importer = AsyncMock()
    importer.import_url = AsyncMock(return_value=_sample_document("imported-1"))
    importer.import_file = AsyncMock(return_value=_sample_document("imported-2"))
    return importer


@pytest.fixture
def mock_graph():
    """Return an AsyncMock that mimics KnowledgeGraph."""
    graph = AsyncMock()
    graph.list_entities = AsyncMock(return_value=[])
    graph.get_entity_neighborhood = AsyncMock(return_value=EntityGraph())
    graph.upsert_entity = AsyncMock(return_value=None)
    graph.delete_entity = AsyncMock(return_value=True)
    graph.get_stats = AsyncMock(
        return_value={
            "entity_count": 10,
            "relation_count": 25,
            "entity_types": {"service": 5, "database": 3, "team": 2},
            "relation_types": {"depends_on": 15, "owned_by": 10},
        }
    )
    return graph


@pytest.fixture
async def admin_client(mock_indexer, mock_doc_store, mock_importer, mock_graph):
    """AsyncClient with an admin user session and mocked dependencies."""
    env = {
        "FLYDEK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDEK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDEK_OIDC_CLIENT_ID": "test",
        "FLYDEK_OIDC_CLIENT_SECRET": "test",
        "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydek.api.knowledge import (
            get_knowledge_doc_store,
            get_knowledge_graph,
            get_knowledge_importer,
            get_knowledge_indexer,
        )
        from flydek.server import create_app

        app = create_app()
        app.dependency_overrides[get_knowledge_indexer] = lambda: mock_indexer
        app.dependency_overrides[get_knowledge_doc_store] = lambda: mock_doc_store
        app.dependency_overrides[get_knowledge_importer] = lambda: mock_importer
        app.dependency_overrides[get_knowledge_graph] = lambda: mock_graph

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
async def non_admin_client(mock_indexer, mock_doc_store, mock_importer, mock_graph):
    """AsyncClient with a non-admin user session."""
    env = {
        "FLYDEK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDEK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDEK_OIDC_CLIENT_ID": "test",
        "FLYDEK_OIDC_CLIENT_SECRET": "test",
        "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydek.api.knowledge import (
            get_knowledge_doc_store,
            get_knowledge_graph,
            get_knowledge_importer,
            get_knowledge_indexer,
        )
        from flydek.server import create_app

        app = create_app()
        app.dependency_overrides[get_knowledge_indexer] = lambda: mock_indexer
        app.dependency_overrides[get_knowledge_doc_store] = lambda: mock_doc_store
        app.dependency_overrides[get_knowledge_importer] = lambda: mock_importer
        app.dependency_overrides[get_knowledge_graph] = lambda: mock_graph

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
# Get Document by ID
# ---------------------------------------------------------------------------


class TestGetDocument:
    async def test_get_document_success(self, admin_client, mock_doc_store):
        doc = _sample_document()
        mock_doc_store.get_document.return_value = doc
        response = await admin_client.get("/api/knowledge/documents/doc-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "doc-1"
        assert data["title"] == "Troubleshooting Guide"
        assert "content" in data  # Full document includes content

    async def test_get_document_not_found(self, admin_client, mock_doc_store):
        mock_doc_store.get_document.return_value = None
        response = await admin_client.get("/api/knowledge/documents/no-such")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Update Document Metadata
# ---------------------------------------------------------------------------


class TestUpdateDocumentMetadata:
    async def test_update_document_metadata(self, admin_client, mock_doc_store):
        updated_doc = _sample_document()
        updated_doc.title = "Updated Title"
        mock_doc_store.update_document.return_value = updated_doc
        response = await admin_client.put(
            "/api/knowledge/documents/doc-1",
            json={"title": "Updated Title"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"
        mock_doc_store.update_document.assert_awaited_once_with(
            "doc-1", title="Updated Title", document_type=None, tags=None
        )

    async def test_update_document_not_found(self, admin_client, mock_doc_store):
        mock_doc_store.update_document.return_value = None
        response = await admin_client.put(
            "/api/knowledge/documents/no-such",
            json={"title": "New Title"},
        )
        assert response.status_code == 404


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
# Import from URL
# ---------------------------------------------------------------------------


class TestImportURL:
    async def test_import_url_success(self, admin_client, mock_importer):
        response = await admin_client.post(
            "/api/knowledge/documents/import-url",
            json={"url": "https://example.com/docs"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "imported-1"
        mock_importer.import_url.assert_awaited_once_with(
            url="https://example.com/docs",
            title=None,
            doc_type=None,
            tags=None,
        )

    async def test_import_url_with_metadata(self, admin_client, mock_importer):
        response = await admin_client.post(
            "/api/knowledge/documents/import-url",
            json={
                "url": "https://example.com/api",
                "title": "API Docs",
                "document_type": "api_spec",
                "tags": ["api"],
            },
        )
        assert response.status_code == 201
        mock_importer.import_url.assert_awaited_once_with(
            url="https://example.com/api",
            title="API Docs",
            doc_type=DocumentType.API_SPEC,
            tags=["api"],
        )


# ---------------------------------------------------------------------------
# Import from File Upload
# ---------------------------------------------------------------------------


class TestImportFile:
    async def test_import_file_success(self, admin_client, mock_importer):
        file_content = b"# My Document\n\nSome content here."
        response = await admin_client.post(
            "/api/knowledge/documents/import-file",
            files={"file": ("readme.md", io.BytesIO(file_content), "text/markdown")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "imported-2"
        mock_importer.import_file.assert_awaited_once()
        call_kwargs = mock_importer.import_file.call_args
        assert call_kwargs.kwargs["filename"] == "readme.md"

    async def test_import_file_with_tags(self, admin_client, mock_importer):
        file_content = b"Some content."
        response = await admin_client.post(
            "/api/knowledge/documents/import-file",
            files={"file": ("notes.txt", io.BytesIO(file_content), "text/plain")},
            data={"tags": "ops,internal"},
        )
        assert response.status_code == 201
        call_kwargs = mock_importer.import_file.call_args
        assert call_kwargs.kwargs["tags"] == ["ops", "internal"]


# ---------------------------------------------------------------------------
# Import OpenAPI Spec
# ---------------------------------------------------------------------------


class TestImportOpenAPI:
    async def test_import_openapi_spec(self, admin_client, mock_indexer):
        spec = {
            "openapi": "3.0.0",
            "info": {"title": "Pet Store", "version": "1.0.0"},
            "paths": {
                "/pets": {
                    "get": {
                        "summary": "List pets",
                        "tags": ["Pets"],
                        "responses": {"200": {"description": "OK"}},
                    }
                }
            },
        }
        import json

        response = await admin_client.post(
            "/api/knowledge/documents/import-openapi",
            json={"spec_content": json.dumps(spec), "spec_format": "json"},
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["documents"]) >= 1  # At least the overview document
        # Each document should not contain content (stripped)
        for doc in data["documents"]:
            assert "content" not in doc


# ---------------------------------------------------------------------------
# Graph: List/Search Entities
# ---------------------------------------------------------------------------


class TestListEntities:
    async def test_list_entities_empty(self, admin_client, mock_graph):
        mock_graph.list_entities.return_value = []
        response = await admin_client.get("/api/knowledge/graph/entities")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_entities_with_results(self, admin_client, mock_graph):
        mock_graph.list_entities.return_value = [_sample_entity()]
        response = await admin_client.get("/api/knowledge/graph/entities")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "ent-1"
        assert data[0]["name"] == "Auth Service"
        assert data[0]["entity_type"] == "service"

    async def test_list_entities_with_query(self, admin_client, mock_graph):
        mock_graph.list_entities.return_value = [_sample_entity()]
        response = await admin_client.get(
            "/api/knowledge/graph/entities", params={"query": "Auth"}
        )
        assert response.status_code == 200
        mock_graph.list_entities.assert_awaited_once_with(
            query="Auth", entity_type=None, limit=50, offset=0
        )

    async def test_list_entities_with_type_filter(self, admin_client, mock_graph):
        mock_graph.list_entities.return_value = [_sample_entity()]
        response = await admin_client.get(
            "/api/knowledge/graph/entities", params={"type": "service"}
        )
        assert response.status_code == 200
        mock_graph.list_entities.assert_awaited_once_with(
            query=None, entity_type="service", limit=50, offset=0
        )


# ---------------------------------------------------------------------------
# Graph: Entity Neighborhood
# ---------------------------------------------------------------------------


class TestEntityNeighborhood:
    async def test_get_neighborhood_success(self, admin_client, mock_graph):
        entity = _sample_entity()
        neighbor = Entity(
            id="ent-2",
            entity_type="database",
            name="User DB",
        )
        relation = Relation(
            source_id="ent-1",
            target_id="ent-2",
            relation_type="depends_on",
        )
        mock_graph.get_entity_neighborhood.return_value = EntityGraph(
            entities=[entity, neighbor],
            relations=[relation],
        )
        response = await admin_client.get(
            "/api/knowledge/graph/entities/ent-1/neighborhood"
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["entities"]) == 2
        assert len(data["relations"]) == 1
        assert data["relations"][0]["relation_type"] == "depends_on"

    async def test_get_neighborhood_not_found(self, admin_client, mock_graph):
        mock_graph.get_entity_neighborhood.return_value = EntityGraph()
        response = await admin_client.get(
            "/api/knowledge/graph/entities/no-such/neighborhood"
        )
        assert response.status_code == 404

    async def test_get_neighborhood_with_depth(self, admin_client, mock_graph):
        entity = _sample_entity()
        mock_graph.get_entity_neighborhood.return_value = EntityGraph(
            entities=[entity], relations=[]
        )
        response = await admin_client.get(
            "/api/knowledge/graph/entities/ent-1/neighborhood", params={"depth": 2}
        )
        assert response.status_code == 200
        mock_graph.get_entity_neighborhood.assert_awaited_once_with(
            "ent-1", depth=2
        )


# ---------------------------------------------------------------------------
# Graph: Create Entity
# ---------------------------------------------------------------------------


class TestCreateEntity:
    async def test_create_entity_success(self, admin_client, mock_graph):
        response = await admin_client.post(
            "/api/knowledge/graph/entities",
            json={
                "id": "new-ent",
                "entity_type": "service",
                "name": "Payment Service",
                "properties": {"region": "us-east"},
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "new-ent"
        assert data["name"] == "Payment Service"
        mock_graph.upsert_entity.assert_awaited_once()


# ---------------------------------------------------------------------------
# Graph: Delete Entity
# ---------------------------------------------------------------------------


class TestDeleteEntity:
    async def test_delete_entity_success(self, admin_client, mock_graph):
        mock_graph.delete_entity.return_value = True
        response = await admin_client.delete("/api/knowledge/graph/entities/ent-1")
        assert response.status_code == 204
        mock_graph.delete_entity.assert_awaited_once_with("ent-1")

    async def test_delete_entity_not_found(self, admin_client, mock_graph):
        mock_graph.delete_entity.return_value = False
        response = await admin_client.delete("/api/knowledge/graph/entities/no-such")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Graph: Statistics
# ---------------------------------------------------------------------------


class TestGraphStats:
    async def test_graph_stats(self, admin_client, mock_graph):
        response = await admin_client.get("/api/knowledge/graph/stats")
        assert response.status_code == 200
        data = response.json()
        assert data["entity_count"] == 10
        assert data["relation_count"] == 25
        assert data["entity_types"]["service"] == 5
        assert data["relation_types"]["depends_on"] == 15


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

    async def test_non_admin_cannot_import_url(self, non_admin_client):
        response = await non_admin_client.post(
            "/api/knowledge/documents/import-url",
            json={"url": "https://example.com"},
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_create_entity(self, non_admin_client):
        response = await non_admin_client.post(
            "/api/knowledge/graph/entities",
            json={"id": "e1", "entity_type": "svc", "name": "Test"},
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_delete_entity(self, non_admin_client):
        response = await non_admin_client.delete(
            "/api/knowledge/graph/entities/ent-1"
        )
        assert response.status_code == 403

    async def test_non_admin_cannot_read_graph_entities(self, non_admin_client):
        response = await non_admin_client.get("/api/knowledge/graph/entities")
        assert response.status_code == 403

    async def test_non_admin_cannot_read_graph_stats(self, non_admin_client):
        response = await non_admin_client.get("/api/knowledge/graph/stats")
        assert response.status_code == 403
