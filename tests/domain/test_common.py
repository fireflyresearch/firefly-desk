# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for domain common enums."""

from __future__ import annotations

from flydesk.domain.common import (
    DocumentStatus,
    DocumentType,
    EmailProviderType,
    VectorStoreType,
)


# ---------------------------------------------------------------------------
# DocumentType enum
# ---------------------------------------------------------------------------


class TestDocumentType:
    def test_all_values_present(self):
        """DocumentType enum contains all expected members."""
        expected = {
            "manual",
            "tutorial",
            "api_spec",
            "faq",
            "policy",
            "reference",
            "changelog",
            "readme",
            "other",
        }
        assert {dt.value for dt in DocumentType} == expected

    def test_member_count(self):
        """There are exactly 9 document types."""
        assert len(DocumentType) == 9

    def test_strenum_behaviour(self):
        """DocumentType members are usable as plain strings."""
        assert DocumentType.MANUAL == "manual"
        assert DocumentType.FAQ == "faq"
        assert str(DocumentType.API_SPEC) == "api_spec"


# ---------------------------------------------------------------------------
# DocumentStatus enum
# ---------------------------------------------------------------------------


class TestDocumentStatus:
    def test_all_values_present(self):
        """DocumentStatus enum contains all expected members."""
        expected = {"draft", "indexing", "published", "error", "archived"}
        assert {ds.value for ds in DocumentStatus} == expected

    def test_member_count(self):
        """There are exactly 5 document statuses."""
        assert len(DocumentStatus) == 5

    def test_strenum_behaviour(self):
        """DocumentStatus members are usable as plain strings."""
        assert DocumentStatus.DRAFT == "draft"
        assert DocumentStatus.PUBLISHED == "published"
        assert str(DocumentStatus.ERROR) == "error"


# ---------------------------------------------------------------------------
# EmailProviderType enum
# ---------------------------------------------------------------------------


class TestEmailProviderType:
    def test_all_values_present(self):
        """EmailProviderType enum contains all expected members."""
        expected = {"resend", "ses", "sendgrid"}
        assert {ep.value for ep in EmailProviderType} == expected

    def test_member_count(self):
        """There are exactly 3 email provider types."""
        assert len(EmailProviderType) == 3

    def test_strenum_behaviour(self):
        """EmailProviderType members are usable as plain strings."""
        assert EmailProviderType.RESEND == "resend"
        assert EmailProviderType.SES == "ses"
        assert str(EmailProviderType.SENDGRID) == "sendgrid"


# ---------------------------------------------------------------------------
# VectorStoreType enum
# ---------------------------------------------------------------------------


class TestVectorStoreType:
    def test_all_values_present(self):
        """VectorStoreType enum contains all expected members."""
        expected = {"pgvector", "chromadb", "pinecone", "sqlite", "memory"}
        assert {vs.value for vs in VectorStoreType} == expected

    def test_member_count(self):
        """There are exactly 5 vector store types."""
        assert len(VectorStoreType) == 5

    def test_strenum_behaviour(self):
        """VectorStoreType members are usable as plain strings."""
        assert VectorStoreType.PGVECTOR == "pgvector"
        assert VectorStoreType.MEMORY == "memory"
        assert str(VectorStoreType.CHROMADB) == "chromadb"
