# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for CatalogRepository system document link/unlink methods."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.catalog.models import SystemDocument
from flydesk.catalog.repository import CatalogRepository
from flydesk.models.base import Base


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def repo(session_factory):
    return CatalogRepository(session_factory)


class TestSystemDocuments:
    async def test_link_document(self, repo):
        await repo.link_document("sys-1", "doc-1", role="api_spec")
        docs = await repo.list_system_documents("sys-1")
        assert len(docs) == 1
        assert docs[0].system_id == "sys-1"
        assert docs[0].document_id == "doc-1"
        assert docs[0].role == "api_spec"

    async def test_unlink_document(self, repo):
        await repo.link_document("sys-1", "doc-1")
        await repo.unlink_document("sys-1", "doc-1")
        docs = await repo.list_system_documents("sys-1")
        assert len(docs) == 0

    async def test_list_system_documents(self, repo):
        await repo.link_document("sys-1", "doc-1", role="reference")
        await repo.link_document("sys-1", "doc-2", role="api_spec")
        await repo.link_document("sys-2", "doc-3", role="changelog")

        docs = await repo.list_system_documents("sys-1")
        assert len(docs) == 2
        doc_ids = {d.document_id for d in docs}
        assert doc_ids == {"doc-1", "doc-2"}

    async def test_list_systems_for_document(self, repo):
        await repo.link_document("sys-1", "doc-shared")
        await repo.link_document("sys-2", "doc-shared")
        await repo.link_document("sys-3", "doc-other")

        system_ids = await repo.list_systems_for_document("doc-shared")
        assert set(system_ids) == {"sys-1", "sys-2"}
