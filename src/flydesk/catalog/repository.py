# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Persistence layer for the Service Catalog."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from flydesk.catalog.enums import SystemStatus
from flydesk.catalog.models import AuthConfig, ExternalSystem, ServiceEndpoint
from flydesk.models.catalog import ExternalSystemRow, ServiceEndpointRow


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
                auth_config=_to_json(system.auth_config.model_dump()) if system.auth_config else None,
                health_check_path=system.health_check_path,
                tags=_to_json(system.tags),
                agent_enabled=system.agent_enabled,
                status=system.status.value,
                metadata_=_to_json(system.metadata),
                workspace_id=system.workspace_id,
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

    async def list_systems(
        self,
        *,
        workspace_id: str | None = None,
        status: SystemStatus | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ExternalSystem], int]:
        """Return systems with optional filters. Returns (items, total_count)."""
        async with self._session_factory() as session:
            stmt = select(ExternalSystemRow)
            count_stmt = select(func.count()).select_from(ExternalSystemRow)

            if workspace_id is not None:
                stmt = stmt.where(ExternalSystemRow.workspace_id == workspace_id)
                count_stmt = count_stmt.where(ExternalSystemRow.workspace_id == workspace_id)
            if status is not None:
                stmt = stmt.where(ExternalSystemRow.status == status.value)
                count_stmt = count_stmt.where(ExternalSystemRow.status == status.value)
            if search is not None:
                pattern = f"%{search}%"
                stmt = stmt.where(ExternalSystemRow.name.ilike(pattern))
                count_stmt = count_stmt.where(ExternalSystemRow.name.ilike(pattern))

            total_result = await session.execute(count_stmt)
            total = total_result.scalar() or 0

            stmt = stmt.order_by(ExternalSystemRow.name).limit(limit).offset(offset)
            result = await session.execute(stmt)
            systems = [self._row_to_system(r) for r in result.scalars().all()]
            return systems, total

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
            row.auth_config = _to_json(system.auth_config.model_dump()) if system.auth_config else None
            row.health_check_path = system.health_check_path
            row.tags = _to_json(system.tags)
            row.agent_enabled = system.agent_enabled
            row.status = system.status.value
            row.metadata_ = _to_json(system.metadata)
            row.workspace_id = system.workspace_id
            await session.commit()

    async def delete_system(self, system_id: str) -> None:
        """Delete an external system by ID."""
        async with self._session_factory() as session:
            await session.execute(
                delete(ExternalSystemRow).where(ExternalSystemRow.id == system_id)
            )
            await session.commit()

    async def bulk_delete_systems(self, ids: list[str]) -> int:
        """Delete multiple systems. Returns count of deleted rows."""
        if not ids:
            return 0
        async with self._session_factory() as session:
            result = await session.execute(
                delete(ExternalSystemRow).where(ExternalSystemRow.id.in_(ids))
            )
            await session.commit()
            return result.rowcount or 0

    async def bulk_update_status(self, ids: list[str], status: SystemStatus) -> int:
        """Update status for multiple systems. Returns count of updated rows."""
        if not ids:
            return 0
        async with self._session_factory() as session:
            result = await session.execute(
                update(ExternalSystemRow)
                .where(ExternalSystemRow.id.in_(ids))
                .values(status=status.value)
            )
            await session.commit()
            return result.rowcount or 0

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
                protocol_type=endpoint.protocol_type.value,
                graphql_query=endpoint.graphql_query,
                graphql_operation_name=endpoint.graphql_operation_name,
                soap_action=endpoint.soap_action,
                soap_body_template=endpoint.soap_body_template,
                grpc_service=endpoint.grpc_service,
                grpc_method_name=endpoint.grpc_method_name,
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
            row.path_params = _to_json(
                {k: v.model_dump() for k, v in endpoint.path_params.items()}
                if endpoint.path_params
                else None
            )
            row.query_params = _to_json(
                {k: v.model_dump() for k, v in endpoint.query_params.items()}
                if endpoint.query_params
                else None
            )
            row.request_body = _to_json(endpoint.request_body)
            row.response_schema = _to_json(endpoint.response_schema)
            row.when_to_use = endpoint.when_to_use
            row.examples = _to_json(endpoint.examples)
            row.risk_level = endpoint.risk_level.value
            row.required_permissions = _to_json(endpoint.required_permissions)
            row.rate_limit = _to_json(
                endpoint.rate_limit.model_dump() if endpoint.rate_limit else None
            )
            row.timeout_seconds = endpoint.timeout_seconds
            row.retry_policy = _to_json(
                endpoint.retry_policy.model_dump() if endpoint.retry_policy else None
            )
            row.tags = _to_json(endpoint.tags)
            row.protocol_type = endpoint.protocol_type.value
            row.graphql_query = endpoint.graphql_query
            row.graphql_operation_name = endpoint.graphql_operation_name
            row.soap_action = endpoint.soap_action
            row.soap_body_template = endpoint.soap_body_template
            row.grpc_service = endpoint.grpc_service
            row.grpc_method_name = endpoint.grpc_method_name
            await session.commit()

    async def delete_endpoint(self, endpoint_id: str) -> None:
        """Delete a service endpoint by ID."""
        async with self._session_factory() as session:
            await session.execute(
                delete(ServiceEndpointRow).where(ServiceEndpointRow.id == endpoint_id)
            )
            await session.commit()

    # -- Credentials --

    async def list_credentials(self) -> list:
        """Return all stored credentials."""
        from flydesk.catalog.models import Credential
        from flydesk.models.catalog import CredentialRow

        async with self._session_factory() as session:
            result = await session.execute(select(CredentialRow))
            return [
                Credential(
                    id=r.id,
                    system_id=r.system_id,
                    name=r.name,
                    encrypted_value=r.encrypted_value,
                    credential_type=r.credential_type,
                    expires_at=r.expires_at,
                    last_rotated=r.last_rotated,
                )
                for r in result.scalars().all()
            ]

    async def get_credential(self, credential_id: str):
        """Retrieve a credential by ID."""
        from flydesk.catalog.models import Credential
        from flydesk.models.catalog import CredentialRow

        async with self._session_factory() as session:
            row = await session.get(CredentialRow, credential_id)
            if row is None:
                return None
            return Credential(
                id=row.id,
                system_id=row.system_id,
                name=row.name,
                encrypted_value=row.encrypted_value,
                credential_type=row.credential_type,
                expires_at=row.expires_at,
                last_rotated=row.last_rotated,
            )

    async def create_credential(self, credential) -> None:
        """Persist a new credential."""
        from flydesk.models.catalog import CredentialRow

        async with self._session_factory() as session:
            row = CredentialRow(
                id=credential.id,
                system_id=credential.system_id,
                name=credential.name,
                encrypted_value=credential.encrypted_value,
                credential_type=credential.credential_type,
                expires_at=credential.expires_at,
                last_rotated=credential.last_rotated,
            )
            session.add(row)
            await session.commit()

    async def update_credential(self, credential) -> None:
        """Update an existing credential."""
        from flydesk.models.catalog import CredentialRow

        async with self._session_factory() as session:
            row = await session.get(CredentialRow, credential.id)
            if row is None:
                msg = f"Credential {credential.id} not found"
                raise ValueError(msg)
            row.system_id = credential.system_id
            row.name = credential.name
            row.encrypted_value = credential.encrypted_value
            row.credential_type = credential.credential_type
            row.expires_at = credential.expires_at
            row.last_rotated = credential.last_rotated
            await session.commit()

    async def delete_credential(self, credential_id: str) -> None:
        """Delete a credential by ID."""
        from flydesk.models.catalog import CredentialRow

        async with self._session_factory() as session:
            await session.execute(
                delete(CredentialRow).where(CredentialRow.id == credential_id)
            )
            await session.commit()

    # -- Knowledge Documents --

    async def list_knowledge_documents(self, *, workspace_id: str | None = None) -> list:
        """Return all knowledge documents, optionally filtered by workspace."""
        from flydesk.knowledge.models import DocumentStatus, DocumentType, KnowledgeDocument
        from flydesk.models.knowledge_base import KnowledgeDocumentRow

        async with self._session_factory() as session:
            stmt = select(KnowledgeDocumentRow)
            if workspace_id is not None:
                stmt = stmt.where(KnowledgeDocumentRow.workspace_id == workspace_id)
            result = await session.execute(stmt)
            return [
                KnowledgeDocument(
                    id=r.id,
                    title=r.title,
                    content=r.content,
                    document_type=DocumentType(r.document_type) if r.document_type else DocumentType.OTHER,
                    status=DocumentStatus(r.status) if r.status else DocumentStatus.DRAFT,
                    source=r.source,
                    workspace_id=r.workspace_id,
                    tags=_from_json(r.tags) if r.tags else [],
                    metadata=_from_json(r.metadata_) if r.metadata_ else {},
                )
                for r in result.scalars().all()
            ]

    async def get_knowledge_document(self, document_id: str):
        """Retrieve a knowledge document by ID."""
        from flydesk.knowledge.models import DocumentStatus, DocumentType, KnowledgeDocument
        from flydesk.models.knowledge_base import KnowledgeDocumentRow

        async with self._session_factory() as session:
            row = await session.get(KnowledgeDocumentRow, document_id)
            if row is None:
                return None
            return KnowledgeDocument(
                id=row.id,
                title=row.title,
                content=row.content,
                document_type=DocumentType(row.document_type) if row.document_type else DocumentType.OTHER,
                status=DocumentStatus(row.status) if row.status else DocumentStatus.DRAFT,
                source=row.source,
                workspace_id=row.workspace_id,
                tags=_from_json(row.tags) if row.tags else [],
                metadata=_from_json(row.metadata_) if row.metadata_ else {},
            )

    async def update_knowledge_document(
        self, document_id: str, *, title=None, document_type=None, tags=None, content=None, status=None, workspace_id=None
    ):
        """Update a knowledge document's metadata and optionally content."""
        import json as _json

        from flydesk.knowledge.models import DocumentStatus, DocumentType, KnowledgeDocument
        from flydesk.models.knowledge_base import KnowledgeDocumentRow

        async with self._session_factory() as session:
            row = await session.get(KnowledgeDocumentRow, document_id)
            if row is None:
                return None
            if title is not None:
                row.title = title
            if document_type is not None:
                row.document_type = str(document_type)
            if tags is not None:
                row.tags = _json.dumps(tags)
            if content is not None:
                row.content = content
            if status is not None:
                row.status = str(status)
            if workspace_id is not None:
                row.workspace_id = workspace_id or None
            await session.commit()
            await session.refresh(row)
            return KnowledgeDocument(
                id=row.id,
                title=row.title,
                content=row.content,
                document_type=DocumentType(row.document_type) if row.document_type else DocumentType.OTHER,
                status=DocumentStatus(row.status) if row.status else DocumentStatus.DRAFT,
                source=row.source,
                workspace_id=row.workspace_id,
                tags=_from_json(row.tags) if row.tags else [],
                metadata=_from_json(row.metadata_) if row.metadata_ else {},
            )

    # -- Mapping helpers --

    @staticmethod
    def _row_to_system(row: ExternalSystemRow) -> ExternalSystem:
        return ExternalSystem(
            id=row.id,
            name=row.name,
            description=row.description,
            base_url=row.base_url,
            auth_config=AuthConfig(**_from_json(row.auth_config)) if row.auth_config else None,
            health_check_path=row.health_check_path,
            tags=_from_json(row.tags),
            status=SystemStatus(row.status),
            metadata=_from_json(row.metadata_),
            agent_enabled=row.agent_enabled,
            workspace_id=row.workspace_id,
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
            rate_limit=_from_json_or_none(row.rate_limit),
            timeout_seconds=row.timeout_seconds,
            retry_policy=_from_json_or_none(row.retry_policy),
            tags=_from_json(row.tags),
            protocol_type=row.protocol_type or "rest",
            graphql_query=row.graphql_query,
            graphql_operation_name=row.graphql_operation_name,
            soap_action=row.soap_action,
            soap_body_template=row.soap_body_template,
            grpc_service=row.grpc_service,
            grpc_method_name=row.grpc_method_name,
        )
