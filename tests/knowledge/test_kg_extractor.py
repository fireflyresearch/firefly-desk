# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for KGExtractor -- LLM-based knowledge graph entity/relation extraction."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.knowledge.kg_extractor import (
    ExtractedEntity,
    ExtractedRelation,
    KGExtractionResult,
    KGExtractor,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_extraction_response(
    entities: list[dict] | None = None,
    relations: list[dict] | None = None,
) -> str:
    """Build a JSON string matching the KGExtractionResult schema."""
    return json.dumps(
        {
            "entities": entities or [],
            "relations": relations or [],
        }
    )


def _sample_extraction_response() -> str:
    """Return a sample extraction response from the LLM."""
    return _make_extraction_response(
        entities=[
            {
                "name": "Customer",
                "entity_type": "concept",
                "properties": {"domain": "crm"},
                "confidence": 0.95,
            },
            {
                "name": "Order",
                "entity_type": "concept",
                "properties": {"domain": "commerce"},
                "confidence": 0.9,
            },
        ],
        relations=[
            {
                "source": "Customer",
                "target": "Order",
                "relation_type": "places",
                "properties": {},
                "confidence": 0.85,
            }
        ],
    )


def _make_mock_agent(response_text: str) -> AsyncMock:
    """Create a mock FireflyAgent whose run() returns the given text."""
    agent = AsyncMock()
    result = MagicMock()
    result.output = response_text
    agent.run.return_value = result
    return agent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_agent_factory():
    factory = AsyncMock()
    factory.create_agent.return_value = None  # Default: no LLM configured
    return factory


@pytest.fixture
def extractor(mock_agent_factory):
    return KGExtractor(mock_agent_factory)


# ---------------------------------------------------------------------------
# Tests: _parse_response
# ---------------------------------------------------------------------------


class TestParseResponse:
    """Tests for KGExtractor._parse_response()."""

    def test_valid_json(self):
        """A well-formed JSON response is parsed correctly."""
        text = _sample_extraction_response()
        result = KGExtractor._parse_response(text)
        assert len(result.entities) == 2
        assert result.entities[0].name == "Customer"
        assert result.entities[0].entity_type == "concept"
        assert result.entities[0].confidence == 0.95
        assert len(result.relations) == 1
        assert result.relations[0].source == "Customer"
        assert result.relations[0].target == "Order"

    def test_json_with_markdown_code_block(self):
        """JSON wrapped in markdown code fences is handled."""
        inner = _sample_extraction_response()
        text = f"```json\n{inner}\n```"
        result = KGExtractor._parse_response(text)
        assert len(result.entities) == 2

    def test_json_with_plain_code_block(self):
        """JSON wrapped in plain code fences is handled."""
        inner = _sample_extraction_response()
        text = f"```\n{inner}\n```"
        result = KGExtractor._parse_response(text)
        assert len(result.entities) == 2

    def test_malformed_json_returns_empty(self):
        """Malformed JSON returns an empty result."""
        result = KGExtractor._parse_response("this is not json {{{")
        assert result.entities == []
        assert result.relations == []

    def test_wrong_schema_returns_empty(self):
        """Valid JSON that doesn't match the schema returns empty result."""
        result = KGExtractor._parse_response('{"foo": "bar"}')
        assert result.entities == []
        assert result.relations == []

    def test_empty_entities_and_relations(self):
        """An empty entities/relations list is valid."""
        text = _make_extraction_response([], [])
        result = KGExtractor._parse_response(text)
        assert result.entities == []
        assert result.relations == []

    def test_whitespace_handling(self):
        """Leading/trailing whitespace is stripped."""
        text = f"  \n  {_sample_extraction_response()}  \n  "
        result = KGExtractor._parse_response(text)
        assert len(result.entities) == 2

    def test_entity_defaults(self):
        """Entity with only required fields uses defaults."""
        text = _make_extraction_response(
            entities=[{"name": "Foo", "entity_type": "concept"}]
        )
        result = KGExtractor._parse_response(text)
        assert result.entities[0].confidence == 1.0
        assert result.entities[0].properties == {}


# ---------------------------------------------------------------------------
# Tests: extract_from_document
# ---------------------------------------------------------------------------


class TestExtractFromDocument:
    """Tests for KGExtractor.extract_from_document()."""

    async def test_no_llm_configured(self, extractor, mock_agent_factory):
        """When no LLM provider is configured, returns empty lists."""
        mock_agent_factory.create_agent.return_value = None
        entities, relations = await extractor.extract_from_document(
            "Some content", "Test Doc"
        )
        assert entities == []
        assert relations == []

    async def test_successful_extraction(self, extractor, mock_agent_factory):
        """Successful LLM call extracts entities and relations."""
        mock_agent = _make_mock_agent(_sample_extraction_response())
        mock_agent_factory.create_agent.return_value = mock_agent

        entities, relations = await extractor.extract_from_document(
            "Customer places an order", "Order Process"
        )
        assert len(entities) == 2
        assert entities[0]["name"] == "Customer"
        assert entities[0]["entity_type"] == "concept"
        assert "id" in entities[0]  # UUID is generated
        assert entities[0]["confidence"] == 0.95

        assert len(relations) == 1
        assert relations[0]["relation_type"] == "places"
        assert relations[0]["source_id"] == entities[0]["id"]
        assert relations[0]["target_id"] == entities[1]["id"]

    async def test_llm_call_exception_returns_empty(self, extractor, mock_agent_factory):
        """An LLM call that throws returns empty lists."""
        mock_agent = AsyncMock()
        mock_agent.run.side_effect = RuntimeError("API timeout")
        mock_agent_factory.create_agent.return_value = mock_agent

        entities, relations = await extractor.extract_from_document(
            "Content", "Title"
        )
        assert entities == []
        assert relations == []

    async def test_malformed_llm_response(self, extractor, mock_agent_factory):
        """Malformed LLM output returns empty lists."""
        mock_agent = _make_mock_agent("Sorry, I cannot help with that.")
        mock_agent_factory.create_agent.return_value = mock_agent

        entities, relations = await extractor.extract_from_document(
            "Content", "Title"
        )
        assert entities == []
        assert relations == []

    async def test_content_truncated(self, extractor, mock_agent_factory):
        """Long content is truncated to avoid token limits."""
        mock_agent = _make_mock_agent(_make_extraction_response([], []))
        mock_agent_factory.create_agent.return_value = mock_agent

        long_content = "x" * 20000
        await extractor.extract_from_document(long_content, "Long Doc")

        # Verify the agent was called (content should have been truncated)
        mock_agent.run.assert_called_once()
        prompt = mock_agent.run.call_args.args[0]
        # The content in the prompt should be at most 8000 chars
        assert len(prompt) < 20000

    async def test_relation_with_unknown_entity_skipped(self, extractor, mock_agent_factory):
        """Relations referencing unknown entities are skipped."""
        response = _make_extraction_response(
            entities=[
                {"name": "Customer", "entity_type": "concept", "confidence": 0.9}
            ],
            relations=[
                {
                    "source": "Customer",
                    "target": "UnknownEntity",
                    "relation_type": "uses",
                    "confidence": 0.8,
                }
            ],
        )
        mock_agent = _make_mock_agent(response)
        mock_agent_factory.create_agent.return_value = mock_agent

        entities, relations = await extractor.extract_from_document("Content", "Title")
        assert len(entities) == 1
        assert len(relations) == 0  # Relation skipped because target not found


# ---------------------------------------------------------------------------
# Tests: extract_from_catalog
# ---------------------------------------------------------------------------


class TestExtractFromCatalog:
    """Tests for KGExtractor.extract_from_catalog()."""

    async def test_no_llm_configured(self, extractor, mock_agent_factory):
        """When no LLM is configured, returns empty lists."""
        mock_agent_factory.create_agent.return_value = None
        entities, relations = await extractor.extract_from_catalog(
            system_name="CRM",
            system_description="Customer management",
            base_url="https://crm.example.com",
            status="active",
            tags=["crm"],
            endpoints=[],
        )
        assert entities == []
        assert relations == []

    async def test_successful_catalog_extraction(self, extractor, mock_agent_factory):
        """Successful extraction from catalog system data."""
        response = _make_extraction_response(
            entities=[
                {"name": "CRM System", "entity_type": "system", "confidence": 1.0},
                {"name": "Create Customer", "entity_type": "api_endpoint", "confidence": 0.9},
            ],
            relations=[
                {
                    "source": "CRM System",
                    "target": "Create Customer",
                    "relation_type": "has_endpoint",
                    "confidence": 0.95,
                }
            ],
        )
        mock_agent = _make_mock_agent(response)
        mock_agent_factory.create_agent.return_value = mock_agent

        entities, relations = await extractor.extract_from_catalog(
            system_name="CRM",
            system_description="Customer management system",
            base_url="https://crm.example.com",
            status="active",
            tags=["crm", "core"],
            endpoints=[
                {
                    "method": "POST",
                    "path": "/api/customers",
                    "name": "Create Customer",
                    "description": "Creates a new customer record",
                }
            ],
        )
        assert len(entities) == 2
        assert entities[0]["name"] == "CRM System"
        assert entities[0]["source_system"] == "CRM"
        assert len(relations) == 1
        assert relations[0]["relation_type"] == "has_endpoint"

    async def test_catalog_with_no_endpoints(self, extractor, mock_agent_factory):
        """Catalog extraction with no endpoints still works."""
        response = _make_extraction_response(
            entities=[
                {"name": "Billing System", "entity_type": "system", "confidence": 1.0}
            ],
        )
        mock_agent = _make_mock_agent(response)
        mock_agent_factory.create_agent.return_value = mock_agent

        entities, relations = await extractor.extract_from_catalog(
            system_name="Billing",
            system_description="Payment processing",
            base_url="https://billing.example.com",
            status="active",
            tags=[],
            endpoints=[],
        )
        assert len(entities) == 1
        assert entities[0]["name"] == "Billing System"


# ---------------------------------------------------------------------------
# Tests: Pydantic models
# ---------------------------------------------------------------------------


class TestModels:
    """Tests for extraction Pydantic models."""

    def test_extracted_entity_defaults(self):
        """ExtractedEntity uses correct defaults."""
        entity = ExtractedEntity(name="Foo", entity_type="concept")
        assert entity.confidence == 1.0
        assert entity.properties == {}

    def test_extracted_relation_defaults(self):
        """ExtractedRelation uses correct defaults."""
        rel = ExtractedRelation(source="A", target="B", relation_type="uses")
        assert rel.confidence == 1.0
        assert rel.properties == {}

    def test_kg_extraction_result_defaults(self):
        """KGExtractionResult defaults to empty lists."""
        result = KGExtractionResult()
        assert result.entities == []
        assert result.relations == []

    def test_kg_extraction_result_from_dict(self):
        """KGExtractionResult can be created from a dict."""
        data = {
            "entities": [{"name": "X", "entity_type": "system"}],
            "relations": [{"source": "X", "target": "Y", "relation_type": "uses"}],
        }
        result = KGExtractionResult.model_validate(data)
        assert len(result.entities) == 1
        assert len(result.relations) == 1
