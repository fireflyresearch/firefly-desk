# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Concrete KnowledgeDocumentStore backed by the CatalogRepository."""

from __future__ import annotations

from flydesk.catalog.repository import CatalogRepository
from flydesk.knowledge.models import DocumentType, KnowledgeDocument


class CatalogDocumentStore:
    """KnowledgeDocumentStore that delegates to CatalogRepository."""

    def __init__(self, catalog_repo: CatalogRepository) -> None:
        self._repo = catalog_repo

    async def list_documents(
        self, *, workspace_id: str | None = None
    ) -> list[KnowledgeDocument]:
        return await self._repo.list_knowledge_documents(workspace_id=workspace_id)

    async def get_document(self, document_id: str) -> KnowledgeDocument | None:
        return await self._repo.get_knowledge_document(document_id)

    async def update_document(
        self,
        document_id: str,
        *,
        title: str | None = None,
        document_type: DocumentType | None = None,
        tags: list[str] | None = None,
        content: str | None = None,
        status: str | None = None,
        workspace_ids: list[str] | None = None,
    ) -> KnowledgeDocument | None:
        return await self._repo.update_knowledge_document(
            document_id,
            title=title,
            document_type=document_type,
            tags=tags,
            content=content,
            status=status,
            workspace_ids=workspace_ids,
        )
