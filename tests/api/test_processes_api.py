# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the Processes REST API endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from flydesk.auth.models import UserSession
from flydesk.jobs.models import Job, JobStatus
from flydesk.processes.models import (
    BusinessProcess,
    ProcessDependency,
    ProcessSource,
    ProcessStatus,
    ProcessStep,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 1, 15, 12, 0, 0, tzinfo=timezone.utc)


def _make_user_session(*, permissions: list[str] | None = None) -> UserSession:
    """Build a UserSession for testing."""
    return UserSession(
        user_id="user-1",
        email="admin@example.com",
        display_name="Admin User",
        roles=["admin"],
        permissions=permissions or ["*"],
        tenant_id="tenant-1",
        session_id="sess-1",
        token_expires_at=datetime(2099, 1, 1, tzinfo=timezone.utc),
        raw_claims={},
    )


def _sample_step(step_id: str = "step-1", order: int = 0) -> ProcessStep:
    return ProcessStep(
        id=step_id,
        name=f"Step {step_id}",
        description="A test step",
        step_type="action",
        system_id="sys-1",
        endpoint_id="ep-1",
        order=order,
        inputs=["data"],
        outputs=["result"],
    )


def _sample_dependency() -> ProcessDependency:
    return ProcessDependency(
        source_step_id="step-1",
        target_step_id="step-2",
        condition="success",
    )


def _sample_process(
    process_id: str = "proc-1",
    *,
    status: ProcessStatus = ProcessStatus.DISCOVERED,
    with_steps: bool = True,
) -> BusinessProcess:
    steps = [_sample_step("step-1", 0), _sample_step("step-2", 1)] if with_steps else []
    deps = [_sample_dependency()] if with_steps else []
    return BusinessProcess(
        id=process_id,
        name=f"Process {process_id}",
        description="A test process",
        category="operations",
        steps=steps,
        dependencies=deps,
        source=ProcessSource.AUTO_DISCOVERED,
        confidence=0.85,
        status=status,
        tags=["test", "api"],
        created_at=_NOW,
        updated_at=_NOW,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_repo():
    """Return an AsyncMock that mimics ProcessRepository."""
    repo = AsyncMock()
    repo.list = AsyncMock(return_value=[])
    repo.get = AsyncMock(return_value=None)
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock(return_value=False)
    repo.update_step = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_engine():
    """Return an AsyncMock that mimics ProcessDiscoveryEngine."""
    engine = AsyncMock()
    job = Job(
        id="job-123",
        job_type="process_discovery",
        status=JobStatus.PENDING,
        created_at=_NOW,
        payload={"trigger": "test"},
    )
    engine.discover = AsyncMock(return_value=job)
    return engine


@pytest.fixture
def mock_job_runner():
    """Return a MagicMock that mimics JobRunner."""
    return MagicMock()


@pytest.fixture
async def admin_client(mock_repo, mock_engine, mock_job_runner):
    """AsyncClient with an admin user session and mocked dependencies."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.processes import get_process_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_process_repo] = lambda: mock_repo

        # Inject engine and runner on app.state
        app.state.discovery_engine = mock_engine
        app.state.job_runner = mock_job_runner

        # Inject admin user_session via middleware
        admin_session = _make_user_session()

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def operator_client(mock_repo, mock_engine, mock_job_runner):
    """AsyncClient with an operator user session (processes:read + processes:write)."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.processes import get_process_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_process_repo] = lambda: mock_repo
        app.state.discovery_engine = mock_engine
        app.state.job_runner = mock_job_runner

        operator_session = _make_user_session(
            permissions=["processes:read", "processes:write"]
        )

        async def _set_user(request, call_next):
            request.state.user_session = operator_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def viewer_client(mock_repo):
    """AsyncClient with a viewer user session (processes:read only)."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.processes import get_process_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_process_repo] = lambda: mock_repo

        viewer_session = _make_user_session(permissions=["processes:read"])

        async def _set_user(request, call_next):
            request.state.user_session = viewer_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.fixture
async def no_perm_client(mock_repo):
    """AsyncClient with no process permissions."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.processes import get_process_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_process_repo] = lambda: mock_repo

        no_perm_session = _make_user_session(permissions=["chat:send"])

        async def _set_user(request, call_next):
            request.state.user_session = no_perm_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


# ---------------------------------------------------------------------------
# List Processes
# ---------------------------------------------------------------------------


class TestListProcesses:
    async def test_list_empty(self, admin_client, mock_repo):
        """GET /api/processes returns empty list when no processes exist."""
        mock_repo.list.return_value = []
        response = await admin_client.get("/api/processes")
        assert response.status_code == 200
        assert response.json() == []

    async def test_list_returns_summaries(self, admin_client, mock_repo):
        """GET /api/processes returns process summaries."""
        mock_repo.list.return_value = [_sample_process("proc-1")]
        response = await admin_client.get("/api/processes")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == "proc-1"
        assert data[0]["name"] == "Process proc-1"
        assert data[0]["step_count"] == 2
        # Summaries should NOT include full steps/dependencies
        assert "steps" not in data[0]
        assert "dependencies" not in data[0]

    async def test_list_with_category_filter(self, admin_client, mock_repo):
        """GET /api/processes?category=operations passes category to repo."""
        mock_repo.list.return_value = []
        response = await admin_client.get(
            "/api/processes", params={"category": "operations"}
        )
        assert response.status_code == 200
        mock_repo.list.assert_awaited_once()
        call_kwargs = mock_repo.list.call_args.kwargs
        assert call_kwargs["category"] == "operations"

    async def test_list_with_status_filter(self, admin_client, mock_repo):
        """GET /api/processes?status=verified passes status to repo."""
        mock_repo.list.return_value = []
        response = await admin_client.get(
            "/api/processes", params={"status": "verified"}
        )
        assert response.status_code == 200
        call_kwargs = mock_repo.list.call_args.kwargs
        assert call_kwargs["status"] == ProcessStatus.VERIFIED

    async def test_list_with_tag_filter(self, admin_client, mock_repo):
        """GET /api/processes?tag=test passes tag to repo."""
        mock_repo.list.return_value = []
        response = await admin_client.get(
            "/api/processes", params={"tag": "test"}
        )
        assert response.status_code == 200
        call_kwargs = mock_repo.list.call_args.kwargs
        assert call_kwargs["tag"] == "test"

    async def test_list_invalid_status(self, admin_client, mock_repo):
        """GET /api/processes?status=bogus returns 400."""
        response = await admin_client.get(
            "/api/processes", params={"status": "bogus"}
        )
        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    async def test_list_with_limit_and_offset(self, admin_client, mock_repo):
        """GET /api/processes?limit=10&offset=5 passes pagination to repo."""
        mock_repo.list.return_value = []
        response = await admin_client.get(
            "/api/processes", params={"limit": 10, "offset": 5}
        )
        assert response.status_code == 200
        call_kwargs = mock_repo.list.call_args.kwargs
        assert call_kwargs["limit"] == 10
        assert call_kwargs["offset"] == 5


# ---------------------------------------------------------------------------
# Get Process
# ---------------------------------------------------------------------------


class TestGetProcess:
    async def test_get_process_found(self, admin_client, mock_repo):
        """GET /api/processes/{id} returns full detail with steps and deps."""
        proc = _sample_process("proc-1")
        mock_repo.get.return_value = proc
        response = await admin_client.get("/api/processes/proc-1")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "proc-1"
        assert len(data["steps"]) == 2
        assert len(data["dependencies"]) == 1
        assert data["steps"][0]["name"] == "Step step-1"
        assert data["dependencies"][0]["source_step_id"] == "step-1"

    async def test_get_process_not_found(self, admin_client, mock_repo):
        """GET /api/processes/{id} returns 404 for unknown process."""
        mock_repo.get.return_value = None
        response = await admin_client.get("/api/processes/nonexistent")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Update Process
# ---------------------------------------------------------------------------


class TestUpdateProcess:
    async def test_update_process_success(self, admin_client, mock_repo):
        """PUT /api/processes/{id} updates a process and returns it."""
        proc = _sample_process("proc-1")
        mock_repo.get.return_value = proc
        updated = _sample_process("proc-1")
        updated.name = "Updated Name"
        mock_repo.update.return_value = updated

        response = await admin_client.put(
            "/api/processes/proc-1",
            json=proc.model_dump(mode="json"),
        )
        assert response.status_code == 200
        mock_repo.update.assert_awaited_once()

    async def test_update_process_not_found(self, admin_client, mock_repo):
        """PUT /api/processes/{id} returns 404 for unknown process."""
        mock_repo.get.return_value = None
        proc = _sample_process("proc-1")
        response = await admin_client.put(
            "/api/processes/proc-1",
            json=proc.model_dump(mode="json"),
        )
        assert response.status_code == 404

    async def test_update_process_overrides_id_from_path(self, admin_client, mock_repo):
        """PUT /api/processes/{id} ensures path ID is used."""
        proc = _sample_process("proc-wrong-id")
        mock_repo.get.return_value = _sample_process("proc-1")
        mock_repo.update.return_value = _sample_process("proc-1")

        response = await admin_client.put(
            "/api/processes/proc-1",
            json=proc.model_dump(mode="json"),
        )
        assert response.status_code == 200
        call_args = mock_repo.update.call_args[0][0]
        assert call_args.id == "proc-1"


# ---------------------------------------------------------------------------
# Delete Process
# ---------------------------------------------------------------------------


class TestDeleteProcess:
    async def test_delete_process_success(self, admin_client, mock_repo):
        """DELETE /api/processes/{id} returns 204 on success."""
        mock_repo.delete.return_value = True
        response = await admin_client.delete("/api/processes/proc-1")
        assert response.status_code == 204
        mock_repo.delete.assert_awaited_once_with("proc-1")

    async def test_delete_process_not_found(self, admin_client, mock_repo):
        """DELETE /api/processes/{id} returns 404 for unknown process."""
        mock_repo.delete.return_value = False
        response = await admin_client.delete("/api/processes/nonexistent")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Trigger Discovery
# ---------------------------------------------------------------------------


class TestTriggerDiscovery:
    async def test_trigger_discovery_returns_job(self, admin_client, mock_engine):
        """POST /api/processes/discover returns job ID."""
        response = await admin_client.post(
            "/api/processes/discover",
            json={"trigger": "New CRM added"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == "job-123"
        assert data["status"] == "pending"
        mock_engine.discover.assert_awaited_once()

    async def test_trigger_discovery_empty_trigger(self, admin_client, mock_engine):
        """POST /api/processes/discover with empty trigger still works."""
        response = await admin_client.post(
            "/api/processes/discover",
            json={"trigger": ""},
        )
        assert response.status_code == 200
        assert "job_id" in response.json()

    async def test_trigger_discovery_no_body(self, admin_client, mock_engine):
        """POST /api/processes/discover with no body uses empty trigger."""
        response = await admin_client.post("/api/processes/discover")
        assert response.status_code == 200
        assert "job_id" in response.json()


# ---------------------------------------------------------------------------
# Update Step
# ---------------------------------------------------------------------------


class TestUpdateStep:
    async def test_update_step_success(self, admin_client, mock_repo):
        """PUT /api/processes/{id}/steps/{step_id} updates a step."""
        proc = _sample_process("proc-1")
        mock_repo.get.return_value = proc
        mock_repo.update_step.return_value = _sample_step("step-1")

        step_data = {
            "name": "Updated Step",
            "description": "Updated description",
            "step_type": "decision",
            "order": 0,
            "inputs": ["input1"],
            "outputs": ["output1"],
        }
        response = await admin_client.put(
            "/api/processes/proc-1/steps/step-1",
            json=step_data,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "step-1"
        mock_repo.update_step.assert_awaited_once()

    async def test_update_step_process_not_found(self, admin_client, mock_repo):
        """PUT /api/processes/{id}/steps/{step_id} returns 404 if process missing."""
        mock_repo.get.return_value = None
        step_data = {"name": "Test", "description": "desc"}
        response = await admin_client.put(
            "/api/processes/nonexistent/steps/step-1",
            json=step_data,
        )
        assert response.status_code == 404

    async def test_update_step_repo_returns_none(self, admin_client, mock_repo):
        """PUT /api/processes/{id}/steps/{step_id} returns 404 if repo returns None."""
        mock_repo.get.return_value = _sample_process("proc-1")
        mock_repo.update_step.return_value = None
        step_data = {"name": "Test", "description": "desc"}
        response = await admin_client.put(
            "/api/processes/proc-1/steps/step-1",
            json=step_data,
        )
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Verify Process
# ---------------------------------------------------------------------------


class TestVerifyProcess:
    async def test_verify_process_success(self, admin_client, mock_repo):
        """POST /api/processes/{id}/verify sets status to VERIFIED."""
        proc = _sample_process("proc-1", status=ProcessStatus.DISCOVERED)
        mock_repo.get.return_value = proc
        # The repo.update should return the updated process
        verified = _sample_process("proc-1", status=ProcessStatus.VERIFIED)
        mock_repo.update.return_value = verified

        response = await admin_client.post("/api/processes/proc-1/verify")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "verified"
        mock_repo.update.assert_awaited_once()
        # The process passed to update should have VERIFIED status
        call_arg = mock_repo.update.call_args[0][0]
        assert call_arg.status == ProcessStatus.VERIFIED

    async def test_verify_process_not_found(self, admin_client, mock_repo):
        """POST /api/processes/{id}/verify returns 404 for unknown process."""
        mock_repo.get.return_value = None
        response = await admin_client.post("/api/processes/nonexistent/verify")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# RBAC: Operator access (read + write)
# ---------------------------------------------------------------------------


class TestOperatorAccess:
    async def test_operator_can_list_processes(self, operator_client, mock_repo):
        """Operator with processes:read can list processes."""
        mock_repo.list.return_value = []
        response = await operator_client.get("/api/processes")
        assert response.status_code == 200

    async def test_operator_can_get_process(self, operator_client, mock_repo):
        """Operator with processes:read can get a process."""
        mock_repo.get.return_value = _sample_process("proc-1")
        response = await operator_client.get("/api/processes/proc-1")
        assert response.status_code == 200

    async def test_operator_can_delete_process(self, operator_client, mock_repo):
        """Operator with processes:write can delete a process."""
        mock_repo.delete.return_value = True
        response = await operator_client.delete("/api/processes/proc-1")
        assert response.status_code == 204

    async def test_operator_can_verify(self, operator_client, mock_repo):
        """Operator with processes:write can verify a process."""
        proc = _sample_process("proc-1")
        mock_repo.get.return_value = proc
        mock_repo.update.return_value = _sample_process(
            "proc-1", status=ProcessStatus.VERIFIED
        )
        response = await operator_client.post("/api/processes/proc-1/verify")
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# RBAC: Viewer access (read only)
# ---------------------------------------------------------------------------


class TestViewerAccess:
    async def test_viewer_can_list_processes(self, viewer_client, mock_repo):
        """Viewer with processes:read can list processes."""
        mock_repo.list.return_value = []
        response = await viewer_client.get("/api/processes")
        assert response.status_code == 200

    async def test_viewer_can_get_process(self, viewer_client, mock_repo):
        """Viewer with processes:read can get a process."""
        mock_repo.get.return_value = _sample_process("proc-1")
        response = await viewer_client.get("/api/processes/proc-1")
        assert response.status_code == 200

    async def test_viewer_cannot_update_process(self, viewer_client, mock_repo):
        """Viewer without processes:write cannot update a process."""
        proc = _sample_process("proc-1")
        response = await viewer_client.put(
            "/api/processes/proc-1",
            json=proc.model_dump(mode="json"),
        )
        assert response.status_code == 403

    async def test_viewer_cannot_delete_process(self, viewer_client, mock_repo):
        """Viewer without processes:write cannot delete a process."""
        response = await viewer_client.delete("/api/processes/proc-1")
        assert response.status_code == 403

    async def test_viewer_cannot_trigger_discovery(self, viewer_client):
        """Viewer without processes:write cannot trigger discovery."""
        response = await viewer_client.post(
            "/api/processes/discover", json={"trigger": "test"}
        )
        assert response.status_code == 403

    async def test_viewer_cannot_update_step(self, viewer_client, mock_repo):
        """Viewer without processes:write cannot update a step."""
        response = await viewer_client.put(
            "/api/processes/proc-1/steps/step-1",
            json={"name": "Updated"},
        )
        assert response.status_code == 403

    async def test_viewer_cannot_verify(self, viewer_client, mock_repo):
        """Viewer without processes:write cannot verify a process."""
        response = await viewer_client.post("/api/processes/proc-1/verify")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# RBAC: No permissions
# ---------------------------------------------------------------------------


class TestNoPermAccess:
    async def test_no_perm_cannot_list_processes(self, no_perm_client):
        """User without processes:read cannot list processes."""
        response = await no_perm_client.get("/api/processes")
        assert response.status_code == 403

    async def test_no_perm_cannot_get_process(self, no_perm_client):
        """User without processes:read cannot get a process."""
        response = await no_perm_client.get("/api/processes/proc-1")
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Settings: auto_analyze toggle
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_settings_repo():
    """Return an AsyncMock that mimics SettingsRepository."""
    repo = AsyncMock()
    repo.get_all_app_settings = AsyncMock(return_value={})
    repo.set_app_setting = AsyncMock(return_value=None)
    repo.get_app_setting = AsyncMock(return_value=None)
    return repo


@pytest.fixture
async def settings_client(mock_settings_repo):
    """AsyncClient with an admin session and mocked SettingsRepository."""
    env = {
        "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///:memory:",
        "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
        "FLYDESK_OIDC_CLIENT_ID": "test",
        "FLYDESK_OIDC_CLIENT_SECRET": "test",
        "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
    }
    with patch.dict(os.environ, env):
        from flydesk.api.settings import get_settings_repo
        from flydesk.server import create_app

        app = create_app()
        app.dependency_overrides[get_settings_repo] = lambda: mock_settings_repo

        admin_session = _make_user_session()

        async def _set_user(request, call_next):
            request.state.user_session = admin_session
            return await call_next(request)

        from starlette.middleware.base import BaseHTTPMiddleware

        app.add_middleware(BaseHTTPMiddleware, dispatch=_set_user)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


class TestAnalysisSettings:
    async def test_get_analysis_config_default(self, settings_client, mock_settings_repo):
        """GET /api/settings/analysis returns default auto_analyze=false."""
        mock_settings_repo.get_all_app_settings.return_value = {}
        response = await settings_client.get("/api/settings/analysis")
        assert response.status_code == 200
        data = response.json()
        assert data["auto_analyze"] is False

    async def test_get_analysis_config_enabled(self, settings_client, mock_settings_repo):
        """GET /api/settings/analysis returns true when stored as 'true'."""
        mock_settings_repo.get_all_app_settings.return_value = {"auto_analyze": "true"}
        response = await settings_client.get("/api/settings/analysis")
        assert response.status_code == 200
        data = response.json()
        assert data["auto_analyze"] is True

    async def test_update_analysis_config(self, settings_client, mock_settings_repo):
        """PUT /api/settings/analysis updates auto_analyze toggle."""
        response = await settings_client.put(
            "/api/settings/analysis",
            json={"auto_analyze": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["auto_analyze"] is True
        mock_settings_repo.set_app_setting.assert_awaited_once_with(
            "auto_analyze", "true", category="analysis"
        )


# ---------------------------------------------------------------------------
# Serialization checks
# ---------------------------------------------------------------------------


class TestSerialization:
    async def test_process_detail_includes_timestamps(self, admin_client, mock_repo):
        """Process detail includes ISO-formatted timestamps."""
        proc = _sample_process("proc-1")
        mock_repo.get.return_value = proc
        response = await admin_client.get("/api/processes/proc-1")
        data = response.json()
        assert data["created_at"] is not None
        assert "2026-01-15" in data["created_at"]

    async def test_process_summary_includes_step_count(self, admin_client, mock_repo):
        """Process summary includes step_count field."""
        mock_repo.list.return_value = [_sample_process("proc-1")]
        response = await admin_client.get("/api/processes")
        data = response.json()
        assert data[0]["step_count"] == 2

    async def test_step_detail_includes_all_fields(self, admin_client, mock_repo):
        """Step in process detail includes all expected fields."""
        proc = _sample_process("proc-1")
        mock_repo.get.return_value = proc
        response = await admin_client.get("/api/processes/proc-1")
        step = response.json()["steps"][0]
        assert "id" in step
        assert "name" in step
        assert "description" in step
        assert "step_type" in step
        assert "system_id" in step
        assert "endpoint_id" in step
        assert "order" in step
        assert "inputs" in step
        assert "outputs" in step

    async def test_dependency_includes_all_fields(self, admin_client, mock_repo):
        """Dependency in process detail includes all expected fields."""
        proc = _sample_process("proc-1")
        mock_repo.get.return_value = proc
        response = await admin_client.get("/api/processes/proc-1")
        dep = response.json()["dependencies"][0]
        assert dep["source_step_id"] == "step-1"
        assert dep["target_step_id"] == "step-2"
        assert dep["condition"] == "success"

    async def test_process_with_no_steps(self, admin_client, mock_repo):
        """Process detail works correctly with empty steps/dependencies."""
        proc = _sample_process("proc-1", with_steps=False)
        mock_repo.get.return_value = proc
        response = await admin_client.get("/api/processes/proc-1")
        data = response.json()
        assert data["steps"] == []
        assert data["dependencies"] == []
