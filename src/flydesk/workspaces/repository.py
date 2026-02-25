# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Persistence layer for workspaces."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.models.workspace import WorkspaceRoleRow, WorkspaceRow, WorkspaceUserRow
from flydesk.workspaces.models import CreateWorkspace, UpdateWorkspace, Workspace


class WorkspaceRepository:
    """CRUD operations for workspaces."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create(self, body: CreateWorkspace) -> Workspace:
        """Create a new workspace with its roles and users."""
        workspace_id = str(uuid.uuid4())
        async with self._session_factory() as session:
            row = WorkspaceRow(
                id=workspace_id,
                name=body.name,
                description=body.description,
                icon=body.icon,
                color=body.color,
            )
            session.add(row)

            for role_name in body.roles:
                session.add(WorkspaceRoleRow(
                    workspace_id=workspace_id,
                    role_name=role_name,
                ))

            for user_id in body.users:
                session.add(WorkspaceUserRow(
                    workspace_id=workspace_id,
                    user_id=user_id,
                ))

            await session.commit()

        return Workspace(
            id=workspace_id,
            name=body.name,
            description=body.description,
            icon=body.icon,
            color=body.color,
            roles=list(body.roles),
            users=list(body.users),
        )

    async def get(self, workspace_id: str) -> Workspace | None:
        """Retrieve a workspace by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(WorkspaceRow, workspace_id)
            if row is None:
                return None

            roles_result = await session.execute(
                select(WorkspaceRoleRow.role_name).where(
                    WorkspaceRoleRow.workspace_id == workspace_id
                )
            )
            roles = [r for (r,) in roles_result.all()]

            users_result = await session.execute(
                select(WorkspaceUserRow.user_id).where(
                    WorkspaceUserRow.workspace_id == workspace_id
                )
            )
            users = [u for (u,) in users_result.all()]

            return Workspace(
                id=row.id,
                name=row.name,
                description=row.description,
                icon=row.icon,
                color=row.color,
                roles=roles,
                users=users,
            )

    async def list_all(self) -> list[Workspace]:
        """Return every workspace with roles and users."""
        async with self._session_factory() as session:
            result = await session.execute(select(WorkspaceRow))
            rows = result.scalars().all()

            workspaces: list[Workspace] = []
            for row in rows:
                roles_result = await session.execute(
                    select(WorkspaceRoleRow.role_name).where(
                        WorkspaceRoleRow.workspace_id == row.id
                    )
                )
                roles = [r for (r,) in roles_result.all()]

                users_result = await session.execute(
                    select(WorkspaceUserRow.user_id).where(
                        WorkspaceUserRow.workspace_id == row.id
                    )
                )
                users = [u for (u,) in users_result.all()]

                workspaces.append(Workspace(
                    id=row.id,
                    name=row.name,
                    description=row.description,
                    icon=row.icon,
                    color=row.color,
                    roles=roles,
                    users=users,
                ))

            return workspaces

    async def update(self, workspace_id: str, body: UpdateWorkspace) -> Workspace | None:
        """Update an existing workspace. Returns ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(WorkspaceRow, workspace_id)
            if row is None:
                return None

            if body.name is not None:
                row.name = body.name
            if body.description is not None:
                row.description = body.description
            if body.icon is not None:
                row.icon = body.icon
            if body.color is not None:
                row.color = body.color

            if body.roles is not None:
                await session.execute(
                    delete(WorkspaceRoleRow).where(
                        WorkspaceRoleRow.workspace_id == workspace_id
                    )
                )
                for role_name in body.roles:
                    session.add(WorkspaceRoleRow(
                        workspace_id=workspace_id,
                        role_name=role_name,
                    ))

            if body.users is not None:
                await session.execute(
                    delete(WorkspaceUserRow).where(
                        WorkspaceUserRow.workspace_id == workspace_id
                    )
                )
                for user_id in body.users:
                    session.add(WorkspaceUserRow(
                        workspace_id=workspace_id,
                        user_id=user_id,
                    ))

            await session.commit()
            await session.refresh(row)

            # Re-fetch roles and users
            roles_result = await session.execute(
                select(WorkspaceRoleRow.role_name).where(
                    WorkspaceRoleRow.workspace_id == workspace_id
                )
            )
            roles = [r for (r,) in roles_result.all()]

            users_result = await session.execute(
                select(WorkspaceUserRow.user_id).where(
                    WorkspaceUserRow.workspace_id == workspace_id
                )
            )
            users = [u for (u,) in users_result.all()]

            return Workspace(
                id=row.id,
                name=row.name,
                description=row.description,
                icon=row.icon,
                color=row.color,
                roles=roles,
                users=users,
            )

    async def delete(self, workspace_id: str) -> None:
        """Delete a workspace by ID (roles and users cascade)."""
        async with self._session_factory() as session:
            await session.execute(
                delete(WorkspaceRow).where(WorkspaceRow.id == workspace_id)
            )
            await session.commit()

    async def list_for_user(self, user_id: str, roles: list[str]) -> list[Workspace]:
        """Return workspaces the user belongs to via user_id or role membership."""
        async with self._session_factory() as session:
            # Find workspace IDs where user is directly assigned OR has a matching role
            conditions = [
                WorkspaceUserRow.user_id == user_id,
            ]

            # Start with user-based workspace IDs
            user_ws_query = select(WorkspaceUserRow.workspace_id).where(
                WorkspaceUserRow.user_id == user_id
            )

            if roles:
                role_ws_query = select(WorkspaceRoleRow.workspace_id).where(
                    WorkspaceRoleRow.role_name.in_(roles)
                )
                combined_query = select(WorkspaceRow).where(
                    or_(
                        WorkspaceRow.id.in_(user_ws_query),
                        WorkspaceRow.id.in_(role_ws_query),
                    )
                )
            else:
                combined_query = select(WorkspaceRow).where(
                    WorkspaceRow.id.in_(user_ws_query)
                )

            result = await session.execute(combined_query)
            rows = result.scalars().all()

            workspaces: list[Workspace] = []
            for row in rows:
                roles_result = await session.execute(
                    select(WorkspaceRoleRow.role_name).where(
                        WorkspaceRoleRow.workspace_id == row.id
                    )
                )
                ws_roles = [r for (r,) in roles_result.all()]

                users_result = await session.execute(
                    select(WorkspaceUserRow.user_id).where(
                        WorkspaceUserRow.workspace_id == row.id
                    )
                )
                ws_users = [u for (u,) in users_result.all()]

                workspaces.append(Workspace(
                    id=row.id,
                    name=row.name,
                    description=row.description,
                    icon=row.icon,
                    color=row.color,
                    roles=ws_roles,
                    users=ws_users,
                ))

            return workspaces
