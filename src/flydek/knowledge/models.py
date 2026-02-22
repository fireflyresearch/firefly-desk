# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Domain models for the knowledge base."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DocumentType(StrEnum):
    """Classification of knowledge documents."""

    MANUAL = "manual"
    TUTORIAL = "tutorial"
    API_SPEC = "api_spec"
    FAQ = "faq"
    POLICY = "policy"
    REFERENCE = "reference"
    OTHER = "other"


class KnowledgeDocument(BaseModel):
    """A knowledge base document (operational procedure, policy, etc.)."""

    id: str
    title: str
    content: str
    document_type: DocumentType = DocumentType.OTHER
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    """A chunk of a knowledge document for embedding."""

    chunk_id: str
    document_id: str
    content: str
    chunk_index: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    """A result from knowledge base retrieval."""

    chunk: DocumentChunk
    score: float
    document_title: str
