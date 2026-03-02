# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for SystemDocument join model."""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.catalog.models import SystemDocument
from flydesk.models.base import Base
from flydesk.models.catalog import SystemDocumentRow


class TestSystemDocumentModel:
    def test_create_with_defaults(self):
        sd = SystemDocument(system_id="sys-1", document_id="doc-1")
        assert sd.role == "reference"

    def test_create_with_role(self):
        sd = SystemDocument(system_id="sys-1", document_id="doc-1", role="api_spec")
        assert sd.role == "api_spec"


class TestSystemDocumentORM:
    @pytest.fixture
    async def session_factory(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        yield factory
        await engine.dispose()

    async def test_create_and_query(self, session_factory):
        async with session_factory() as session:
            row = SystemDocumentRow(
                system_id="sys-1", document_id="doc-1", role="api_spec"
            )
            session.add(row)
            await session.commit()

        async with session_factory() as session:
            result = await session.execute(
                select(SystemDocumentRow).where(
                    SystemDocumentRow.system_id == "sys-1"
                )
            )
            rows = result.scalars().all()
            assert len(rows) == 1
            assert rows[0].document_id == "doc-1"
            assert rows[0].role == "api_spec"

    async def test_multiple_docs_per_system(self, session_factory):
        async with session_factory() as session:
            session.add(
                SystemDocumentRow(
                    system_id="sys-1", document_id="doc-1", role="api_spec"
                )
            )
            session.add(
                SystemDocumentRow(
                    system_id="sys-1", document_id="doc-2", role="setup_guide"
                )
            )
            await session.commit()

        async with session_factory() as session:
            result = await session.execute(
                select(SystemDocumentRow).where(
                    SystemDocumentRow.system_id == "sys-1"
                )
            )
            assert len(result.scalars().all()) == 2
