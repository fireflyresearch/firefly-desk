# Admin Overhaul Tier 1: Whitelist Enforcement & System Catalog Wizard

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Add agent call whitelisting (whitelist-by-default mode with `agent_enabled` per system, URL enforcement in executor) and replace the flat catalog form with a 4-step system creation wizard.

**Architecture:** New `agent_enabled: bool` column on `ExternalSystemRow` + `tool_access_mode` app setting filter tools at the `ToolFactory` layer. URL enforcement guard in `ToolExecutor._resolve_url()` blocks path-parameter injection attacks. Frontend replaces `CatalogManager.svelte`'s inline form with a multi-step `SystemWizard.svelte` component.

**Tech Stack:** Python 3.13, SQLAlchemy 2 (async), FastAPI, Pydantic v2, Svelte 5 (runes), TailwindCSS

**Design doc:** `docs/plans/2026-02-24-admin-overhaul-design.md`

---

## Task 1: Add `agent_enabled` Column to ORM

Add `agent_enabled: bool = False` column to `ExternalSystemRow`. This is the foundation for whitelist filtering — systems must be explicitly enabled for agent access.

**Files:**
- Modify: `src/flydesk/models/catalog.py:29-46`
- Modify: `src/flydesk/catalog/models.py:53-64`
- Modify: `src/flydesk/catalog/repository.py:53-99,365-376`
- Test: `tests/catalog/test_orm.py`

**Step 1: Write failing test**

Add a test to `tests/catalog/test_orm.py` that verifies the new column exists and defaults to `False`:

```python
def test_external_system_row_agent_enabled_defaults_false(session_factory):
    """agent_enabled column exists and defaults to False."""
    from flydesk.models.catalog import ExternalSystemRow

    row = ExternalSystemRow(
        id="test-sys",
        name="Test",
        description="Test system",
        base_url="https://example.com",
        auth_config='{"auth_type": "bearer", "credential_id": "c1"}',
        tags="[]",
        status="active",
        metadata_="{}",
    )
    assert row.agent_enabled is False
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/catalog/test_orm.py::test_external_system_row_agent_enabled_defaults_false -v
```

Expected: `AttributeError: agent_enabled` — column doesn't exist yet.

**Step 3: Add column to ORM model**

In `src/flydesk/models/catalog.py`, add after line 41 (`tags` column):

```python
agent_enabled: Mapped[bool] = mapped_column(default=False)
```

**Step 4: Add field to Pydantic domain model**

In `src/flydesk/catalog/models.py`, add to `ExternalSystem` class after `metadata` field (line 64):

```python
agent_enabled: bool = False
```

**Step 5: Update repository create/update/mapping**

In `src/flydesk/catalog/repository.py`:

1. In `create_system()` (line 56-68), add to the `ExternalSystemRow(...)` constructor:
   ```python
   agent_enabled=system.agent_enabled,
   ```

2. In `update_system()` (line 84-99), add before `await session.commit()`:
   ```python
   row.agent_enabled = system.agent_enabled
   ```

3. In `_row_to_system()` (line 365-376), add to the `ExternalSystem(...)` constructor:
   ```python
   agent_enabled=row.agent_enabled,
   ```

**Step 6: Run test to verify it passes**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/catalog/test_orm.py -v
```

Expected: PASS

**Step 7: Run full test suite to catch regressions**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py -x
```

Expected: All existing tests still pass.

**Step 8: Commit**

```bash
git add src/flydesk/models/catalog.py src/flydesk/catalog/models.py src/flydesk/catalog/repository.py tests/catalog/test_orm.py
git commit -m "feat(catalog): add agent_enabled column to ExternalSystemRow"
```

---

## Task 2: Whitelist Filtering in ToolFactory

Add `tool_access_mode` support to `ToolFactory.build_tool_definitions()`. When mode is `"whitelist"` (default), only endpoints from systems with `agent_enabled=True` are included. Mode `"all_enabled"` bypasses the check (dev/demo).

The factory needs a new parameter: a mapping of `system_id → agent_enabled` status, plus the `tool_access_mode` string.

**Files:**
- Modify: `src/flydesk/tools/factory.py:40-61`
- Modify: `src/flydesk/agent/desk_agent.py:676-689`
- Test: `tests/tools/test_factory.py`

**Step 1: Write failing tests**

Add to `tests/tools/test_factory.py`:

```python
class TestToolFactoryWhitelist:
    """Test agent_enabled / tool_access_mode whitelist filtering."""

    def test_whitelist_mode_excludes_disabled_systems(self):
        """In whitelist mode, systems with agent_enabled=False are excluded."""
        factory = ToolFactory()
        endpoints = [
            _make_endpoint("ep-a", ["p:read"], system_id="sys-a"),
            _make_endpoint("ep-b", ["p:read"], system_id="sys-b"),
        ]
        # sys-a enabled, sys-b disabled
        agent_enabled_map = {"sys-a": True, "sys-b": False}
        tools = factory.build_tool_definitions(
            endpoints=endpoints,
            user_permissions=["p:read"],
            tool_access_mode="whitelist",
            agent_enabled_map=agent_enabled_map,
        )
        assert len(tools) == 1
        assert tools[0].endpoint_id == "ep-a"

    def test_all_enabled_mode_includes_all(self):
        """In all_enabled mode, agent_enabled flag is ignored."""
        factory = ToolFactory()
        endpoints = [
            _make_endpoint("ep-a", ["p:read"], system_id="sys-a"),
            _make_endpoint("ep-b", ["p:read"], system_id="sys-b"),
        ]
        agent_enabled_map = {"sys-a": True, "sys-b": False}
        tools = factory.build_tool_definitions(
            endpoints=endpoints,
            user_permissions=["p:read"],
            tool_access_mode="all_enabled",
            agent_enabled_map=agent_enabled_map,
        )
        assert len(tools) == 2

    def test_whitelist_mode_no_map_excludes_all(self):
        """In whitelist mode, if no agent_enabled_map provided, no tools returned."""
        factory = ToolFactory()
        endpoints = [_make_endpoint("ep-a", ["p:read"], system_id="sys-a")]
        tools = factory.build_tool_definitions(
            endpoints=endpoints,
            user_permissions=["p:read"],
            tool_access_mode="whitelist",
            agent_enabled_map={},
        )
        assert len(tools) == 0

    def test_default_mode_is_whitelist(self):
        """When tool_access_mode not specified, defaults to whitelist behavior."""
        factory = ToolFactory()
        endpoints = [
            _make_endpoint("ep-a", ["p:read"], system_id="sys-a"),
        ]
        agent_enabled_map = {"sys-a": False}
        tools = factory.build_tool_definitions(
            endpoints=endpoints,
            user_permissions=["p:read"],
            agent_enabled_map=agent_enabled_map,
        )
        assert len(tools) == 0
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/tools/test_factory.py::TestToolFactoryWhitelist -v
```

Expected: `TypeError` — `build_tool_definitions()` doesn't accept `tool_access_mode` or `agent_enabled_map` yet.

**Step 3: Add whitelist params to ToolFactory**

Replace `build_tool_definitions()` in `src/flydesk/tools/factory.py:40-61`:

```python
def build_tool_definitions(
    self,
    endpoints: list[ServiceEndpoint],
    user_permissions: list[str],
    access_scopes: AccessScopes | None = None,
    tool_access_mode: str = "whitelist",
    agent_enabled_map: dict[str, bool] | None = None,
) -> list[ToolDefinition]:
    """Build tools the user is permitted to use.

    When *access_scopes* is provided, endpoints are additionally filtered
    so only tools belonging to allowed systems are included.  Admin users
    (wildcard permission) bypass scope checks.

    When *tool_access_mode* is ``"whitelist"`` (the default), only
    endpoints whose parent system has ``agent_enabled=True`` in
    *agent_enabled_map* are included.  Mode ``"all_enabled"`` bypasses
    the whitelist check.
    """
    _map = agent_enabled_map or {}
    return [
        self._to_definition(ep)
        for ep in endpoints
        if self._has_permission(user_permissions, ep.required_permissions)
        and (
            access_scopes is None
            or "*" in user_permissions
            or access_scopes.can_access_system(ep.system_id)
        )
        and (
            tool_access_mode != "whitelist"
            or _map.get(ep.system_id, False)
        )
    ]
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/tools/test_factory.py -v
```

Expected: ALL tests pass (new + existing — existing callers don't pass the new args, which default to `"whitelist"` + `None` → empty map → no filtering issue only if map is None... wait.)

**IMPORTANT:** The default `agent_enabled_map=None` must NOT break existing callers. When `agent_enabled_map is None` AND `tool_access_mode="whitelist"`, we should treat it as "no filtering" (caller hasn't opted in to whitelist checks yet). Update the condition:

```python
and (
    tool_access_mode != "whitelist"
    or agent_enabled_map is None
    or _map.get(ep.system_id, False)
)
```

This way:
- Old callers (no `agent_enabled_map`) → `None` → condition passes → all tools included (backward compatible)
- New callers (`agent_enabled_map={}`) → not None → condition checks the map
- `tool_access_mode="all_enabled"` → condition passes regardless

Update the failing test `test_whitelist_mode_no_map_excludes_all` to pass an explicit empty dict `{}` (which triggers filtering), and add a test for `None` (which skips filtering):

```python
def test_whitelist_mode_none_map_skips_filtering(self):
    """When agent_enabled_map is None, whitelist filtering is skipped (backward compat)."""
    factory = ToolFactory()
    endpoints = [_make_endpoint("ep-a", ["p:read"], system_id="sys-a")]
    tools = factory.build_tool_definitions(
        endpoints=endpoints,
        user_permissions=["p:read"],
        tool_access_mode="whitelist",
        agent_enabled_map=None,
    )
    assert len(tools) == 1
```

**Step 5: Run full test suite**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py -x
```

Expected: All tests pass.

**Step 6: Commit**

```bash
git add src/flydesk/tools/factory.py tests/tools/test_factory.py
git commit -m "feat(tools): add whitelist filtering to ToolFactory.build_tool_definitions"
```

---

## Task 3: Wire Whitelist into DeskAgent

Connect the whitelist to the actual agent tool-loading path. The `DeskAgent._resolve_tools_and_prompt()` method (line 676-689 of `desk_agent.py`) needs to:
1. Read `tool_access_mode` from app settings
2. Build `agent_enabled_map` from system list
3. Pass both to `build_tool_definitions()`

**Files:**
- Modify: `src/flydesk/agent/desk_agent.py:676-689`
- Test: `tests/agent/test_desk_agent.py` (add whitelist wiring test)

**Step 1: Write failing test**

Add a test that verifies the agent excludes tools from disabled systems. Check existing test fixtures in `tests/agent/test_desk_agent.py` first (read the file to understand patterns).

```python
@pytest.mark.asyncio
async def test_resolve_tools_excludes_disabled_systems(desk_agent_fixture):
    """Tools from systems with agent_enabled=False should be excluded in whitelist mode."""
    agent, catalog_repo, settings_repo = desk_agent_fixture

    # Set tool_access_mode to "whitelist"
    settings_repo.get_app_setting = AsyncMock(return_value="whitelist")

    # Two systems: one enabled, one disabled
    enabled_system = _make_system("sys-enabled")
    enabled_system.agent_enabled = True
    disabled_system = _make_system("sys-disabled")
    disabled_system.agent_enabled = False
    catalog_repo.list_systems = AsyncMock(return_value=[enabled_system, disabled_system])

    # Endpoints from both systems
    ep_enabled = _make_endpoint("ep-1", system_id="sys-enabled")
    ep_disabled = _make_endpoint("ep-2", system_id="sys-disabled")
    catalog_repo.list_endpoints = AsyncMock(return_value=[ep_enabled, ep_disabled])

    tools, _ = await agent._resolve_tools_and_prompt(session=_admin_session(), tools=None)

    tool_ids = [t.endpoint_id for t in tools if hasattr(t, "endpoint_id")]
    assert "ep-1" in tool_ids
    assert "ep-2" not in tool_ids
```

Note: Read `tests/agent/test_desk_agent.py` first to match the actual fixture patterns and adjust. The key logic is what matters.

**Step 2: Run test to verify it fails**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/agent/test_desk_agent.py::test_resolve_tools_excludes_disabled_systems -v
```

**Step 3: Update `_resolve_tools_and_prompt()` in desk_agent.py**

In `src/flydesk/agent/desk_agent.py`, around lines 676-689, update the catalog tool loading block:

```python
if self._catalog_repo is not None:
    try:
        endpoints = await self._catalog_repo.list_endpoints()

        # Build agent_enabled map from systems
        agent_enabled_map: dict[str, bool] | None = None
        tool_access_mode = "whitelist"
        if self._settings_repo is not None:
            mode = await self._settings_repo.get_app_setting("tool_access_mode")
            if mode is not None:
                tool_access_mode = mode
            systems = await self._catalog_repo.list_systems()
            agent_enabled_map = {s.id: s.agent_enabled for s in systems}

        tools = self._tool_factory.build_tool_definitions(
            endpoints,
            list(session.permissions),
            access_scopes=None if admin_user else scopes,
            tool_access_mode=tool_access_mode,
            agent_enabled_map=agent_enabled_map,
        )
        _logger.debug("Loaded %d catalog tools for user %s", len(tools), session.user_id)
    except Exception:
        _logger.debug("Failed to load tools from catalog.", exc_info=True)
```

Note: The `DeskAgent.__init__` may need `settings_repo` as a parameter. Check the constructor and add if needed. Use the same `SettingsRepository` type used elsewhere.

**Step 4: Run test to verify it passes**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/agent/test_desk_agent.py -v --tb=short
```

**Step 5: Run full test suite**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py -x
```

**Step 6: Commit**

```bash
git add src/flydesk/agent/desk_agent.py tests/agent/test_desk_agent.py
git commit -m "feat(agent): wire whitelist filtering into DeskAgent tool resolution"
```

---

## Task 4: URL Enforcement Guard in ToolExecutor

Add a guard in `ToolExecutor._resolve_url()` that verifies the final URL starts with the system's `base_url`. This prevents prompt injection attacks where manipulated path parameters redirect calls to arbitrary hosts (e.g., `{id}` → `../../evil.com/steal`).

**Files:**
- Modify: `src/flydesk/tools/executor.py:579-589`
- Test: `tests/tools/test_executor.py`

**Step 1: Write failing tests**

Add to `tests/tools/test_executor.py`:

```python
class TestURLEnforcement:
    """URL enforcement prevents path traversal / host redirection."""

    def test_resolve_url_normal_path(self):
        """Normal path parameters resolve correctly."""
        executor = _make_executor()
        system = _make_system()
        endpoint = _make_endpoint(path="/orders/{id}")
        call = ToolCall(call_id="c1", tool_name="t1", endpoint_id="ep-1", arguments={"path": {"id": "123"}})
        url = executor._resolve_url(endpoint, system, call)
        assert url == "https://api.example.com/orders/123"

    def test_resolve_url_rejects_path_traversal(self):
        """Path params that escape base_url are rejected."""
        executor = _make_executor()
        system = _make_system()
        endpoint = _make_endpoint(path="/orders/{id}")
        call = ToolCall(
            call_id="c1", tool_name="t1", endpoint_id="ep-1",
            arguments={"path": {"id": "../../evil.com/steal"}}
        )
        with pytest.raises(Exception, match="URL does not match system base_url"):
            executor._resolve_url(endpoint, system, call)

    def test_resolve_url_rejects_absolute_url_injection(self):
        """Path params that inject an absolute URL are rejected."""
        executor = _make_executor()
        system = _make_system()
        endpoint = _make_endpoint(path="/orders/{id}")
        call = ToolCall(
            call_id="c1", tool_name="t1", endpoint_id="ep-1",
            arguments={"path": {"id": "https://evil.com/steal"}}
        )
        with pytest.raises(Exception, match="URL does not match system base_url"):
            executor._resolve_url(endpoint, system, call)
```

Note: Read `tests/tools/test_executor.py` to check if a `_make_executor()` helper exists. If not, create one:

```python
def _make_executor() -> ToolExecutor:
    return ToolExecutor(
        http_client=AsyncMock(),
        catalog_repo=AsyncMock(),
        credential_store=AsyncMock(),
        audit_logger=AsyncMock(),
    )
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/tools/test_executor.py::TestURLEnforcement -v
```

Expected: `test_resolve_url_normal_path` passes, `test_resolve_url_rejects_path_traversal` fails (no exception raised), `test_resolve_url_rejects_absolute_url_injection` fails.

**Step 3: Add URL enforcement guard**

In `src/flydesk/tools/executor.py`, update `_resolve_url()` (lines 579-589):

```python
def _resolve_url(self, endpoint: Any, system: Any, call: ToolCall) -> str:
    """Build URL with path-parameter substitution and enforcement."""
    path = endpoint.path
    path_params = call.arguments.get("path", {})
    for param_name, param_value in path_params.items():
        path = re.sub(
            r"\{" + re.escape(param_name) + r"\}",
            str(param_value),
            path,
        )
    resolved = system.base_url.rstrip("/") + "/" + path.lstrip("/")

    # Guard: resolved URL must stay within system base_url
    base = system.base_url.rstrip("/") + "/"
    if not resolved.startswith(base) or ".." in resolved:
        from flydesk.tools.executor import ToolResult  # avoid circular at module level
        raise ValueError(
            f"URL does not match system base_url: "
            f"resolved={resolved!r}, base={system.base_url!r}"
        )
    return resolved
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/tools/test_executor.py::TestURLEnforcement -v
```

**Step 5: Run full test suite**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py -x
```

**Step 6: Commit**

```bash
git add src/flydesk/tools/executor.py tests/tools/test_executor.py
git commit -m "feat(tools): add URL enforcement guard to prevent path traversal attacks"
```

---

## Task 5: `tool_access_mode` Admin API Endpoint

Add an endpoint for admins to get/set the `tool_access_mode` app setting. This lets the admin toggle between `"whitelist"` and `"all_enabled"` modes from the UI.

**Files:**
- Modify: `src/flydesk/api/tools_admin.py` — Add GET/PUT endpoints for whitelist mode
- Test: `tests/api/test_tools_admin.py`

**Step 1: Write failing tests**

Add to `tests/api/test_tools_admin.py` (create if needed):

```python
class TestToolAccessMode:
    @pytest.mark.asyncio
    async def test_get_tool_access_mode_default(self, client, mock_settings_repo):
        """GET returns 'whitelist' when no setting stored."""
        mock_settings_repo.get_app_setting = AsyncMock(return_value=None)
        response = await client.get("/api/tools/access-mode")
        assert response.status_code == 200
        assert response.json() == {"mode": "whitelist"}

    @pytest.mark.asyncio
    async def test_set_tool_access_mode(self, client, mock_settings_repo):
        """PUT updates the tool_access_mode setting."""
        mock_settings_repo.set_app_setting = AsyncMock()
        response = await client.put(
            "/api/tools/access-mode",
            json={"mode": "all_enabled"},
        )
        assert response.status_code == 200
        mock_settings_repo.set_app_setting.assert_awaited_once_with(
            "tool_access_mode", "all_enabled", category="security"
        )

    @pytest.mark.asyncio
    async def test_set_tool_access_mode_invalid(self, client):
        """PUT rejects invalid mode values."""
        response = await client.put(
            "/api/tools/access-mode",
            json={"mode": "invalid_mode"},
        )
        assert response.status_code == 422
```

Note: Read `tests/api/test_tools_admin.py` first to match existing fixture patterns.

**Step 2: Run tests to verify they fail**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/api/test_tools_admin.py::TestToolAccessMode -v
```

**Step 3: Add endpoints to tools_admin.py**

In `src/flydesk/api/tools_admin.py`, add:

```python
from pydantic import BaseModel
from enum import StrEnum

class ToolAccessMode(StrEnum):
    WHITELIST = "whitelist"
    ALL_ENABLED = "all_enabled"

class ToolAccessModeRequest(BaseModel):
    mode: ToolAccessMode

class ToolAccessModeResponse(BaseModel):
    mode: str

@router.get("/access-mode", dependencies=[AdminSettings])
async def get_tool_access_mode(settings_repo: SettingsRepo) -> ToolAccessModeResponse:
    """Get the current tool access mode."""
    mode = await settings_repo.get_app_setting("tool_access_mode")
    return ToolAccessModeResponse(mode=mode or "whitelist")

@router.put("/access-mode", dependencies=[AdminSettings])
async def set_tool_access_mode(
    body: ToolAccessModeRequest, settings_repo: SettingsRepo
) -> ToolAccessModeResponse:
    """Set the tool access mode (whitelist or all_enabled)."""
    await settings_repo.set_app_setting("tool_access_mode", body.mode.value, category="security")
    return ToolAccessModeResponse(mode=body.mode.value)
```

**Step 4: Run tests to verify they pass**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/api/test_tools_admin.py::TestToolAccessMode -v
```

**Step 5: Run full test suite**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py -x
```

**Step 6: Commit**

```bash
git add src/flydesk/api/tools_admin.py tests/api/test_tools_admin.py
git commit -m "feat(api): add tool_access_mode GET/PUT endpoints for whitelist management"
```

---

## Task 6: Expose `agent_enabled` in Catalog API

Ensure the catalog API create/update system endpoints accept and return the `agent_enabled` field. The `ExternalSystem` Pydantic model already has it from Task 1, but verify the API roundtrip works.

**Files:**
- Test: `tests/api/test_catalog_api.py`
- Potentially modify: `src/flydesk/api/catalog.py` (only if needed)

**Step 1: Write test**

Add to `tests/api/test_catalog_api.py`:

```python
class TestAgentEnabledField:
    @pytest.mark.asyncio
    async def test_create_system_with_agent_enabled(self, client, mock_repo):
        """Creating a system with agent_enabled=True persists correctly."""
        system_data = _sample_system().model_dump()
        system_data["agent_enabled"] = True
        mock_repo.create_system = AsyncMock()
        mock_repo.get_system = AsyncMock(return_value=None)

        response = await client.post("/api/catalog/systems", json=system_data)
        assert response.status_code == 201
        assert response.json()["agent_enabled"] is True

    @pytest.mark.asyncio
    async def test_create_system_agent_enabled_defaults_false(self, client, mock_repo):
        """Creating a system without agent_enabled defaults to False."""
        system_data = _sample_system().model_dump()
        # Don't include agent_enabled — should default to False
        system_data.pop("agent_enabled", None)
        mock_repo.create_system = AsyncMock()

        response = await client.post("/api/catalog/systems", json=system_data)
        assert response.status_code == 201
        assert response.json()["agent_enabled"] is False
```

**Step 2: Run tests**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/api/test_catalog_api.py::TestAgentEnabledField -v
```

These should pass immediately since the Pydantic model change in Task 1 auto-exposes the field. If they fail, debug and fix.

**Step 3: Run full test suite**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py -x
```

**Step 4: Commit**

```bash
git add tests/api/test_catalog_api.py
git commit -m "test(api): verify agent_enabled field roundtrip in catalog API"
```

---

## Task 7: SystemWizard.svelte — Multi-Step Wizard Component

Replace the flat inline form in `CatalogManager.svelte` with a proper 4-step wizard. This is a new component that handles:
- Step 1: System Basics (name, description, base_url, status, tags, health_check_path)
- Step 2: Authentication (auth_type selector, dynamic fields per type)
- Step 3: Agent Access (agent_enabled toggle, whitelist mode notice)
- Step 4: Review & Create (summary card, create button)

**Files:**
- Create: `frontend/src/lib/components/admin/SystemWizard.svelte`
- Modify: `frontend/src/lib/components/admin/CatalogManager.svelte`

**Step 1: Create SystemWizard.svelte**

Create `frontend/src/lib/components/admin/SystemWizard.svelte` with:

```svelte
<!--
  SystemWizard.svelte - 4-step wizard for creating/editing external systems.

  Copyright 2026 Firefly Software Solutions Inc. All rights reserved.
  Licensed under the Apache License, Version 2.0.
-->
<script lang="ts">
    import { X, ChevronLeft, ChevronRight, Save, Loader2, Check, Shield, Activity } from 'lucide-svelte';
    import { apiJson } from '$lib/services/api.js';

    // Props
    interface Props {
        editingSystem?: any | null;
        onClose: () => void;
        onSaved: () => void;
    }
    let { editingSystem = null, onClose, onSaved }: Props = $props();

    // Wizard state
    let currentStep = $state(1);
    const totalSteps = 4;
    let saving = $state(false);
    let error = $state('');
    let testingHealth = $state(false);
    let healthResult = $state<{ ok: boolean; message: string } | null>(null);
    let testingAuth = $state(false);
    let authResult = $state<{ ok: boolean; message: string } | null>(null);

    // Form data
    let formData = $state({
        // Step 1: Basics
        id: editingSystem?.id || '',
        name: editingSystem?.name || '',
        description: editingSystem?.description || '',
        base_url: editingSystem?.base_url || '',
        status: editingSystem?.status || 'active',
        tags: editingSystem?.tags?.join(', ') || '',
        health_check_path: editingSystem?.health_check_path || '',

        // Step 2: Authentication
        auth_type: editingSystem?.auth_config?.auth_type || 'bearer',
        credential_id: editingSystem?.auth_config?.credential_id || '',
        token_url: editingSystem?.auth_config?.token_url || '',
        scopes: editingSystem?.auth_config?.scopes?.join(', ') || '',

        // Step 3: Agent Access
        agent_enabled: editingSystem?.agent_enabled ?? false,
    });

    // Step validation
    let step1Valid = $derived(
        formData.name.trim() !== '' &&
        formData.description.trim() !== '' &&
        formData.base_url.trim() !== ''
    );
    let step2Valid = $derived(
        formData.auth_type !== '' &&
        formData.credential_id.trim() !== ''
    );

    const stepLabels = ['Basics', 'Authentication', 'Agent Access', 'Review'];

    // Auth type options
    const authTypes = [
        { value: 'oauth2', label: 'OAuth 2.0' },
        { value: 'api_key', label: 'API Key' },
        { value: 'basic', label: 'Basic Auth' },
        { value: 'bearer', label: 'Bearer Token' },
        { value: 'mutual_tls', label: 'Mutual TLS' },
    ];

    function canProceed(): boolean {
        if (currentStep === 1) return step1Valid;
        if (currentStep === 2) return step2Valid;
        return true;
    }

    function nextStep() {
        if (currentStep < totalSteps && canProceed()) {
            currentStep++;
        }
    }

    function prevStep() {
        if (currentStep > 1) {
            currentStep--;
        }
    }

    function generateId(name: string): string {
        return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    }

    async function submit() {
        saving = true;
        error = '';

        const payload = {
            id: formData.id || generateId(formData.name),
            name: formData.name,
            description: formData.description,
            base_url: formData.base_url,
            status: formData.status,
            tags: formData.tags.split(',').map((t: string) => t.trim()).filter(Boolean),
            health_check_path: formData.health_check_path || null,
            auth_config: {
                auth_type: formData.auth_type,
                credential_id: formData.credential_id,
                token_url: formData.token_url || null,
                scopes: formData.scopes ? formData.scopes.split(',').map((s: string) => s.trim()).filter(Boolean) : null,
            },
            agent_enabled: formData.agent_enabled,
            metadata: {},
        };

        try {
            if (editingSystem) {
                await apiJson(`/catalog/systems/${editingSystem.id}`, {
                    method: 'PUT',
                    body: JSON.stringify(payload),
                });
            } else {
                await apiJson('/catalog/systems', {
                    method: 'POST',
                    body: JSON.stringify(payload),
                });
            }
            onSaved();
        } catch (e) {
            error = e instanceof Error ? e.message : 'Failed to save system';
        } finally {
            saving = false;
        }
    }
</script>

<div class="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
    <div class="w-full max-w-2xl rounded-xl border border-border bg-surface shadow-2xl">
        <!-- Header -->
        <div class="flex items-center justify-between border-b border-border px-6 py-4">
            <div>
                <h2 class="text-lg font-semibold text-text-primary">
                    {editingSystem ? 'Edit System' : 'New System'}
                </h2>
                <p class="text-sm text-text-secondary">
                    Step {currentStep} of {totalSteps} — {stepLabels[currentStep - 1]}
                </p>
            </div>
            <button type="button" onclick={onClose} class="text-text-secondary hover:text-text-primary">
                <X size={20} />
            </button>
        </div>

        <!-- Step indicators -->
        <div class="flex items-center gap-1 px-6 pt-4">
            {#each stepLabels as label, i}
                {@const stepNum = i + 1}
                {@const isActive = currentStep === stepNum}
                {@const isComplete = currentStep > stepNum}
                <div class="flex items-center gap-1 {i > 0 ? 'ml-1' : ''}">
                    {#if i > 0}
                        <div class="h-px w-6 {isComplete || isActive ? 'bg-accent' : 'bg-border'}"></div>
                    {/if}
                    <div class="flex items-center gap-1.5">
                        <div class="flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium
                            {isComplete ? 'bg-accent text-white' : isActive ? 'border-2 border-accent text-accent' : 'border border-border text-text-secondary'}">
                            {#if isComplete}
                                <Check size={12} />
                            {:else}
                                {stepNum}
                            {/if}
                        </div>
                        <span class="hidden text-xs sm:inline {isActive ? 'font-medium text-text-primary' : 'text-text-secondary'}">
                            {label}
                        </span>
                    </div>
                </div>
            {/each}
        </div>

        <!-- Error banner -->
        {#if error}
            <div class="mx-6 mt-4 rounded-md border border-danger/30 bg-danger/5 px-4 py-2.5 text-sm text-danger">
                {error}
            </div>
        {/if}

        <!-- Step content -->
        <div class="px-6 py-5">
            {#if currentStep === 1}
                <!-- Step 1: Basics -->
                <div class="grid grid-cols-2 gap-4">
                    <label class="col-span-2 flex flex-col gap-1">
                        <span class="text-xs font-medium text-text-secondary">Name *</span>
                        <input type="text" bind:value={formData.name} required placeholder="e.g. Core Banking API"
                            class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent" />
                    </label>

                    <label class="col-span-2 flex flex-col gap-1">
                        <span class="text-xs font-medium text-text-secondary">Description *</span>
                        <textarea bind:value={formData.description} required rows={3} placeholder="What does this system do?"
                            class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"></textarea>
                    </label>

                    <label class="col-span-2 flex flex-col gap-1">
                        <span class="text-xs font-medium text-text-secondary">Base URL *</span>
                        <input type="url" bind:value={formData.base_url} required placeholder="https://api.example.com/v1"
                            class="rounded-md border border-border bg-surface px-3 py-2 text-sm font-mono text-text-primary outline-none focus:border-accent" />
                    </label>

                    <label class="flex flex-col gap-1">
                        <span class="text-xs font-medium text-text-secondary">Status</span>
                        <select bind:value={formData.status}
                            class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent">
                            <option value="active">Active</option>
                            <option value="inactive">Inactive</option>
                            <option value="degraded">Degraded</option>
                        </select>
                    </label>

                    <label class="flex flex-col gap-1">
                        <span class="text-xs font-medium text-text-secondary">Tags (comma-separated)</span>
                        <input type="text" bind:value={formData.tags} placeholder="e.g. banking, internal"
                            class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent" />
                    </label>

                    <label class="col-span-2 flex flex-col gap-1">
                        <span class="text-xs font-medium text-text-secondary">Health Check Path (optional)</span>
                        <input type="text" bind:value={formData.health_check_path} placeholder="/health"
                            class="rounded-md border border-border bg-surface px-3 py-2 text-sm font-mono text-text-primary outline-none focus:border-accent" />
                    </label>
                </div>

            {:else if currentStep === 2}
                <!-- Step 2: Authentication -->
                <div class="grid grid-cols-2 gap-4">
                    <label class="col-span-2 flex flex-col gap-1">
                        <span class="text-xs font-medium text-text-secondary">Authentication Type *</span>
                        <select bind:value={formData.auth_type}
                            class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent">
                            {#each authTypes as at}
                                <option value={at.value}>{at.label}</option>
                            {/each}
                        </select>
                    </label>

                    <label class="col-span-2 flex flex-col gap-1">
                        <span class="text-xs font-medium text-text-secondary">Credential ID *</span>
                        <input type="text" bind:value={formData.credential_id} required placeholder="credential-id"
                            class="rounded-md border border-border bg-surface px-3 py-2 text-sm font-mono text-text-primary outline-none focus:border-accent" />
                        <span class="text-xs text-text-secondary">Reference to a credential in the Credential Vault</span>
                    </label>

                    {#if formData.auth_type === 'oauth2'}
                        <label class="col-span-2 flex flex-col gap-1">
                            <span class="text-xs font-medium text-text-secondary">Token URL</span>
                            <input type="url" bind:value={formData.token_url} placeholder="https://auth.example.com/oauth/token"
                                class="rounded-md border border-border bg-surface px-3 py-2 text-sm font-mono text-text-primary outline-none focus:border-accent" />
                        </label>

                        <label class="col-span-2 flex flex-col gap-1">
                            <span class="text-xs font-medium text-text-secondary">Scopes (comma-separated)</span>
                            <input type="text" bind:value={formData.scopes} placeholder="read, write"
                                class="rounded-md border border-border bg-surface px-3 py-2 text-sm text-text-primary outline-none focus:border-accent" />
                        </label>
                    {/if}
                </div>

            {:else if currentStep === 3}
                <!-- Step 3: Agent Access -->
                <div class="space-y-4">
                    <div class="rounded-lg border border-border bg-surface-secondary/50 p-4">
                        <div class="flex items-start gap-3">
                            <div class="mt-0.5 rounded-md bg-accent/10 p-2">
                                <Shield size={20} class="text-accent" />
                            </div>
                            <div class="flex-1">
                                <h3 class="text-sm font-semibold text-text-primary">Agent Access Control</h3>
                                <p class="mt-1 text-xs text-text-secondary">
                                    When whitelist mode is active, only systems with agent access enabled can be
                                    called by the AI agent. This prevents the agent from making unauthorized calls
                                    to external systems.
                                </p>
                            </div>
                        </div>
                    </div>

                    <label class="flex items-center gap-3 rounded-lg border border-border p-4 cursor-pointer hover:bg-surface-secondary/30 transition-colors">
                        <input type="checkbox" bind:checked={formData.agent_enabled}
                            class="h-4 w-4 rounded border-border text-accent focus:ring-accent" />
                        <div>
                            <span class="text-sm font-medium text-text-primary">Enable Agent Access</span>
                            <p class="text-xs text-text-secondary">
                                Allow the AI agent to call endpoints on this system
                            </p>
                        </div>
                    </label>

                    {#if !formData.agent_enabled}
                        <div class="rounded-md border border-warning/30 bg-warning/5 px-4 py-2.5 text-xs text-warning">
                            The agent will not be able to use any endpoints from this system in whitelist mode.
                        </div>
                    {/if}
                </div>

            {:else if currentStep === 4}
                <!-- Step 4: Review & Create -->
                <div class="space-y-3">
                    <div class="rounded-lg border border-border bg-surface-secondary/30 p-4">
                        <h3 class="mb-2 text-xs font-semibold uppercase text-text-secondary">System Basics</h3>
                        <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                            <dt class="text-text-secondary">Name</dt>
                            <dd class="font-medium text-text-primary">{formData.name}</dd>
                            <dt class="text-text-secondary">Base URL</dt>
                            <dd class="font-mono text-xs text-text-primary">{formData.base_url}</dd>
                            <dt class="text-text-secondary">Status</dt>
                            <dd class="text-text-primary">{formData.status}</dd>
                            {#if formData.tags}
                                <dt class="text-text-secondary">Tags</dt>
                                <dd class="text-text-primary">{formData.tags}</dd>
                            {/if}
                            {#if formData.health_check_path}
                                <dt class="text-text-secondary">Health Check</dt>
                                <dd class="font-mono text-xs text-text-primary">{formData.health_check_path}</dd>
                            {/if}
                        </dl>
                    </div>

                    <div class="rounded-lg border border-border bg-surface-secondary/30 p-4">
                        <h3 class="mb-2 text-xs font-semibold uppercase text-text-secondary">Authentication</h3>
                        <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                            <dt class="text-text-secondary">Type</dt>
                            <dd class="text-text-primary">{authTypes.find(a => a.value === formData.auth_type)?.label}</dd>
                            <dt class="text-text-secondary">Credential</dt>
                            <dd class="font-mono text-xs text-text-primary">{formData.credential_id}</dd>
                            {#if formData.auth_type === 'oauth2' && formData.token_url}
                                <dt class="text-text-secondary">Token URL</dt>
                                <dd class="font-mono text-xs text-text-primary">{formData.token_url}</dd>
                            {/if}
                        </dl>
                    </div>

                    <div class="rounded-lg border border-border bg-surface-secondary/30 p-4">
                        <h3 class="mb-2 text-xs font-semibold uppercase text-text-secondary">Agent Access</h3>
                        <div class="flex items-center gap-2 text-sm">
                            {#if formData.agent_enabled}
                                <Activity size={14} class="text-success" />
                                <span class="text-success">Enabled</span>
                            {:else}
                                <Shield size={14} class="text-warning" />
                                <span class="text-warning">Disabled (blocked in whitelist mode)</span>
                            {/if}
                        </div>
                    </div>
                </div>
            {/if}
        </div>

        <!-- Footer -->
        <div class="flex items-center justify-between border-t border-border px-6 py-4">
            <button type="button" onclick={currentStep > 1 ? prevStep : onClose}
                class="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-sm text-text-secondary transition-colors hover:bg-surface-hover">
                <ChevronLeft size={14} />
                {currentStep > 1 ? 'Back' : 'Cancel'}
            </button>

            {#if currentStep < totalSteps}
                <button type="button" onclick={nextStep} disabled={!canProceed()}
                    class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50">
                    Next
                    <ChevronRight size={14} />
                </button>
            {:else}
                <button type="button" onclick={submit} disabled={saving}
                    class="inline-flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50">
                    {#if saving}
                        <Loader2 size={14} class="animate-spin" />
                    {:else}
                        <Save size={14} />
                    {/if}
                    {editingSystem ? 'Update System' : 'Create System'}
                </button>
            {/if}
        </div>
    </div>
</div>
```

**Step 2: Integrate wizard into CatalogManager.svelte**

In `frontend/src/lib/components/admin/CatalogManager.svelte`:

1. Add import at the top of the `<script>` block:
   ```typescript
   import SystemWizard from './SystemWizard.svelte';
   ```

2. Add state variable for full system data (needed for edit mode):
   ```typescript
   let editingSystemFull = $state<any | null>(null);
   ```

3. Replace `openAddForm()`:
   ```typescript
   function openAddForm() {
       editingSystemFull = null;
       showForm = true;
   }
   ```

4. Replace `openEditForm()` to fetch full system data:
   ```typescript
   async function openEditForm(system: System) {
       try {
           editingSystemFull = await apiJson(`/catalog/systems/${system.id}`);
           showForm = true;
       } catch (e) {
           error = e instanceof Error ? e.message : 'Failed to load system details';
       }
   }
   ```

5. Replace the inline form block (`{#if showForm}...{/if}`) with:
   ```svelte
   {#if showForm}
       <SystemWizard
           editingSystem={editingSystemFull}
           onClose={cancelForm}
           onSaved={() => { showForm = false; editingSystemFull = null; loadSystems(); }}
       />
   {/if}
   ```

6. Remove old `formData`, `submitForm()`, `editingId` state and logic that are now handled by the wizard.

**Step 3: Verify frontend builds**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk/frontend && npm run check && npm run build
```

Expected: 0 errors, 0 warnings, build succeeds.

**Step 4: Commit**

```bash
git add frontend/src/lib/components/admin/SystemWizard.svelte frontend/src/lib/components/admin/CatalogManager.svelte
git commit -m "feat(frontend): add 4-step system creation wizard with agent access control"
```

---

## Task 8: Update Seed Data to Set `agent_enabled`

The banking seed data creates systems but doesn't set `agent_enabled`. After whitelist mode is active, seeded systems won't be callable unless we set `agent_enabled=True` on them.

**Files:**
- Modify: `src/flydesk/seeds/banking.py` — Set `agent_enabled=True` on all seeded systems

**Step 1: Update seed system definitions**

In `src/flydesk/seeds/banking.py`, find the `SYSTEMS` list (list of `ExternalSystem` objects). Add `agent_enabled=True` to each system definition:

```python
ExternalSystem(
    id="core-banking",
    name="Core Banking API",
    # ... existing fields ...
    agent_enabled=True,  # ADD THIS
)
```

Repeat for all systems in the `SYSTEMS` list.

**Step 2: Run tests**

```bash
cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py -x
```

**Step 3: Commit**

```bash
git add src/flydesk/seeds/banking.py
git commit -m "feat(seeds): set agent_enabled=True on all banking seed systems"
```

---

## Task 9: Verification

1. Run backend tests:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk && uv run python -m pytest tests/ -v --tb=short --ignore=tests/knowledge/test_chroma_store.py
   ```

2. Run frontend checks:
   ```bash
   cd /Users/ancongui/Development/fireflyframework/firefly-desk/frontend && npm run check && npm run build
   ```

3. Manual verification (if backend is running):
   - Navigate to Admin > System Catalog
   - Click "Add System" — verify 4-step wizard opens
   - Fill Step 1 (basics), Step 2 (auth), Step 3 (toggle agent_enabled), Step 4 (review)
   - Create system, verify it appears in the table
   - Edit a system — verify wizard pre-fills existing data
   - Check that `agent_enabled` field is returned in API responses:
     ```bash
     curl http://localhost:8000/api/catalog/systems | python -m json.tool
     ```

---

## Dependency Graph

```
Task 1 (agent_enabled column)         — No deps
Task 2 (ToolFactory whitelist)        — No deps (new params, backward compatible)
Task 3 (DeskAgent wiring)             — Depends on Tasks 1, 2
Task 4 (URL enforcement)              — No deps
Task 5 (tool_access_mode API)         — No deps
Task 6 (catalog API roundtrip)        — Depends on Task 1
Task 7 (SystemWizard frontend)        — Depends on Task 1 (agent_enabled field in API)
Task 8 (seed data update)             — Depends on Task 1
Task 9 (verification)                 — ALL previous tasks
```

**Execution order:**
1. Tasks 1, 2, 4, 5 (parallel — all independent)
2. Tasks 3, 6, 7, 8 (need Task 1 and/or 2)
3. Task 9 (final)

---

## Summary Table

| # | Task | Key Files | Impact |
|---|------|-----------|--------|
| 1 | `agent_enabled` ORM column | `models/catalog.py`, `catalog/models.py`, `catalog/repository.py` | Foundation |
| 2 | ToolFactory whitelist | `tools/factory.py` | **Critical** — filtering engine |
| 3 | DeskAgent wiring | `agent/desk_agent.py` | **Critical** — connects filter to agent |
| 4 | URL enforcement | `tools/executor.py` | **Security** — prevents injection |
| 5 | `tool_access_mode` API | `api/tools_admin.py` | Admin control |
| 6 | Catalog API roundtrip | `api/catalog.py` (tests only) | Verification |
| 7 | SystemWizard frontend | `SystemWizard.svelte`, `CatalogManager.svelte` | **UX** — wizard |
| 8 | Seed data update | `seeds/banking.py` | Ensures seeds work with whitelist |
| 9 | Verification | — | Quality gate |
