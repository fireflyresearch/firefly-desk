# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Persistence layer for the Service Catalog."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydek.catalog.enums import SystemStatus
from flydek.catalog.models import AuthConfig, ExternalSystem, ServiceEndpoint
from flydek.models.catalog import ExternalSystemRow, ServiceEndpointRow


def _to_json(value: Any) -> str | None:
    """Serialize a Python object to a JSON string for SQLite Text columns.

    JSONB handles serialization natively on PostgreSQL, but when using the
    ``Text`` variant (SQLite) the caller must provide a plain string.
    """
    if value is None:
        return None
    return json.dumps(value, default=str)


def _from_json(value: Any) -> dict | list:
    """Deserialize a value that may be a JSON string (SQLite) or already a dict/list."""
    if isinstance(value, str):
        return json.loads(value)
    return value


def _from_json_or_none(value: Any) -> dict | list | None:
    """Deserialize an optional value that may be a JSON string (SQLite) or already parsed."""
    if value is None:
        return None
    return _from_json(value)


class CatalogRepository:
    """CRUD operations for external systems and service endpoints."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # -- External Systems --

    async def create_system(self, system: ExternalSystem) -> None:
        """Persist a new external system."""
        async with self._session_factory() as session:
            row = ExternalSystemRow(
                id=system.id,
                name=system.name,
                description=system.description,
                base_url=system.base_url,
                auth_config=_to_json(system.auth_config.model_dump()),
                health_check_path=system.health_check_path,
                tags=_to_json(system.tags),
                status=system.status.value,
                metadata_=_to_json(system.metadata),
            )
            session.add(row)
            await session.commit()

    async def get_system(self, system_id: str) -> ExternalSystem | None:
        """Retrieve an external system by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(ExternalSystemRow, system_id)
            if row is None:
                return None
            return self._row_to_system(row)

    async def list_systems(self) -> list[ExternalSystem]:
        """Return every registered external system."""
        async with self._session_factory() as session:
            result = await session.execute(select(ExternalSystemRow))
            return [self._row_to_system(r) for r in result.scalars().all()]

    async def update_system(self, system: ExternalSystem) -> None:
        """Update an existing external system (raises ``ValueError`` if missing)."""
        async with self._session_factory() as session:
            row = await session.get(ExternalSystemRow, system.id)
            if row is None:
                msg = f"System {system.id} not found"
                raise ValueError(msg)
            row.name = system.name
            row.description = system.description
            row.base_url = system.base_url
            row.auth_config = _to_json(system.auth_config.model_dump())
            row.health_check_path = system.health_check_path
            row.tags = _to_json(system.tags)
            row.status = system.status.value
            row.metadata_ = _to_json(system.metadata)
            await session.commit()

    async def delete_system(self, system_id: str) -> None:
        """Delete an external system by ID."""
        async with self._session_factory() as session:
            await session.execute(
                delete(ExternalSystemRow).where(ExternalSystemRow.id == system_id)
            )
            await session.commit()

    # -- Service Endpoints --

    async def create_endpoint(self, endpoint: ServiceEndpoint) -> None:
        """Persist a new service endpoint."""
        async with self._session_factory() as session:
            row = ServiceEndpointRow(
                id=endpoint.id,
                system_id=endpoint.system_id,
                name=endpoint.name,
                description=endpoint.description,
                method=endpoint.method.value,
                path=endpoint.path,
                path_params=_to_json(
                    {k: v.model_dump() for k, v in endpoint.path_params.items()}
                    if endpoint.path_params
                    else None
                ),
                query_params=_to_json(
                    {k: v.model_dump() for k, v in endpoint.query_params.items()}
                    if endpoint.query_params
                    else None
                ),
                request_body=_to_json(endpoint.request_body),
                response_schema=_to_json(endpoint.response_schema),
                when_to_use=endpoint.when_to_use,
                examples=_to_json(endpoint.examples),
                risk_level=endpoint.risk_level.value,
                required_permissions=_to_json(endpoint.required_permissions),
                rate_limit=_to_json(
                    endpoint.rate_limit.model_dump() if endpoint.rate_limit else None
                ),
                timeout_seconds=endpoint.timeout_seconds,
                retry_policy=_to_json(
                    endpoint.retry_policy.model_dump() if endpoint.retry_policy else None
                ),
                tags=_to_json(endpoint.tags),
            )
            session.add(row)
            await session.commit()

    async def get_endpoint(self, endpoint_id: str) -> ServiceEndpoint | None:
        """Retrieve a service endpoint by ID, or ``None`` if not found."""
        async with self._session_factory() as session:
            row = await session.get(ServiceEndpointRow, endpoint_id)
            if row is None:
                return None
            return self._row_to_endpoint(row)

    async def list_endpoints(self, system_id: str) -> list[ServiceEndpoint]:
        """Return all endpoints belonging to a specific system."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ServiceEndpointRow).where(ServiceEndpointRow.system_id == system_id)
            )
            return [self._row_to_endpoint(r) for r in result.scalars().all()]

    async def list_active_endpoints(self) -> list[ServiceEndpoint]:
        """List all endpoints whose parent system is ACTIVE."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ServiceEndpointRow)
                .join(
                    ExternalSystemRow,
                    ServiceEndpointRow.system_id == ExternalSystemRow.id,
                )
                .where(ExternalSystemRow.status == SystemStatus.ACTIVE.value)
            )
            return [self._row_to_endpoint(r) for r in result.scalars().all()]

    async def update_endpoint(self, endpoint: ServiceEndpoint) -> None:
        """Update an existing service endpoint (raises ``ValueError`` if missing)."""
        async with self._session_factory() as session:
            row = await session.get(ServiceEndpointRow, endpoint.id)
            if row is None:
                msg = f"Endpoint {endpoint.id} not found"
                raise ValueError(msg)
            row.name = endpoint.name
            row.description = endpoint.description
            row.method = endpoint.method.value
            row.path = endpoint.path
            row.when_to_use = endpoint.when_to_use
            row.examples = _to_json(endpoint.examples)
            row.risk_level = endpoint.risk_level.value
            row.required_permissions = _to_json(endpoint.required_permissions)
            row.timeout_seconds = endpoint.timeout_seconds
            row.tags = _to_json(endpoint.tags)
            await session.commit()

    async def delete_endpoint(self, endpoint_id: str) -> None:
        """Delete a service endpoint by ID."""
        async with self._session_factory() as session:
            await session.execute(
                delete(ServiceEndpointRow).where(ServiceEndpointRow.id == endpoint_id)
            )
            await session.commit()

    # -- Mapping helpers --

    @staticmethod
    def _row_to_system(row: ExternalSystemRow) -> ExternalSystem:
        return ExternalSystem(
            id=row.id,
            name=row.name,
            description=row.description,
            base_url=row.base_url,
            auth_config=AuthConfig(**_from_json(row.auth_config)),
            health_check_path=row.health_check_path,
            tags=_from_json(row.tags),
            status=SystemStatus(row.status),
            metadata=_from_json(row.metadata_),
        )

    @staticmethod
    def _row_to_endpoint(row: ServiceEndpointRow) -> ServiceEndpoint:
        return ServiceEndpoint(
            id=row.id,
            system_id=row.system_id,
            name=row.name,
            description=row.description,
            method=row.method,
            path=row.path,
            path_params=_from_json_or_none(row.path_params),
            query_params=_from_json_or_none(row.query_params),
            request_body=_from_json_or_none(row.request_body),
            response_schema=_from_json_or_none(row.response_schema),
            when_to_use=row.when_to_use,
            examples=_from_json(row.examples),
            risk_level=row.risk_level,
            required_permissions=_from_json(row.required_permissions),
            timeout_seconds=row.timeout_seconds,
            tags=_from_json(row.tags),
        )
