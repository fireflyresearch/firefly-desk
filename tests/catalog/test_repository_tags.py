# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for CatalogRepository tag CRUD and association methods."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.catalog.enums import AuthType, SystemStatus
from flydesk.catalog.models import AuthConfig, ExternalSystem, SystemTag
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


def _make_system(system_id: str, name: str) -> ExternalSystem:
    return ExternalSystem(
        id=system_id,
        name=name,
        description=f"Description for {name}",
        base_url="https://api.test.com",
        auth_config=AuthConfig(auth_type=AuthType.API_KEY, credential_id="cred-1"),
        status=SystemStatus.ACTIVE,
    )


class TestTagCRUD:
    async def test_create_and_list_tags(self, repo):
        tag1 = SystemTag(id="t1", name="backend", color="#FF0000", description="Backend systems")
        tag2 = SystemTag(id="t2", name="analytics", color="#00FF00", description="Analytics systems")
        await repo.create_tag(tag1)
        await repo.create_tag(tag2)

        tags = await repo.list_tags()
        assert len(tags) == 2
        # Ordered by name
        assert tags[0].name == "analytics"
        assert tags[1].name == "backend"
        assert tags[1].color == "#FF0000"
        assert tags[1].description == "Backend systems"

    async def test_delete_tag(self, repo):
        tag = SystemTag(id="t1", name="backend", color="#FF0000")
        await repo.create_tag(tag)
        assert len(await repo.list_tags()) == 1

        await repo.delete_tag("t1")
        assert len(await repo.list_tags()) == 0

    async def test_update_tag(self, repo):
        tag = SystemTag(id="t1", name="backend", color="#FF0000", description="Old desc")
        await repo.create_tag(tag)

        updated = SystemTag(id="t1", name="infra", color="#0000FF", description="New desc")
        await repo.update_tag(updated)

        tags = await repo.list_tags()
        assert len(tags) == 1
        assert tags[0].name == "infra"
        assert tags[0].color == "#0000FF"
        assert tags[0].description == "New desc"


class TestTagAssociations:
    async def test_assign_and_list_system_tags(self, repo):
        system = _make_system("sys-1", "CRM")
        await repo.create_system(system)
        tag1 = SystemTag(id="t1", name="backend", color="#FF0000")
        tag2 = SystemTag(id="t2", name="analytics", color="#00FF00")
        await repo.create_tag(tag1)
        await repo.create_tag(tag2)

        await repo.assign_tag("sys-1", "t1")
        await repo.assign_tag("sys-1", "t2")

        tags = await repo.list_system_tags("sys-1")
        assert len(tags) == 2
        assert tags[0].name == "analytics"
        assert tags[1].name == "backend"

    async def test_remove_tag_from_system(self, repo):
        system = _make_system("sys-1", "CRM")
        await repo.create_system(system)
        tag = SystemTag(id="t1", name="backend")
        await repo.create_tag(tag)
        await repo.assign_tag("sys-1", "t1")

        await repo.remove_tag("sys-1", "t1")
        tags = await repo.list_system_tags("sys-1")
        assert len(tags) == 0

    async def test_list_systems_by_tag(self, repo):
        sys1 = _make_system("sys-1", "CRM")
        sys2 = _make_system("sys-2", "ERP")
        await repo.create_system(sys1)
        await repo.create_system(sys2)
        tag = SystemTag(id="t1", name="backend")
        await repo.create_tag(tag)
        await repo.assign_tag("sys-1", "t1")

        systems, total = await repo.list_systems(tag_ids=["t1"])
        assert total == 1
        assert systems[0].id == "sys-1"

    async def test_list_systems_by_tag_no_match(self, repo):
        system = _make_system("sys-1", "CRM")
        await repo.create_system(system)
        tag = SystemTag(id="t1", name="backend")
        await repo.create_tag(tag)
        # Tag not assigned to any system

        systems, total = await repo.list_systems(tag_ids=["t1"])
        assert total == 0
        assert len(systems) == 0
