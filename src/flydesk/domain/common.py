"""Shared enums and constants used across the domain layer."""
from __future__ import annotations

from enum import StrEnum


class DocumentStatus(StrEnum):
    """Lifecycle status of a knowledge document."""

    DRAFT = "draft"
    INDEXING = "indexing"
    PUBLISHED = "published"
    ERROR = "error"
    ARCHIVED = "archived"


class DocumentType(StrEnum):
    """Classification of knowledge documents."""

    MANUAL = "manual"
    TUTORIAL = "tutorial"
    API_SPEC = "api_spec"
    FAQ = "faq"
    POLICY = "policy"
    REFERENCE = "reference"
    CHANGELOG = "changelog"
    README = "readme"
    OTHER = "other"


class EmailProviderType(StrEnum):
    """Supported email provider backends."""

    RESEND = "resend"
    SES = "ses"
    SENDGRID = "sendgrid"


class VectorStoreType(StrEnum):
    """Supported vector store backends."""

    PGVECTOR = "pgvector"
    CHROMADB = "chromadb"
    PINECONE = "pinecone"
    SQLITE = "sqlite"
    MEMORY = "memory"
