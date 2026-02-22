# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Parallel and sequential tool execution engine."""

from __future__ import annotations

import asyncio
import logging
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

from flydek.audit.models import AuditEvent, AuditEventType
from flydek.tools.auth_resolver import AuthResolver

if TYPE_CHECKING:
    from flydek.api.credentials import CredentialStore
    from flydek.audit.logger import AuditLogger
    from flydek.catalog.repository import CatalogRepository

logger = logging.getLogger(__name__)

# HTTP methods considered read-only (safe for parallel execution within a system).
_READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


@dataclass(frozen=True)
class ToolCall:
    """A request to invoke a single external tool."""

    call_id: str
    tool_name: str
    endpoint_id: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """The outcome of a single tool invocation."""

    call_id: str
    tool_name: str
    success: bool
    data: Any
    error: str | None
    duration_ms: float
    status_code: int | None


class ToolExecutor:
    """Execute external tool calls with configurable parallelism.

    Parallelism heuristic:
    - Calls to **different** systems are independent and run in parallel.
    - Within the **same** system, read-only calls (GET) run in parallel while
      write calls (POST/PUT/PATCH/DELETE) are sequential to avoid conflicts.
    - A global :class:`asyncio.Semaphore` limits total concurrency.
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        catalog_repo: CatalogRepository,
        credential_store: CredentialStore,
        audit_logger: AuditLogger,
        max_parallel: int = 5,
    ) -> None:
        self._http_client = http_client
        self._catalog_repo = catalog_repo
        self._credential_store = credential_store
        self._audit_logger = audit_logger
        self._semaphore = asyncio.Semaphore(max_parallel)
        self._auth_resolver = AuthResolver(credential_store)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_parallel(
        self,
        calls: list[ToolCall],
        user_session: Any,
        conversation_id: str,
    ) -> list[ToolResult]:
        """Execute tool calls with automatic parallelism classification.

        Calls are grouped into batches via :meth:`_classify_parallelism`.
        Each batch runs concurrently; batches themselves run sequentially.
        """
        if not calls:
            return []

        batches = self._classify_parallelism(calls)
        results: list[ToolResult] = []
        for batch in batches:
            batch_results = await asyncio.gather(
                *(
                    self._guarded_execute(call, user_session, conversation_id)
                    for call in batch
                )
            )
            results.extend(batch_results)
        return results

    async def execute_sequential(
        self,
        calls: list[ToolCall],
        user_session: Any,
        conversation_id: str,
    ) -> list[ToolResult]:
        """Execute all tool calls one at a time, in order."""
        results: list[ToolResult] = []
        for call in calls:
            result = await self._guarded_execute(call, user_session, conversation_id)
            results.append(result)
        return results

    def _classify_parallelism(self, calls: list[ToolCall]) -> list[list[ToolCall]]:
        """Group tool calls into execution batches.

        Strategy:
        1. Look up each call's endpoint to determine its HTTP method and system.
        2. Calls to *different* systems are independent -- they go into the same
           parallel batch.
        3. Within a *single* system, read-only calls (GET/HEAD/OPTIONS) are
           independent.  Write calls (POST/PUT/PATCH/DELETE) must run
           sequentially to prevent data races.

        Because endpoint look-ups are async but this method is sync (used for
        planning before execution), we rely on the ``method`` hint stored in
        the call arguments under the key ``_method``, falling back to treating
        unknowns as writes (conservative).
        """
        if not calls:
            return []

        # Partition calls by system_id (from arguments hint or treat as unique).
        system_calls: dict[str, list[ToolCall]] = {}
        for call in calls:
            system_id = call.arguments.get("_system_id", call.endpoint_id)
            system_calls.setdefault(system_id, []).append(call)

        # Build ordered batches.
        # First batch: all reads across all systems + first write per system.
        # Subsequent batches: remaining writes (one per batch per system).
        batches: list[list[ToolCall]] = []
        remaining: dict[str, list[ToolCall]] = {}

        first_batch: list[ToolCall] = []
        for system_id, sys_calls in system_calls.items():
            reads: list[ToolCall] = []
            writes: list[ToolCall] = []
            for c in sys_calls:
                method = str(c.arguments.get("_method", "POST")).upper()
                if method in _READ_METHODS:
                    reads.append(c)
                else:
                    writes.append(c)

            # All reads can go in the first batch.
            first_batch.extend(reads)
            # First write per system can also go in the first batch.
            if writes:
                first_batch.append(writes[0])
                if len(writes) > 1:
                    remaining[system_id] = writes[1:]

        if first_batch:
            batches.append(first_batch)

        # Drain remaining writes one-per-system per batch.
        while remaining:
            batch: list[ToolCall] = []
            exhausted: list[str] = []
            for system_id, writes in remaining.items():
                batch.append(writes.pop(0))
                if not writes:
                    exhausted.append(system_id)
            for sid in exhausted:
                del remaining[sid]
            if batch:
                batches.append(batch)

        return batches

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _guarded_execute(
        self,
        call: ToolCall,
        user_session: Any,
        conversation_id: str,
    ) -> ToolResult:
        """Execute a single tool call, gated by the concurrency semaphore."""
        async with self._semaphore:
            return await self._execute_single(call, user_session, conversation_id)

    async def _execute_single(
        self,
        call: ToolCall,
        user_session: Any,
        conversation_id: str,
    ) -> ToolResult:
        """Look up endpoint/system, resolve auth, make HTTP request, log audit."""
        start = time.monotonic()

        # Look up endpoint and system from catalog.
        endpoint = await self._catalog_repo.get_endpoint(call.endpoint_id)
        if endpoint is None:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                data=None,
                error=f"Endpoint {call.endpoint_id} not found in catalog",
                duration_ms=round((time.monotonic() - start) * 1000, 1),
                status_code=None,
            )

        system = await self._catalog_repo.get_system(endpoint.system_id)
        if system is None:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                data=None,
                error=f"System {endpoint.system_id} not found in catalog",
                duration_ms=round((time.monotonic() - start) * 1000, 1),
                status_code=None,
            )

        # Audit: log the tool call *before* execution.
        user_id = (
            user_session.user_id
            if hasattr(user_session, "user_id")
            else str(user_session)
        )
        await self._audit_logger.log(
            AuditEvent(
                event_type=AuditEventType.TOOL_CALL,
                user_id=user_id,
                conversation_id=conversation_id,
                system_id=system.id,
                endpoint_id=endpoint.id,
                action=f"{endpoint.method} {endpoint.path}",
                detail={
                    "call_id": call.call_id,
                    "tool_name": call.tool_name,
                    "arguments": {
                        k: v
                        for k, v in call.arguments.items()
                        if not k.startswith("_")
                    },
                },
                risk_level=endpoint.risk_level.value,
            )
        )

        # Resolve auth headers.
        try:
            auth_headers = await self._auth_resolver.resolve_headers(system)
        except Exception as exc:
            return ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                data=None,
                error=f"Auth resolution failed: {exc}",
                duration_ms=round((time.monotonic() - start) * 1000, 1),
                status_code=None,
            )

        # Build URL with path-parameter substitution.
        path = endpoint.path
        path_params = call.arguments.get("path", {})
        for param_name, param_value in path_params.items():
            path = re.sub(
                r"\{" + re.escape(param_name) + r"\}",
                str(param_value),
                path,
            )

        url = system.base_url.rstrip("/") + "/" + path.lstrip("/")

        # Build request kwargs.
        query_params = call.arguments.get("query", {})
        body = call.arguments.get("body")

        request_kwargs: dict[str, Any] = {
            "method": endpoint.method.value,
            "url": url,
            "headers": auth_headers,
            "timeout": endpoint.timeout_seconds,
        }
        if query_params:
            request_kwargs["params"] = query_params
        if body is not None:
            request_kwargs["json"] = body

        # Execute the HTTP request.
        try:
            response = await self._http_client.request(**request_kwargs)
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)

            # Attempt to parse JSON; fall back to text.
            try:
                data = response.json()
            except Exception:
                data = response.text

            success = 200 <= response.status_code < 400
            error = None if success else f"HTTP {response.status_code}"

            result = ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=success,
                data=data,
                error=error,
                duration_ms=elapsed_ms,
                status_code=response.status_code,
            )
        except httpx.TimeoutException:
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            result = ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                data=None,
                error="Request timed out",
                duration_ms=elapsed_ms,
                status_code=None,
            )
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)
            result = ToolResult(
                call_id=call.call_id,
                tool_name=call.tool_name,
                success=False,
                data=None,
                error=str(exc),
                duration_ms=elapsed_ms,
                status_code=None,
            )

        # Audit: log the tool result.
        await self._audit_logger.log(
            AuditEvent(
                event_type=AuditEventType.TOOL_RESULT,
                user_id=user_id,
                conversation_id=conversation_id,
                system_id=system.id,
                endpoint_id=endpoint.id,
                action=f"{endpoint.method} {endpoint.path}",
                detail={
                    "call_id": call.call_id,
                    "tool_name": call.tool_name,
                    "success": result.success,
                    "status_code": result.status_code,
                    "duration_ms": result.duration_ms,
                    "error": result.error,
                },
                risk_level=endpoint.risk_level.value,
            )
        )

        return result
