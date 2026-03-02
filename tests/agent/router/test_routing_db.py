"""Tests for the routing config ORM model."""

from __future__ import annotations


def test_routing_config_row_tablename():
    from flydesk.models.routing import ModelRoutingConfigRow

    assert ModelRoutingConfigRow.__tablename__ == "model_routing_config"


def test_routing_config_row_defaults():
    from flydesk.models.routing import ModelRoutingConfigRow

    row = ModelRoutingConfigRow(id="default")
    assert row.enabled is False
    assert row.default_tier == "balanced"
    assert row.tier_mappings == {}
