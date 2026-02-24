# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Knowledge Admin REST API -- manage knowledge base documents and graph."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request, Response, UploadFile
from pydantic import BaseModel, Field

from flydesk.knowledge.graph import KnowledgeGraph
from flydesk.knowledge.importer import KnowledgeImporter
from flydesk.knowledge.indexer import KnowledgeIndexer
from flydesk.knowledge.models import DocumentType, KnowledgeDocument
from flydesk.knowledge.openapi_parser import OpenAPIParser
from flydesk.knowledge.queue import IndexingQueueProducer, IndexingTask
from flydesk.rbac.guards import KnowledgeDelete, KnowledgeRead, KnowledgeWrite
from flydesk.triggers.auto_trigger import AutoTriggerService

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

    async def update_document(
        self,
        document_id: str,
        *,
        title: str | None = None,
        document_type: DocumentType | None = None,
        tags: list[str] | None = None,
        content: str | None = None,
        status: str | None = None,
    ) -> KnowledgeDocument | None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class IndexResult(BaseModel):
    """Response after successfully indexing a document."""

    document_id: str
    chunks_created: int


class IndexingEnqueued(BaseModel):
    """Response returned when a document has been enqueued for background indexing."""

    document_id: str
    status: str = "indexing"


class DocumentMetadataUpdate(BaseModel):
    """Request body for updating document metadata."""

    title: str | None = None
    document_type: DocumentType | None = None
    tags: list[str] | None = None
    content: str | None = None
    status: str | None = None


class ImportURLRequest(BaseModel):
    """Request body for importing a document from a URL."""

    url: str
    title: str | None = None
    document_type: DocumentType | None = None
    tags: list[str] | None = None


class ImportOpenAPIRequest(BaseModel):
    """Request body for importing an OpenAPI spec."""

    spec_content: str
    spec_format: str = "json"
    tags: list[str] | None = None


class ImportResult(BaseModel):
    """Response after importing one or more documents."""

    documents: list[dict[str, Any]]


class BulkDocumentRequest(BaseModel):
    """Request body for bulk document operations."""

    document_ids: list[str]


class EntityCreate(BaseModel):
    """Request body for creating a graph entity."""

    id: str
    entity_type: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    source_system: str | None = None
    confidence: float = 1.0


class EntityResponse(BaseModel):
    """API response for a graph entity."""

    id: str
    entity_type: str
    name: str
    properties: dict[str, Any] = Field(default_factory=dict)
    source_system: str | None = None
    confidence: float = 1.0
    mention_count: int = 1


class RelationResponse(BaseModel):
    """API response for a graph relation."""

    source_id: str
    target_id: str
    relation_type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 1.0


class NeighborhoodResponse(BaseModel):
    """API response for an entity neighborhood."""

    entities: list[EntityResponse]
    relations: list[RelationResponse]


class GraphStatsResponse(BaseModel):
    """API response for graph statistics."""

    entity_count: int
    relation_count: int
    entity_types: dict[str, int]
    relation_types: dict[str, int]


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


def get_knowledge_importer() -> KnowledgeImporter:
    """Provide a KnowledgeImporter instance.

    In production this is wired via the lifespan with the real indexer and HTTP client.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_knowledge_importer must be overridden via app.dependency_overrides"
    )


def get_indexing_producer() -> IndexingQueueProducer:
    """Provide the background indexing queue producer.

    In production this is wired via the lifespan.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_indexing_producer must be overridden via app.dependency_overrides"
    )


def get_knowledge_graph() -> KnowledgeGraph:
    """Provide a KnowledgeGraph instance.

    In production this is wired via the lifespan with the real session factory.
    In tests the dependency is overridden with a mock.
    """
    raise NotImplementedError(
        "get_knowledge_graph must be overridden via app.dependency_overrides"
    )


def get_auto_trigger() -> AutoTriggerService | None:
    """Provide the AutoTriggerService instance (or None if not wired).

    In production this is wired via the lifespan.
    In tests the dependency is overridden with a mock.
    """
    return None


Indexer = Annotated[KnowledgeIndexer, Depends(get_knowledge_indexer)]
DocStore = Annotated[KnowledgeDocumentStore, Depends(get_knowledge_doc_store)]
Importer = Annotated[KnowledgeImporter, Depends(get_knowledge_importer)]
Graph = Annotated[KnowledgeGraph, Depends(get_knowledge_graph)]
Producer = Annotated[IndexingQueueProducer, Depends(get_indexing_producer)]
Trigger = Annotated[AutoTriggerService | None, Depends(get_auto_trigger)]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _strip_content(doc: KnowledgeDocument) -> dict[str, Any]:
    """Return document metadata without the full content field."""
    data = doc.model_dump(mode="json")
    data.pop("content", None)
    return data


# ---------------------------------------------------------------------------
# Document Routes
# ---------------------------------------------------------------------------


@router.get("/documents", dependencies=[KnowledgeRead])
async def list_documents(store: DocStore) -> list[dict[str, Any]]:
    """List all knowledge documents (metadata only, content excluded)."""
    documents = await store.list_documents()
    return [_strip_content(d) for d in documents]


@router.get("/documents/{document_id}", dependencies=[KnowledgeRead])
async def get_document(document_id: str, store: DocStore) -> dict[str, Any]:
    """Get a full document with metadata and content."""
    doc = await store.get_document(document_id)
    if doc is None:
        raise HTTPException(
            status_code=404, detail=f"Document {document_id} not found"
        )
    return doc.model_dump(mode="json")


@router.post("/documents", status_code=202, dependencies=[KnowledgeWrite])
async def create_document(
    document: KnowledgeDocument, producer: Producer, trigger: Trigger
) -> IndexingEnqueued:
    """Enqueue a knowledge document for background indexing.

    Returns immediately with ``status: "indexing"`` while the document is
    chunked and embedded asynchronously by the indexing queue consumer.
    If auto-analysis is enabled, schedules KG recomputation.
    """
    task = IndexingTask(
        document_id=document.id,
        title=document.title,
        content=document.content,
        document_type=str(document.document_type),
        source=document.source or "",
        tags=document.tags,
        metadata=document.metadata,
    )
    await producer.enqueue(task)

    if trigger is not None:
        await trigger.on_document_indexed(document.id)

    return IndexingEnqueued(document_id=document.id)


@router.put("/documents/{document_id}", dependencies=[KnowledgeWrite])
async def update_document_metadata(
    document_id: str, body: DocumentMetadataUpdate, store: DocStore
) -> dict[str, Any]:
    """Update document metadata and optionally content."""
    updated = await store.update_document(
        document_id,
        title=body.title,
        document_type=body.document_type,
        tags=body.tags,
        content=body.content,
        status=body.status,
    )
    if updated is None:
        raise HTTPException(
            status_code=404, detail=f"Document {document_id} not found"
        )
    return updated.model_dump(mode="json")


@router.delete(
    "/documents/{document_id}", status_code=204, dependencies=[KnowledgeDelete]
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


# ---------------------------------------------------------------------------
# Bulk Operations
# ---------------------------------------------------------------------------


@router.post("/documents/bulk-delete", status_code=200, dependencies=[KnowledgeDelete])
async def bulk_delete_documents(
    body: BulkDocumentRequest, indexer: Indexer, store: DocStore
) -> dict[str, Any]:
    """Delete multiple knowledge documents and their chunks."""
    deleted = 0
    errors: list[dict[str, str]] = []
    for doc_id in body.document_ids:
        try:
            existing = await store.get_document(doc_id)
            if existing is None:
                errors.append({"document_id": doc_id, "error": "Not found"})
                continue
            await indexer.delete_document(doc_id)
            deleted += 1
        except Exception as exc:
            errors.append({"document_id": doc_id, "error": str(exc)})
    return {"deleted": deleted, "errors": errors}


@router.post("/documents/bulk-archive", status_code=200, dependencies=[KnowledgeWrite])
async def bulk_archive_documents(
    body: BulkDocumentRequest, store: DocStore
) -> dict[str, Any]:
    """Archive multiple knowledge documents."""
    archived = 0
    errors: list[dict[str, str]] = []
    for doc_id in body.document_ids:
        try:
            result = await store.update_document(doc_id, status="archived")
            if result is None:
                errors.append({"document_id": doc_id, "error": "Not found"})
                continue
            archived += 1
        except Exception as exc:
            errors.append({"document_id": doc_id, "error": str(exc)})
    return {"archived": archived, "errors": errors}


@router.post("/documents/bulk-reindex", status_code=202, dependencies=[KnowledgeWrite])
async def bulk_reindex_documents(
    body: BulkDocumentRequest, store: DocStore, producer: Producer
) -> dict[str, Any]:
    """Re-index multiple knowledge documents."""
    queued = 0
    errors: list[dict[str, str]] = []
    for doc_id in body.document_ids:
        try:
            doc = await store.get_document(doc_id)
            if doc is None:
                errors.append({"document_id": doc_id, "error": "Not found"})
                continue
            task = IndexingTask(
                document_id=doc.id,
                title=doc.title,
                content=doc.content,
                document_type=str(doc.document_type),
                source=doc.source or "",
                tags=doc.tags,
                metadata=doc.metadata,
            )
            await producer.enqueue(task)
            queued += 1
        except Exception as exc:
            errors.append({"document_id": doc_id, "error": str(exc)})
    return {"queued": queued, "errors": errors}


# ---------------------------------------------------------------------------
# Import Routes
# ---------------------------------------------------------------------------


@router.post("/documents/import-url", status_code=201, dependencies=[KnowledgeWrite])
async def import_from_url(body: ImportURLRequest, importer: Importer) -> dict[str, Any]:
    """Import a knowledge document from a URL."""
    doc = await importer.import_url(
        url=body.url,
        title=body.title,
        doc_type=body.document_type,
        tags=body.tags,
    )
    return _strip_content(doc)


@router.post("/documents/import-file", status_code=201, dependencies=[KnowledgeWrite])
async def import_from_file(
    file: UploadFile,
    importer: Importer,
    title: str | None = Form(default=None),
    document_type: DocumentType | None = Form(default=None),
    tags: str | None = Form(default=None),
) -> dict[str, Any]:
    """Import a knowledge document from an uploaded file.

    Tags should be passed as a comma-separated string query parameter.
    """
    content = await file.read()
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    doc = await importer.import_file(
        filename=file.filename or "uploaded_file",
        content=content,
        content_type=file.content_type or "text/plain",
        title=title,
        doc_type=document_type,
        tags=tag_list,
    )
    return _strip_content(doc)


@router.post(
    "/documents/import-openapi", status_code=201, dependencies=[KnowledgeWrite]
)
async def import_openapi_spec(
    body: ImportOpenAPIRequest, indexer: Indexer
) -> ImportResult:
    """Parse an OpenAPI spec and import the resulting documents."""
    parser = OpenAPIParser()
    documents = parser.parse(body.spec_content, body.spec_format)

    # Apply user-supplied tags to all parsed documents
    if body.tags:
        for doc in documents:
            doc.tags = list(set(doc.tags + body.tags))

    # Index all parsed documents
    for doc in documents:
        await indexer.index_document(doc)

    return ImportResult(documents=[_strip_content(d) for d in documents])


# ---------------------------------------------------------------------------
# Graph Routes
# ---------------------------------------------------------------------------


@router.get("/graph/entities", dependencies=[KnowledgeRead])
async def list_entities(
    graph: Graph,
    query: str | None = Query(default=None, description="Search entities by name"),
    entity_type: str | None = Query(
        default=None, alias="type", description="Filter by entity type"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[EntityResponse]:
    """List or search knowledge graph entities."""
    entities = await graph.list_entities(
        query=query, entity_type=entity_type, limit=limit, offset=offset
    )
    return [EntityResponse(**asdict(e)) for e in entities]


@router.get(
    "/graph/entities/{entity_id}/neighborhood", dependencies=[KnowledgeRead]
)
async def get_entity_neighborhood(
    entity_id: str,
    graph: Graph,
    depth: int = Query(default=1, ge=1, le=3),
) -> NeighborhoodResponse:
    """Get an entity and its neighbors up to the specified depth."""
    neighborhood = await graph.get_entity_neighborhood(entity_id, depth=depth)
    if not neighborhood.entities:
        raise HTTPException(
            status_code=404, detail=f"Entity {entity_id} not found"
        )
    return NeighborhoodResponse(
        entities=[EntityResponse(**asdict(e)) for e in neighborhood.entities],
        relations=[RelationResponse(**asdict(r)) for r in neighborhood.relations],
    )


@router.post("/graph/entities", status_code=201, dependencies=[KnowledgeWrite])
async def create_entity(body: EntityCreate, graph: Graph) -> EntityResponse:
    """Manually create a knowledge graph entity."""
    from flydesk.knowledge.graph import Entity

    entity = Entity(
        id=body.id,
        entity_type=body.entity_type,
        name=body.name,
        properties=body.properties,
        source_system=body.source_system,
        confidence=body.confidence,
    )
    await graph.upsert_entity(entity)
    return EntityResponse(**asdict(entity))


class EntityUpdate(BaseModel):
    """Request body for updating a graph entity."""

    entity_type: str | None = None
    name: str | None = None
    properties: dict[str, Any] | None = None
    source_system: str | None = None
    confidence: float | None = None


@router.patch("/graph/entities/{entity_id}", dependencies=[KnowledgeWrite])
async def update_entity(entity_id: str, body: EntityUpdate, graph: Graph) -> EntityResponse:
    """Update a knowledge graph entity."""
    existing = await graph.get_entity(entity_id)
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"Entity {entity_id} not found"
        )
    if body.entity_type is not None:
        existing.entity_type = body.entity_type
    if body.name is not None:
        existing.name = body.name
    if body.properties is not None:
        existing.properties = body.properties
    if body.source_system is not None:
        existing.source_system = body.source_system
    if body.confidence is not None:
        existing.confidence = body.confidence
    await graph.upsert_entity(existing)
    return EntityResponse(**asdict(existing))


@router.delete(
    "/graph/entities/{entity_id}", status_code=204, dependencies=[KnowledgeDelete]
)
async def delete_entity(entity_id: str, graph: Graph) -> Response:
    """Delete a knowledge graph entity and its relations."""
    deleted = await graph.delete_entity(entity_id)
    if not deleted:
        raise HTTPException(
            status_code=404, detail=f"Entity {entity_id} not found"
        )
    return Response(status_code=204)


@router.get("/graph/stats", dependencies=[KnowledgeRead])
async def get_graph_stats(graph: Graph) -> GraphStatsResponse:
    """Get knowledge graph statistics."""
    stats = await graph.get_stats()
    return GraphStatsResponse(**stats)


@router.post("/graph/recompute", dependencies=[KnowledgeWrite])
async def trigger_kg_recompute(request: Request) -> dict:
    """Trigger a background knowledge graph recompute job.

    Extracts entities and relations from all indexed documents using
    the configured LLM.  Returns a job ID for progress tracking.
    """
    job_runner = getattr(request.app.state, "job_runner", None)
    if job_runner is None:
        raise HTTPException(status_code=503, detail="Job runner not available")
    kg_extractor = getattr(request.app.state, "kg_extractor", None)
    if kg_extractor is None:
        raise HTTPException(
            status_code=503,
            detail="KG extractor not available — ensure an LLM provider is configured",
        )
    try:
        job = await job_runner.submit("kg_recompute", {})
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"job_id": job.id, "status": job.status.value}
