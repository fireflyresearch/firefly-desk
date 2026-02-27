# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for ProcessDiscoveryEngine -- LLM-driven process discovery."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.audit.models import AuditEventType
from flydesk.jobs.handlers import JobHandler, ProcessDiscoveryHandler
from flydesk.models.base import Base
from flydesk.processes.discovery import (
    DiscoveredDependency,
    DiscoveredProcess,
    DiscoveredStep,
    DiscoveryContext,
    DiscoveryResult,
    ProcessDiscoveryEngine,
    SystemContext,
)
from flydesk.processes.models import (
    BusinessProcess,
    ProcessDependency,
    ProcessSource,
    ProcessStatus,
    ProcessStep,
)
from flydesk.processes.repository import ProcessRepository


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def session_factory():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def process_repo(session_factory):
    return ProcessRepository(session_factory)


@pytest.fixture
def mock_catalog_repo():
    repo = AsyncMock()
    repo.list_systems.return_value = ([], 0)
    repo.list_endpoints.return_value = []
    repo.list_knowledge_documents.return_value = []
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


def _make_llm_response(processes: list[dict]) -> str:
    """Build a JSON string matching the DiscoveryResult schema."""
    return json.dumps({"processes": processes})


def _sample_process_dict(
    name: str = "Order Fulfillment",
    confidence: float = 0.85,
    category: str = "operations",
) -> dict:
    """Return a sample process dict as the LLM would produce."""
    return {
        "name": name,
        "description": f"The {name} business process",
        "category": category,
        "confidence": confidence,
        "tags": ["auto-discovered", category],
        "steps": [
            {
                "id": "step-1",
                "name": "Receive Order",
                "description": "Customer places an order",
                "step_type": "action",
                "system_id": "sys-crm",
                "endpoint_id": "ep-orders",
                "order": 0,
                "inputs": ["customer_id"],
                "outputs": ["order_id"],
            },
            {
                "id": "step-2",
                "name": "Process Payment",
                "description": "Validate and process payment",
                "step_type": "action",
                "system_id": "sys-billing",
                "endpoint_id": None,
                "order": 1,
                "inputs": ["order_id"],
                "outputs": ["payment_status"],
            },
        ],
        "dependencies": [
            {
                "source_step_id": "step-1",
                "target_step_id": "step-2",
                "condition": None,
            }
        ],
    }


def _make_mock_agent(response_text: str, input_tokens: int = 100, output_tokens: int = 50) -> AsyncMock:
    """Create a mock FireflyAgent whose run() returns the given text."""
    agent = AsyncMock()
    agent._model_identifier = "test-model"
    result = MagicMock()
    result.output = response_text
    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.total_tokens = input_tokens + output_tokens
    result.usage.return_value = usage
    agent.run.return_value = result
    return agent


def _make_process(
    process_id: str = "p-1",
    name: str = "Test Process",
    status: ProcessStatus = ProcessStatus.DISCOVERED,
    **kwargs,
) -> BusinessProcess:
    now = datetime.now(timezone.utc)
    return BusinessProcess(
        id=process_id,
        name=name,
        description=kwargs.pop("description", "A test process"),
        category=kwargs.pop("category", "operations"),
        steps=kwargs.pop("steps", []),
        dependencies=kwargs.pop("dependencies", []),
        source=kwargs.pop("source", ProcessSource.AUTO_DISCOVERED),
        confidence=kwargs.pop("confidence", 0.5),
        status=status,
        tags=kwargs.pop("tags", ["test"]),
        created_at=kwargs.pop("created_at", now),
        updated_at=kwargs.pop("updated_at", now),
        **kwargs,
    )


@pytest.fixture
def engine(mock_agent_factory, process_repo, mock_catalog_repo, mock_knowledge_graph):
    return ProcessDiscoveryEngine(
        agent_factory=mock_agent_factory,
        process_repo=process_repo,
        catalog_repo=mock_catalog_repo,
        knowledge_graph=mock_knowledge_graph,
    )


@pytest.fixture
def on_progress():
    return AsyncMock()


# ---------------------------------------------------------------------------
# Tests: DiscoveryResult parsing
# ---------------------------------------------------------------------------


class TestLLMResponseParsing:
    """Tests for ProcessDiscoveryEngine._parse_llm_response()."""

    def test_valid_json(self):
        """A well-formed JSON response is parsed into DiscoveryResult."""
        text = _make_llm_response([_sample_process_dict()])
        result, _error = ProcessDiscoveryEngine._parse_llm_response(text)
        assert len(result.processes) == 1
        assert result.processes[0].name == "Order Fulfillment"
        assert result.processes[0].confidence == 0.85
        assert len(result.processes[0].steps) == 2
        assert len(result.processes[0].dependencies) == 1

    def test_json_with_markdown_code_block(self):
        """JSON wrapped in markdown code fences is handled."""
        inner = _make_llm_response([_sample_process_dict()])
        text = f"```json\n{inner}\n```"
        result, _error = ProcessDiscoveryEngine._parse_llm_response(text)
        assert len(result.processes) == 1

    def test_json_with_plain_code_block(self):
        """JSON wrapped in plain code fences (no language) is handled."""
        inner = _make_llm_response([_sample_process_dict()])
        text = f"```\n{inner}\n```"
        result, _error = ProcessDiscoveryEngine._parse_llm_response(text)
        assert len(result.processes) == 1

    def test_malformed_json_returns_empty(self):
        """Malformed JSON returns an empty DiscoveryResult instead of raising."""
        result, _error = ProcessDiscoveryEngine._parse_llm_response("this is not json {{{")
        assert result.processes == []

    def test_valid_json_wrong_schema_returns_empty(self):
        """Valid JSON that doesn't match the schema returns empty result."""
        result, _error = ProcessDiscoveryEngine._parse_llm_response('{"foo": "bar"}')
        # Pydantic will accept it with processes defaulting to []
        assert result.processes == []

    def test_empty_processes_list(self):
        """An empty processes list is valid."""
        result, _error = ProcessDiscoveryEngine._parse_llm_response('{"processes": []}')
        assert result.processes == []

    def test_multiple_processes_parsed(self):
        """Multiple processes in the response are all parsed."""
        procs = [
            _sample_process_dict("Process A", 0.9, "hr"),
            _sample_process_dict("Process B", 0.7, "finance"),
        ]
        result, _error = ProcessDiscoveryEngine._parse_llm_response(_make_llm_response(procs))
        assert len(result.processes) == 2
        assert result.processes[0].name == "Process A"
        assert result.processes[1].name == "Process B"

    def test_whitespace_handling(self):
        """Leading/trailing whitespace is stripped before parsing."""
        text = f"   \n  {_make_llm_response([_sample_process_dict()])}  \n  "
        result, _error = ProcessDiscoveryEngine._parse_llm_response(text)
        assert len(result.processes) == 1

    def test_step_defaults(self):
        """Steps with missing optional fields use defaults."""
        proc = {
            "name": "Minimal",
            "steps": [{"id": "s1", "name": "Step One"}],
            "dependencies": [],
        }
        result, _error = ProcessDiscoveryEngine._parse_llm_response(_make_llm_response([proc]))
        step = result.processes[0].steps[0]
        assert step.step_type == "action"
        assert step.system_id is None
        assert step.order == 0
        assert step.inputs == []
        assert step.outputs == []


# ---------------------------------------------------------------------------
# Tests: Domain model conversion
# ---------------------------------------------------------------------------


class TestDomainModelConversion:
    """Tests for ProcessDiscoveryEngine._to_business_processes()."""

    def test_converts_single_process(self):
        """A DiscoveryResult with one process converts to one BusinessProcess."""
        disc_result = DiscoveryResult(
            processes=[
                DiscoveredProcess(
                    name="Test Process",
                    description="A test",
                    category="ops",
                    confidence=0.9,
                    tags=["tag1"],
                    steps=[
                        DiscoveredStep(id="s1", name="Step 1", order=0),
                        DiscoveredStep(id="s2", name="Step 2", order=1),
                    ],
                    dependencies=[
                        DiscoveredDependency(source_step_id="s1", target_step_id="s2")
                    ],
                )
            ]
        )
        processes = ProcessDiscoveryEngine._to_business_processes(disc_result)
        assert len(processes) == 1
        proc = processes[0]
        assert proc.name == "Test Process"
        assert proc.source == ProcessSource.AUTO_DISCOVERED
        assert proc.status == ProcessStatus.DISCOVERED
        assert proc.confidence == 0.9
        assert len(proc.steps) == 2
        assert len(proc.dependencies) == 1
        assert proc.id  # UUID is generated
        # Step IDs are namespaced with process UUID prefix
        prefix = proc.id[:8]
        assert proc.steps[0].id == f"{prefix}-s1"
        assert proc.steps[1].id == f"{prefix}-s2"
        # Dependency step IDs are also namespaced
        assert proc.dependencies[0].source_step_id == f"{prefix}-s1"
        assert proc.dependencies[0].target_step_id == f"{prefix}-s2"

    def test_converts_empty_result(self):
        """An empty DiscoveryResult converts to an empty list."""
        result = ProcessDiscoveryEngine._to_business_processes(
            DiscoveryResult(processes=[])
        )
        assert result == []

    def test_step_fields_preserved(self):
        """All step fields are correctly mapped from DiscoveredStep to ProcessStep."""
        disc_result = DiscoveryResult(
            processes=[
                DiscoveredProcess(
                    name="P",
                    steps=[
                        DiscoveredStep(
                            id="s1",
                            name="Full Step",
                            description="desc",
                            step_type="decision",
                            system_id="sys-1",
                            endpoint_id="ep-1",
                            order=5,
                            inputs=["a", "b"],
                            outputs=["c"],
                        )
                    ],
                )
            ]
        )
        proc = ProcessDiscoveryEngine._to_business_processes(disc_result)[0]
        step = proc.steps[0]
        assert step.id.endswith("-s1")  # Namespaced with process UUID prefix
        assert step.name == "Full Step"
        assert step.description == "desc"
        assert step.step_type == "decision"
        assert step.system_id == "sys-1"
        assert step.endpoint_id == "ep-1"
        assert step.order == 5
        assert step.inputs == ["a", "b"]
        assert step.outputs == ["c"]


# ---------------------------------------------------------------------------
# Tests: Context gathering
# ---------------------------------------------------------------------------


class TestContextGathering:
    """Tests for ProcessDiscoveryEngine._gather_context()."""

    async def test_empty_context_when_no_data(self, engine):
        """When no catalog/KG/KB data exists, context is empty but valid."""
        ctx = await engine._gather_context()
        assert ctx.systems == []
        assert ctx.entities == []
        assert ctx.relations == []
        assert ctx.documents == []

    async def test_catalog_systems_gathered(
        self, engine, mock_catalog_repo
    ):
        """Catalog systems and their endpoints are gathered."""
        system = MagicMock()
        system.id = "sys-1"
        system.name = "CRM"
        system.description = "Customer management"
        system.base_url = "https://crm.example.com"
        system.status = "active"
        system.tags = ["crm"]

        endpoint = MagicMock()
        endpoint.id = "ep-1"
        endpoint.name = "Create Customer"
        endpoint.description = "Creates a new customer"
        endpoint.method = "POST"
        endpoint.path = "/api/customers"
        endpoint.when_to_use = "When creating a customer"
        endpoint.risk_level = "low"

        mock_catalog_repo.list_systems.return_value = ([system], 1)
        mock_catalog_repo.list_endpoints.return_value = [endpoint]

        ctx = await engine._gather_context()
        assert len(ctx.systems) == 1
        assert ctx.systems[0].name == "CRM"
        assert len(ctx.systems[0].endpoints) == 1
        assert ctx.systems[0].endpoints[0]["name"] == "Create Customer"

    async def test_knowledge_graph_entities_gathered(
        self, engine, mock_knowledge_graph
    ):
        """Knowledge graph entities and relations are gathered."""
        entity = MagicMock()
        entity.id = "ent-1"
        entity.name = "Customer"
        entity.entity_type = "concept"
        entity.confidence = 0.95
        entity.properties = {"domain": "crm"}

        mock_knowledge_graph.list_entities.return_value = [entity]

        neighborhood = MagicMock()
        relation = MagicMock()
        relation.source_id = "ent-1"
        relation.target_id = "ent-2"
        relation.relation_type = "HAS_ORDER"
        relation.properties = {}
        neighborhood.relations = [relation]
        mock_knowledge_graph.get_entity_neighborhood.return_value = neighborhood

        ctx = await engine._gather_context()
        assert len(ctx.entities) == 1
        assert ctx.entities[0]["name"] == "Customer"
        assert len(ctx.relations) == 1
        assert ctx.relations[0]["relation_type"] == "HAS_ORDER"

    async def test_knowledge_documents_gathered(
        self, engine, mock_catalog_repo
    ):
        """Knowledge base documents are gathered."""
        doc = MagicMock()
        doc.title = "Customer Onboarding Guide"
        doc.document_type = "manual"
        doc.tags = ["onboarding"]
        doc.content = "This guide describes the customer onboarding process."

        mock_catalog_repo.list_knowledge_documents.return_value = [doc]

        ctx = await engine._gather_context()
        assert len(ctx.documents) == 1
        assert ctx.documents[0]["title"] == "Customer Onboarding Guide"

    async def test_catalog_error_handled_gracefully(
        self, engine, mock_catalog_repo
    ):
        """Catalog errors are caught and context gathering continues."""
        mock_catalog_repo.list_systems.side_effect = RuntimeError("DB error")
        ctx = await engine._gather_context()
        assert ctx.systems == []
        # Other contexts should still be gathered
        assert isinstance(ctx.entities, list)
        assert isinstance(ctx.documents, list)

    async def test_kg_error_handled_gracefully(
        self, engine, mock_knowledge_graph
    ):
        """Knowledge graph errors are caught and context gathering continues."""
        mock_knowledge_graph.list_entities.side_effect = RuntimeError("KG error")
        ctx = await engine._gather_context()
        assert ctx.entities == []

    async def test_kb_error_handled_gracefully(
        self, engine, mock_catalog_repo
    ):
        """Knowledge base errors are caught and context gathering continues."""
        mock_catalog_repo.list_knowledge_documents.side_effect = RuntimeError("KB error")
        ctx = await engine._gather_context()
        assert ctx.documents == []


# ---------------------------------------------------------------------------
# Tests: Prompt rendering
# ---------------------------------------------------------------------------


class TestPromptRendering:
    """Tests for prompt template rendering."""

    def test_system_prompt_renders_without_trigger(self, engine):
        """System prompt renders correctly with no trigger."""
        prompt = engine._render_system_prompt("")
        assert "business process discovery analyst" in prompt
        assert "JSON" in prompt

    def test_system_prompt_includes_trigger(self, engine):
        """System prompt includes the trigger description when provided."""
        prompt = engine._render_system_prompt("New CRM integration")
        assert "New CRM integration" in prompt
        assert "Discovery trigger" in prompt

    def test_context_prompt_with_empty_context(self, engine):
        """Context prompt renders with empty context (no data)."""
        ctx = DiscoveryContext()
        prompt = engine._render_context_prompt(ctx)
        assert "No external systems" in prompt
        assert "No knowledge graph entities" in prompt
        assert "No knowledge base documents" in prompt

    def test_context_prompt_with_systems(self, engine):
        """Context prompt renders system information."""
        ctx = DiscoveryContext(
            systems=[
                SystemContext(
                    id="sys-1",
                    name="CRM System",
                    description="Customer management",
                    base_url="https://crm.example.com",
                    status="active",
                    tags=["crm"],
                    endpoints=[
                        {
                            "id": "ep-1",
                            "name": "List Customers",
                            "description": "Returns customers",
                            "method": "GET",
                            "path": "/api/customers",
                            "when_to_use": "To list customers",
                            "risk_level": "low",
                        }
                    ],
                )
            ]
        )
        prompt = engine._render_context_prompt(ctx)
        assert "CRM System" in prompt
        assert "List Customers" in prompt
        assert "sys-1" in prompt

    def test_context_prompt_with_entities(self, engine):
        """Context prompt renders knowledge graph entities."""
        ctx = DiscoveryContext(
            entities=[
                {
                    "name": "Customer",
                    "entity_type": "concept",
                    "confidence": 0.95,
                    "properties": {"domain": "crm"},
                }
            ],
            relations=[
                {
                    "source_id": "ent-1",
                    "target_id": "ent-2",
                    "relation_type": "HAS_ORDER",
                    "properties": {},
                }
            ],
        )
        prompt = engine._render_context_prompt(ctx)
        assert "Customer" in prompt
        assert "HAS_ORDER" in prompt

    def test_context_prompt_with_documents(self, engine):
        """Context prompt renders knowledge base documents."""
        ctx = DiscoveryContext(
            documents=[
                {
                    "title": "Onboarding Guide",
                    "document_type": "manual",
                    "tags": ["onboarding"],
                    "content": "Steps for onboarding...",
                }
            ]
        )
        prompt = engine._render_context_prompt(ctx)
        assert "Onboarding Guide" in prompt
        assert "Steps for onboarding" in prompt


# ---------------------------------------------------------------------------
# Tests: LLM interaction
# ---------------------------------------------------------------------------


class TestLLMInteraction:
    """Tests for ProcessDiscoveryEngine._call_llm()."""

    async def test_no_llm_configured_returns_none(self, engine, mock_agent_factory, on_progress):
        """When no LLM provider is configured, _call_llm returns None."""
        mock_agent_factory.create_agent.return_value = None
        result, usage = await engine._call_llm("system prompt", "user prompt", on_progress)
        assert result is None
        assert usage == {}

    async def test_successful_llm_call(self, engine, mock_agent_factory, on_progress):
        """A successful LLM call returns parsed DiscoveryResult."""
        response_text = _make_llm_response([_sample_process_dict()])
        mock_agent = _make_mock_agent(response_text)
        mock_agent_factory.create_agent.return_value = mock_agent

        result, usage = await engine._call_llm("system prompt", "user prompt", on_progress)
        assert result is not None
        assert len(result.processes) == 1
        assert result.processes[0].name == "Order Fulfillment"
        mock_agent.run.assert_called_once_with("user prompt")

    async def test_llm_call_exception_returns_empty(self, engine, mock_agent_factory, on_progress):
        """An LLM call that throws returns an empty DiscoveryResult."""
        mock_agent = AsyncMock()
        mock_agent.run.side_effect = RuntimeError("API timeout")
        mock_agent_factory.create_agent.return_value = mock_agent

        result, usage = await engine._call_llm("system prompt", "user prompt", on_progress)
        assert result is not None
        assert result.processes == []

    async def test_llm_returns_malformed_json(self, engine, mock_agent_factory, on_progress):
        """Malformed LLM output returns empty DiscoveryResult."""
        mock_agent = _make_mock_agent("I'm sorry, I cannot help with that.")
        mock_agent_factory.create_agent.return_value = mock_agent

        result, usage = await engine._call_llm("system prompt", "user prompt", on_progress)
        assert result is not None
        assert result.processes == []


# ---------------------------------------------------------------------------
# Tests: Merge strategy
# ---------------------------------------------------------------------------


class TestMergeStrategy:
    """Tests for ProcessDiscoveryEngine._merge_processes()."""

    async def test_new_processes_created(self, engine, process_repo):
        """Brand new processes are created in the repository."""
        procs = [
            BusinessProcess(
                id="new-1",
                name="New Process",
                description="A new process",
                source=ProcessSource.AUTO_DISCOVERED,
                status=ProcessStatus.DISCOVERED,
                confidence=0.8,
            )
        ]
        stats = await engine._merge_processes(procs)
        assert stats["created"] == 1
        assert stats["updated"] == 0
        assert stats["skipped"] == 0

        stored = await process_repo.list()
        assert len(stored) == 1
        assert stored[0].name == "New Process"

    async def test_discovered_process_updated(self, engine, process_repo):
        """Existing DISCOVERED processes get updated on re-discovery."""
        # Create an existing discovered process
        existing = _make_process(
            name="Order Fulfillment",
            confidence=0.5,
            status=ProcessStatus.DISCOVERED,
        )
        await process_repo.create(existing)

        # Re-discover with higher confidence
        new_procs = [
            BusinessProcess(
                id="new-id",
                name="Order Fulfillment",
                description="Updated description",
                category="operations",
                source=ProcessSource.AUTO_DISCOVERED,
                status=ProcessStatus.DISCOVERED,
                confidence=0.9,
            )
        ]
        stats = await engine._merge_processes(new_procs)
        assert stats["updated"] == 1
        assert stats["created"] == 0

        stored = await process_repo.list()
        assert len(stored) == 1
        assert stored[0].confidence == 0.9
        assert stored[0].description == "Updated description"

    async def test_verified_process_not_overwritten(self, engine, process_repo):
        """VERIFIED processes are never overwritten during re-discovery."""
        existing = _make_process(
            name="Order Fulfillment",
            confidence=0.5,
            status=ProcessStatus.VERIFIED,
        )
        await process_repo.create(existing)

        new_procs = [
            BusinessProcess(
                id="new-id",
                name="Order Fulfillment",
                description="LLM says different",
                source=ProcessSource.AUTO_DISCOVERED,
                status=ProcessStatus.DISCOVERED,
                confidence=0.95,
            )
        ]
        stats = await engine._merge_processes(new_procs)
        assert stats["skipped"] == 1
        assert stats["updated"] == 0

        stored = await process_repo.list()
        assert len(stored) == 1
        assert stored[0].confidence == 0.5  # Not changed
        assert stored[0].status == ProcessStatus.VERIFIED

    async def test_modified_process_not_overwritten(self, engine, process_repo):
        """MODIFIED processes are never overwritten during re-discovery."""
        existing = _make_process(
            name="HR Onboarding",
            confidence=0.6,
            status=ProcessStatus.MODIFIED,
        )
        await process_repo.create(existing)

        new_procs = [
            BusinessProcess(
                id="new-id",
                name="HR Onboarding",
                description="LLM version",
                source=ProcessSource.AUTO_DISCOVERED,
                status=ProcessStatus.DISCOVERED,
                confidence=0.8,
            )
        ]
        stats = await engine._merge_processes(new_procs)
        assert stats["skipped"] == 1

        stored = await process_repo.list()
        assert stored[0].status == ProcessStatus.MODIFIED
        assert stored[0].confidence == 0.6

    async def test_archived_process_updated(self, engine, process_repo):
        """ARCHIVED processes can be updated on re-discovery."""
        existing = _make_process(
            name="Legacy Process",
            confidence=0.3,
            status=ProcessStatus.ARCHIVED,
        )
        await process_repo.create(existing)

        new_procs = [
            BusinessProcess(
                id="new-id",
                name="Legacy Process",
                description="Rediscovered",
                source=ProcessSource.AUTO_DISCOVERED,
                status=ProcessStatus.DISCOVERED,
                confidence=0.75,
            )
        ]
        stats = await engine._merge_processes(new_procs)
        assert stats["updated"] == 1

        stored = await process_repo.list()
        assert stored[0].confidence == 0.75
        assert stored[0].status == ProcessStatus.DISCOVERED

    async def test_mixed_merge_scenario(self, engine, process_repo):
        """Mixed scenario: create new, update discovered, skip verified."""
        now = datetime.now(timezone.utc)
        await process_repo.create(
            _make_process("p-1", name="Existing Discovered", status=ProcessStatus.DISCOVERED, created_at=now)
        )
        await process_repo.create(
            _make_process("p-2", name="Existing Verified", status=ProcessStatus.VERIFIED, created_at=now)
        )

        new_procs = [
            BusinessProcess(
                id="n-1",
                name="Existing Discovered",
                description="Updated",
                source=ProcessSource.AUTO_DISCOVERED,
                status=ProcessStatus.DISCOVERED,
                confidence=0.9,
            ),
            BusinessProcess(
                id="n-2",
                name="Existing Verified",
                description="Should skip",
                source=ProcessSource.AUTO_DISCOVERED,
                status=ProcessStatus.DISCOVERED,
                confidence=0.9,
            ),
            BusinessProcess(
                id="n-3",
                name="Brand New Process",
                description="New one",
                source=ProcessSource.AUTO_DISCOVERED,
                status=ProcessStatus.DISCOVERED,
                confidence=0.8,
            ),
        ]

        stats = await engine._merge_processes(new_procs)
        assert stats["discovered"] == 3
        assert stats["created"] == 1
        assert stats["updated"] == 1
        assert stats["skipped"] == 1


# ---------------------------------------------------------------------------
# Tests: Full analysis pipeline
# ---------------------------------------------------------------------------


def _add_minimal_context(mock_catalog_repo):
    """Set up mock catalog with a single system so _analyze passes the empty-context check."""
    system = MagicMock()
    system.id = "sys-ctx"
    system.name = "Context System"
    system.description = "Provides context for pipeline tests"
    system.base_url = "https://ctx.example.com"
    system.status = "active"
    system.tags = []
    mock_catalog_repo.list_systems.return_value = ([system], 1)
    mock_catalog_repo.list_endpoints.return_value = []


class TestAnalyzePipeline:
    """Integration-level tests for the _analyze() pipeline."""

    async def test_full_pipeline_with_llm(
        self, engine, mock_agent_factory, mock_catalog_repo, on_progress, process_repo
    ):
        """Full pipeline: gather context -> call LLM -> parse -> merge -> persist."""
        _add_minimal_context(mock_catalog_repo)
        response_text = _make_llm_response([_sample_process_dict()])
        mock_agent = _make_mock_agent(response_text)
        mock_agent_factory.create_agent.return_value = mock_agent

        result = await engine._analyze(
            "job-123",
            {"trigger": "New system added"},
            on_progress,
        )
        assert result["status"] == "completed"
        assert result["processes_discovered"] == 1
        assert result["processes_created"] == 1
        assert result["trigger"] == "New system added"

        # Verify the process was persisted
        stored = await process_repo.list()
        assert len(stored) == 1
        assert stored[0].name == "Order Fulfillment"
        assert stored[0].source == ProcessSource.AUTO_DISCOVERED

        # Verify progress was reported
        assert on_progress.call_count >= 5

    async def test_pipeline_no_llm_configured(
        self, engine, mock_agent_factory, mock_catalog_repo, on_progress
    ):
        """Pipeline gracefully handles no LLM configured."""
        _add_minimal_context(mock_catalog_repo)
        mock_agent_factory.create_agent.return_value = None

        result = await engine._analyze("job-456", {"trigger": ""}, on_progress)
        assert result["status"] == "skipped"
        assert result["reason"] == "no_llm_configured"
        assert result["processes_discovered"] == 0

    async def test_pipeline_llm_returns_empty(
        self, engine, mock_agent_factory, mock_catalog_repo, on_progress
    ):
        """Pipeline handles LLM returning no processes."""
        _add_minimal_context(mock_catalog_repo)
        response_text = _make_llm_response([])
        mock_agent = _make_mock_agent(response_text)
        mock_agent_factory.create_agent.return_value = mock_agent

        result = await engine._analyze("job-789", {"trigger": "test"}, on_progress)
        assert result["status"] == "completed"
        assert result["processes_discovered"] == 0
        assert result["processes_created"] == 0

    async def test_pipeline_llm_malformed_response(
        self, engine, mock_agent_factory, mock_catalog_repo, on_progress
    ):
        """Pipeline handles malformed LLM response gracefully."""
        _add_minimal_context(mock_catalog_repo)
        mock_agent = _make_mock_agent("I cannot help with that request.")
        mock_agent_factory.create_agent.return_value = mock_agent

        result = await engine._analyze("job-bad", {"trigger": "test"}, on_progress)
        assert result["status"] == "completed"
        assert result["processes_discovered"] == 0

    async def test_pipeline_multiple_processes(
        self, engine, mock_agent_factory, mock_catalog_repo, on_progress, process_repo
    ):
        """Pipeline discovers and persists multiple processes."""
        _add_minimal_context(mock_catalog_repo)
        procs = [
            _sample_process_dict("Process A", 0.9, "hr"),
            _sample_process_dict("Process B", 0.7, "finance"),
            _sample_process_dict("Process C", 0.6, "operations"),
        ]
        response_text = _make_llm_response(procs)
        mock_agent = _make_mock_agent(response_text)
        mock_agent_factory.create_agent.return_value = mock_agent

        result = await engine._analyze("job-multi", {"trigger": ""}, on_progress)
        assert result["processes_discovered"] == 3
        assert result["processes_created"] == 3

        stored = await process_repo.list()
        assert len(stored) == 3

    async def test_pipeline_progress_callback(
        self, engine, mock_agent_factory, mock_catalog_repo, on_progress
    ):
        """Progress callback is invoked at each stage."""
        _add_minimal_context(mock_catalog_repo)
        response_text = _make_llm_response([_sample_process_dict()])
        mock_agent = _make_mock_agent(response_text)
        mock_agent_factory.create_agent.return_value = mock_agent

        await engine._analyze("job-prog", {"trigger": "test"}, on_progress)

        # Verify progress was called with increasing percentages
        progress_calls = [call.args[0] for call in on_progress.call_args_list]
        assert progress_calls[0] == 5
        assert progress_calls[-1] == 100
        # Verify monotonically increasing
        for i in range(1, len(progress_calls)):
            assert progress_calls[i] >= progress_calls[i - 1]


# ---------------------------------------------------------------------------
# Tests: ProcessDiscoveryHandler
# ---------------------------------------------------------------------------


class TestProcessDiscoveryHandler:
    """Tests for the ProcessDiscoveryHandler job handler."""

    def test_satisfies_job_handler_protocol(self, engine):
        """ProcessDiscoveryHandler satisfies the JobHandler protocol."""
        handler = ProcessDiscoveryHandler(engine)
        assert isinstance(handler, JobHandler)

    async def test_handler_delegates_to_engine(
        self, engine, mock_agent_factory, mock_catalog_repo, on_progress
    ):
        """Handler.execute() delegates to engine._analyze()."""
        _add_minimal_context(mock_catalog_repo)
        mock_agent_factory.create_agent.return_value = None
        handler = ProcessDiscoveryHandler(engine)

        result = await handler.execute("job-1", {"trigger": "test"}, on_progress)
        assert result["status"] == "skipped"

    async def test_handler_passes_payload(
        self, engine, mock_agent_factory, mock_catalog_repo, on_progress
    ):
        """Handler passes the payload through to the engine."""
        _add_minimal_context(mock_catalog_repo)
        response_text = _make_llm_response([_sample_process_dict()])
        mock_agent = _make_mock_agent(response_text)
        mock_agent_factory.create_agent.return_value = mock_agent

        handler = ProcessDiscoveryHandler(engine)
        result = await handler.execute(
            "job-2", {"trigger": "Manual trigger"}, on_progress
        )
        assert result["trigger"] == "Manual trigger"


# ---------------------------------------------------------------------------
# Tests: Cost tracking
# ---------------------------------------------------------------------------


class TestCostTracking:
    """Tests for LLM cost tracking in process discovery."""

    async def test_analyze_includes_cost_in_result(
        self, engine, mock_agent_factory, on_progress
    ):
        """_analyze() includes token counts and cost in the result dict."""
        _add_minimal_context(engine._catalog_repo)
        response_text = _make_llm_response([_sample_process_dict()])
        mock_agent = _make_mock_agent(response_text, input_tokens=500, output_tokens=200)
        mock_agent_factory.create_agent.return_value = mock_agent

        result = await engine._analyze("job-cost-1", {"trigger": "test"}, on_progress)
        assert result["status"] == "completed"
        assert result["input_tokens"] == 500
        assert result["output_tokens"] == 200
        assert result["model"] == "test-model"

    async def test_analyze_emits_audit_event(
        self, mock_agent_factory, process_repo, mock_catalog_repo, mock_knowledge_graph, on_progress
    ):
        """_analyze() logs a DISCOVERY_RESPONSE audit event when audit_logger is provided."""
        audit_logger = AsyncMock()
        audit_logger.log = AsyncMock(return_value="evt-1")
        engine = ProcessDiscoveryEngine(
            agent_factory=mock_agent_factory,
            process_repo=process_repo,
            catalog_repo=mock_catalog_repo,
            knowledge_graph=mock_knowledge_graph,
            audit_logger=audit_logger,
        )
        _add_minimal_context(mock_catalog_repo)

        response_text = _make_llm_response([_sample_process_dict()])
        mock_agent = _make_mock_agent(response_text, input_tokens=1000, output_tokens=500)
        mock_agent_factory.create_agent.return_value = mock_agent

        await engine._analyze("job-audit-1", {"trigger": "test"}, on_progress)

        audit_logger.log.assert_called_once()
        event = audit_logger.log.call_args[0][0]
        assert event.event_type == AuditEventType.DISCOVERY_RESPONSE
        assert event.action == "process_discovery"
        assert event.detail["job_id"] == "job-audit-1"
        assert event.detail["input_tokens"] == 1000
        assert event.detail["output_tokens"] == 500

    async def test_no_audit_when_logger_not_provided(
        self, engine, mock_agent_factory, on_progress
    ):
        """No audit event is logged when audit_logger is None."""
        _add_minimal_context(engine._catalog_repo)
        response_text = _make_llm_response([_sample_process_dict()])
        mock_agent = _make_mock_agent(response_text)
        mock_agent_factory.create_agent.return_value = mock_agent

        # engine fixture has no audit_logger — should not raise
        result = await engine._analyze("job-no-audit", {"trigger": "test"}, on_progress)
        assert result["status"] == "completed"


# ---------------------------------------------------------------------------
# Tests: Discover (submission)
# ---------------------------------------------------------------------------


class TestDiscover:
    """Tests for ProcessDiscoveryEngine.discover() job submission."""

    async def test_discover_submits_job(self, engine):
        """discover() submits a process_discovery job to the runner."""
        mock_runner = AsyncMock()
        mock_job = MagicMock()
        mock_job.id = "job-submitted"
        mock_runner.submit.return_value = mock_job

        job = await engine.discover("New CRM added", mock_runner)
        assert job.id == "job-submitted"
        mock_runner.submit.assert_called_once_with(
            "process_discovery", {"trigger": "New CRM added"}
        )


# ---------------------------------------------------------------------------
# Tests: Edge cases / robustness
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Additional edge cases and robustness tests."""

    def test_discovery_result_model(self):
        """DiscoveryResult model can be created from raw dict."""
        data = {
            "processes": [
                {
                    "name": "Test",
                    "description": "desc",
                    "category": "ops",
                    "confidence": 0.5,
                    "tags": [],
                    "steps": [],
                    "dependencies": [],
                }
            ]
        }
        result = DiscoveryResult.model_validate(data)
        assert len(result.processes) == 1
        assert result.processes[0].name == "Test"

    def test_discovered_step_model(self):
        """DiscoveredStep model validates correctly."""
        step = DiscoveredStep(id="s1", name="Step 1")
        assert step.step_type == "action"
        assert step.inputs == []

    def test_discovered_dependency_model(self):
        """DiscoveredDependency model validates correctly."""
        dep = DiscoveredDependency(source_step_id="s1", target_step_id="s2")
        assert dep.condition is None

    def test_system_context_dataclass(self):
        """SystemContext dataclass works with defaults."""
        ctx = SystemContext(
            id="sys-1",
            name="Test",
            description="desc",
            base_url="https://example.com",
            status="active",
        )
        assert ctx.tags == []
        assert ctx.endpoints == []

    async def test_duplicate_relations_deduplicated(
        self, engine, mock_knowledge_graph
    ):
        """Duplicate relations from overlapping neighborhoods are deduplicated."""
        entity1 = MagicMock()
        entity1.id = "e1"
        entity1.name = "Entity 1"
        entity1.entity_type = "concept"
        entity1.confidence = 1.0
        entity1.properties = {}

        entity2 = MagicMock()
        entity2.id = "e2"
        entity2.name = "Entity 2"
        entity2.entity_type = "concept"
        entity2.confidence = 1.0
        entity2.properties = {}

        mock_knowledge_graph.list_entities.return_value = [entity1, entity2]

        # Both entities share the same relation
        shared_relation = MagicMock()
        shared_relation.source_id = "e1"
        shared_relation.target_id = "e2"
        shared_relation.relation_type = "RELATES_TO"
        shared_relation.properties = {}

        neighborhood = MagicMock()
        neighborhood.relations = [shared_relation]
        mock_knowledge_graph.get_entity_neighborhood.return_value = neighborhood

        ctx = await engine._gather_context()
        # The relation should appear only once even though both entities share it
        assert len(ctx.relations) == 1
