# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for reasoning pattern support in DeskAgent."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from flydesk.agent.context import ContextEnricher, EnrichedContext
from flydesk.agent.desk_agent import DeskAgent
from flydesk.agent.prompt import SystemPromptBuilder
from flydesk.api.events import SSEEvent, SSEEventType
from flydesk.audit.logger import AuditLogger
from flydesk.auth.models import UserSession
from flydesk.tools.factory import ToolFactory
from flydesk.widgets.parser import ParseResult, WidgetParser


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
def mock_agent_factory() -> MagicMock:
    from flydesk.agent.genai_bridge import DeskAgentFactory

    factory = MagicMock(spec=DeskAgentFactory)
    factory.create_agent = AsyncMock()
    return factory


@pytest.fixture
def desk_agent(
    context_enricher,
    prompt_builder,
    tool_factory,
    widget_parser,
    audit_logger,
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


@pytest.fixture
def desk_agent_with_factory(
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


def _make_reasoning_result(
    output: str = "The answer is 42.",
    pattern_name: str = "react",
    steps: list | None = None,
    steps_taken: int = 3,
) -> MagicMock:
    """Build a mock ReasoningResult with configurable trace."""
    if steps is None:
        step1 = MagicMock()
        step1.kind = "thought"
        step1.content = "Analyzing the request"
        step2 = MagicMock()
        step2.kind = "action"
        step2.content = "Looking up order"
        step3 = MagicMock()
        step3.kind = "observation"
        step3.content = "Found order details"
        steps = [step1, step2, step3]

    trace = MagicMock()
    trace.steps = steps
    trace.pattern_name = pattern_name

    result = MagicMock()
    result.output = output
    result.trace = trace
    result.steps_taken = steps_taken
    result.success = True
    return result


# ---------------------------------------------------------------------------
# _select_reasoning_pattern tests
# ---------------------------------------------------------------------------

class TestSelectReasoningPattern:
    """Tests for DeskAgent._select_reasoning_pattern()."""

    def test_auto_with_few_tools_selects_react(self, desk_agent):
        """Auto pattern with <= 2 tools should select ReAct."""
        with patch("fireflyframework_genai.reasoning.ReActPattern") as MockReAct, \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            mock_instance = MagicMock()
            MockReAct.return_value = mock_instance

            result = desk_agent._select_reasoning_pattern("auto", ["tool1", "tool2"])
            MockReAct.assert_called_once_with(max_steps=5)
            assert result is mock_instance

    def test_auto_with_no_tools_selects_react(self, desk_agent):
        """Auto pattern with no tools should select ReAct."""
        with patch("fireflyframework_genai.reasoning.ReActPattern") as MockReAct, \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            mock_instance = MagicMock()
            MockReAct.return_value = mock_instance

            result = desk_agent._select_reasoning_pattern("auto", None)
            MockReAct.assert_called_once_with(max_steps=5)
            assert result is mock_instance

    def test_auto_with_many_tools_selects_plan_and_execute(self, desk_agent):
        """Auto pattern with > 2 tools should select PlanAndExecute."""
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern") as MockPlan:
            mock_instance = MagicMock()
            MockPlan.return_value = mock_instance

            result = desk_agent._select_reasoning_pattern("auto", ["t1", "t2", "t3"])
            MockPlan.assert_called_once_with(max_steps=8)
            assert result is mock_instance

    def test_explicit_react(self, desk_agent):
        """Explicit 'react' should select ReActPattern."""
        with patch("fireflyframework_genai.reasoning.ReActPattern") as MockReAct, \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            mock_instance = MagicMock()
            MockReAct.return_value = mock_instance

            result = desk_agent._select_reasoning_pattern("react", None)
            MockReAct.assert_called_once_with(max_steps=5)
            assert result is mock_instance

    def test_explicit_plan_and_execute(self, desk_agent):
        """Explicit 'plan_and_execute' should select PlanAndExecutePattern."""
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern") as MockPlan:
            mock_instance = MagicMock()
            MockPlan.return_value = mock_instance

            result = desk_agent._select_reasoning_pattern("plan_and_execute", None)
            MockPlan.assert_called_once_with(max_steps=8)
            assert result is mock_instance

    def test_explicit_chain_of_thought(self, desk_agent):
        """Explicit 'chain_of_thought' should select ChainOfThoughtPattern."""
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"), \
             patch("fireflyframework_genai.reasoning.ChainOfThoughtPattern") as MockCoT:
            mock_instance = MagicMock()
            MockCoT.return_value = mock_instance

            result = desk_agent._select_reasoning_pattern("chain_of_thought", None)
            MockCoT.assert_called_once_with(max_steps=5)
            assert result is mock_instance

    def test_explicit_reflexion(self, desk_agent):
        """Explicit 'reflexion' should select ReflexionPattern."""
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"), \
             patch("fireflyframework_genai.reasoning.ReflexionPattern") as MockReflex:
            mock_instance = MagicMock()
            MockReflex.return_value = mock_instance

            result = desk_agent._select_reasoning_pattern("reflexion", None)
            MockReflex.assert_called_once_with(max_steps=5)
            assert result is mock_instance

    def test_unknown_pattern_defaults_to_react(self, desk_agent):
        """Unknown pattern name should default to ReAct."""
        with patch("fireflyframework_genai.reasoning.ReActPattern") as MockReAct, \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            mock_instance = MagicMock()
            MockReAct.return_value = mock_instance

            result = desk_agent._select_reasoning_pattern("nonexistent_pattern", None)
            MockReAct.assert_called_once_with(max_steps=5)
            assert result is mock_instance


# ---------------------------------------------------------------------------
# run_with_reasoning tests
# ---------------------------------------------------------------------------

class TestRunWithReasoning:
    """Tests for DeskAgent.run_with_reasoning() SSE event generation."""

    async def test_no_factory_yields_echo_fallback(self, desk_agent, user_session):
        """Without agent_factory, run_with_reasoning yields echo TOKEN + DONE."""
        events: list[SSEEvent] = []
        async for evt in desk_agent.run_with_reasoning("Hello", user_session, "conv-1"):
            events.append(evt)

        assert len(events) == 2
        assert events[0].event == SSEEventType.TOKEN
        assert "No language model provider is configured" in events[0].data["content"]
        assert "Hello" in events[0].data["content"]
        assert events[1].event == SSEEventType.DONE
        assert events[1].data["conversation_id"] == "conv-1"

    async def test_factory_returns_none_agent_yields_echo(
        self, desk_agent_with_factory, mock_agent_factory, user_session,
    ):
        """When create_agent returns None, yields echo fallback."""
        mock_agent_factory.create_agent.return_value = None

        events: list[SSEEvent] = []
        async for evt in desk_agent_with_factory.run_with_reasoning(
            "Hi", user_session, "conv-1",
        ):
            events.append(evt)

        assert events[0].event == SSEEventType.TOKEN
        assert "No language model provider is configured" in events[0].data["content"]
        assert events[-1].event == SSEEventType.DONE

    async def test_yields_reasoning_step_events(
        self, desk_agent_with_factory, mock_agent_factory, user_session,
    ):
        """run_with_reasoning should yield REASONING_STEP events for each trace step."""
        mock_agent = AsyncMock()
        reasoning_result = _make_reasoning_result()
        mock_agent.run_with_reasoning = AsyncMock(return_value=reasoning_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        events: list[SSEEvent] = []
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            async for evt in desk_agent_with_factory.run_with_reasoning(
                "What is order 123?", user_session, "conv-1",
            ):
                events.append(evt)

        step_events = [e for e in events if e.event == SSEEventType.REASONING_STEP]
        assert len(step_events) == 3
        assert step_events[0].data["step_number"] == 1
        assert step_events[0].data["step_type"] == "thought"
        assert step_events[0].data["description"] == "Analyzing the request"
        assert step_events[0].data["status"] == "completed"
        assert step_events[1].data["step_number"] == 2
        assert step_events[1].data["step_type"] == "action"
        assert step_events[2].data["step_number"] == 3
        assert step_events[2].data["step_type"] == "observation"

    async def test_yields_token_events_for_output(
        self, desk_agent_with_factory, mock_agent_factory, user_session,
    ):
        """run_with_reasoning should yield TOKEN events for the final output text."""
        mock_agent = AsyncMock()
        reasoning_result = _make_reasoning_result(output="The answer is 42.")
        mock_agent.run_with_reasoning = AsyncMock(return_value=reasoning_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        events: list[SSEEvent] = []
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            async for evt in desk_agent_with_factory.run_with_reasoning(
                "What?", user_session, "conv-1",
            ):
                events.append(evt)

        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        full_text = "".join(e.data["content"] for e in token_events)
        assert full_text == "The answer is 42."

    async def test_yields_done_event_last(
        self, desk_agent_with_factory, mock_agent_factory, user_session,
    ):
        """run_with_reasoning should always yield DONE as the last event."""
        mock_agent = AsyncMock()
        reasoning_result = _make_reasoning_result()
        mock_agent.run_with_reasoning = AsyncMock(return_value=reasoning_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        events: list[SSEEvent] = []
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            async for evt in desk_agent_with_factory.run_with_reasoning(
                "test", user_session, "conv-1",
            ):
                events.append(evt)

        assert events[-1].event == SSEEventType.DONE
        assert events[-1].data["conversation_id"] == "conv-1"
        assert "turn_id" in events[-1].data

    async def test_done_has_unique_turn_id(
        self, desk_agent_with_factory, mock_agent_factory, user_session,
    ):
        """Each run_with_reasoning call should generate a unique turn_id."""
        mock_agent = AsyncMock()
        reasoning_result = _make_reasoning_result()
        mock_agent.run_with_reasoning = AsyncMock(return_value=reasoning_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        turn_ids = []
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            for _ in range(2):
                async for evt in desk_agent_with_factory.run_with_reasoning(
                    "test", user_session, "conv-1",
                ):
                    if evt.event == SSEEventType.DONE:
                        turn_ids.append(evt.data["turn_id"])

        assert len(turn_ids) == 2
        assert turn_ids[0] != turn_ids[1]

    async def test_plan_and_execute_emits_plan_event(
        self, desk_agent_with_factory, mock_agent_factory, user_session,
    ):
        """PlanAndExecute results should emit a PLAN event."""
        plan_step = MagicMock()
        plan_step.kind = "plan"
        plan_step.content = "Step 1: Look up order"

        action_step = MagicMock()
        action_step.kind = "action"
        action_step.content = "Executing lookup"

        reasoning_result = _make_reasoning_result(
            pattern_name="plan_and_execute",
            steps=[plan_step, action_step],
        )
        mock_agent = AsyncMock()
        mock_agent.run_with_reasoning = AsyncMock(return_value=reasoning_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        events: list[SSEEvent] = []
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            async for evt in desk_agent_with_factory.run_with_reasoning(
                "look up order", user_session, "conv-1",
            ):
                events.append(evt)

        plan_events = [e for e in events if e.event == SSEEventType.PLAN]
        assert len(plan_events) == 1
        assert len(plan_events[0].data["steps"]) == 1
        assert plan_events[0].data["steps"][0]["status"] == "completed"

    async def test_reasoning_failure_yields_error_and_done(
        self, desk_agent_with_factory, mock_agent_factory, user_session,
    ):
        """When reasoning raises an exception, an error TOKEN + DONE should be emitted."""
        mock_agent = AsyncMock()
        mock_agent.run_with_reasoning = AsyncMock(
            side_effect=RuntimeError("Model overloaded"),
        )
        mock_agent_factory.create_agent.return_value = mock_agent

        events: list[SSEEvent] = []
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"), \
             patch("asyncio.sleep", new_callable=AsyncMock):
            async for evt in desk_agent_with_factory.run_with_reasoning(
                "fail", user_session, "conv-1",
            ):
                events.append(evt)

        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        assert len(token_events) == 1
        # Transient errors get the friendly overloaded message (includes original error text)
        assert "temporarily overloaded" in token_events[0].data["content"]
        assert "Model overloaded" in token_events[0].data["content"]

        assert events[-1].event == SSEEventType.DONE

    async def test_audit_log_on_successful_reasoning(
        self, desk_agent_with_factory, mock_agent_factory, audit_logger, user_session,
    ):
        """Successful reasoning should log an audit event with pattern info."""
        mock_agent = AsyncMock()
        reasoning_result = _make_reasoning_result(pattern_name="react", steps_taken=3)
        mock_agent.run_with_reasoning = AsyncMock(return_value=reasoning_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            async for _ in desk_agent_with_factory.run_with_reasoning(
                "test", user_session, "conv-1",
            ):
                pass

        audit_logger.log.assert_awaited_once()
        logged_event = audit_logger.log.call_args[0][0]
        assert logged_event.action == "agent_reasoning_turn"
        assert logged_event.user_id == "user-42"
        assert logged_event.conversation_id == "conv-1"
        assert logged_event.detail["pattern"] == "react"
        assert logged_event.detail["steps_taken"] == 3

    async def test_no_audit_log_on_failure(
        self, desk_agent_with_factory, mock_agent_factory, audit_logger, user_session,
    ):
        """Failed reasoning should not log an audit event."""
        mock_agent = AsyncMock()
        mock_agent.run_with_reasoning = AsyncMock(
            side_effect=RuntimeError("boom"),
        )
        mock_agent_factory.create_agent.return_value = mock_agent

        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            async for _ in desk_agent_with_factory.run_with_reasoning(
                "fail", user_session, "conv-1",
            ):
                pass

        audit_logger.log.assert_not_awaited()

    async def test_event_order(
        self, desk_agent_with_factory, mock_agent_factory, user_session,
    ):
        """Events should follow: REASONING_STEP(s) -> TOKEN(s) -> DONE."""
        mock_agent = AsyncMock()
        reasoning_result = _make_reasoning_result()
        mock_agent.run_with_reasoning = AsyncMock(return_value=reasoning_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        event_types: list[SSEEventType] = []
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            async for evt in desk_agent_with_factory.run_with_reasoning(
                "test", user_session, "conv-1",
            ):
                event_types.append(evt.event)

        # REASONING_STEP events come first
        first_step = event_types.index(SSEEventType.REASONING_STEP)
        # TOKEN events come after all reasoning steps
        first_token = event_types.index(SSEEventType.TOKEN)
        # DONE is last
        done_idx = event_types.index(SSEEventType.DONE)

        assert first_step < first_token < done_idx

    async def test_step_without_kind_attribute(
        self, desk_agent_with_factory, mock_agent_factory, user_session,
    ):
        """Steps without 'kind' attribute should use class name as step_type."""

        class BareStep:
            """A step object with no 'kind' or 'content' attributes."""

            def __str__(self) -> str:
                return "Custom step description"

        step = BareStep()

        reasoning_result = _make_reasoning_result(steps=[step])
        mock_agent = AsyncMock()
        mock_agent.run_with_reasoning = AsyncMock(return_value=reasoning_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        events: list[SSEEvent] = []
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            async for evt in desk_agent_with_factory.run_with_reasoning(
                "test", user_session, "conv-1",
            ):
                events.append(evt)

        step_events = [e for e in events if e.event == SSEEventType.REASONING_STEP]
        assert len(step_events) == 1
        # Without kind, uses type(step).__name__
        assert step_events[0].data["step_type"] == "BareStep"
        # Without content, uses str(step)
        assert step_events[0].data["description"] == "Custom step description"

    async def test_empty_output_yields_no_tokens(
        self, desk_agent_with_factory, mock_agent_factory, user_session,
    ):
        """When output is empty, no TOKEN events should be emitted."""
        reasoning_result = _make_reasoning_result(output="")
        mock_agent = AsyncMock()
        mock_agent.run_with_reasoning = AsyncMock(return_value=reasoning_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        events: list[SSEEvent] = []
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            async for evt in desk_agent_with_factory.run_with_reasoning(
                "test", user_session, "conv-1",
            ):
                events.append(evt)

        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        assert len(token_events) == 0

    async def test_none_output_yields_no_tokens(
        self, desk_agent_with_factory, mock_agent_factory, user_session,
    ):
        """When output is None, no TOKEN events should be emitted."""
        reasoning_result = _make_reasoning_result(output="")
        reasoning_result.output = None
        mock_agent = AsyncMock()
        mock_agent.run_with_reasoning = AsyncMock(return_value=reasoning_result)
        mock_agent_factory.create_agent.return_value = mock_agent

        events: list[SSEEvent] = []
        with patch("fireflyframework_genai.reasoning.ReActPattern"), \
             patch("fireflyframework_genai.reasoning.PlanAndExecutePattern"):
            async for evt in desk_agent_with_factory.run_with_reasoning(
                "test", user_session, "conv-1",
            ):
                events.append(evt)

        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        assert len(token_events) == 0
