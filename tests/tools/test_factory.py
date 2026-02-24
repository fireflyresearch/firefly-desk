# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for the dynamic ToolFactory."""

from __future__ import annotations

from flydesk.catalog.enums import HttpMethod, RiskLevel
from flydesk.catalog.models import ServiceEndpoint
from flydesk.rbac.models import AccessScopes
from flydesk.tools.factory import ToolFactory


def _make_endpoint(
    ep_id: str,
    perms: list[str],
    risk: RiskLevel = RiskLevel.READ,
    system_id: str = "sys1",
) -> ServiceEndpoint:
    return ServiceEndpoint(
        id=ep_id,
        system_id=system_id,
        name=f"Tool {ep_id}",
        description=f"Description for {ep_id}",
        method=HttpMethod.GET,
        path=f"/{ep_id}",
        when_to_use=f"Use {ep_id}",
        risk_level=risk,
        required_permissions=perms,
    )


class TestToolFactory:
    def test_builds_tools_for_permitted_endpoints(self):
        factory = ToolFactory()
        endpoints = [
            _make_endpoint("read-customers", ["customers:read"]),
            _make_endpoint("write-customers", ["customers:write"]),
            _make_endpoint("read-billing", ["billing:read"]),
        ]
        tools = factory.build_tool_definitions(
            endpoints=endpoints,
            user_permissions=["customers:read", "billing:read"],
        )
        tool_ids = [t.endpoint_id for t in tools]
        assert "read-customers" in tool_ids
        assert "read-billing" in tool_ids
        assert "write-customers" not in tool_ids

    def test_empty_permissions_yields_no_tools(self):
        factory = ToolFactory()
        endpoints = [_make_endpoint("ep1", ["perm:read"])]
        tools = factory.build_tool_definitions(endpoints=endpoints, user_permissions=[])
        assert tools == []

    def test_tool_description_includes_when_to_use(self):
        factory = ToolFactory()
        endpoints = [_make_endpoint("ep1", ["p:read"])]
        tools = factory.build_tool_definitions(endpoints=endpoints, user_permissions=["p:read"])
        assert "Use ep1" in tools[0].description

    def test_tool_includes_risk_level(self):
        factory = ToolFactory()
        endpoints = [_make_endpoint("ep1", ["p:write"], risk=RiskLevel.HIGH_WRITE)]
        tools = factory.build_tool_definitions(endpoints=endpoints, user_permissions=["p:write"])
        assert tools[0].risk_level == RiskLevel.HIGH_WRITE


class TestToolFactoryAccessScopes:
    """Test scope-based tool filtering via access_scopes parameter."""

    def test_no_scopes_returns_all_permitted(self):
        """When access_scopes is None, all permitted tools are returned."""
        factory = ToolFactory()
        endpoints = [
            _make_endpoint("ep1", ["p:read"], system_id="sys-a"),
            _make_endpoint("ep2", ["p:read"], system_id="sys-b"),
        ]
        tools = factory.build_tool_definitions(
            endpoints=endpoints,
            user_permissions=["p:read"],
            access_scopes=None,
        )
        assert len(tools) == 2

    def test_scopes_filter_by_system(self):
        """Only tools from allowed systems are returned."""
        factory = ToolFactory()
        endpoints = [
            _make_endpoint("ep-a", ["p:read"], system_id="sys-a"),
            _make_endpoint("ep-b", ["p:read"], system_id="sys-b"),
            _make_endpoint("ep-c", ["p:read"], system_id="sys-c"),
        ]
        scopes = AccessScopes(systems=["sys-a", "sys-c"])
        tools = factory.build_tool_definitions(
            endpoints=endpoints,
            user_permissions=["p:read"],
            access_scopes=scopes,
        )
        tool_ids = [t.endpoint_id for t in tools]
        assert "ep-a" in tool_ids
        assert "ep-c" in tool_ids
        assert "ep-b" not in tool_ids

    def test_empty_scopes_allow_all_systems(self):
        """Empty systems list means unrestricted -- all systems allowed."""
        factory = ToolFactory()
        endpoints = [
            _make_endpoint("ep-a", ["p:read"], system_id="sys-a"),
            _make_endpoint("ep-b", ["p:read"], system_id="sys-b"),
        ]
        scopes = AccessScopes(systems=[])
        tools = factory.build_tool_definitions(
            endpoints=endpoints,
            user_permissions=["p:read"],
            access_scopes=scopes,
        )
        assert len(tools) == 2

    def test_admin_wildcard_bypasses_scope(self):
        """Admin users (wildcard permission) bypass scope checks."""
        factory = ToolFactory()
        endpoints = [
            _make_endpoint("ep-a", ["p:read"], system_id="sys-a"),
            _make_endpoint("ep-b", ["p:read"], system_id="sys-b"),
        ]
        scopes = AccessScopes(systems=["sys-a"])
        tools = factory.build_tool_definitions(
            endpoints=endpoints,
            user_permissions=["*"],
            access_scopes=scopes,
        )
        assert len(tools) == 2

    def test_scopes_combined_with_permission_check(self):
        """Scope filtering works in conjunction with permission filtering."""
        factory = ToolFactory()
        endpoints = [
            _make_endpoint("ep-allowed", ["p:read"], system_id="sys-a"),
            _make_endpoint("ep-no-perm", ["p:write"], system_id="sys-a"),
            _make_endpoint("ep-no-scope", ["p:read"], system_id="sys-b"),
        ]
        scopes = AccessScopes(systems=["sys-a"])
        tools = factory.build_tool_definitions(
            endpoints=endpoints,
            user_permissions=["p:read"],
            access_scopes=scopes,
        )
        assert len(tools) == 1
        assert tools[0].endpoint_id == "ep-allowed"


class TestToolFactoryWhitelist:
    """Test whitelist-based tool filtering via agent_enabled_map parameter."""

    def test_whitelist_mode_excludes_disabled_systems(self):
        factory = ToolFactory()
        endpoints = [
            _make_endpoint("ep-a", ["p:read"], system_id="sys-a"),
            _make_endpoint("ep-b", ["p:read"], system_id="sys-b"),
        ]
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

    def test_whitelist_mode_empty_map_excludes_all(self):
        factory = ToolFactory()
        endpoints = [_make_endpoint("ep-a", ["p:read"], system_id="sys-a")]
        tools = factory.build_tool_definitions(
            endpoints=endpoints,
            user_permissions=["p:read"],
            tool_access_mode="whitelist",
            agent_enabled_map={},
        )
        assert len(tools) == 0

    def test_none_map_skips_filtering_backward_compat(self):
        factory = ToolFactory()
        endpoints = [_make_endpoint("ep-a", ["p:read"], system_id="sys-a")]
        tools = factory.build_tool_definitions(
            endpoints=endpoints,
            user_permissions=["p:read"],
            tool_access_mode="whitelist",
            agent_enabled_map=None,
        )
        assert len(tools) == 1
