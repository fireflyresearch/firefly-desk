# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Persistence layer for skills."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.skill import SkillRow
from flydesk.skills.models import Skill

_UPDATABLE_FIELDS = frozenset({
    "name",
    "description",
    "content",
    "tags",
    "active",
})


def _to_json(value: Any) -> str | None:
    """Serialize a Python object to a JSON string for SQLite Text columns."""
    if value is None:
        return None
    return json.dumps(value, default=str)


def _from_json(value: Any) -> list:
    """Deserialize a value that may be a JSON string (SQLite) or already a list."""
    if isinstance(value, str):
        return json.loads(value)
    return value if value is not None else []


class SkillRepository:
    """CRUD operations for skills."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # -- Queries --

    async def list_skills(
        self,
        active_only: bool = False,
        tag_filter: list[str] | None = None,
    ) -> list[Skill]:
        """Return skills, optionally filtered by active status and tags."""
        async with self._session_factory() as session:
            stmt = select(SkillRow).order_by(SkillRow.name.asc())
            if active_only:
                stmt = stmt.where(SkillRow.active.is_(True))
            result = await session.execute(stmt)
            rows = result.scalars().all()

        skills = [self._row_to_skill(r) for r in rows]

        # Post-filter by tags if requested (JSON column may vary across backends)
        if tag_filter:
            tag_set = set(tag_filter)
            skills = [s for s in skills if tag_set.intersection(s.tags)]

        return skills

    async def get_skill(self, skill_id: str) -> Skill | None:
        """Retrieve a skill by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(SkillRow, skill_id)
            if row is None:
                return None
            return self._row_to_skill(row)

    # -- Mutations --

    async def create_skill(self, skill: Skill) -> Skill:
        """Persist a new skill and return it with timestamps populated."""
        async with self._session_factory() as session:
            row = SkillRow(
                id=skill.id,
                name=skill.name,
                description=skill.description,
                content=skill.content,
                tags=_to_json(skill.tags),
                active=skill.active,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._row_to_skill(row)

    async def update_skill(self, skill_id: str, **kwargs: Any) -> Skill | None:
        """Update allowed fields on a skill. Returns the updated skill or ``None``."""
        async with self._session_factory() as session:
            row = await session.get(SkillRow, skill_id)
            if row is None:
                return None
            for key, value in kwargs.items():
                if key not in _UPDATABLE_FIELDS:
                    msg = f"Field '{key}' is not updatable"
                    raise ValueError(msg)
                if key == "tags":
                    value = _to_json(value)
                setattr(row, key, value)
            row.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(row)
            return self._row_to_skill(row)

    async def delete_skill(self, skill_id: str) -> bool:
        """Delete a skill. Returns True if deleted."""
        async with self._session_factory() as session:
            row = await session.get(SkillRow, skill_id)
            if row is None:
                return False
            await session.delete(row)
            await session.commit()
            return True

    # -- Mapping helpers --

    @staticmethod
    def _row_to_skill(row: SkillRow) -> Skill:
        return Skill(
            id=row.id,
            name=row.name,
            description=row.description,
            content=row.content,
            tags=_from_json(row.tags),
            active=row.active,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
