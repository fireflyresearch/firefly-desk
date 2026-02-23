# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Generate agent tools dynamically from Service Catalog entries."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from flydesk.catalog.enums import RiskLevel

if TYPE_CHECKING:
    from flydesk.catalog.models import ServiceEndpoint
    from flydesk.rbac.models import AccessScopes


@dataclass(frozen=True)
class ToolDefinition:
    """A tool descriptor ready to be registered with the Desk Agent."""

    endpoint_id: str
    name: str
    description: str
    risk_level: RiskLevel
    system_id: str
    method: str
    path: str
    parameters: dict[str, Any] = field(default_factory=dict)

    @property
    def requires_confirmation(self) -> bool:
        return self.risk_level in (RiskLevel.HIGH_WRITE, RiskLevel.DESTRUCTIVE)


class ToolFactory:
    """Generates tool definitions from catalog endpoints, filtered by user permissions."""

    def build_tool_definitions(
        self,
        endpoints: list[ServiceEndpoint],
        user_permissions: list[str],
        access_scopes: AccessScopes | None = None,
    ) -> list[ToolDefinition]:
        """Build tools the user is permitted to use.

        When *access_scopes* is provided, endpoints are additionally filtered
        so only tools belonging to allowed systems are included.  Admin users
        (wildcard permission) bypass scope checks.
        """
        return [
            self._to_definition(ep)
            for ep in endpoints
            if self._has_permission(user_permissions, ep.required_permissions)
            and (
                access_scopes is None
                or "*" in user_permissions
                or access_scopes.can_access_system(ep.system_id)
            )
        ]

    @staticmethod
    def _has_permission(
        user_permissions: list[str],
        required_permissions: list[str],
    ) -> bool:
        """Check that the user has ALL required permissions for the endpoint.

        The wildcard ``"*"`` grants all permissions (superuser / admin).
        """
        if "*" in user_permissions:
            return True
        return all(p in user_permissions for p in required_permissions)

    @staticmethod
    def _to_definition(endpoint: ServiceEndpoint) -> ToolDefinition:
        description = endpoint.description
        description += f"\n\nWhen to use: {endpoint.when_to_use}"
        if endpoint.examples:
            description += f"\n\nExamples: {', '.join(endpoint.examples)}"

        parameters: dict[str, Any] = {}
        if endpoint.path_params:
            parameters["path"] = {
                k: v.model_dump() for k, v in endpoint.path_params.items()
            }
        if endpoint.query_params:
            parameters["query"] = {
                k: v.model_dump() for k, v in endpoint.query_params.items()
            }
        if endpoint.request_body:
            parameters["body"] = endpoint.request_body

        return ToolDefinition(
            endpoint_id=endpoint.id,
            name=endpoint.name,
            description=description,
            risk_level=endpoint.risk_level,
            system_id=endpoint.system_id,
            method=endpoint.method,
            path=endpoint.path,
            parameters=parameters,
        )
