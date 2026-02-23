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
import random
import re
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx

from flydesk.audit.models import AuditEvent, AuditEventType
from flydesk.tools.auth_resolver import AuthResolver

if TYPE_CHECKING:
    from flydesk.api.credentials import CredentialStore
    from flydesk.auth.models import UserSession
    from flydesk.auth.sso_mapping import SSOAttributeMapping
    from flydesk.audit.logger import AuditLogger
    from flydesk.catalog.models import RateLimit, RetryPolicy
    from flydesk.catalog.repository import CatalogRepository

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


# ---------------------------------------------------------------------------
# Rate limiter (in-memory token bucket per endpoint)
# ---------------------------------------------------------------------------


class _RateLimiter:
    """In-memory token bucket rate limiter keyed by endpoint ID."""

    def __init__(self) -> None:
        self._buckets: dict[str, dict[str, float]] = defaultdict(
            lambda: {"tokens": 0.0, "last_refill": 0.0, "max_tokens": 0.0, "refill_rate": 0.0}
        )

    def configure(self, endpoint_id: str, rate_limit: RateLimit) -> None:
        bucket = self._buckets[endpoint_id]
        bucket["max_tokens"] = float(rate_limit.max_requests)
        bucket["refill_rate"] = rate_limit.max_requests / rate_limit.window_seconds
        if bucket["last_refill"] == 0.0:
            bucket["tokens"] = float(rate_limit.max_requests)
            bucket["last_refill"] = time.monotonic()

    async def acquire(self, endpoint_id: str) -> None:
        """Wait until a token is available for the given endpoint."""
        bucket = self._buckets.get(endpoint_id)
        if bucket is None or bucket["max_tokens"] == 0.0:
            return

        while True:
            now = time.monotonic()
            elapsed = now - bucket["last_refill"]
            bucket["tokens"] = min(
                bucket["max_tokens"],
                bucket["tokens"] + elapsed * bucket["refill_rate"],
            )
            bucket["last_refill"] = now

            if bucket["tokens"] >= 1.0:
                bucket["tokens"] -= 1.0
                return

            wait = (1.0 - bucket["tokens"]) / bucket["refill_rate"]
            await asyncio.sleep(wait)


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


def _parse_response(response: httpx.Response) -> Any:
    """Parse response body based on Content-Type header."""
    content_type = response.headers.get("content-type", "")

    # JSON
    if "json" in content_type or "javascript" in content_type:
        try:
            return response.json()
        except Exception:
            return response.text

    # XML / SOAP
    if "xml" in content_type:
        try:
            return _xml_to_dict(ET.fromstring(response.text))
        except Exception:
            return response.text

    # CSV
    if "csv" in content_type:
        return _parse_csv(response.text)

    # Default: try JSON first, fall back to text
    try:
        return response.json()
    except Exception:
        return response.text


def _xml_to_dict(element: ET.Element) -> dict[str, Any]:
    """Recursively convert an XML element to a dict."""
    tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
    result: dict[str, Any] = {}
    if element.attrib:
        result["@attributes"] = dict(element.attrib)
    children: dict[str, list[Any]] = defaultdict(list)
    for child in element:
        child_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        children[child_tag].append(_xml_to_dict(child))
    for k, v in children.items():
        result[k] = v[0] if len(v) == 1 else v
    if element.text and element.text.strip():
        if result:
            result["#text"] = element.text.strip()
        else:
            return {tag: element.text.strip()}
    if not result:
        return {tag: None}
    return {tag: result}


def _parse_csv(text: str) -> list[dict[str, str]]:
    """Parse CSV text into a list of dicts using the first row as headers."""
    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if len(lines) < 2:
        return [{"raw": text}]
    headers = [h.strip().strip('"') for h in lines[0].split(",")]
    rows: list[dict[str, str]] = []
    for line in lines[1:]:
        values = [v.strip().strip('"') for v in line.split(",")]
        rows.append(dict(zip(headers, values)))
    return rows


# ---------------------------------------------------------------------------
# Retry helper
# ---------------------------------------------------------------------------

# Status codes that are safe to retry.
_RETRYABLE_STATUS_CODES = frozenset({429, 502, 503, 504})


async def _execute_with_retry(
    http_client: httpx.AsyncClient,
    request_kwargs: dict[str, Any],
    retry_policy: RetryPolicy | None,
    rate_limiter: _RateLimiter,
    endpoint_id: str,
) -> httpx.Response:
    """Execute HTTP request with retry/backoff and rate limiting."""
    max_retries = retry_policy.max_retries if retry_policy else 0
    backoff_factor = retry_policy.backoff_factor if retry_policy else 1.0

    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        await rate_limiter.acquire(endpoint_id)

        try:
            response = await http_client.request(**request_kwargs)

            if response.status_code not in _RETRYABLE_STATUS_CODES or attempt == max_retries:
                return response

            # Retryable status code — apply backoff
            if response.status_code == 429:
                retry_after = response.headers.get("retry-after")
                if retry_after:
                    try:
                        wait = float(retry_after)
                    except ValueError:
                        wait = backoff_factor * (2 ** attempt)
                else:
                    wait = backoff_factor * (2 ** attempt)
            else:
                wait = backoff_factor * (2 ** attempt)

            jitter = random.uniform(0, wait * 0.25)
            logger.info(
                "Retrying %s (attempt %d/%d, status=%d, wait=%.1fs)",
                request_kwargs.get("url"),
                attempt + 1,
                max_retries,
                response.status_code,
                wait + jitter,
            )
            await asyncio.sleep(wait + jitter)

        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exc = exc
            if attempt == max_retries:
                raise
            wait = backoff_factor * (2 ** attempt)
            jitter = random.uniform(0, wait * 0.25)
            logger.info(
                "Retrying %s (attempt %d/%d, error=%s, wait=%.1fs)",
                request_kwargs.get("url"),
                attempt + 1,
                max_retries,
                exc,
                wait + jitter,
            )
            await asyncio.sleep(wait + jitter)

    # Should not reach here, but just in case
    if last_exc:
        raise last_exc
    raise RuntimeError("Retry loop completed without result")


class ToolExecutor:
    """Execute external tool calls with configurable parallelism.

    Parallelism heuristic:
    - Calls to **different** systems are independent and run in parallel.
    - Within the **same** system, read-only calls (GET) run in parallel while
      write calls (POST/PUT/PATCH/DELETE) are sequential to avoid conflicts.
    - A global :class:`asyncio.Semaphore` limits total concurrency.

    Supports retry with exponential backoff+jitter via endpoint RetryPolicy,
    per-endpoint rate limiting via RateLimit, and multi-format response parsing
    (JSON, XML, CSV).
    """

    def __init__(
        self,
        http_client: httpx.AsyncClient,
        catalog_repo: CatalogRepository,
        credential_store: CredentialStore,
        audit_logger: AuditLogger,
        max_parallel: int = 5,
        kms: Any | None = None,
        sso_mappings: list[SSOAttributeMapping] | None = None,
    ) -> None:
        self._http_client = http_client
        self._catalog_repo = catalog_repo
        self._credential_store = credential_store
        self._audit_logger = audit_logger
        self._semaphore = asyncio.Semaphore(max_parallel)
        self._auth_resolver = AuthResolver(
            credential_store, http_client=http_client, kms=kms
        )
        self._rate_limiter = _RateLimiter()
        self._sso_mappings: list[SSOAttributeMapping] = sso_mappings or []

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

        # Resolve auth headers (with optional SSO claim forwarding).
        _user_session_obj = (
            user_session
            if hasattr(user_session, "raw_claims")
            else None
        )
        try:
            auth_headers = await self._auth_resolver.resolve_headers(
                system,
                user_session=_user_session_obj,
                sso_mappings=self._sso_mappings or None,
            )
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

        # Configure rate limiter if endpoint has rate limiting.
        if endpoint.rate_limit:
            self._rate_limiter.configure(endpoint.id, endpoint.rate_limit)

        # Build protocol-specific request.
        request_kwargs = self._build_request(endpoint, system, call, auth_headers)

        # Execute the HTTP request with retry and rate limiting.
        try:
            response = await _execute_with_retry(
                self._http_client,
                request_kwargs,
                endpoint.retry_policy,
                self._rate_limiter,
                endpoint.id,
            )
            elapsed_ms = round((time.monotonic() - start) * 1000, 1)

            data = _parse_response(response)

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

    # ------------------------------------------------------------------
    # Protocol-specific request builders
    # ------------------------------------------------------------------

    def _resolve_url(self, endpoint: Any, system: Any, call: ToolCall) -> str:
        """Build URL with path-parameter substitution."""
        path = endpoint.path
        path_params = call.arguments.get("path", {})
        for param_name, param_value in path_params.items():
            path = re.sub(
                r"\{" + re.escape(param_name) + r"\}",
                str(param_value),
                path,
            )
        return system.base_url.rstrip("/") + "/" + path.lstrip("/")

    def _build_request(
        self,
        endpoint: Any,
        system: Any,
        call: ToolCall,
        auth_headers: dict[str, str],
    ) -> dict[str, Any]:
        """Build protocol-specific HTTP request kwargs."""
        protocol = getattr(endpoint, "protocol_type", "rest")

        if protocol == "graphql":
            return self._build_graphql_request(endpoint, system, call, auth_headers)
        if protocol == "soap":
            return self._build_soap_request(endpoint, system, call, auth_headers)
        if protocol == "grpc":
            return self._build_grpc_request(endpoint, system, call, auth_headers)
        return self._build_rest_request(endpoint, system, call, auth_headers)

    def _build_rest_request(
        self,
        endpoint: Any,
        system: Any,
        call: ToolCall,
        auth_headers: dict[str, str],
    ) -> dict[str, Any]:
        """Build HTTP request kwargs for a REST endpoint."""
        url = self._resolve_url(endpoint, system, call)
        query_params = call.arguments.get("query", {})
        body = call.arguments.get("body")

        kwargs: dict[str, Any] = {
            "method": endpoint.method.value,
            "url": url,
            "headers": auth_headers,
            "timeout": endpoint.timeout_seconds,
        }
        if query_params:
            kwargs["params"] = query_params
        if body is not None:
            kwargs["json"] = body
        return kwargs

    def _build_graphql_request(
        self,
        endpoint: Any,
        system: Any,
        call: ToolCall,
        auth_headers: dict[str, str],
    ) -> dict[str, Any]:
        """Build HTTP request kwargs for a GraphQL endpoint.

        Sends a POST with ``{"query": ..., "variables": ..., "operationName": ...}``
        regardless of the endpoint's declared HTTP method.
        """
        url = self._resolve_url(endpoint, system, call)
        variables = call.arguments.get("body", {})

        graphql_body: dict[str, Any] = {"query": endpoint.graphql_query or ""}
        if variables:
            graphql_body["variables"] = variables
        if endpoint.graphql_operation_name:
            graphql_body["operationName"] = endpoint.graphql_operation_name

        return {
            "method": "POST",
            "url": url,
            "headers": {**auth_headers, "Content-Type": "application/json"},
            "json": graphql_body,
            "timeout": endpoint.timeout_seconds,
        }

    def _build_soap_request(
        self,
        endpoint: Any,
        system: Any,
        call: ToolCall,
        auth_headers: dict[str, str],
    ) -> dict[str, Any]:
        """Build HTTP request kwargs for a SOAP endpoint.

        Renders ``soap_body_template`` with ``{placeholder}`` substitution from
        call arguments, sets ``Content-Type: text/xml`` and optional ``SOAPAction``
        header.
        """
        url = self._resolve_url(endpoint, system, call)

        body_template = endpoint.soap_body_template or ""
        body_params = call.arguments.get("body", {})
        soap_body = body_template
        for key, value in body_params.items():
            soap_body = soap_body.replace("{" + key + "}", str(value))

        headers = {
            **auth_headers,
            "Content-Type": "text/xml; charset=utf-8",
        }
        if endpoint.soap_action:
            headers["SOAPAction"] = endpoint.soap_action

        return {
            "method": "POST",
            "url": url,
            "headers": headers,
            "content": soap_body.encode("utf-8"),
            "timeout": endpoint.timeout_seconds,
        }

    def _build_grpc_request(
        self,
        endpoint: Any,
        system: Any,
        call: ToolCall,
        auth_headers: dict[str, str],
    ) -> dict[str, Any]:
        """Build HTTP request kwargs for gRPC via JSON transcoding (gRPC-Web).

        Constructs URL as ``{base_url}/{grpc_service}/{grpc_method_name}`` and
        sends a JSON-encoded POST body.
        """
        service = endpoint.grpc_service or ""
        method_name = endpoint.grpc_method_name or ""
        base = system.base_url.rstrip("/")
        url = f"{base}/{service}/{method_name}"

        body = call.arguments.get("body", {})

        return {
            "method": "POST",
            "url": url,
            "headers": {**auth_headers, "Content-Type": "application/json"},
            "json": body,
            "timeout": endpoint.timeout_seconds,
        }
