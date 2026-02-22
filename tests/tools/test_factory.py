# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for the dynamic ToolFactory."""

from __future__ import annotations

from flydesk.catalog.enums import HttpMethod, RiskLevel
from flydesk.catalog.models import ServiceEndpoint
from flydesk.tools.factory import ToolFactory


def _make_endpoint(
    ep_id: str,
    perms: list[str],
    risk: RiskLevel = RiskLevel.READ,
) -> ServiceEndpoint:
    return ServiceEndpoint(
        id=ep_id,
        system_id="sys1",
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
