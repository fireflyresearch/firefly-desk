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

from flydesk.agent.context import ContextEnricher, EnrichedContext
from flydesk.agent.desk_agent import DeskAgent
from flydesk.agent.prompt import PromptContext, SystemPromptBuilder
from flydesk.agent.response import AgentResponse
from flydesk.api.events import SSEEvent, SSEEventType
from flydesk.audit.logger import AuditLogger
from flydesk.audit.models import AuditEvent
from flydesk.auth.models import UserSession
from flydesk.catalog.enums import RiskLevel
from flydesk.tools.factory import ToolDefinition, ToolFactory
from flydesk.widgets.parser import ParseResult, WidgetParser
from flydesk.widgets.schema import WidgetDirective, WidgetDisplay


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
        context_enricher.enrich.assert_awaited_once_with(
            "Hello", conversation_history=[], knowledge_tag_filter=None,
        )

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

    async def test_run_with_no_catalog_tools_still_has_builtins(
        self, desk_agent, prompt_builder, user_session
    ):
        """Without catalog_repo, only built-in tools are provided."""
        await desk_agent.run("Hello", user_session, "conv-1")
        call_ctx = prompt_builder.build.call_args[0][0]
        names = {t["name"] for t in call_ctx.tool_summaries}
        # Platform status is always available (no special permissions needed)
        assert "get_platform_status" in names
        # No catalog tools since there's no catalog_repo
        assert "list_catalog_systems" not in names

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
        from flydesk.files.models import FileUpload

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
        text_context, multimodal_parts = await desk_agent_with_files._build_file_context(["f-a", "f-b"])

        assert file_repo.get.await_count == 2
        file_repo.get.assert_any_await("f-a")
        file_repo.get.assert_any_await("f-b")
        assert "- [report-f-a.pdf]: Text from f-a" in text_context
        assert "- [report-f-b.pdf]: Text from f-b" in text_context
        # No file_storage configured, so multimodal_parts should be empty
        assert multimodal_parts == []


# ---------------------------------------------------------------------------
# DeskAgent conversation history (per-user scoping) tests
# ---------------------------------------------------------------------------

class TestDeskAgentConversationHistory:
    """Tests for per-user conversation history scoping in DeskAgent."""

    @pytest.fixture
    def conversation_repo(self) -> AsyncMock:
        from flydesk.conversation.models import Message, MessageRole

        mock = AsyncMock()
        mock.get_messages = AsyncMock(return_value=[
            Message(
                id="msg-1",
                conversation_id="conv-1",
                role=MessageRole.USER,
                content="What is the refund policy?",
            ),
            Message(
                id="msg-2",
                conversation_id="conv-1",
                role=MessageRole.ASSISTANT,
                content="The refund policy requires manager approval for amounts over $500.",
            ),
        ])
        return mock

    @pytest.fixture
    def desk_agent_with_history(
        self,
        context_enricher,
        prompt_builder,
        tool_factory,
        widget_parser,
        audit_logger,
        conversation_repo,
    ) -> DeskAgent:
        return DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=tool_factory,
            widget_parser=widget_parser,
            audit_logger=audit_logger,
            agent_name="Test Assistant",
            company_name="TestCo",
            conversation_repo=conversation_repo,
        )

    async def test_run_loads_conversation_history(
        self, desk_agent_with_history, conversation_repo, user_session
    ):
        """run() should call get_messages with user-scoped parameters."""
        await desk_agent_with_history.run("Follow up question", user_session, "conv-1")
        conversation_repo.get_messages.assert_awaited_once_with(
            "conv-1", "user-42", limit=20,
        )

    async def test_run_passes_history_to_enricher(
        self, desk_agent_with_history, context_enricher, user_session
    ):
        """run() should pass loaded conversation history to enrich()."""
        await desk_agent_with_history.run("Follow up question", user_session, "conv-1")
        context_enricher.enrich.assert_awaited_once()
        call_kwargs = context_enricher.enrich.call_args
        history = call_kwargs.kwargs["conversation_history"]
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "What is the refund policy?"}
        assert history[1]["role"] == "assistant"

    async def test_run_includes_conversation_summary_in_prompt(
        self,
        desk_agent_with_history,
        prompt_builder,
        context_enricher,
        enriched_context,
        user_session,
    ):
        """run() should populate conversation_summary in the PromptContext."""
        # Make enricher return context with history so summary is generated
        enriched_with_history = EnrichedContext(
            relevant_entities=[],
            knowledge_snippets=[],
            conversation_history=[
                {"role": "user", "content": "What is the refund policy?"},
                {"role": "assistant", "content": "The refund policy requires manager approval."},
            ],
        )
        context_enricher.enrich = AsyncMock(return_value=enriched_with_history)

        await desk_agent_with_history.run("Follow up", user_session, "conv-1")

        call_ctx: PromptContext = prompt_builder.build.call_args[0][0]
        assert "Recent conversation:" in call_ctx.conversation_summary
        assert "User: What is the refund policy?" in call_ctx.conversation_summary
        assert "Assistant: The refund policy requires manager approval." in call_ctx.conversation_summary

    async def test_run_without_conversation_repo_has_empty_history(
        self, desk_agent, context_enricher, user_session
    ):
        """run() without a conversation_repo should pass empty history to enrich()."""
        await desk_agent.run("Hello", user_session, "conv-1")
        context_enricher.enrich.assert_awaited_once_with(
            "Hello", conversation_history=[], knowledge_tag_filter=None,
        )

    async def test_format_conversation_history_empty(self):
        """_format_conversation_history returns empty string for empty list."""
        result = DeskAgent._format_conversation_history([])
        assert result == ""

    async def test_format_conversation_history_limits_to_10(self):
        """_format_conversation_history takes only the last 10 messages."""
        history = [
            {"role": "user", "content": f"Message {i}"}
            for i in range(15)
        ]
        result = DeskAgent._format_conversation_history(history)
        lines = result.split("\n")
        # First line is "Recent conversation:", then 10 message lines
        assert lines[0] == "Recent conversation:"
        assert len(lines) == 11  # header + 10 messages
        assert "Message 5" in result  # 15 - 10 = 5 (first included)
        assert "Message 4" not in result  # excluded

    async def test_format_conversation_history_truncates_long_content(self):
        """_format_conversation_history truncates messages over 200 chars."""
        long_content = "x" * 300
        history = [{"role": "user", "content": long_content}]
        result = DeskAgent._format_conversation_history(history)
        # The content should be truncated to 200 chars
        assert len(result.split("\n")[1]) < 250  # "User: " + 200 chars

    async def test_load_conversation_history_without_repo(self, desk_agent):
        """_load_conversation_history returns empty list when repo is None."""
        result = await desk_agent._load_conversation_history("conv-1", "user-42")
        assert result == []

    async def test_load_conversation_history_maps_messages(
        self, desk_agent_with_history
    ):
        """_load_conversation_history converts Message objects to dicts."""
        result = await desk_agent_with_history._load_conversation_history(
            "conv-1", "user-42",
        )
        assert len(result) == 2
        assert result[0] == {"role": "user", "content": "What is the refund policy?"}
        assert result[1] == {
            "role": "assistant",
            "content": "The refund policy requires manager approval for amounts over $500.",
        }

    async def test_stores_conversation_repo(
        self,
        context_enricher,
        prompt_builder,
        tool_factory,
        widget_parser,
        audit_logger,
        conversation_repo,
    ):
        """DeskAgent should store the conversation_repo dependency."""
        agent = DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=tool_factory,
            widget_parser=widget_parser,
            audit_logger=audit_logger,
            conversation_repo=conversation_repo,
        )
        assert agent._conversation_repo is conversation_repo

    async def test_conversation_repo_defaults_to_none(
        self,
        context_enricher,
        prompt_builder,
        tool_factory,
        widget_parser,
        audit_logger,
    ):
        """DeskAgent should default conversation_repo to None."""
        agent = DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=tool_factory,
            widget_parser=widget_parser,
            audit_logger=audit_logger,
        )
        assert agent._conversation_repo is None


# ---------------------------------------------------------------------------
# DeskAgent._call_llm() tests with agent_factory
# ---------------------------------------------------------------------------

class TestDeskAgentCallLlm:
    """Tests for _call_llm when an agent_factory is provided."""

    @pytest.fixture
    def mock_agent_factory(self) -> MagicMock:
        from flydesk.agent.genai_bridge import DeskAgentFactory

        factory = MagicMock(spec=DeskAgentFactory)
        factory.create_agent = AsyncMock()
        return factory

    @pytest.fixture
    def desk_agent_with_factory(
        self,
        context_enricher,
        prompt_builder,
        tool_factory,
        widget_parser,
        audit_logger,
        mock_agent_factory,
    ) -> DeskAgent:
        return DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=tool_factory,
            widget_parser=widget_parser,
            audit_logger=audit_logger,
            agent_name="Test Assistant",
            company_name="TestCo",
            agent_factory=mock_agent_factory,
        )

    async def test_call_llm_calls_create_agent_with_system_prompt(
        self, desk_agent_with_factory, mock_agent_factory
    ):
        """_call_llm should call agent_factory.create_agent with the system prompt."""
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = "Hello from LLM"
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        await desk_agent_with_factory._call_llm("user message", "system prompt text", "conv-1")
        mock_agent_factory.create_agent.assert_awaited_once_with("system prompt text", tools=None)

    async def test_call_llm_returns_agent_output(
        self, desk_agent_with_factory, mock_agent_factory
    ):
        """_call_llm should return str(result.output) from agent.run()."""
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = "The answer is 42."
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        result = await desk_agent_with_factory._call_llm("question", "prompt", "conv-1")
        assert result == "The answer is 42."

    async def test_call_llm_passes_conversation_id_to_agent_run(
        self, desk_agent_with_factory, mock_agent_factory
    ):
        """_call_llm should forward conversation_id to agent.run()."""
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = "response"
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        await desk_agent_with_factory._call_llm("msg", "prompt", "conv-42")
        mock_agent.run.assert_awaited_once_with("msg", conversation_id="conv-42")

    async def test_call_llm_passes_none_conversation_id(
        self, desk_agent_with_factory, mock_agent_factory
    ):
        """_call_llm with no conversation_id should pass None to agent.run()."""
        mock_agent = AsyncMock()
        mock_result = MagicMock()
        mock_result.output = "response"
        mock_agent.run = AsyncMock(return_value=mock_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        await desk_agent_with_factory._call_llm("msg", "prompt")
        mock_agent.run.assert_awaited_once_with("msg", conversation_id=None)

    async def test_call_llm_returns_error_on_exception(
        self, desk_agent_with_factory, mock_agent_factory
    ):
        """_call_llm should return an error message when agent.run() raises."""
        mock_agent = AsyncMock()
        mock_agent.run = AsyncMock(side_effect=ConnectionError("API unreachable"))
        mock_agent_factory.create_agent.return_value = mock_agent

        result = await desk_agent_with_factory._call_llm("question", "prompt", "conv-1")
        assert "error connecting to the language model" in result.lower()
        assert "API unreachable" in result

    async def test_call_llm_falls_back_to_echo_when_no_agent(
        self, desk_agent_with_factory, mock_agent_factory
    ):
        """_call_llm should use echo fallback when create_agent() returns None."""
        mock_agent_factory.create_agent.return_value = None

        result = await desk_agent_with_factory._call_llm("hello world", "prompt", "conv-1")
        assert "No language model provider is configured" in result
        assert "hello world" in result

    async def test_call_llm_without_factory_uses_echo(self, desk_agent):
        """_call_llm should use echo fallback when no agent_factory is set."""
        result = await desk_agent._call_llm("test message", "prompt")
        assert "No language model provider is configured" in result
        assert "test message" in result


# ---------------------------------------------------------------------------
# DeskAgent._stream_llm() tests with agent_factory
# ---------------------------------------------------------------------------

class TestDeskAgentStreamLlm:
    """Tests for _stream_llm when an agent_factory is provided."""

    @pytest.fixture
    def mock_agent_factory(self) -> MagicMock:
        from flydesk.agent.genai_bridge import DeskAgentFactory

        factory = MagicMock(spec=DeskAgentFactory)
        factory.create_agent = AsyncMock()
        return factory

    @pytest.fixture
    def desk_agent_with_factory(
        self,
        context_enricher,
        prompt_builder,
        tool_factory,
        widget_parser,
        audit_logger,
        mock_agent_factory,
    ) -> DeskAgent:
        return DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=tool_factory,
            widget_parser=widget_parser,
            audit_logger=audit_logger,
            agent_name="Test Assistant",
            company_name="TestCo",
            agent_factory=mock_agent_factory,
        )

    async def test_stream_llm_without_factory_yields_echo_chunks(self, desk_agent):
        """_stream_llm should yield echo fallback chunks when no factory is set."""
        tokens: list[str] = []
        async for token in desk_agent._stream_llm("hello", "prompt"):
            tokens.append(token)
        full_text = "".join(tokens)
        assert "No language model provider is configured" in full_text
        assert "hello" in full_text

    async def test_stream_llm_yields_echo_when_agent_is_none(
        self, desk_agent_with_factory, mock_agent_factory
    ):
        """_stream_llm should yield echo when create_agent() returns None."""
        mock_agent_factory.create_agent.return_value = None
        tokens: list[str] = []
        async for token in desk_agent_with_factory._stream_llm("hi", "prompt"):
            tokens.append(token)
        full_text = "".join(tokens)
        assert "No language model provider is configured" in full_text

    async def test_stream_llm_yields_tokens_from_agent(
        self, desk_agent_with_factory, mock_agent_factory
    ):
        """_stream_llm should yield tokens from agent.run_stream()."""
        # Build a mock that simulates the async context manager + async iterator
        mock_agent = AsyncMock()

        async def fake_stream_tokens():
            for tok in ["Hello", " world", "!"]:
                yield tok

        mock_stream = MagicMock()
        mock_stream.stream_tokens = fake_stream_tokens

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_agent.run_stream = AsyncMock(return_value=mock_stream_ctx)
        mock_agent_factory.create_agent.return_value = mock_agent

        tokens: list[str] = []
        async for token in desk_agent_with_factory._stream_llm("test", "prompt", "conv-1"):
            tokens.append(token)

        assert tokens == ["Hello", " world", "!"]
        mock_agent.run_stream.assert_awaited_once_with(
            "test", streaming_mode="incremental", conversation_id="conv-1",
        )

    async def test_stream_llm_passes_conversation_id(
        self, desk_agent_with_factory, mock_agent_factory
    ):
        """_stream_llm should forward conversation_id to agent.run_stream()."""
        mock_agent = AsyncMock()

        async def fake_stream_tokens():
            yield "tok"

        mock_stream = MagicMock()
        mock_stream.stream_tokens = fake_stream_tokens

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_agent.run_stream = AsyncMock(return_value=mock_stream_ctx)
        mock_agent_factory.create_agent.return_value = mock_agent

        tokens: list[str] = []
        async for token in desk_agent_with_factory._stream_llm("msg", "prompt", "conv-99"):
            tokens.append(token)

        mock_agent.run_stream.assert_awaited_once_with(
            "msg", streaming_mode="incremental", conversation_id="conv-99",
        )

    async def test_stream_llm_passes_none_conversation_id(
        self, desk_agent_with_factory, mock_agent_factory
    ):
        """_stream_llm with no conversation_id should pass None to agent.run_stream()."""
        mock_agent = AsyncMock()

        async def fake_stream_tokens():
            yield "tok"

        mock_stream = MagicMock()
        mock_stream.stream_tokens = fake_stream_tokens

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_agent.run_stream = AsyncMock(return_value=mock_stream_ctx)
        mock_agent_factory.create_agent.return_value = mock_agent

        tokens: list[str] = []
        async for token in desk_agent_with_factory._stream_llm("msg", "prompt"):
            tokens.append(token)

        mock_agent.run_stream.assert_awaited_once_with(
            "msg", streaming_mode="incremental", conversation_id=None,
        )

    async def test_stream_llm_yields_error_on_exception(
        self, desk_agent_with_factory, mock_agent_factory
    ):
        """_stream_llm should yield an error message when streaming raises."""
        mock_agent = AsyncMock()

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(side_effect=ConnectionError("stream failed"))
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_agent.run_stream = AsyncMock(return_value=mock_stream_ctx)
        mock_agent_factory.create_agent.return_value = mock_agent

        tokens: list[str] = []
        async for token in desk_agent_with_factory._stream_llm("test", "prompt", "conv-1"):
            tokens.append(token)

        full_text = "".join(tokens)
        assert "error connecting to the language model" in full_text.lower()
        assert "stream failed" in full_text


# ---------------------------------------------------------------------------
# DeskAgent.stream() with real streaming tests
# ---------------------------------------------------------------------------

class TestDeskAgentStreamWithFactory:
    """Tests for DeskAgent.stream() when agent_factory is provided (real streaming)."""

    @pytest.fixture
    def mock_agent_factory(self) -> MagicMock:
        from flydesk.agent.genai_bridge import DeskAgentFactory

        factory = MagicMock(spec=DeskAgentFactory)
        factory.create_agent = AsyncMock()
        return factory

    @pytest.fixture
    def desk_agent_with_factory(
        self,
        context_enricher,
        prompt_builder,
        tool_factory,
        widget_parser,
        audit_logger,
        mock_agent_factory,
    ) -> DeskAgent:
        return DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=tool_factory,
            widget_parser=widget_parser,
            audit_logger=audit_logger,
            agent_name="Test Assistant",
            company_name="TestCo",
            agent_factory=mock_agent_factory,
        )

    async def test_stream_with_factory_emits_real_tokens(
        self, desk_agent_with_factory, mock_agent_factory, user_session
    ):
        """stream() with agent_factory should emit TOKEN events from real streaming."""
        mock_agent = AsyncMock()

        async def fake_stream_tokens():
            for tok in ["Hello", ", ", "Alice", "!"]:
                yield tok

        mock_stream = MagicMock()
        mock_stream.stream_tokens = fake_stream_tokens

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_agent.run_stream = AsyncMock(return_value=mock_stream_ctx)
        mock_agent_factory.create_agent.return_value = mock_agent

        events: list[SSEEvent] = []
        async for evt in desk_agent_with_factory.stream("Hi", user_session, "conv-1"):
            events.append(evt)

        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        token_contents = [e.data["content"] for e in token_events]
        assert token_contents == ["Hello", ", ", "Alice", "!"]

    async def test_stream_with_factory_emits_all_event_types(
        self, desk_agent_with_factory, mock_agent_factory, user_session
    ):
        """stream() should emit TOOL_START, TOOL_END, TOKEN+, TOOL_SUMMARY, DONE."""
        mock_agent = AsyncMock()

        async def fake_stream_tokens():
            yield "response"

        mock_stream = MagicMock()
        mock_stream.stream_tokens = fake_stream_tokens

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_agent.run_stream = AsyncMock(return_value=mock_stream_ctx)
        mock_agent_factory.create_agent.return_value = mock_agent

        event_types: list[SSEEventType] = []
        async for evt in desk_agent_with_factory.stream("test", user_session, "conv-1"):
            event_types.append(evt.event)

        assert event_types[0] == SSEEventType.TOOL_START
        assert event_types[1] == SSEEventType.TOOL_END
        assert SSEEventType.TOKEN in event_types
        assert SSEEventType.TOOL_SUMMARY in event_types
        assert event_types[-1] == SSEEventType.DONE

    async def test_stream_with_factory_logs_audit(
        self, desk_agent_with_factory, mock_agent_factory, audit_logger, user_session
    ):
        """stream() should write an audit log entry."""
        mock_agent = AsyncMock()

        async def fake_stream_tokens():
            yield "audited text"

        mock_stream = MagicMock()
        mock_stream.stream_tokens = fake_stream_tokens

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_agent.run_stream = AsyncMock(return_value=mock_stream_ctx)
        mock_agent_factory.create_agent.return_value = mock_agent

        events = []
        async for evt in desk_agent_with_factory.stream("msg", user_session, "conv-1"):
            events.append(evt)

        audit_logger.log.assert_awaited_once()
        logged_event = audit_logger.log.call_args[0][0]
        assert logged_event.user_id == "user-42"
        assert logged_event.conversation_id == "conv-1"


# ---------------------------------------------------------------------------
# DeskAgent USAGE event emission tests
# ---------------------------------------------------------------------------

class TestDeskAgentUsageEvent:
    """Tests for USAGE SSE event emission in stream() and run_with_reasoning()."""

    @pytest.fixture
    def mock_agent_factory(self) -> MagicMock:
        from flydesk.agent.genai_bridge import DeskAgentFactory

        factory = MagicMock(spec=DeskAgentFactory)
        factory.create_agent = AsyncMock()
        return factory

    @pytest.fixture
    def desk_agent_with_factory(
        self,
        context_enricher,
        prompt_builder,
        tool_factory,
        widget_parser,
        audit_logger,
        mock_agent_factory,
    ) -> DeskAgent:
        return DeskAgent(
            context_enricher=context_enricher,
            prompt_builder=prompt_builder,
            tool_factory=tool_factory,
            widget_parser=widget_parser,
            audit_logger=audit_logger,
            agent_name="Test Assistant",
            company_name="TestCo",
            agent_factory=mock_agent_factory,
        )

    def _make_mock_agent_with_usage(self, mock_agent_factory, tokens=("Hello",)):
        """Create a mock agent with streaming that exposes usage() on the stream."""
        mock_agent = AsyncMock()
        # Give the agent a _model_identifier for usage extraction
        mock_agent._model_identifier = "openai:gpt-4o"

        async def fake_stream_tokens():
            for tok in tokens:
                yield tok

        mock_stream = MagicMock()
        mock_stream.stream_tokens = fake_stream_tokens

        # The stream.usage() method returns token counts
        mock_usage = MagicMock()
        mock_usage.input_tokens = 150
        mock_usage.output_tokens = 50
        mock_usage.total_tokens = 200
        mock_stream.usage = MagicMock(return_value=mock_usage)

        mock_stream_ctx = AsyncMock()
        mock_stream_ctx.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream_ctx.__aexit__ = AsyncMock(return_value=False)

        mock_agent.run_stream = AsyncMock(return_value=mock_stream_ctx)
        mock_agent_factory.create_agent.return_value = mock_agent

        return mock_agent

    async def test_stream_emits_usage_event_before_done(
        self, desk_agent_with_factory, mock_agent_factory, user_session
    ):
        """stream() should emit a USAGE event before the DONE event."""
        self._make_mock_agent_with_usage(mock_agent_factory)

        events: list[SSEEvent] = []
        async for evt in desk_agent_with_factory.stream("Hello", user_session, "conv-1"):
            events.append(evt)

        event_types = [e.event for e in events]
        assert SSEEventType.USAGE in event_types
        usage_idx = event_types.index(SSEEventType.USAGE)
        done_idx = event_types.index(SSEEventType.DONE)
        assert usage_idx < done_idx

    async def test_stream_usage_event_contains_token_counts(
        self, desk_agent_with_factory, mock_agent_factory, user_session
    ):
        """The USAGE event should contain input_tokens, output_tokens, total_tokens."""
        self._make_mock_agent_with_usage(mock_agent_factory)

        events: list[SSEEvent] = []
        async for evt in desk_agent_with_factory.stream("Hello", user_session, "conv-1"):
            events.append(evt)

        usage_events = [e for e in events if e.event == SSEEventType.USAGE]
        assert len(usage_events) == 1

        data = usage_events[0].data
        assert data["input_tokens"] == 150
        assert data["output_tokens"] == 50
        assert data["total_tokens"] == 200

    async def test_stream_usage_event_contains_model(
        self, desk_agent_with_factory, mock_agent_factory, user_session
    ):
        """The USAGE event should contain the model identifier."""
        self._make_mock_agent_with_usage(mock_agent_factory)

        events: list[SSEEvent] = []
        async for evt in desk_agent_with_factory.stream("Hello", user_session, "conv-1"):
            events.append(evt)

        usage_events = [e for e in events if e.event == SSEEventType.USAGE]
        assert len(usage_events) == 1
        assert usage_events[0].data["model"] == "openai:gpt-4o"

    async def test_stream_usage_event_contains_cost(
        self, desk_agent_with_factory, mock_agent_factory, user_session
    ):
        """The USAGE event should contain a cost_usd field."""
        self._make_mock_agent_with_usage(mock_agent_factory)

        events: list[SSEEvent] = []
        async for evt in desk_agent_with_factory.stream("Hello", user_session, "conv-1"):
            events.append(evt)

        usage_events = [e for e in events if e.event == SSEEventType.USAGE]
        assert len(usage_events) == 1
        assert "cost_usd" in usage_events[0].data

    async def test_stream_no_usage_when_no_factory(
        self, desk_agent, user_session
    ):
        """stream() without agent_factory should not emit a USAGE event (fallback echo)."""
        events: list[SSEEvent] = []
        async for evt in desk_agent.stream("Hello", user_session, "conv-1"):
            events.append(evt)

        usage_events = [e for e in events if e.event == SSEEventType.USAGE]
        assert len(usage_events) == 0

    async def test_stream_no_usage_when_agent_is_none(
        self, desk_agent_with_factory, mock_agent_factory, user_session
    ):
        """stream() should not emit USAGE when create_agent() returns None."""
        mock_agent_factory.create_agent.return_value = None

        events: list[SSEEvent] = []
        async for evt in desk_agent_with_factory.stream("Hello", user_session, "conv-1"):
            events.append(evt)

        usage_events = [e for e in events if e.event == SSEEventType.USAGE]
        assert len(usage_events) == 0

    async def test_stream_event_order_with_usage(
        self, desk_agent_with_factory, mock_agent_factory, user_session
    ):
        """Events should follow: TOOL_START, TOOL_END, TOKEN+, TOOL_SUMMARY, USAGE, DONE."""
        self._make_mock_agent_with_usage(mock_agent_factory)

        event_types: list[SSEEventType] = []
        async for evt in desk_agent_with_factory.stream("test", user_session, "conv-1"):
            event_types.append(evt.event)

        assert event_types[0] == SSEEventType.TOOL_START
        assert event_types[1] == SSEEventType.TOOL_END
        assert SSEEventType.TOKEN in event_types
        assert SSEEventType.TOOL_SUMMARY in event_types

        summary_idx = event_types.index(SSEEventType.TOOL_SUMMARY)
        usage_idx = event_types.index(SSEEventType.USAGE)
        done_idx = event_types.index(SSEEventType.DONE)
        assert summary_idx < usage_idx < done_idx

    async def test_usage_event_serializes_to_sse(self):
        """SSEEvent with USAGE type should serialize correctly."""
        event = SSEEvent(
            event=SSEEventType.USAGE,
            data={
                "input_tokens": 100,
                "output_tokens": 25,
                "total_tokens": 125,
                "cost_usd": 0.0012,
                "model": "anthropic:claude-sonnet-4-20250514",
            },
        )
        sse_str = event.to_sse()
        assert "event: usage" in sse_str
        assert '"input_tokens": 100' in sse_str
        assert '"model": "anthropic:claude-sonnet-4-20250514"' in sse_str

    async def test_extract_stream_usage_populates_dict(self):
        """_extract_stream_usage should populate the usage_out dict from a stream."""
        mock_stream = MagicMock()
        mock_usage = MagicMock()
        mock_usage.input_tokens = 300
        mock_usage.output_tokens = 100
        mock_usage.total_tokens = 400
        mock_stream.usage = MagicMock(return_value=mock_usage)

        mock_agent = MagicMock()
        mock_agent._model_identifier = "google-gla:gemini-2.0-flash"

        usage_out: dict = {}
        DeskAgent._extract_stream_usage(mock_stream, mock_agent, usage_out)

        assert usage_out["input_tokens"] == 300
        assert usage_out["output_tokens"] == 100
        assert usage_out["total_tokens"] == 400
        assert usage_out["model"] == "google-gla:gemini-2.0-flash"
        assert "cost_usd" in usage_out

    async def test_extract_stream_usage_handles_missing_usage(self):
        """_extract_stream_usage should handle streams without usage()."""
        mock_stream = MagicMock(spec=[])  # No attributes at all
        mock_agent = MagicMock()
        mock_agent._model_identifier = "openai:gpt-4o"

        usage_out: dict = {}
        DeskAgent._extract_stream_usage(mock_stream, mock_agent, usage_out)

        assert usage_out == {}

    async def test_extract_result_usage_returns_dict(self):
        """_extract_result_usage should return a populated dict from a result."""
        mock_result = MagicMock()
        mock_usage = MagicMock()
        mock_usage.input_tokens = 200
        mock_usage.output_tokens = 75
        mock_usage.total_tokens = 275
        mock_result.usage = MagicMock(return_value=mock_usage)

        mock_agent = MagicMock()
        mock_agent._model_identifier = "openai:gpt-4o-mini"

        result = DeskAgent._extract_result_usage(mock_result, mock_agent)

        assert result["input_tokens"] == 200
        assert result["output_tokens"] == 75
        assert result["total_tokens"] == 275
        assert result["model"] == "openai:gpt-4o-mini"

    async def test_extract_result_usage_returns_empty_on_no_usage(self):
        """_extract_result_usage should return {} when result has no usage()."""
        mock_result = MagicMock(spec=[])
        mock_agent = MagicMock()
        mock_agent._model_identifier = "openai:gpt-4o"

        result = DeskAgent._extract_result_usage(mock_result, mock_agent)
        assert result == {}
