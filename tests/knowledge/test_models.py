# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for knowledge domain models and ORM models."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.knowledge.models import DocumentType, KnowledgeDocument
from flydesk.models.base import Base
from flydesk.models.knowledge_base import KnowledgeDocumentRow


# ---------------------------------------------------------------------------
# DocumentType enum
# ---------------------------------------------------------------------------


class TestDocumentType:
    def test_all_values_present(self):
        """DocumentType enum contains all expected members."""
        expected = {"manual", "tutorial", "api_spec", "faq", "policy", "reference", "other"}
        assert {dt.value for dt in DocumentType} == expected

    def test_member_count(self):
        """There are exactly 7 document types."""
        assert len(DocumentType) == 7

    def test_strenum_behaviour(self):
        """DocumentType members are usable as plain strings."""
        assert DocumentType.MANUAL == "manual"
        assert DocumentType.FAQ == "faq"
        assert str(DocumentType.API_SPEC) == "api_spec"

    def test_value_round_trip(self):
        """Constructing from a string value yields the correct member."""
        assert DocumentType("policy") is DocumentType.POLICY
        assert DocumentType("other") is DocumentType.OTHER


# ---------------------------------------------------------------------------
# KnowledgeDocument domain model
# ---------------------------------------------------------------------------


class TestKnowledgeDocument:
    def test_default_document_type_is_other(self):
        """document_type defaults to OTHER when not specified."""
        doc = KnowledgeDocument(id="d1", title="Test", content="body")
        assert doc.document_type is DocumentType.OTHER

    def test_explicit_document_type(self):
        """document_type can be set explicitly."""
        doc = KnowledgeDocument(
            id="d2", title="API Guide", content="...", document_type=DocumentType.API_SPEC
        )
        assert doc.document_type is DocumentType.API_SPEC

    def test_document_type_from_string(self):
        """Pydantic coerces a raw string into the DocumentType enum."""
        doc = KnowledgeDocument(
            id="d3", title="FAQ", content="...", document_type="faq"
        )
        assert doc.document_type is DocumentType.FAQ

    def test_model_dump_includes_document_type(self):
        """Serialization includes document_type."""
        doc = KnowledgeDocument(
            id="d4", title="Manual", content="...", document_type=DocumentType.MANUAL
        )
        data = doc.model_dump(mode="json")
        assert data["document_type"] == "manual"

    def test_backward_compatible_construction(self):
        """Documents created without document_type still work (defaulting to OTHER)."""
        doc = KnowledgeDocument(
            id="d5",
            title="Legacy Doc",
            content="some text",
            source="import",
            tags=["legacy"],
            metadata={"version": "1.0"},
        )
        assert doc.document_type is DocumentType.OTHER
        assert doc.source == "import"
        assert doc.tags == ["legacy"]


# ---------------------------------------------------------------------------
# KnowledgeDocumentRow ORM model
# ---------------------------------------------------------------------------


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


class TestKnowledgeDocumentRow:
    def test_column_exists(self):
        """KnowledgeDocumentRow has a 'document_type' mapped attribute."""
        mapper = inspect(KnowledgeDocumentRow)
        column_names = {c.key for c in mapper.column_attrs}
        assert "document_type" in column_names

    async def test_default_value_on_insert(self, session_factory):
        """Inserting a row without explicit document_type uses the default 'other'."""
        async with session_factory() as session:
            row = KnowledgeDocumentRow(
                id="row-1",
                title="Test Row",
                content="content",
                tags=json.dumps([]),
                metadata_=json.dumps({}),
            )
            session.add(row)
            await session.commit()

        async with session_factory() as session:
            loaded = await session.get(KnowledgeDocumentRow, "row-1")
            assert loaded is not None
            assert loaded.document_type == "other"

    async def test_explicit_document_type(self, session_factory):
        """Inserting a row with an explicit document_type persists it."""
        async with session_factory() as session:
            row = KnowledgeDocumentRow(
                id="row-2",
                title="API Spec",
                content="openapi: 3.0",
                document_type="api_spec",
                tags=json.dumps([]),
                metadata_=json.dumps({}),
            )
            session.add(row)
            await session.commit()

        async with session_factory() as session:
            loaded = await session.get(KnowledgeDocumentRow, "row-2")
            assert loaded is not None
            assert loaded.document_type == "api_spec"

    async def test_round_trip_with_all_types(self, session_factory):
        """Each DocumentType value can be stored and retrieved."""
        async with session_factory() as session:
            for i, dt in enumerate(DocumentType):
                row = KnowledgeDocumentRow(
                    id=f"row-rt-{i}",
                    title=f"Doc {dt.value}",
                    content="...",
                    document_type=dt.value,
                    tags=json.dumps([]),
                    metadata_=json.dumps({}),
                )
                session.add(row)
            await session.commit()

        async with session_factory() as session:
            for i, dt in enumerate(DocumentType):
                loaded = await session.get(KnowledgeDocumentRow, f"row-rt-{i}")
                assert loaded is not None
                assert loaded.document_type == dt.value
