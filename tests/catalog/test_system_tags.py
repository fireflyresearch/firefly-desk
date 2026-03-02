# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for SystemTag domain model and ORM persistence."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.catalog.models import SystemTag
from flydesk.models.base import Base
from flydesk.models.catalog import SystemTagAssociationRow, SystemTagRow


class TestSystemTagModel:
    def test_create_tag(self):
        tag = SystemTag(id="tag-1", name="CRM")
        assert tag.name == "CRM"
        assert tag.color is None
        assert tag.description is None

    def test_create_tag_with_color(self):
        tag = SystemTag(
            id="tag-1",
            name="ERP",
            color="#FF5733",
            description="Enterprise Resource Planning",
        )
        assert tag.color == "#FF5733"
        assert tag.description == "Enterprise Resource Planning"


class TestSystemTagORM:
    @pytest.fixture
    async def session_factory(self):
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)
        yield factory
        await engine.dispose()

    async def test_create_tag_row(self, session_factory):
        async with session_factory() as session:
            row = SystemTagRow(id="tag-1", name="CRM", color="#3B82F6")
            session.add(row)
            await session.commit()

        async with session_factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(SystemTagRow).where(SystemTagRow.id == "tag-1")
            )
            tag = result.scalar_one()
            assert tag.name == "CRM"
            assert tag.color == "#3B82F6"

    async def test_create_association(self, session_factory):
        async with session_factory() as session:
            tag = SystemTagRow(id="tag-1", name="CRM")
            session.add(tag)
            assoc = SystemTagAssociationRow(system_id="sys-1", tag_id="tag-1")
            session.add(assoc)
            await session.commit()

        async with session_factory() as session:
            from sqlalchemy import select

            result = await session.execute(
                select(SystemTagAssociationRow).where(
                    SystemTagAssociationRow.system_id == "sys-1"
                )
            )
            rows = result.scalars().all()
            assert len(rows) == 1
            assert rows[0].tag_id == "tag-1"
