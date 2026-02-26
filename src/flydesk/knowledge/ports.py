# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Port interfaces for the knowledge domain."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from flydesk.knowledge.models import DocumentType, KnowledgeDocument


@runtime_checkable
class KnowledgeDocumentStore(Protocol):
    """Port for knowledge document CRUD operations."""

    async def list_documents(
        self, *, workspace_id: str | None = None
    ) -> list[KnowledgeDocument]: ...

    async def get_document(
        self, document_id: str
    ) -> KnowledgeDocument | None: ...

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
    ) -> KnowledgeDocument | None: ...
