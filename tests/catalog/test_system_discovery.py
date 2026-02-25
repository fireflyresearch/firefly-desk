# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for SystemDiscoveryEngine -- LLM-driven system discovery."""

from __future__ import annotations

import json
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.catalog.discovery import (
    DiscoveredSystem,
    SystemDiscoveryEngine,
    SystemDiscoveryResult,
)
from flydesk.catalog.enums import AuthType, SystemStatus
from flydesk.catalog.models import ExternalSystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm_response(systems: list[dict]) -> str:
    """Build a JSON string matching the SystemDiscoveryResult schema."""
    return json.dumps({"systems": systems})


def _sample_system_dict(
    name: str = "Salesforce CRM",
    confidence: float = 0.85,
    category: str = "crm",
    auth_type: str = "oauth2",
) -> dict:
    """Return a sample system dict as the LLM would produce."""
    return {
        "name": name,
        "description": f"The {name} platform",
        "base_url": f"https://{name.lower().replace(' ', '-')}.example.com",
        "category": category,
        "auth_type": auth_type,
        "confidence": confidence,
        "tags": ["auto-discovered", category],
        "evidence": ["Found in KB document 'API Integration Guide'"],
    }


def _make_system(
    system_id: str = "sys-1",
    name: str = "Existing System",
) -> ExternalSystem:
    """Create a simple ExternalSystem for fixture returns."""
    return ExternalSystem(
        id=system_id,
        name=name,
        description="An existing system",
        base_url="https://existing.example.com",
        status=SystemStatus.ACTIVE,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_catalog_repo():
    repo = AsyncMock()
    repo.list_systems.return_value = []
    repo.list_endpoints.return_value = []
    repo.list_knowledge_documents.return_value = []
    repo.create_system = AsyncMock()
    repo.get_system = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_knowledge_graph():
    kg = AsyncMock()
    kg.list_entities.return_value = []
    kg.get_entity_neighborhood.return_value = MagicMock(entities=[], relations=[])
    return kg


@pytest.fixture
def mock_agent_factory():
    factory = AsyncMock()
    factory.create_agent.return_value = None  # Default: no LLM configured
    return factory


@pytest.fixture
def engine(mock_agent_factory, mock_catalog_repo, mock_knowledge_graph):
    return SystemDiscoveryEngine(
        agent_factory=mock_agent_factory,
        catalog_repo=mock_catalog_repo,
        knowledge_graph=mock_knowledge_graph,
    )


# ---------------------------------------------------------------------------
# Tests: _parse_llm_response
# ---------------------------------------------------------------------------


class TestParseLLMResponse:
    """Tests for SystemDiscoveryEngine._parse_llm_response()."""

    def test_valid_json(self):
        """A well-formed JSON response is parsed into SystemDiscoveryResult."""
        text = _make_llm_response([_sample_system_dict()])
        result = SystemDiscoveryEngine._parse_llm_response(text)
        assert len(result.systems) == 1
        assert result.systems[0].name == "Salesforce CRM"
        assert result.systems[0].confidence == 0.85
        assert result.systems[0].category == "crm"
        assert result.systems[0].auth_type == "oauth2"

    def test_json_with_markdown_code_block(self):
        """JSON wrapped in ```json code fences is handled."""
        inner = _make_llm_response([_sample_system_dict()])
        text = f"```json\n{inner}\n```"
        result = SystemDiscoveryEngine._parse_llm_response(text)
        assert len(result.systems) == 1
        assert result.systems[0].name == "Salesforce CRM"

    def test_json_with_plain_code_block(self):
        """JSON wrapped in plain ``` code fences (no language) is handled."""
        inner = _make_llm_response([_sample_system_dict()])
        text = f"```\n{inner}\n```"
        result = SystemDiscoveryEngine._parse_llm_response(text)
        assert len(result.systems) == 1

    def test_invalid_json_returns_empty(self):
        """Malformed JSON returns an empty SystemDiscoveryResult (no exception)."""
        result = SystemDiscoveryEngine._parse_llm_response("this is not json {{{")
        assert result.systems == []

    def test_empty_systems_list(self):
        """An empty systems list is a valid empty result."""
        result = SystemDiscoveryEngine._parse_llm_response('{"systems": []}')
        assert result.systems == []

    def test_multiple_systems_parsed(self):
        """Multiple systems in the response are all parsed."""
        systems = [
            _sample_system_dict("System A", 0.9, "hr"),
            _sample_system_dict("System B", 0.7, "finance"),
            _sample_system_dict("System C", 0.5, "operations"),
        ]
        result = SystemDiscoveryEngine._parse_llm_response(_make_llm_response(systems))
        assert len(result.systems) == 3
        assert result.systems[0].name == "System A"
        assert result.systems[1].name == "System B"
        assert result.systems[2].name == "System C"

    def test_whitespace_handling(self):
        """Leading/trailing whitespace is stripped before parsing."""
        text = f"   \n  {_make_llm_response([_sample_system_dict()])}  \n  "
        result = SystemDiscoveryEngine._parse_llm_response(text)
        assert len(result.systems) == 1

    def test_wrong_schema_returns_empty(self):
        """Valid JSON that doesn't match the schema returns empty result."""
        result = SystemDiscoveryEngine._parse_llm_response('{"foo": "bar"}')
        # Pydantic will accept it with systems defaulting to []
        assert result.systems == []


# ---------------------------------------------------------------------------
# Tests: _to_external_systems
# ---------------------------------------------------------------------------


class TestToExternalSystems:
    """Tests for SystemDiscoveryEngine._to_external_systems()."""

    def test_confidence_preserved_in_metadata(self):
        """Confidence score is preserved in metadata."""
        disc_result = SystemDiscoveryResult(
            systems=[
                DiscoveredSystem(name="Test", confidence=0.92, category="ops"),
            ]
        )
        systems = SystemDiscoveryEngine._to_external_systems(disc_result)
        assert len(systems) == 1
        assert systems[0].metadata["confidence"] == 0.92

    def test_category_preserved_in_metadata(self):
        """Category is preserved in metadata."""
        disc_result = SystemDiscoveryResult(
            systems=[
                DiscoveredSystem(name="Test", category="finance"),
            ]
        )
        systems = SystemDiscoveryEngine._to_external_systems(disc_result)
        assert systems[0].metadata["category"] == "finance"

    def test_evidence_preserved_in_metadata(self):
        """Evidence list is preserved in metadata."""
        disc_result = SystemDiscoveryResult(
            systems=[
                DiscoveredSystem(
                    name="Test",
                    evidence=["KB doc #1", "Entity: Payment Gateway"],
                ),
            ]
        )
        systems = SystemDiscoveryEngine._to_external_systems(disc_result)
        assert systems[0].metadata["evidence"] == ["KB doc #1", "Entity: Payment Gateway"]

    def test_status_is_draft(self):
        """All converted systems have DRAFT status."""
        disc_result = SystemDiscoveryResult(
            systems=[DiscoveredSystem(name="Draft System")]
        )
        systems = SystemDiscoveryEngine._to_external_systems(disc_result)
        assert systems[0].status == SystemStatus.DRAFT

    def test_auth_type_mapped_correctly(self):
        """auth_type string is mapped to the correct AuthType enum."""
        disc_result = SystemDiscoveryResult(
            systems=[DiscoveredSystem(name="OAuth Sys", auth_type="oauth2")]
        )
        systems = SystemDiscoveryEngine._to_external_systems(disc_result)
        assert systems[0].auth_config.auth_type == AuthType.OAUTH2

    def test_unknown_auth_type_defaults_to_none(self):
        """Unrecognised auth_type falls back to NONE."""
        disc_result = SystemDiscoveryResult(
            systems=[DiscoveredSystem(name="Unknown Auth", auth_type="kerberos")]
        )
        systems = SystemDiscoveryEngine._to_external_systems(disc_result)
        assert systems[0].auth_config.auth_type == AuthType.NONE

    def test_agent_enabled_is_false(self):
        """All converted systems have agent_enabled=False."""
        disc_result = SystemDiscoveryResult(
            systems=[DiscoveredSystem(name="Test")]
        )
        systems = SystemDiscoveryEngine._to_external_systems(disc_result)
        assert systems[0].agent_enabled is False

    def test_id_is_uuid_format(self):
        """Generated id is a valid UUID."""
        disc_result = SystemDiscoveryResult(
            systems=[DiscoveredSystem(name="UUID Test")]
        )
        systems = SystemDiscoveryEngine._to_external_systems(disc_result)
        # Should not raise ValueError
        parsed = uuid.UUID(systems[0].id)
        assert str(parsed) == systems[0].id

    def test_empty_result_converts_to_empty_list(self):
        """An empty SystemDiscoveryResult converts to an empty list."""
        result = SystemDiscoveryEngine._to_external_systems(
            SystemDiscoveryResult(systems=[])
        )
        assert result == []

    def test_name_and_description_preserved(self):
        """Name and description are passed through from DiscoveredSystem."""
        disc_result = SystemDiscoveryResult(
            systems=[
                DiscoveredSystem(
                    name="Payment Gateway",
                    description="Handles all payment processing",
                )
            ]
        )
        systems = SystemDiscoveryEngine._to_external_systems(disc_result)
        assert systems[0].name == "Payment Gateway"
        assert systems[0].description == "Handles all payment processing"

    def test_tags_preserved(self):
        """Tags from the discovered system are passed through."""
        disc_result = SystemDiscoveryResult(
            systems=[
                DiscoveredSystem(name="Tagged", tags=["payments", "api"])
            ]
        )
        systems = SystemDiscoveryEngine._to_external_systems(disc_result)
        assert systems[0].tags == ["payments", "api"]

    def test_metadata_source_is_auto_discovered(self):
        """Metadata source field is set to 'auto_discovered'."""
        disc_result = SystemDiscoveryResult(
            systems=[DiscoveredSystem(name="Test")]
        )
        systems = SystemDiscoveryEngine._to_external_systems(disc_result)
        assert systems[0].metadata["source"] == "auto_discovered"


# ---------------------------------------------------------------------------
# Tests: _merge_systems
# ---------------------------------------------------------------------------


class TestMergeSystems:
    """Tests for SystemDiscoveryEngine._merge_systems()."""

    async def test_new_system_created(self, engine, mock_catalog_repo):
        """Brand new system is created via catalog_repo.create_system."""
        mock_catalog_repo.list_systems.return_value = []

        new_system = ExternalSystem(
            id="new-1",
            name="Brand New System",
            description="A new system",
            base_url="https://new.example.com",
            status=SystemStatus.DRAFT,
        )
        stats = await engine._merge_systems([new_system])
        assert stats["created"] == 1
        assert stats["skipped"] == 0
        assert stats["discovered"] == 1
        mock_catalog_repo.create_system.assert_awaited_once_with(new_system)

    async def test_existing_name_skipped(self, engine, mock_catalog_repo):
        """System with matching name (exact) is skipped."""
        mock_catalog_repo.list_systems.return_value = [
            _make_system("existing-1", name="CRM System"),
        ]

        new_system = ExternalSystem(
            id="new-1",
            name="CRM System",
            description="Duplicate",
            base_url="https://crm.example.com",
            status=SystemStatus.DRAFT,
        )
        stats = await engine._merge_systems([new_system])
        assert stats["created"] == 0
        assert stats["skipped"] == 1
        mock_catalog_repo.create_system.assert_not_awaited()

    async def test_existing_name_case_insensitive(self, engine, mock_catalog_repo):
        """Case-insensitive name match skips the system."""
        mock_catalog_repo.list_systems.return_value = [
            _make_system("existing-1", name="CRM System"),
        ]

        new_system = ExternalSystem(
            id="new-1",
            name="crm system",  # different case
            description="Should be skipped",
            base_url="",
            status=SystemStatus.DRAFT,
        )
        stats = await engine._merge_systems([new_system])
        assert stats["created"] == 0
        assert stats["skipped"] == 1

    async def test_mixed_scenario_correct_counts(self, engine, mock_catalog_repo):
        """Mixed: some new, some existing -- correct created/skipped counts."""
        mock_catalog_repo.list_systems.return_value = [
            _make_system("e-1", name="Existing CRM"),
            _make_system("e-2", name="Existing ERP"),
        ]

        discovered = [
            ExternalSystem(
                id="n-1",
                name="Existing CRM",  # already exists
                description="Skip me",
                base_url="",
                status=SystemStatus.DRAFT,
            ),
            ExternalSystem(
                id="n-2",
                name="Brand New Payment Gateway",  # new
                description="Create me",
                base_url="https://pay.example.com",
                status=SystemStatus.DRAFT,
            ),
            ExternalSystem(
                id="n-3",
                name="existing erp",  # case-insensitive match
                description="Skip me too",
                base_url="",
                status=SystemStatus.DRAFT,
            ),
            ExternalSystem(
                id="n-4",
                name="New HR System",  # new
                description="Create me too",
                base_url="https://hr.example.com",
                status=SystemStatus.DRAFT,
            ),
        ]

        stats = await engine._merge_systems(discovered)
        assert stats["discovered"] == 4
        assert stats["created"] == 2
        assert stats["skipped"] == 2
        assert mock_catalog_repo.create_system.await_count == 2

    async def test_empty_discovered_list(self, engine, mock_catalog_repo):
        """Empty discovered list produces zero counts."""
        stats = await engine._merge_systems([])
        assert stats["discovered"] == 0
        assert stats["created"] == 0
        assert stats["skipped"] == 0
        mock_catalog_repo.create_system.assert_not_awaited()
