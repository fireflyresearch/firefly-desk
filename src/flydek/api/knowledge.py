# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Knowledge Admin REST API -- manage knowledge base documents."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from flydek.knowledge.indexer import KnowledgeIndexer
from flydek.knowledge.models import KnowledgeDocument

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


# ---------------------------------------------------------------------------
# Knowledge Document Store interface
# ---------------------------------------------------------------------------


class KnowledgeDocumentStore:
    """Thin store for listing/fetching knowledge documents.

    The real implementation will query the database directly.
    Methods are async stubs -- overridden in production and mocked in tests.
    """

    async def list_documents(self) -> list[KnowledgeDocument]:
        raise NotImplementedError

    async def get_document(self, document_id: str) -> KnowledgeDocument | None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------


class IndexResult(BaseModel):
    """Response after successfully indexing a document."""

    document_id: str
    chunks_created: int


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


def get_knowledge_indexer() -> KnowledgeIndexer:
    """Provide a KnowledgeIndexer instance.

    In production this is wired to the real indexer with embeddings.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_knowledge_indexer must be overridden via app.dependency_overrides"
    )


def get_knowledge_doc_store() -> KnowledgeDocumentStore:
    """Provide a KnowledgeDocumentStore instance.

    In production this is wired to the real database.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_knowledge_doc_store must be overridden via app.dependency_overrides"
    )


async def _require_admin(request: Request) -> None:
    """Raise 403 unless the authenticated user has the 'admin' role."""
    user = getattr(request.state, "user_session", None)
    if user is None or "admin" not in user.roles:
        raise HTTPException(status_code=403, detail="Admin role required")


AdminGuard = Depends(_require_admin)
Indexer = Annotated[KnowledgeIndexer, Depends(get_knowledge_indexer)]
DocStore = Annotated[KnowledgeDocumentStore, Depends(get_knowledge_doc_store)]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _strip_content(doc: KnowledgeDocument) -> dict[str, Any]:
    """Return document metadata without the full content field."""
    data = doc.model_dump(mode="json")
    data.pop("content", None)
    return data


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/documents", dependencies=[AdminGuard])
async def list_documents(store: DocStore) -> list[dict[str, Any]]:
    """List all knowledge documents (metadata only, content excluded)."""
    documents = await store.list_documents()
    return [_strip_content(d) for d in documents]


@router.post("/documents", status_code=201, dependencies=[AdminGuard])
async def create_document(document: KnowledgeDocument, indexer: Indexer) -> IndexResult:
    """Upload and index a knowledge document."""
    chunks = await indexer.index_document(document)
    return IndexResult(document_id=document.id, chunks_created=len(chunks))


@router.delete(
    "/documents/{document_id}", status_code=204, dependencies=[AdminGuard]
)
async def delete_document(
    document_id: str, indexer: Indexer, store: DocStore
) -> Response:
    """Delete a knowledge document and all its chunks."""
    existing = await store.get_document(document_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"Document {document_id} not found"
        )
    await indexer.delete_document(document_id)
    return Response(status_code=204)
