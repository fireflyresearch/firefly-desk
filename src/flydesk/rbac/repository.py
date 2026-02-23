# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Persistence layer for RBAC roles."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.role import RoleRow
from flydesk.rbac.models import AccessScopes, Role
from flydesk.rbac.permissions import BUILTIN_ROLES, merge_access_scopes

_UPDATABLE_FIELDS = frozenset({
    "name",
    "display_name",
    "description",
    "permissions",
    "access_scopes",
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
    return value


class RoleRepository:
    """CRUD operations for RBAC roles."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # -- Queries --

    async def list_roles(self) -> list[Role]:
        """Return all roles ordered by name."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(RoleRow).order_by(RoleRow.name.asc())
            )
            return [self._row_to_role(r) for r in result.scalars().all()]

    async def get_role(self, role_id: str) -> Role | None:
        """Retrieve a role by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(RoleRow, role_id)
            if row is None:
                return None
            return self._row_to_role(row)

    async def get_role_by_name(self, name: str) -> Role | None:
        """Retrieve a role by its unique name, or ``None`` if not found."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(RoleRow).where(RoleRow.name == name)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return self._row_to_role(row)

    # -- Mutations --

    async def create_role(self, role: Role) -> Role:
        """Persist a new role and return it with timestamps populated."""
        async with self._session_factory() as session:
            row = RoleRow(
                id=role.id,
                name=role.name,
                display_name=role.display_name,
                description=role.description,
                permissions=_to_json(role.permissions),
                access_scopes=_to_json(role.access_scopes.model_dump()),
                is_builtin=role.is_builtin,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return self._row_to_role(row)

    async def update_role(self, role_id: str, **kwargs: Any) -> Role | None:
        """Update allowed fields on a role.  Returns the updated role or ``None``."""
        async with self._session_factory() as session:
            row = await session.get(RoleRow, role_id)
            if row is None:
                return None
            for key, value in kwargs.items():
                if key not in _UPDATABLE_FIELDS:
                    msg = f"Field '{key}' is not updatable"
                    raise ValueError(msg)
                if key == "permissions":
                    value = _to_json(value)
                elif key == "access_scopes":
                    # Accept dict or AccessScopes; store as JSON dict
                    if isinstance(value, AccessScopes):
                        value = _to_json(value.model_dump())
                    elif isinstance(value, dict):
                        value = _to_json(value)
                setattr(row, key, value)
            row.updated_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(row)
            return self._row_to_role(row)

    async def delete_role(self, role_id: str) -> bool:
        """Delete a role.  Refuses to delete built-in roles.  Returns True if deleted."""
        async with self._session_factory() as session:
            row = await session.get(RoleRow, role_id)
            if row is None:
                return False
            if row.is_builtin:
                msg = f"Cannot delete built-in role '{row.name}'"
                raise ValueError(msg)
            await session.delete(row)
            await session.commit()
            return True

    # -- Permission resolution --

    async def get_permissions_for_roles(self, role_names: list[str]) -> list[str]:
        """Union permissions for all roles matching the given names.

        If any role carries the wildcard ``["*"]``, returns ``["*"]``.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(RoleRow).where(RoleRow.name.in_(role_names))
            )
            rows = result.scalars().all()

        all_perms: set[str] = set()
        for row in rows:
            perms = _from_json(row.permissions) if row.permissions else []
            if "*" in perms:
                return ["*"]
            all_perms.update(perms)
        return sorted(all_perms)

    async def get_access_scopes_for_roles(
        self, role_names: list[str],
    ) -> AccessScopes:
        """Merge access scopes for all roles matching the given names.

        Returns an :class:`AccessScopes` representing the union (most-permissive)
        of all matching roles' scopes.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(RoleRow).where(RoleRow.name.in_(role_names))
            )
            rows = result.scalars().all()

        scopes_list: list[AccessScopes] = []
        for row in rows:
            scopes_list.append(self._parse_access_scopes(row.access_scopes))

        return merge_access_scopes(scopes_list)

    # -- Seeding --

    async def seed_builtin_roles(self) -> None:
        """Idempotent: create or update built-in roles."""
        async with self._session_factory() as session:
            for role in BUILTIN_ROLES:
                existing = await session.get(RoleRow, role.id)
                if existing is None:
                    session.add(
                        RoleRow(
                            id=role.id,
                            name=role.name,
                            display_name=role.display_name,
                            description=role.description,
                            permissions=_to_json(role.permissions),
                            is_builtin=True,
                        )
                    )
                else:
                    # Update permissions and scopes in case they changed
                    existing.permissions = _to_json(role.permissions)
                    existing.access_scopes = _to_json(role.access_scopes.model_dump())
                    existing.display_name = role.display_name
                    existing.description = role.description
                    existing.updated_at = datetime.now(timezone.utc)
            await session.commit()

    # -- Mapping helpers --

    @staticmethod
    def _parse_access_scopes(raw: Any) -> AccessScopes:
        """Deserialize an access_scopes column value into an AccessScopes model."""
        if raw is None:
            return AccessScopes()
        data = raw
        if isinstance(data, str):
            data = json.loads(data)
        if isinstance(data, dict):
            return AccessScopes(**data)
        return AccessScopes()

    @staticmethod
    def _row_to_role(row: RoleRow) -> Role:
        return Role(
            id=row.id,
            name=row.name,
            display_name=row.display_name,
            description=row.description,
            permissions=_from_json(row.permissions) if row.permissions else [],
            access_scopes=RoleRepository._parse_access_scopes(row.access_scopes),
            is_builtin=row.is_builtin,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
