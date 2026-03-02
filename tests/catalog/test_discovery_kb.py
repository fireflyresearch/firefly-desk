# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for SystemDiscoveryEngine KB document support."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.catalog.discovery import SystemDiscoveryEngine
from flydesk.catalog.enums import SystemStatus
from flydesk.catalog.models import ExternalSystem
from flydesk.knowledge.models import KnowledgeDocument


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_llm_response(systems: list[dict]) -> str:
    """Build a JSON string matching the SystemDiscoveryResult schema."""
    return json.dumps({"systems": systems})


def _sample_system_dict(
    name: str = "Salesforce CRM",
    confidence: float = 0.85,
) -> dict:
    return {
        "name": name,
        "description": f"The {name} platform",
        "base_url": f"https://{name.lower().replace(' ', '-')}.example.com",
        "category": "crm",
        "auth_type": "oauth2",
        "confidence": confidence,
        "tags": ["auto-discovered"],
        "evidence": ["Found in KB document"],
    }


def _make_mock_agent(response_text: str) -> AsyncMock:
    agent = AsyncMock()
    agent._model_identifier = "test-model"
    result = MagicMock()
    result.output = response_text
    usage = MagicMock()
    usage.input_tokens = 100
    usage.output_tokens = 50
    usage.total_tokens = 150
    result.usage.return_value = usage
    agent.run.return_value = result
    return agent


def _make_kb_doc(
    doc_id: str = "kb-1",
    title: str = "API Integration Guide",
    content: str = "This document describes the Salesforce API integration.",
) -> KnowledgeDocument:
    return KnowledgeDocument(id=doc_id, title=title, content=content)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_catalog_repo():
    repo = AsyncMock()
    repo.list_systems.return_value = ([], 0)
    repo.list_endpoints.return_value = []
    repo.list_knowledge_documents.return_value = []
    repo.create_system = AsyncMock()
    repo.create_endpoint = AsyncMock()
    repo.link_document = AsyncMock()
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
    factory.create_agent.return_value = None
    return factory


@pytest.fixture
def engine(mock_agent_factory, mock_catalog_repo, mock_knowledge_graph):
    return SystemDiscoveryEngine(
        agent_factory=mock_agent_factory,
        catalog_repo=mock_catalog_repo,
        knowledge_graph=mock_knowledge_graph,
    )


@pytest.fixture
def on_progress():
    return AsyncMock()


# ---------------------------------------------------------------------------
# Tests: discover() accepts knowledge_documents
# ---------------------------------------------------------------------------


class TestDiscoverAcceptsKBDocuments:
    """Tests that discover() accepts and passes through knowledge_documents."""

    async def test_discover_accepts_knowledge_documents(self, engine):
        """discover() accepts knowledge_documents parameter without error."""
        runner = AsyncMock()
        runner.submit = AsyncMock(return_value=MagicMock(id="job-1"))

        docs = [_make_kb_doc()]
        job = await engine.discover(
            "Test trigger",
            runner,
            knowledge_documents=docs,
        )
        assert job.id == "job-1"
        # Payload should include document IDs
        call_args = runner.submit.call_args
        payload = call_args[0][1]
        assert payload["knowledge_document_ids"] == ["kb-1"]

    async def test_discover_without_knowledge_documents(self, engine):
        """discover() works fine without knowledge_documents (backward compat)."""
        runner = AsyncMock()
        runner.submit = AsyncMock(return_value=MagicMock(id="job-2"))

        job = await engine.discover("Test trigger", runner)
        assert job.id == "job-2"
        call_args = runner.submit.call_args
        payload = call_args[0][1]
        assert "knowledge_document_ids" not in payload


# ---------------------------------------------------------------------------
# Tests: _gather_context includes KB documents
# ---------------------------------------------------------------------------


class TestGatherContextWithKBDocs:
    """Tests that _gather_context includes provided knowledge_documents."""

    async def test_kb_docs_included_in_context(self, engine):
        """Provided knowledge_documents are included in context.documents."""
        docs = [
            _make_kb_doc("d1", "Guide A", "Content about Jira integration"),
            _make_kb_doc("d2", "Guide B", "Content about Slack setup"),
        ]
        ctx = await engine._gather_context(knowledge_documents=docs)
        titles = [d["title"] for d in ctx.documents]
        assert "Guide A" in titles
        assert "Guide B" in titles

    async def test_kb_docs_content_in_context(self, engine):
        """Content from knowledge_documents appears in context."""
        docs = [_make_kb_doc(content="Custom API details for PagerDuty")]
        ctx = await engine._gather_context(knowledge_documents=docs)
        contents = [d["content"] for d in ctx.documents]
        assert any("PagerDuty" in c for c in contents)

    async def test_kb_docs_deduplicated_with_existing(self, engine, mock_catalog_repo):
        """KB docs with the same title as repo docs are not duplicated."""
        # Simulate a doc already in the repo
        existing_doc = MagicMock()
        existing_doc.id = "repo-1"
        existing_doc.title = "API Guide"
        existing_doc.document_type = "other"
        existing_doc.tags = []
        existing_doc.content = "Existing content"
        existing_doc.workspace_ids = ["ws-1"]
        mock_catalog_repo.list_knowledge_documents.return_value = [existing_doc]

        new_docs = [_make_kb_doc("d1", "API Guide", "New content")]
        ctx = await engine._gather_context(knowledge_documents=new_docs)

        # Should only have one entry with title "API Guide"
        matching = [d for d in ctx.documents if d["title"] == "API Guide"]
        assert len(matching) == 1

    async def test_none_knowledge_documents_no_error(self, engine):
        """None knowledge_documents does not cause errors."""
        ctx = await engine._gather_context(knowledge_documents=None)
        assert isinstance(ctx.documents, list)


# ---------------------------------------------------------------------------
# Tests: _analyze auto-links documents to created systems
# ---------------------------------------------------------------------------


class TestAnalyzeAutoLinks:
    """Tests that _analyze auto-links KB documents to created systems."""

    async def test_auto_links_documents_to_created_systems(
        self, engine, mock_agent_factory, mock_catalog_repo, on_progress,
    ):
        """Created systems get linked to source knowledge documents."""
        response_text = _make_llm_response([_sample_system_dict()])
        mock_agent = _make_mock_agent(response_text)
        mock_agent_factory.create_agent.return_value = mock_agent

        # Stash knowledge docs via discover() flow
        docs = [_make_kb_doc("kb-1"), _make_kb_doc("kb-2", "Other Guide", "Other content")]
        engine._pending_knowledge_documents = docs

        result = await engine._analyze(
            "job-link-1",
            {
                "trigger": "test",
                "knowledge_document_ids": ["kb-1", "kb-2"],
            },
            on_progress,
        )

        assert result["status"] == "completed"
        assert result["systems_created"] >= 1
        # link_document should have been called for each doc x each created system
        assert mock_catalog_repo.link_document.await_count >= 2

    async def test_no_links_when_no_kb_docs(
        self, engine, mock_agent_factory, mock_catalog_repo, on_progress,
    ):
        """No linking calls when no knowledge_document_ids in payload."""
        response_text = _make_llm_response([_sample_system_dict()])
        mock_agent = _make_mock_agent(response_text)
        mock_agent_factory.create_agent.return_value = mock_agent

        result = await engine._analyze(
            "job-no-link",
            {"trigger": "test"},
            on_progress,
        )

        assert result["status"] == "completed"
        mock_catalog_repo.link_document.assert_not_awaited()
