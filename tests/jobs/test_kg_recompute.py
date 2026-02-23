# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for KGRecomputeHandler -- knowledge graph recomputation job handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.jobs.handlers import JobHandler, KGRecomputeHandler


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_catalog_repo():
    repo = AsyncMock()
    repo.list_knowledge_documents.return_value = []
    return repo


@pytest.fixture
def mock_knowledge_graph():
    kg = AsyncMock()
    return kg


@pytest.fixture
def mock_extractor():
    extractor = AsyncMock()
    extractor.extract_from_document.return_value = ([], [])
    return extractor


@pytest.fixture
def handler(mock_catalog_repo, mock_knowledge_graph, mock_extractor):
    return KGRecomputeHandler(mock_catalog_repo, mock_knowledge_graph, mock_extractor)


@pytest.fixture
def on_progress():
    return AsyncMock()


def _make_doc(doc_id: str, title: str, content: str) -> MagicMock:
    """Create a mock knowledge document."""
    doc = MagicMock()
    doc.id = doc_id
    doc.title = title
    doc.content = content
    return doc


# ---------------------------------------------------------------------------
# Tests: Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    """KGRecomputeHandler satisfies the JobHandler protocol."""

    def test_satisfies_job_handler_protocol(self, handler):
        assert isinstance(handler, JobHandler)


# ---------------------------------------------------------------------------
# Tests: execute
# ---------------------------------------------------------------------------


class TestExecute:
    """Tests for KGRecomputeHandler.execute()."""

    async def test_no_documents(self, handler, on_progress):
        """When there are no documents, returns zeros and reports 100%."""
        result = await handler.execute("job-1", {}, on_progress)
        assert result == {"entities_added": 0, "relations_added": 0, "documents_processed": 0}
        # Progress should report 0% start and 100% end
        on_progress.assert_any_call(0, "Loading knowledge documents")
        on_progress.assert_any_call(100, "No documents to process")

    async def test_single_document_extraction(
        self, handler, mock_catalog_repo, mock_extractor, mock_knowledge_graph, on_progress
    ):
        """Processes a single document and upserts entities/relations."""
        doc = _make_doc("d-1", "Onboarding Guide", "How to onboard new employees.")
        mock_catalog_repo.list_knowledge_documents.return_value = [doc]

        mock_extractor.extract_from_document.return_value = (
            [
                {
                    "id": "ent-1",
                    "entity_type": "process",
                    "name": "Onboarding",
                    "properties": {},
                    "source_system": None,
                    "confidence": 0.9,
                },
                {
                    "id": "ent-2",
                    "entity_type": "role",
                    "name": "HR Manager",
                    "properties": {},
                    "source_system": None,
                    "confidence": 0.8,
                },
            ],
            [
                {
                    "source_id": "ent-1",
                    "target_id": "ent-2",
                    "relation_type": "managed_by",
                    "properties": {},
                    "confidence": 0.85,
                }
            ],
        )

        result = await handler.execute("job-2", {}, on_progress)

        assert result["entities_added"] == 2
        assert result["relations_added"] == 1
        assert result["documents_processed"] == 1

        # Verify entities were upserted
        assert mock_knowledge_graph.upsert_entity.call_count == 2
        # Verify relation was added
        assert mock_knowledge_graph.add_relation.call_count == 1

        # Verify progress reported
        on_progress.assert_any_call(0, "Loading knowledge documents")
        on_progress.assert_any_call(
            100, "Processed 1/1 documents (2 entities, 1 relations)"
        )

    async def test_multiple_documents(
        self, handler, mock_catalog_repo, mock_extractor, mock_knowledge_graph, on_progress
    ):
        """Processes multiple documents and accumulates counts."""
        docs = [
            _make_doc("d-1", "Doc A", "Content A"),
            _make_doc("d-2", "Doc B", "Content B"),
            _make_doc("d-3", "Doc C", "Content C"),
        ]
        mock_catalog_repo.list_knowledge_documents.return_value = docs

        # Each doc yields 1 entity and 0 relations
        mock_extractor.extract_from_document.return_value = (
            [{"id": "e-x", "entity_type": "concept", "name": "X", "properties": {}, "confidence": 1.0}],
            [],
        )

        result = await handler.execute("job-3", {}, on_progress)

        assert result["entities_added"] == 3
        assert result["relations_added"] == 0
        assert result["documents_processed"] == 3
        assert mock_extractor.extract_from_document.call_count == 3

    async def test_empty_document_skipped(
        self, handler, mock_catalog_repo, mock_extractor, on_progress
    ):
        """Documents with empty content are skipped."""
        doc = _make_doc("d-1", "Empty Doc", "")
        mock_catalog_repo.list_knowledge_documents.return_value = [doc]

        result = await handler.execute("job-4", {}, on_progress)

        assert result["entities_added"] == 0
        assert result["documents_processed"] == 1
        mock_extractor.extract_from_document.assert_not_called()

    async def test_extraction_failure_handled(
        self, handler, mock_catalog_repo, mock_extractor, mock_knowledge_graph, on_progress
    ):
        """When extraction fails for a document, it is logged and skipped."""
        docs = [
            _make_doc("d-1", "Good Doc", "Good content"),
            _make_doc("d-2", "Bad Doc", "Bad content"),
        ]
        mock_catalog_repo.list_knowledge_documents.return_value = docs

        # First call succeeds, second fails
        mock_extractor.extract_from_document.side_effect = [
            (
                [{"id": "e-1", "entity_type": "concept", "name": "X", "properties": {}, "confidence": 1.0}],
                [],
            ),
            RuntimeError("LLM failed"),
        ]

        result = await handler.execute("job-5", {}, on_progress)

        assert result["entities_added"] == 1
        assert result["relations_added"] == 0
        assert result["documents_processed"] == 2

    async def test_progress_percentage_calculation(
        self, handler, mock_catalog_repo, mock_extractor, on_progress
    ):
        """Progress percentages are calculated correctly for multiple documents."""
        docs = [
            _make_doc("d-1", "Doc A", "Content A"),
            _make_doc("d-2", "Doc B", "Content B"),
            _make_doc("d-3", "Doc C", "Content C"),
            _make_doc("d-4", "Doc D", "Content D"),
        ]
        mock_catalog_repo.list_knowledge_documents.return_value = docs
        mock_extractor.extract_from_document.return_value = ([], [])

        await handler.execute("job-6", {}, on_progress)

        # Check progress calls (excluding the initial "Loading" call)
        progress_calls = [
            call.args[0]
            for call in on_progress.call_args_list
            if isinstance(call.args[0], int) and call.args[0] > 0
        ]
        # Should be 25%, 50%, 75%, 100%
        assert progress_calls == [25, 50, 75, 100]

    async def test_entity_properties_passed_correctly(
        self, handler, mock_catalog_repo, mock_extractor, mock_knowledge_graph, on_progress
    ):
        """Entity fields are correctly passed to KnowledgeGraph.upsert_entity()."""
        doc = _make_doc("d-1", "Test", "Test content")
        mock_catalog_repo.list_knowledge_documents.return_value = [doc]

        mock_extractor.extract_from_document.return_value = (
            [
                {
                    "id": "ent-abc",
                    "entity_type": "system",
                    "name": "CRM",
                    "properties": {"vendor": "Salesforce"},
                    "source_system": "catalog",
                    "confidence": 0.95,
                }
            ],
            [],
        )

        await handler.execute("job-7", {}, on_progress)

        # Verify the entity passed to upsert_entity
        entity_arg = mock_knowledge_graph.upsert_entity.call_args.args[0]
        assert entity_arg.id == "ent-abc"
        assert entity_arg.entity_type == "system"
        assert entity_arg.name == "CRM"
        assert entity_arg.properties == {"vendor": "Salesforce"}
        assert entity_arg.source_system == "catalog"
        assert entity_arg.confidence == 0.95

    async def test_relation_properties_passed_correctly(
        self, handler, mock_catalog_repo, mock_extractor, mock_knowledge_graph, on_progress
    ):
        """Relation fields are correctly passed to KnowledgeGraph.add_relation()."""
        doc = _make_doc("d-1", "Test", "Test content")
        mock_catalog_repo.list_knowledge_documents.return_value = [doc]

        mock_extractor.extract_from_document.return_value = (
            [
                {"id": "e1", "entity_type": "system", "name": "A", "properties": {}, "confidence": 1.0},
                {"id": "e2", "entity_type": "system", "name": "B", "properties": {}, "confidence": 1.0},
            ],
            [
                {
                    "source_id": "e1",
                    "target_id": "e2",
                    "relation_type": "integrates_with",
                    "properties": {"protocol": "REST"},
                    "confidence": 0.88,
                }
            ],
        )

        await handler.execute("job-8", {}, on_progress)

        relation_arg = mock_knowledge_graph.add_relation.call_args.args[0]
        assert relation_arg.source_id == "e1"
        assert relation_arg.target_id == "e2"
        assert relation_arg.relation_type == "integrates_with"
        assert relation_arg.properties == {"protocol": "REST"}
        assert relation_arg.confidence == 0.88
