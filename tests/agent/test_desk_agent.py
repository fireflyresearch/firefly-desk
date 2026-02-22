# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the DeskAgent orchestrator and AgentResponse."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydek.agent.context import ContextEnricher, EnrichedContext
from flydek.agent.desk_agent import DeskAgent
from flydek.agent.prompt import PromptContext, SystemPromptBuilder
from flydek.agent.response import AgentResponse
from flydek.api.events import SSEEvent, SSEEventType
from flydek.audit.logger import AuditLogger
from flydek.audit.models import AuditEvent
from flydek.auth.models import UserSession
from flydek.catalog.enums import RiskLevel
from flydek.tools.factory import ToolDefinition, ToolFactory
from flydek.widgets.parser import ParseResult, WidgetParser
from flydek.widgets.schema import WidgetDirective, WidgetDisplay


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def user_session() -> UserSession:
    return UserSession(
        user_id="user-42",
        email="alice@example.com",
        display_name="Alice Smith",
        roles=["admin", "support"],
        permissions=["orders:read", "orders:write"],
        tenant_id="tenant-1",
        session_id="sess-abc",
        token_expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
        raw_claims={},
    )


@pytest.fixture
def enriched_context() -> EnrichedContext:
    return EnrichedContext(
        relevant_entities=[],
        knowledge_snippets=[],
        conversation_history=[],
    )


@pytest.fixture
def context_enricher(enriched_context: EnrichedContext) -> ContextEnricher:
    mock = MagicMock(spec=ContextEnricher)
    mock.enrich = AsyncMock(return_value=enriched_context)
    return mock


@pytest.fixture
def prompt_builder() -> SystemPromptBuilder:
    mock = MagicMock(spec=SystemPromptBuilder)
    mock.build = MagicMock(return_value="You are the Desk Agent.")
    return mock


@pytest.fixture
def tool_factory() -> ToolFactory:
    return MagicMock(spec=ToolFactory)


@pytest.fixture
def widget_parser() -> WidgetParser:
    mock = MagicMock(spec=WidgetParser)
    mock.parse = MagicMock(return_value=ParseResult(
        text_segments=["Hello, how can I help?"],
        widgets=[],
    ))
    return mock


@pytest.fixture
def audit_logger() -> AuditLogger:
    mock = MagicMock(spec=AuditLogger)
    mock.log = AsyncMock(return_value="audit-evt-1")
    return mock


@pytest.fixture
def sample_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            endpoint_id="ep-1",
            name="get_order",
            description="Fetch an order by ID",
            risk_level=RiskLevel.READ,
            system_id="orders-svc",
            method="GET",
            path="/orders/{id}",
        ),
    ]


@pytest.fixture
def desk_agent(
    context_enricher: ContextEnricher,
    prompt_builder: SystemPromptBuilder,
    tool_factory: ToolFactory,
    widget_parser: WidgetParser,
    audit_logger: AuditLogger,
) -> DeskAgent:
    return DeskAgent(
        context_enricher=context_enricher,
        prompt_builder=prompt_builder,
        tool_factory=tool_factory,
        widget_parser=widget_parser,
        audit_logger=audit_logger,
        agent_name="Test Assistant",
        company_name="TestCo",
    )


# ---------------------------------------------------------------------------
# AgentResponse tests
# ---------------------------------------------------------------------------

class TestAgentResponse:
    """Tests for the AgentResponse dataclass."""

    def test_create_with_all_fields(self):
        widget = WidgetDirective(type="status-badge", props={"status": "ok"})
        resp = AgentResponse(
            text="Order found.",
            widgets=[widget],
            raw_text='Order found.\n:::widget{type="status-badge"}\n{"status":"ok"}\n:::',
            conversation_id="conv-1",
            turn_id="turn-1",
        )
        assert resp.text == "Order found."
        assert len(resp.widgets) == 1
        assert resp.widgets[0].type == "status-badge"
        assert resp.conversation_id == "conv-1"
        assert resp.turn_id == "turn-1"

    def test_raw_text_preserved(self):
        raw = 'Some text :::widget{type="x"}\n{}\n::: more text'
        resp = AgentResponse(
            text="Some text  more text",
            widgets=[],
            raw_text=raw,
            conversation_id="c-1",
            turn_id="t-1",
        )
        assert resp.raw_text == raw
        assert ":::widget" not in resp.text

    def test_empty_widgets_list(self):
        resp = AgentResponse(
            text="Just text.",
            widgets=[],
            raw_text="Just text.",
            conversation_id="c-1",
            turn_id="t-1",
        )
        assert resp.widgets == []

    def test_multiple_widgets(self):
        widgets = [
            WidgetDirective(type="status-badge", props={}),
            WidgetDirective(type="data-table", props={"rows": []}),
        ]
        resp = AgentResponse(
            text="result",
            widgets=widgets,
            raw_text="result",
            conversation_id="c-1",
            turn_id="t-1",
        )
        assert len(resp.widgets) == 2


# ---------------------------------------------------------------------------
# DeskAgent initialization tests
# ---------------------------------------------------------------------------

class TestDeskAgentInit:
    """Tests for DeskAgent construction."""

    def test_stores_dependencies(
        self,
        context_enricher,
        prompt_builder,
        tool_factory,
        widget_parser,
        audit_logger,
    ):
        agent = DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=tool_factory,
            widget_parser=widget_parser,
            audit_logger=audit_logger,
        )
        assert agent._context_enricher is context_enricher
        assert agent._prompt_builder is prompt_builder
        assert agent._widget_parser is widget_parser
        assert agent._audit_logger is audit_logger

    def test_default_agent_name(
        self,
        context_enricher,
        prompt_builder,
        tool_factory,
        widget_parser,
        audit_logger,
    ):
        agent = DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=tool_factory,
            widget_parser=widget_parser,
            audit_logger=audit_logger,
        )
        assert agent._agent_name == "Ember"

    def test_custom_agent_name_and_company(
        self,
        context_enricher,
        prompt_builder,
        tool_factory,
        widget_parser,
        audit_logger,
    ):
        agent = DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=tool_factory,
            widget_parser=widget_parser,
            audit_logger=audit_logger,
            agent_name="Custom Agent",
            company_name="Acme Inc",
        )
        assert agent._agent_name == "Custom Agent"
        assert agent._company_name == "Acme Inc"


# ---------------------------------------------------------------------------
# DeskAgent.run() tests
# ---------------------------------------------------------------------------

class TestDeskAgentRun:
    """Tests for the DeskAgent.run() lifecycle."""

    async def test_run_calls_enricher(
        self, desk_agent, context_enricher, user_session
    ):
        await desk_agent.run("Hello", user_session, "conv-1")
        context_enricher.enrich.assert_awaited_once_with("Hello")

    async def test_run_calls_prompt_builder(
        self, desk_agent, prompt_builder, user_session
    ):
        await desk_agent.run("Hello", user_session, "conv-1")
        prompt_builder.build.assert_called_once()
        call_ctx = prompt_builder.build.call_args[0][0]
        assert isinstance(call_ctx, PromptContext)
        assert call_ctx.agent_name == "Test Assistant"
        assert call_ctx.company_name == "TestCo"
        assert call_ctx.user_name == "Alice Smith"
        assert call_ctx.user_roles == ["admin", "support"]
        assert call_ctx.user_permissions == ["orders:read", "orders:write"]

    async def test_run_passes_tool_summaries_to_prompt(
        self, desk_agent, prompt_builder, user_session, sample_tools
    ):
        await desk_agent.run("Hello", user_session, "conv-1", tools=sample_tools)
        call_ctx = prompt_builder.build.call_args[0][0]
        assert len(call_ctx.tool_summaries) == 1
        assert call_ctx.tool_summaries[0]["name"] == "get_order"
        assert call_ctx.tool_summaries[0]["description"] == "Fetch an order by ID"

    async def test_run_calls_widget_parser(
        self, desk_agent, widget_parser, user_session
    ):
        await desk_agent.run("Hello", user_session, "conv-1")
        widget_parser.parse.assert_called_once()

    async def test_run_calls_audit_logger(
        self, desk_agent, audit_logger, user_session
    ):
        await desk_agent.run("Hello", user_session, "conv-1")
        audit_logger.log.assert_awaited_once()
        logged_event = audit_logger.log.call_args[0][0]
        assert isinstance(logged_event, AuditEvent)
        assert logged_event.action == "agent_turn"
        assert logged_event.user_id == "user-42"
        assert logged_event.conversation_id == "conv-1"

    async def test_run_returns_agent_response(
        self, desk_agent, user_session
    ):
        result = await desk_agent.run("Hello", user_session, "conv-1")
        assert isinstance(result, AgentResponse)
        assert result.conversation_id == "conv-1"
        assert result.turn_id  # non-empty
        assert isinstance(result.text, str)
        assert isinstance(result.widgets, list)
        assert isinstance(result.raw_text, str)

    async def test_run_strips_widgets_from_text(
        self, desk_agent, widget_parser, user_session
    ):
        """The response text should be assembled from text_segments (widgets stripped)."""
        widget_parser.parse.return_value = ParseResult(
            text_segments=["Before.", "After."],
            widgets=[WidgetDirective(type="status-badge", props={"status": "ok"})],
        )
        result = await desk_agent.run("Hello", user_session, "conv-1")
        assert "Before." in result.text
        assert "After." in result.text
        assert len(result.widgets) == 1

    async def test_run_with_no_tools(self, desk_agent, prompt_builder, user_session):
        await desk_agent.run("Hello", user_session, "conv-1")
        call_ctx = prompt_builder.build.call_args[0][0]
        assert call_ctx.tool_summaries == []

    async def test_run_generates_unique_turn_ids(self, desk_agent, user_session):
        r1 = await desk_agent.run("Hello", user_session, "conv-1")
        r2 = await desk_agent.run("Again", user_session, "conv-1")
        assert r1.turn_id != r2.turn_id

    async def test_run_placeholder_echoes_message(self, desk_agent, widget_parser, user_session):
        """The MVP placeholder LLM should incorporate the user message."""
        # We need the parser to return whatever it receives
        widget_parser.parse = MagicMock(
            side_effect=lambda text: ParseResult(text_segments=[text], widgets=[])
        )
        result = await desk_agent.run("Show me order 123", user_session, "conv-1")
        assert "Show me order 123" in result.raw_text


# ---------------------------------------------------------------------------
# DeskAgent.stream() tests
# ---------------------------------------------------------------------------

class TestDeskAgentStream:
    """Tests for DeskAgent.stream() SSE event generation."""

    async def test_stream_yields_token_events(self, desk_agent, user_session):
        events: list[SSEEvent] = []
        async for evt in desk_agent.stream("Hello", user_session, "conv-1"):
            events.append(evt)

        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        assert len(token_events) >= 1

    async def test_stream_yields_done_event_last(self, desk_agent, user_session):
        events: list[SSEEvent] = []
        async for evt in desk_agent.stream("Hello", user_session, "conv-1"):
            events.append(evt)

        assert events[-1].event == SSEEventType.DONE

    async def test_stream_yields_widget_events(
        self, desk_agent, widget_parser, user_session
    ):
        widget = WidgetDirective(
            type="data-table",
            props={"rows": [{"id": 1}]},
            display=WidgetDisplay.PANEL,
        )
        widget_parser.parse.return_value = ParseResult(
            text_segments=["Here is the data:"],
            widgets=[widget],
        )

        events: list[SSEEvent] = []
        async for evt in desk_agent.stream("Show data", user_session, "conv-1"):
            events.append(evt)

        widget_events = [e for e in events if e.event == SSEEventType.WIDGET]
        assert len(widget_events) == 1
        assert widget_events[0].data["type"] == "data-table"
        assert widget_events[0].data["props"] == {"rows": [{"id": 1}]}

    async def test_stream_event_order(
        self, desk_agent, widget_parser, user_session
    ):
        """Events should follow: TOKEN(s) -> WIDGET(s) -> DONE."""
        widget_parser.parse.return_value = ParseResult(
            text_segments=["text"],
            widgets=[WidgetDirective(type="alert", props={"level": "info"})],
        )
        event_types: list[SSEEventType] = []
        async for evt in desk_agent.stream("test", user_session, "conv-1"):
            event_types.append(evt.event)

        # TOKEN events come first
        first_token = event_types.index(SSEEventType.TOKEN)
        # WIDGET events come after all tokens
        widget_idx = event_types.index(SSEEventType.WIDGET)
        # DONE is last
        done_idx = event_types.index(SSEEventType.DONE)

        assert first_token < widget_idx < done_idx

    async def test_stream_no_widgets_still_has_done(
        self, desk_agent, user_session
    ):
        events: list[SSEEvent] = []
        async for evt in desk_agent.stream("simple", user_session, "conv-1"):
            events.append(evt)

        widget_events = [e for e in events if e.event == SSEEventType.WIDGET]
        assert len(widget_events) == 0
        assert events[-1].event == SSEEventType.DONE

    async def test_stream_token_data_contains_text(self, desk_agent, user_session):
        events: list[SSEEvent] = []
        async for evt in desk_agent.stream("Hello", user_session, "conv-1"):
            events.append(evt)

        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        all_text = "".join(e.data.get("content", "") for e in token_events)
        assert len(all_text) > 0

    async def test_stream_done_includes_conversation_id(
        self, desk_agent, user_session
    ):
        events: list[SSEEvent] = []
        async for evt in desk_agent.stream("Hello", user_session, "conv-1"):
            events.append(evt)

        done_evt = events[-1]
        assert done_evt.data["conversation_id"] == "conv-1"

    async def test_stream_multiple_widgets(
        self, desk_agent, widget_parser, user_session
    ):
        widgets = [
            WidgetDirective(type="status-badge", props={"status": "ok"}),
            WidgetDirective(type="key-value", props={"key": "val"}),
        ]
        widget_parser.parse.return_value = ParseResult(
            text_segments=["text"],
            widgets=widgets,
        )

        events: list[SSEEvent] = []
        async for evt in desk_agent.stream("test", user_session, "conv-1"):
            events.append(evt)

        widget_events = [e for e in events if e.event == SSEEventType.WIDGET]
        assert len(widget_events) == 2
        types = {e.data["type"] for e in widget_events}
        assert types == {"status-badge", "key-value"}


# ---------------------------------------------------------------------------
# DeskAgent file_ids integration tests
# ---------------------------------------------------------------------------

class TestDeskAgentFileIds:
    """Tests for file_ids wiring in DeskAgent.run() and _build_file_context."""

    @pytest.fixture
    def file_repo(self) -> AsyncMock:
        from flydek.files.models import FileUpload

        mock = AsyncMock()
        mock.get = AsyncMock(
            side_effect=lambda fid: FileUpload(
                id=fid,
                user_id="user-42",
                filename=f"report-{fid}.pdf",
                content_type="application/pdf",
                file_size=1024,
                storage_path=f"/tmp/{fid}",
                extracted_text=f"Text from {fid}",
            )
        )
        return mock

    @pytest.fixture
    def desk_agent_with_files(
        self,
        context_enricher,
        prompt_builder,
        tool_factory,
        widget_parser,
        audit_logger,
        file_repo,
    ) -> DeskAgent:
        return DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=tool_factory,
            widget_parser=widget_parser,
            audit_logger=audit_logger,
            agent_name="Test Assistant",
            company_name="TestCo",
            file_repo=file_repo,
        )

    async def test_run_with_file_ids_populates_file_context(
        self, desk_agent_with_files, prompt_builder, user_session
    ):
        """run() with file_ids should pass file_context into the PromptContext."""
        await desk_agent_with_files.run(
            "Summarize the reports", user_session, "conv-1",
            file_ids=["f-1", "f-2"],
        )

        call_ctx: PromptContext = prompt_builder.build.call_args[0][0]
        assert "- [report-f-1.pdf]: Text from f-1" in call_ctx.file_context
        assert "- [report-f-2.pdf]: Text from f-2" in call_ctx.file_context

    async def test_run_without_file_ids_has_empty_file_context(
        self, desk_agent_with_files, prompt_builder, user_session
    ):
        """run() without file_ids should leave file_context as empty string."""
        await desk_agent_with_files.run(
            "Hello", user_session, "conv-1",
        )

        call_ctx: PromptContext = prompt_builder.build.call_args[0][0]
        assert call_ctx.file_context == ""

    async def test_build_file_context_with_mock_repo(
        self, desk_agent_with_files, file_repo
    ):
        """_build_file_context fetches each file and formats the text."""
        result = await desk_agent_with_files._build_file_context(["f-a", "f-b"])

        assert file_repo.get.await_count == 2
        file_repo.get.assert_any_await("f-a")
        file_repo.get.assert_any_await("f-b")
        assert "- [report-f-a.pdf]: Text from f-a" in result
        assert "- [report-f-b.pdf]: Text from f-b" in result
