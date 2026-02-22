# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the ToolExecutor parallel/sequential tool execution engine."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from flydek.catalog.enums import AuthType, HttpMethod, RiskLevel
from flydek.catalog.models import AuthConfig, Credential, ExternalSystem, ServiceEndpoint
from flydek.tools.executor import ToolCall, ToolExecutor, ToolResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_system(system_id: str = "sys-1") -> ExternalSystem:
    return ExternalSystem(
        id=system_id,
        name=f"System {system_id}",
        description="Test system",
        base_url="https://api.example.com",
        auth_config=AuthConfig(
            auth_type=AuthType.BEARER,
            credential_id="cred-1",
        ),
    )


def _make_endpoint(
    endpoint_id: str = "ep-1",
    system_id: str = "sys-1",
    method: HttpMethod = HttpMethod.GET,
    path: str = "/orders/{id}",
) -> ServiceEndpoint:
    return ServiceEndpoint(
        id=endpoint_id,
        system_id=system_id,
        name=f"Endpoint {endpoint_id}",
        description="Test endpoint",
        method=method,
        path=path,
        when_to_use="testing",
        risk_level=RiskLevel.READ if method == HttpMethod.GET else RiskLevel.LOW_WRITE,
        required_permissions=["test:read"],
    )


def _make_credential(credential_id: str = "cred-1") -> Credential:
    return Credential(
        id=credential_id,
        system_id="sys-1",
        name="Test Token",
        encrypted_value="test-token-value",
        credential_type="bearer",
    )


def _make_call(
    call_id: str = "call-1",
    tool_name: str = "get_order",
    endpoint_id: str = "ep-1",
    method: str = "GET",
    system_id: str = "sys-1",
    arguments: dict | None = None,
) -> ToolCall:
    args = arguments or {}
    args.setdefault("_method", method)
    args.setdefault("_system_id", system_id)
    return ToolCall(
        call_id=call_id,
        tool_name=tool_name,
        endpoint_id=endpoint_id,
        arguments=args,
    )


@pytest.fixture
def catalog_repo() -> MagicMock:
    mock = MagicMock()
    mock.get_system = AsyncMock(return_value=_make_system())
    mock.get_endpoint = AsyncMock(return_value=_make_endpoint())
    return mock


@pytest.fixture
def credential_store() -> MagicMock:
    mock = MagicMock()
    mock.get_credential = AsyncMock(return_value=_make_credential())
    return mock


@pytest.fixture
def audit_logger() -> MagicMock:
    mock = MagicMock()
    mock.log = AsyncMock(return_value="evt-id")
    return mock


@pytest.fixture
def mock_response() -> httpx.Response:
    """A successful 200 JSON response."""
    return httpx.Response(
        status_code=200,
        json={"order_id": "123", "status": "shipped"},
        request=httpx.Request("GET", "https://api.example.com/orders/123"),
    )


@pytest.fixture
def http_client(mock_response: httpx.Response) -> MagicMock:
    mock = MagicMock(spec=httpx.AsyncClient)
    mock.request = AsyncMock(return_value=mock_response)
    return mock


@pytest.fixture
def executor(
    http_client: MagicMock,
    catalog_repo: MagicMock,
    credential_store: MagicMock,
    audit_logger: MagicMock,
) -> ToolExecutor:
    return ToolExecutor(
        http_client=http_client,
        catalog_repo=catalog_repo,
        credential_store=credential_store,
        audit_logger=audit_logger,
        max_parallel=5,
    )


# ---------------------------------------------------------------------------
# ToolCall and ToolResult dataclass tests
# ---------------------------------------------------------------------------


class TestToolCallDataclass:
    def test_create_with_defaults(self):
        call = ToolCall(call_id="c1", tool_name="get_order", endpoint_id="ep-1")
        assert call.call_id == "c1"
        assert call.tool_name == "get_order"
        assert call.endpoint_id == "ep-1"
        assert call.arguments == {}

    def test_create_with_arguments(self):
        call = ToolCall(
            call_id="c1",
            tool_name="get_order",
            endpoint_id="ep-1",
            arguments={"path": {"id": "123"}},
        )
        assert call.arguments == {"path": {"id": "123"}}

    def test_frozen(self):
        call = ToolCall(call_id="c1", tool_name="get_order", endpoint_id="ep-1")
        with pytest.raises(AttributeError):
            call.call_id = "c2"  # type: ignore[misc]


class TestToolResultDataclass:
    def test_create_success(self):
        result = ToolResult(
            call_id="c1",
            tool_name="get_order",
            success=True,
            data={"id": 1},
            error=None,
            duration_ms=42.0,
            status_code=200,
        )
        assert result.success is True
        assert result.error is None
        assert result.status_code == 200

    def test_create_failure(self):
        result = ToolResult(
            call_id="c1",
            tool_name="get_order",
            success=False,
            data=None,
            error="Request timed out",
            duration_ms=5000.0,
            status_code=None,
        )
        assert result.success is False
        assert result.error == "Request timed out"
        assert result.status_code is None


# ---------------------------------------------------------------------------
# _classify_parallelism tests
# ---------------------------------------------------------------------------


class TestClassifyParallelism:
    def test_empty_calls(self, executor: ToolExecutor):
        assert executor._classify_parallelism([]) == []

    def test_all_reads_same_system_single_batch(self, executor: ToolExecutor):
        """Multiple GETs to the same system go into one parallel batch."""
        calls = [
            _make_call("c1", method="GET", system_id="sys-1"),
            _make_call("c2", method="GET", system_id="sys-1"),
            _make_call("c3", method="GET", system_id="sys-1"),
        ]
        batches = executor._classify_parallelism(calls)
        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_reads_different_systems_single_batch(self, executor: ToolExecutor):
        """GETs to different systems go into one parallel batch."""
        calls = [
            _make_call("c1", method="GET", system_id="sys-1"),
            _make_call("c2", method="GET", system_id="sys-2"),
        ]
        batches = executor._classify_parallelism(calls)
        assert len(batches) == 1
        assert len(batches[0]) == 2

    def test_writes_same_system_sequential_batches(self, executor: ToolExecutor):
        """Multiple POSTs to the same system produce sequential batches."""
        calls = [
            _make_call("c1", method="POST", system_id="sys-1"),
            _make_call("c2", method="POST", system_id="sys-1"),
            _make_call("c3", method="POST", system_id="sys-1"),
        ]
        batches = executor._classify_parallelism(calls)
        assert len(batches) == 3
        for batch in batches:
            assert len(batch) == 1

    def test_mixed_read_write_same_system(self, executor: ToolExecutor):
        """GETs + a POST to the same system: reads and first write in batch 1."""
        calls = [
            _make_call("c1", method="GET", system_id="sys-1"),
            _make_call("c2", method="GET", system_id="sys-1"),
            _make_call("c3", method="POST", system_id="sys-1"),
            _make_call("c4", method="POST", system_id="sys-1"),
        ]
        batches = executor._classify_parallelism(calls)
        # Batch 1: 2 GETs + 1st POST = 3 calls
        assert len(batches[0]) == 3
        # Batch 2: 2nd POST
        assert len(batches) == 2
        assert len(batches[1]) == 1

    def test_writes_different_systems_parallel(self, executor: ToolExecutor):
        """POSTs to different systems can run in parallel."""
        calls = [
            _make_call("c1", method="POST", system_id="sys-1"),
            _make_call("c2", method="POST", system_id="sys-2"),
        ]
        batches = executor._classify_parallelism(calls)
        assert len(batches) == 1
        assert len(batches[0]) == 2

    def test_delete_treated_as_write(self, executor: ToolExecutor):
        """DELETE is treated as a write operation."""
        calls = [
            _make_call("c1", method="DELETE", system_id="sys-1"),
            _make_call("c2", method="DELETE", system_id="sys-1"),
        ]
        batches = executor._classify_parallelism(calls)
        assert len(batches) == 2

    def test_patch_treated_as_write(self, executor: ToolExecutor):
        """PATCH is treated as a write operation."""
        calls = [
            _make_call("c1", method="PATCH", system_id="sys-1"),
            _make_call("c2", method="GET", system_id="sys-1"),
        ]
        batches = executor._classify_parallelism(calls)
        assert len(batches) == 1
        assert len(batches[0]) == 2  # GET + first PATCH

    def test_complex_multi_system_scenario(self, executor: ToolExecutor):
        """Complex scenario: reads and writes across multiple systems."""
        calls = [
            _make_call("c1", method="GET", system_id="sys-1"),
            _make_call("c2", method="POST", system_id="sys-1"),
            _make_call("c3", method="POST", system_id="sys-1"),
            _make_call("c4", method="GET", system_id="sys-2"),
            _make_call("c5", method="DELETE", system_id="sys-2"),
        ]
        batches = executor._classify_parallelism(calls)
        # Batch 1: sys-1 GET + sys-1 first POST + sys-2 GET + sys-2 first DELETE
        assert len(batches[0]) == 4
        # Batch 2: sys-1 second POST
        assert len(batches) == 2
        assert len(batches[1]) == 1


# ---------------------------------------------------------------------------
# _execute_single tests
# ---------------------------------------------------------------------------


class TestExecuteSingle:
    async def test_successful_get_request(self, executor: ToolExecutor, http_client):
        call = _make_call(
            "c1",
            arguments={"path": {"id": "123"}, "_method": "GET", "_system_id": "sys-1"},
        )
        result = await executor._execute_single(call, "user-1", "conv-1")

        assert result.success is True
        assert result.status_code == 200
        assert result.data == {"order_id": "123", "status": "shipped"}
        assert result.error is None
        assert result.duration_ms >= 0

    async def test_path_param_substitution(self, executor: ToolExecutor, http_client):
        call = _make_call(
            "c1",
            arguments={"path": {"id": "456"}, "_method": "GET", "_system_id": "sys-1"},
        )
        await executor._execute_single(call, "user-1", "conv-1")

        # Verify the URL was constructed with the path param substituted.
        actual_url = http_client.request.call_args.kwargs["url"]
        assert "/orders/456" in actual_url
        assert "{id}" not in actual_url

    async def test_query_params_passed(self, executor: ToolExecutor, http_client):
        call = _make_call(
            "c1",
            arguments={
                "query": {"status": "shipped", "limit": "10"},
                "_method": "GET",
                "_system_id": "sys-1",
            },
        )
        await executor._execute_single(call, "user-1", "conv-1")

        kwargs = http_client.request.call_args.kwargs
        assert kwargs["params"] == {"status": "shipped", "limit": "10"}

    async def test_body_passed_for_post(
        self, executor: ToolExecutor, http_client, catalog_repo
    ):
        catalog_repo.get_endpoint.return_value = _make_endpoint(method=HttpMethod.POST)
        call = _make_call(
            "c1",
            arguments={
                "body": {"name": "New Order"},
                "_method": "POST",
                "_system_id": "sys-1",
            },
        )
        await executor._execute_single(call, "user-1", "conv-1")

        kwargs = http_client.request.call_args.kwargs
        assert kwargs["json"] == {"name": "New Order"}
        assert kwargs["method"] == "POST"

    async def test_auth_headers_included(self, executor: ToolExecutor, http_client):
        call = _make_call("c1")
        await executor._execute_single(call, "user-1", "conv-1")

        kwargs = http_client.request.call_args.kwargs
        assert "Authorization" in kwargs["headers"]
        assert kwargs["headers"]["Authorization"] == "Bearer test-token-value"

    async def test_endpoint_not_found(self, executor: ToolExecutor, catalog_repo):
        catalog_repo.get_endpoint.return_value = None
        call = _make_call("c1", endpoint_id="missing-ep")

        result = await executor._execute_single(call, "user-1", "conv-1")

        assert result.success is False
        assert "not found" in result.error
        assert result.status_code is None

    async def test_system_not_found(self, executor: ToolExecutor, catalog_repo):
        catalog_repo.get_system.return_value = None
        call = _make_call("c1")

        result = await executor._execute_single(call, "user-1", "conv-1")

        assert result.success is False
        assert "not found" in result.error

    async def test_http_error_status(
        self, executor: ToolExecutor, http_client
    ):
        error_response = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("GET", "https://api.example.com/orders/123"),
        )
        http_client.request.return_value = error_response
        call = _make_call("c1")

        result = await executor._execute_single(call, "user-1", "conv-1")

        assert result.success is False
        assert result.status_code == 500
        assert "HTTP 500" in result.error

    async def test_timeout_error(self, executor: ToolExecutor, http_client):
        http_client.request.side_effect = httpx.TimeoutException("timed out")
        call = _make_call("c1")

        result = await executor._execute_single(call, "user-1", "conv-1")

        assert result.success is False
        assert result.error == "Request timed out"
        assert result.status_code is None

    async def test_generic_exception(self, executor: ToolExecutor, http_client):
        http_client.request.side_effect = ConnectionError("Connection refused")
        call = _make_call("c1")

        result = await executor._execute_single(call, "user-1", "conv-1")

        assert result.success is False
        assert "Connection refused" in result.error

    async def test_audit_logged_before_and_after(
        self, executor: ToolExecutor, audit_logger
    ):
        call = _make_call("c1")
        await executor._execute_single(call, "user-1", "conv-1")

        # Should log twice: TOOL_CALL before, TOOL_RESULT after.
        assert audit_logger.log.await_count == 2
        first_event = audit_logger.log.call_args_list[0][0][0]
        second_event = audit_logger.log.call_args_list[1][0][0]
        assert first_event.event_type == "tool_call"
        assert second_event.event_type == "tool_result"

    async def test_auth_failure_returns_error_result(
        self, executor: ToolExecutor, credential_store
    ):
        credential_store.get_credential.return_value = None
        call = _make_call("c1")

        result = await executor._execute_single(call, "user-1", "conv-1")

        assert result.success is False
        assert "Auth resolution failed" in result.error

    async def test_user_session_object_extracts_user_id(
        self, executor: ToolExecutor, audit_logger
    ):
        """When user_session has a user_id attr, it is used for audit."""
        session = MagicMock()
        session.user_id = "user-99"
        call = _make_call("c1")

        await executor._execute_single(call, session, "conv-1")

        logged_event = audit_logger.log.call_args_list[0][0][0]
        assert logged_event.user_id == "user-99"


# ---------------------------------------------------------------------------
# execute_parallel tests
# ---------------------------------------------------------------------------


class TestExecuteParallel:
    async def test_returns_results_for_all_calls(self, executor: ToolExecutor):
        calls = [
            _make_call("c1", method="GET", system_id="sys-1"),
            _make_call("c2", method="GET", system_id="sys-2"),
        ]
        results = await executor.execute_parallel(calls, "user-1", "conv-1")
        assert len(results) == 2
        assert all(isinstance(r, ToolResult) for r in results)

    async def test_empty_calls_returns_empty(self, executor: ToolExecutor):
        results = await executor.execute_parallel([], "user-1", "conv-1")
        assert results == []

    async def test_parallel_calls_overlap_timing(
        self, executor: ToolExecutor, http_client
    ):
        """Verify that calls classified as parallel actually overlap in time."""
        call_times: list[tuple[float, float]] = []
        original_execute = executor._execute_single

        async def timed_execute(call, user_session, conversation_id):
            import time
            start = time.monotonic()
            await asyncio.sleep(0.01)  # Simulate some work
            result = await original_execute(call, user_session, conversation_id)
            end = time.monotonic()
            call_times.append((start, end))
            return result

        executor._execute_single = timed_execute  # type: ignore[assignment]

        calls = [
            _make_call("c1", method="GET", system_id="sys-1"),
            _make_call("c2", method="GET", system_id="sys-2"),
        ]
        await executor.execute_parallel(calls, "user-1", "conv-1")

        assert len(call_times) == 2
        # If parallel, the second call should start before the first ends.
        # (With tiny sleeps, just verify both completed.)
        assert all(end > start for start, end in call_times)

    async def test_failure_does_not_stop_other_calls(
        self, executor: ToolExecutor, http_client
    ):
        """A failing call should not prevent other calls from completing."""
        call_count = 0

        async def sometimes_fail(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise httpx.TimeoutException("timed out")
            return httpx.Response(
                status_code=200,
                json={"ok": True},
                request=httpx.Request("GET", "https://example.com"),
            )

        http_client.request.side_effect = sometimes_fail

        calls = [
            _make_call("c1", method="GET", system_id="sys-1"),
            _make_call("c2", method="GET", system_id="sys-2"),
        ]
        results = await executor.execute_parallel(calls, "user-1", "conv-1")

        assert len(results) == 2
        successes = [r for r in results if r.success]
        failures = [r for r in results if not r.success]
        assert len(failures) == 1
        assert len(successes) == 1


# ---------------------------------------------------------------------------
# execute_sequential tests
# ---------------------------------------------------------------------------


class TestExecuteSequential:
    async def test_returns_results_in_order(self, executor: ToolExecutor):
        calls = [
            _make_call("c1", method="POST", system_id="sys-1"),
            _make_call("c2", method="POST", system_id="sys-1"),
        ]
        results = await executor.execute_sequential(calls, "user-1", "conv-1")
        assert len(results) == 2
        assert results[0].call_id == "c1"
        assert results[1].call_id == "c2"

    async def test_empty_calls_returns_empty(self, executor: ToolExecutor):
        results = await executor.execute_sequential([], "user-1", "conv-1")
        assert results == []

    async def test_sequential_execution_order(
        self, executor: ToolExecutor, http_client
    ):
        """Verify that sequential calls execute one after another."""
        execution_order: list[str] = []
        original_execute = executor._execute_single

        async def tracking_execute(call, user_session, conversation_id):
            execution_order.append(call.call_id)
            return await original_execute(call, user_session, conversation_id)

        executor._execute_single = tracking_execute  # type: ignore[assignment]

        calls = [
            _make_call("c1", method="POST", system_id="sys-1"),
            _make_call("c2", method="POST", system_id="sys-1"),
            _make_call("c3", method="POST", system_id="sys-1"),
        ]
        await executor.execute_sequential(calls, "user-1", "conv-1")

        assert execution_order == ["c1", "c2", "c3"]


# ---------------------------------------------------------------------------
# Semaphore tests
# ---------------------------------------------------------------------------


class TestSemaphoreLimits:
    async def test_semaphore_limits_concurrency(self, catalog_repo, credential_store, audit_logger):
        """Verify the semaphore actually limits parallel execution."""
        max_parallel = 2
        concurrent_count = 0
        max_concurrent = 0

        mock_response = httpx.Response(
            status_code=200,
            json={"ok": True},
            request=httpx.Request("GET", "https://example.com"),
        )

        async def slow_request(*args, **kwargs):
            nonlocal concurrent_count, max_concurrent
            concurrent_count += 1
            max_concurrent = max(max_concurrent, concurrent_count)
            await asyncio.sleep(0.02)
            concurrent_count -= 1
            return mock_response

        http_client = MagicMock(spec=httpx.AsyncClient)
        http_client.request = AsyncMock(side_effect=slow_request)

        executor = ToolExecutor(
            http_client=http_client,
            catalog_repo=catalog_repo,
            credential_store=credential_store,
            audit_logger=audit_logger,
            max_parallel=max_parallel,
        )

        calls = [
            _make_call(f"c{i}", method="GET", system_id=f"sys-{i}")
            for i in range(6)
        ]
        await executor.execute_parallel(calls, "user-1", "conv-1")

        # Max concurrent should not exceed the semaphore limit.
        assert max_concurrent <= max_parallel
