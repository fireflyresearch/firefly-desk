# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for SkillRepository -- CRUD operations with in-memory SQLite."""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.models.base import Base
from flydesk.skills.models import Skill
from flydesk.skills.repository import SkillRepository


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
    return SkillRepository(session_factory)


class TestSkillRepository:
    async def test_create_skill(self, repo):
        """Creating a skill persists and returns it with timestamps."""
        skill = Skill(
            id="skill-001",
            name="summarize-ticket",
            description="Summarizes a support ticket",
            content="You are a summarization assistant...",
            tags=["support", "triage"],
            active=True,
        )
        created = await repo.create_skill(skill)
        assert created.id == "skill-001"
        assert created.name == "summarize-ticket"
        assert created.description == "Summarizes a support ticket"
        assert created.content == "You are a summarization assistant..."
        assert created.tags == ["support", "triage"]
        assert created.active is True
        assert created.created_at is not None

    async def test_get_skill_by_id(self, repo):
        """get_skill returns a skill by its ID."""
        skill = Skill(id="skill-002", name="classify")
        await repo.create_skill(skill)
        result = await repo.get_skill("skill-002")
        assert result is not None
        assert result.name == "classify"

    async def test_get_skill_not_found(self, repo):
        """get_skill returns None for unknown ID."""
        result = await repo.get_skill("nonexistent")
        assert result is None

    async def test_list_skills_returns_all(self, repo):
        """list_skills returns all skills ordered by name."""
        await repo.create_skill(Skill(id="s-b", name="bravo"))
        await repo.create_skill(Skill(id="s-a", name="alpha"))
        await repo.create_skill(Skill(id="s-c", name="charlie"))
        skills = await repo.list_skills()
        assert len(skills) == 3
        assert [s.name for s in skills] == ["alpha", "bravo", "charlie"]

    async def test_list_skills_active_only(self, repo):
        """list_skills with active_only=True filters inactive skills."""
        await repo.create_skill(Skill(id="s-1", name="active-one", active=True))
        await repo.create_skill(Skill(id="s-2", name="inactive-one", active=False))
        skills = await repo.list_skills(active_only=True)
        assert len(skills) == 1
        assert skills[0].name == "active-one"

    async def test_list_skills_tag_filter(self, repo):
        """list_skills with tag_filter returns only skills matching tags."""
        await repo.create_skill(
            Skill(id="s-1", name="tagged", tags=["support", "triage"])
        )
        await repo.create_skill(
            Skill(id="s-2", name="untagged", tags=["billing"])
        )
        skills = await repo.list_skills(tag_filter=["support"])
        assert len(skills) == 1
        assert skills[0].name == "tagged"

    async def test_update_skill(self, repo):
        """update_skill modifies the specified fields."""
        await repo.create_skill(
            Skill(id="s-u", name="original", description="old")
        )
        updated = await repo.update_skill(
            "s-u", description="new description", active=False
        )
        assert updated is not None
        assert updated.description == "new description"
        assert updated.active is False

    async def test_update_skill_tags(self, repo):
        """update_skill can update tags."""
        await repo.create_skill(
            Skill(id="s-t", name="taggable", tags=["old"])
        )
        updated = await repo.update_skill("s-t", tags=["new", "tags"])
        assert updated is not None
        assert updated.tags == ["new", "tags"]

    async def test_update_skill_not_found(self, repo):
        """update_skill returns None for unknown ID."""
        result = await repo.update_skill("nonexistent", name="foo")
        assert result is None

    async def test_update_skill_invalid_field(self, repo):
        """update_skill raises ValueError for non-updatable fields."""
        await repo.create_skill(Skill(id="s-x", name="test"))
        with pytest.raises(ValueError, match="not updatable"):
            await repo.update_skill("s-x", id="new-id")

    async def test_delete_skill(self, repo):
        """Deleting a skill removes it."""
        await repo.create_skill(Skill(id="s-d", name="deletable"))
        deleted = await repo.delete_skill("s-d")
        assert deleted is True
        assert await repo.get_skill("s-d") is None

    async def test_delete_skill_not_found(self, repo):
        """Deleting a nonexistent skill returns False."""
        deleted = await repo.delete_skill("nonexistent")
        assert deleted is False
