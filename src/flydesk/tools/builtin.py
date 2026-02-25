# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Built-in tools for internal platform operations.

These tools let the agent interact with Firefly Desk's own subsystems
(knowledge base, service catalog, audit log) without going through
an external HTTP round-trip.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from flydesk.catalog.enums import HttpMethod, RiskLevel
from flydesk.tools.factory import ToolDefinition

if TYPE_CHECKING:
    from flydesk.audit.logger import AuditLogger
    from flydesk.catalog.repository import CatalogRepository
    from flydesk.knowledge.retriever import KnowledgeRetriever
    from flydesk.processes.repository import ProcessRepository
    from flydesk.tools.document_tools import DocumentToolExecutor
    from flydesk.tools.transform_tools import TransformToolExecutor

logger = logging.getLogger(__name__)

BUILTIN_SYSTEM_ID = "__flydesk__"


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------


def _knowledge_search_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__search_knowledge",
        name="search_knowledge",
        description=(
            "Search the organization's knowledge base by natural-language query. "
            "Returns the most relevant document snippets. "
            "Use when: the user asks a question that might be answered by internal "
            "documentation, policies, guides, or manuals."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/knowledge/search",
        parameters={
            "query": {"type": "string", "description": "Search query", "required": True},
            "top_k": {"type": "integer", "description": "Number of results (default 5)", "required": False},
        },
    )


def _list_catalog_systems_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__list_systems",
        name="list_catalog_systems",
        description=(
            "List all external systems registered in the service catalog. "
            "Returns system names, descriptions, base URLs, and statuses. "
            "Use when: the user asks what systems are available, wants to see "
            "integrations, or needs to browse connected services."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/catalog/systems",
        parameters={},
    )


def _list_system_endpoints_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__list_endpoints",
        name="list_system_endpoints",
        description=(
            "List all endpoints (operations) for a specific external system. "
            "Returns endpoint names, methods, paths, risk levels, and descriptions. "
            "Use when: the user asks what operations are available for a system, "
            "wants to know what they can do with a specific integration."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/catalog/systems/{system_id}/endpoints",
        parameters={
            "system_id": {"type": "string", "description": "System ID to list endpoints for", "required": True},
        },
    )


def _query_audit_log_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__query_audit",
        name="query_audit_log",
        description=(
            "Query the audit log for recent events. "
            "Returns timestamped records of tool calls, agent responses, auth events, etc. "
            "Use when: an admin asks about recent activity, wants to review actions, "
            "or needs to investigate an issue."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/audit/events",
        parameters={
            "limit": {"type": "integer", "description": "Max events to return (default 20)", "required": False},
            "event_type": {"type": "string", "description": "Filter by event type", "required": False},
        },
    )


def _platform_status_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__platform_status",
        name="get_platform_status",
        description=(
            "Get an overview of the Firefly Desk platform status: number of "
            "registered systems, endpoints, knowledge documents, and recent events. "
            "Use when: the user asks about the platform, wants a summary, or is "
            "getting started and wants to know what's available."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/status",
        parameters={},
    )


def _search_processes_tool() -> ToolDefinition:
    return ToolDefinition(
        endpoint_id="__builtin__search_processes",
        name="search_processes",
        description=(
            "Search business processes by name or description. "
            "Returns matching processes with their steps as reference material. "
            "Use when: the user asks about business processes, workflows, or "
            "how a procedure works."
        ),
        risk_level=RiskLevel.READ,
        system_id=BUILTIN_SYSTEM_ID,
        method=HttpMethod.GET.value,
        path="/__builtin__/processes/search",
        parameters={
            "query": {"type": "string", "description": "Search term to find matching processes", "required": True},
        },
    )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class BuiltinToolRegistry:
    """Provides built-in tool definitions for internal platform operations."""

    @staticmethod
    def get_tool_definitions(user_permissions: list[str]) -> list[ToolDefinition]:
        """Return built-in tool definitions filtered by user permissions."""
        has_all = "*" in user_permissions

        tools: list[ToolDefinition] = []

        # Always available
        tools.append(_platform_status_tool())

        # Knowledge tools (require knowledge:read or *)
        if has_all or "knowledge:read" in user_permissions:
            tools.append(_knowledge_search_tool())

        # Catalog tools (require catalog:read or *)
        if has_all or "catalog:read" in user_permissions:
            tools.append(_list_catalog_systems_tool())
            tools.append(_list_system_endpoints_tool())

        # Process tools (require processes:read or *)
        if has_all or "processes:read" in user_permissions:
            tools.append(_search_processes_tool())

        # Audit tools (admin only, require audit:read or *)
        if has_all or "audit:read" in user_permissions:
            tools.append(_query_audit_log_tool())

        # Document tools (require knowledge:read or *)
        if has_all or "knowledge:read" in user_permissions:
            from flydesk.tools.document_tools import (
                document_convert_tool,
                document_create_tool,
                document_modify_tool,
                document_read_tool,
            )

            tools.append(document_read_tool())
            tools.append(document_create_tool())
            tools.append(document_modify_tool())
            tools.append(document_convert_tool())

        # Transform tools (always available — no permission requirement)
        from flydesk.tools.transform_tools import (
            filter_rows_tool,
            grep_result_tool,
            parse_json_tool,
            transform_data_tool,
        )

        tools.append(grep_result_tool())
        tools.append(parse_json_tool())
        tools.append(filter_rows_tool())
        tools.append(transform_data_tool())

        return tools


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


class BuiltinToolExecutor:
    """Execute built-in tools by calling internal repositories directly.

    Unlike :class:`~flydesk.tools.executor.ToolExecutor` which makes HTTP
    requests to external systems, this executor calls repository methods
    in-process.
    """

    def __init__(
        self,
        catalog_repo: CatalogRepository,
        audit_logger: AuditLogger,
        knowledge_retriever: KnowledgeRetriever | None = None,
        process_repo: ProcessRepository | None = None,
    ) -> None:
        self._catalog_repo = catalog_repo
        self._audit_logger = audit_logger
        self._knowledge_retriever = knowledge_retriever
        self._process_repo = process_repo
        self._doc_executor: DocumentToolExecutor | None = None

        from flydesk.tools.transform_tools import (
            TransformToolExecutor as _TransformExec,
        )

        self._transform_executor: TransformToolExecutor = _TransformExec()

    def set_document_executor(self, executor: DocumentToolExecutor) -> None:
        """Attach a :class:`DocumentToolExecutor` for document operations."""
        self._doc_executor = executor

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Execute a built-in tool and return a result dict."""
        # Delegate document_* tools to the dedicated executor
        if tool_name.startswith("document_") and self._doc_executor is not None:
            return await self._doc_executor.execute(tool_name, arguments)

        # Delegate transform tools to the dedicated executor
        if self._transform_executor.is_transform_tool(tool_name):
            return await self._transform_executor.execute(tool_name, arguments)

        handlers = {
            "search_knowledge": self._search_knowledge,
            "list_catalog_systems": self._list_systems,
            "list_system_endpoints": self._list_endpoints,
            "query_audit_log": self._query_audit,
            "get_platform_status": self._platform_status,
            "search_processes": self._search_processes,
        }

        handler = handlers.get(tool_name)
        if handler is None:
            return {"error": f"Unknown built-in tool: {tool_name}"}

        try:
            return await handler(arguments)
        except Exception as exc:
            logger.error("Built-in tool %s failed: %s", tool_name, exc, exc_info=True)
            return {"error": str(exc)}

    def is_builtin(self, endpoint_id: str) -> bool:
        """Check if an endpoint ID belongs to a built-in tool."""
        return endpoint_id.startswith("__builtin__")

    async def _search_knowledge(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = arguments.get("query", "")
        top_k = arguments.get("top_k", 5)

        if not query:
            return {"error": "Query is required"}

        if self._knowledge_retriever is None:
            return {"error": "Knowledge retriever not configured", "results": []}

        try:
            snippets = await self._knowledge_retriever.retrieve(query, top_k=top_k)
            results = [
                {
                    "document_title": s.document_title,
                    "content": s.chunk.content,
                    "score": round(s.score, 3) if hasattr(s, "score") else None,
                }
                for s in snippets
            ]
            return {"query": query, "results": results, "count": len(results)}
        except Exception as exc:
            return {"error": f"Knowledge search failed: {exc}", "results": []}

    async def _list_systems(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        systems = await self._catalog_repo.list_systems()
        return {
            "systems": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "base_url": s.base_url,
                    "status": s.status.value if hasattr(s.status, "value") else str(s.status),
                    "tags": s.tags,
                }
                for s in systems
            ],
            "count": len(systems),
        }

    async def _list_endpoints(self, arguments: dict[str, Any]) -> dict[str, Any]:
        system_id = arguments.get("system_id", "")
        if not system_id:
            return {"error": "system_id is required"}

        endpoints = await self._catalog_repo.list_endpoints()
        filtered = [e for e in endpoints if e.system_id == system_id]

        return {
            "system_id": system_id,
            "endpoints": [
                {
                    "id": e.id,
                    "name": e.name,
                    "description": e.description,
                    "method": e.method.value,
                    "path": e.path,
                    "risk_level": e.risk_level.value,
                    "protocol": getattr(e, "protocol_type", "rest"),
                }
                for e in filtered
            ],
            "count": len(filtered),
        }

    async def _query_audit(self, arguments: dict[str, Any]) -> dict[str, Any]:
        limit = arguments.get("limit", 20)
        event_type = arguments.get("event_type")

        events = await self._audit_logger.query(
            limit=limit,
            event_type=event_type,
        )

        return {
            "events": [
                {
                    "id": e.id,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                    "event_type": e.event_type.value if hasattr(e.event_type, "value") else str(e.event_type),
                    "user_id": e.user_id,
                    "action": e.action,
                    "detail": e.detail,
                }
                for e in events
            ],
            "count": len(events),
        }

    async def _platform_status(self, _arguments: dict[str, Any]) -> dict[str, Any]:
        systems = await self._catalog_repo.list_systems()
        endpoints = await self._catalog_repo.list_endpoints()

        return {
            "systems_count": len(systems),
            "endpoints_count": len(endpoints),
            "systems": [
                {"name": s.name, "status": s.status.value if hasattr(s.status, "value") else str(s.status)}
                for s in systems
            ],
        }

    async def _search_processes(self, arguments: dict[str, Any]) -> dict[str, Any]:
        query = arguments.get("query", "")

        if not query:
            return {"error": "Query is required"}

        if self._process_repo is None:
            return {"error": "Process repository not configured", "processes": []}

        processes = await self._process_repo.list()

        # Simple text search: match query against name, description, and step descriptions
        query_lower = query.lower()
        matches: list[tuple[float, Any]] = []
        for proc in processes:
            score = 0.0
            if query_lower in proc.name.lower():
                score += 2
            if query_lower in proc.description.lower():
                score += 1
            for step in proc.steps:
                if query_lower in step.description.lower():
                    score += 0.5
            if score > 0:
                matches.append((score, proc))

        matches.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, proc in matches[:3]:
            results.append({
                "id": proc.id,
                "name": proc.name,
                "description": proc.description,
                "steps": [
                    {"name": s.name, "description": s.description, "endpoint_id": s.endpoint_id}
                    for s in proc.steps
                ],
                "confidence": score,
            })

        return {"processes": results, "total_matches": len(matches)}
