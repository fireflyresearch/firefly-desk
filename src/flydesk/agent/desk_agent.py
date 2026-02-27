# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""DeskAgent -- the conversational super-agent that orchestrates the full agent lifecycle."""

from __future__ import annotations

import asyncio
import logging
import random
import time
import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

from flydesk.agent.confirmation import ConfirmationService
from flydesk.agent.context import ContextEnricher
from flydesk.agent.prompt import PromptContext, SystemPromptBuilder
from flydesk.agent.response import AgentResponse
from flydesk.api.events import SSEEvent, SSEEventType
from flydesk.audit.logger import AuditLogger
from flydesk.audit.models import AuditEvent, AuditEventType
from flydesk.auth.models import UserSession
from flydesk.rbac.permissions import is_admin
from flydesk.tools.builtin import BuiltinToolExecutor, BuiltinToolRegistry
from flydesk.tools.factory import ToolDefinition, ToolFactory
from flydesk.tools.genai_adapter import adapt_tools
from flydesk.widgets.parser import WidgetParser

if TYPE_CHECKING:
    from flydesk.agent.customization import AgentCustomizationService
    from flydesk.agent.genai_bridge import DeskAgentFactory
    from flydesk.catalog.repository import CatalogRepository
    from flydesk.conversation.repository import ConversationRepository
    from flydesk.feedback.repository import FeedbackRepository
    from flydesk.files.models import FileUpload
    from flydesk.files.repository import FileUploadRepository
    from flydesk.files.storage import FileStorageProvider
    from flydesk.settings.repository import SettingsRepository
    from flydesk.tools.custom_repository import CustomToolRepository
    from flydesk.tools.executor import ToolCall, ToolExecutor, ToolResult
    from flydesk.tools.sandbox import SandboxExecutor

_logger = logging.getLogger(__name__)

# Token chunk size for simulated streaming (number of characters per token event).
_STREAM_CHUNK_SIZE = 20

# Resilience / budget exception types from fireflyframework-genai.
# We import at module level so they can be used in ``except`` clauses.
# If the genai package is not installed (unlikely at runtime) we fall back
# to exception types that can never be raised.
try:
    from fireflyframework_genai.agents.builtin_middleware import (
        BudgetExceededError as _BudgetExceededError,
    )
except ImportError:  # pragma: no cover
    _BudgetExceededError = type("_BudgetExceededError", (Exception,), {})  # type: ignore[assignment,misc]

try:
    from fireflyframework_genai.resilience.circuit_breaker import (
        CircuitBreakerOpenError as _CircuitBreakerOpenError,
    )
except ImportError:  # pragma: no cover
    _CircuitBreakerOpenError = type("_CircuitBreakerOpenError", (Exception,), {})  # type: ignore[assignment,misc]

# Module-level aliases used in ``except`` clauses.
_BUDGET_EXCEEDED_ERROR: type[Exception] = _BudgetExceededError  # type: ignore[assignment]
_CIRCUIT_BREAKER_OPEN_ERROR: type[Exception] = _CircuitBreakerOpenError  # type: ignore[assignment]

# Retry configuration for transient LLM provider errors.
_LLM_MAX_RETRIES = 3
_LLM_RETRY_BASE_DELAY = 3.0  # seconds
_LLM_RETRY_MAX_DELAY = 15.0  # seconds
# Number of fallback model attempts after exhausting primary retries.
_LLM_FALLBACK_RETRIES = 2
# Timeout for a single LLM streaming turn (seconds).  Must be long enough
# to cover the initial streaming response, tool execution, and the follow-up
# call that produces the final answer after tool results are available.
_LLM_STREAM_TIMEOUT = 300
# Timeout for the follow-up LLM call after tool execution (seconds).
_LLM_FOLLOWUP_TIMEOUT = 120

# Strings that indicate a transient/retryable LLM error.
_TRANSIENT_ERROR_INDICATORS = (
    "overloaded",
    "rate_limit",
    "rate limit",
    "too many requests",
    "529",
    "503",
    "502",
    "server_error",
    "temporarily unavailable",
    "capacity",
    "try again",
)


def _is_transient_error(exc: Exception) -> bool:
    """Return True if the exception looks like a transient LLM provider error."""
    msg = str(exc).lower()
    return any(indicator in msg for indicator in _TRANSIENT_ERROR_INDICATORS)


def _friendly_error_message(exc: Exception) -> str:
    """Return a user-friendly error message based on the exception type."""
    if _is_transient_error(exc):
        return (
            "The language model provider is temporarily overloaded. "
            "I retried automatically but it's still busy. "
            "Please try again in a moment.\n\n"
            f"Error: {exc}"
        )
    return (
        "I'm sorry, I encountered an error connecting to the language model. "
        "Please check your LLM provider configuration in Admin > LLM Providers.\n\n"
        f"Error: {exc}"
    )


class DeskAgent:
    """Orchestrates the full Desk Agent lifecycle for a single turn.

    Pipeline:
        1. **Context enrichment** -- knowledge graph + RAG retrieval in parallel.
        2. **Prompt assembly** -- build system prompt from enriched context.
        3. **LLM execution** -- placeholder echo for MVP (real integration later).
        4. **Post-processing** -- parse widget directives, write audit log.
        5. **Streaming** -- yield SSE events (token, widget, done).
    """

    def __init__(
        self,
        *,
        context_enricher: ContextEnricher,
        prompt_builder: SystemPromptBuilder,
        tool_factory: ToolFactory,
        widget_parser: WidgetParser,
        audit_logger: AuditLogger,
        agent_name: str = "Ember",
        company_name: str | None = None,
        tool_executor: ToolExecutor | None = None,
        builtin_executor: BuiltinToolExecutor | None = None,
        file_repo: FileUploadRepository | None = None,
        file_storage: FileStorageProvider | None = None,
        confirmation_service: ConfirmationService | None = None,
        conversation_repo: ConversationRepository | None = None,
        agent_factory: DeskAgentFactory | None = None,
        catalog_repo: CatalogRepository | None = None,
        customization_service: AgentCustomizationService | None = None,
        settings_repo: SettingsRepository | None = None,
        feedback_repo: FeedbackRepository | None = None,
        custom_tool_repo: CustomToolRepository | None = None,
        sandbox_executor: SandboxExecutor | None = None,
    ) -> None:
        self._context_enricher = context_enricher
        self._prompt_builder = prompt_builder
        self._tool_factory = tool_factory
        self._widget_parser = widget_parser
        self._audit_logger = audit_logger
        self._agent_name = agent_name
        self._company_name = company_name
        self._tool_executor = tool_executor
        self._builtin_executor = builtin_executor
        self._file_repo = file_repo
        self._file_storage = file_storage
        self._confirmation_service = confirmation_service
        self._conversation_repo = conversation_repo
        self._agent_factory = agent_factory
        self._catalog_repo = catalog_repo
        self._customization_service = customization_service
        self._settings_repo = settings_repo
        self._feedback_repo = feedback_repo
        self._custom_tool_repo = custom_tool_repo
        self._sandbox_executor = sandbox_executor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        message: str,
        session: UserSession,
        conversation_id: str,
        tools: list[ToolDefinition] | None = None,
        file_ids: list[str] | None = None,
    ) -> AgentResponse:
        """Execute a full agent turn.

        1. Enrich context (knowledge graph + RAG in parallel)
        2. Build system prompt (including attached file context)
        3. Execute LLM
        4. Parse widgets from response
        5. Log audit event
        6. Return AgentResponse
        """
        turn_id = str(uuid.uuid4())

        # Shared context enrichment + prompt building
        tools, system_prompt, multimodal_parts = await self._prepare_turn(
            message, session, conversation_id, tools, file_ids,
        )
        self._last_multimodal_parts = multimodal_parts

        # 3. Adapt catalog tools for genai tool-use and execute LLM
        adapted = await self._adapt_tools(tools, session, conversation_id)
        usage_data: dict[str, Any] = {}
        t0 = time.monotonic()
        raw_text = await self._call_llm(
            message, system_prompt, conversation_id, tools=adapted, usage_out=usage_data,
        )
        latency_ms = round((time.monotonic() - t0) * 1000)

        # 4. Post-processing: parse widget directives
        parse_result = self._widget_parser.parse(raw_text)
        clean_text = "\n\n".join(parse_result.text_segments)

        # 5. Audit logging
        audit_event = AuditEvent(
            event_type=AuditEventType.AGENT_RESPONSE,
            user_id=session.user_id,
            conversation_id=conversation_id,
            action="agent_turn",
            detail={
                "turn_id": turn_id,
                "message_length": len(message),
                "response_length": len(raw_text),
                "widget_count": len(parse_result.widgets),
                "model": usage_data.get("model", "unknown"),
                "input_tokens": usage_data.get("input_tokens", 0),
                "output_tokens": usage_data.get("output_tokens", 0),
                "latency_ms": latency_ms,
            },
        )
        await self._audit_logger.log(audit_event)

        # 6. Return assembled response
        return AgentResponse(
            text=clean_text,
            widgets=parse_result.widgets,
            raw_text=raw_text,
            conversation_id=conversation_id,
            turn_id=turn_id,
        )

    async def stream(
        self,
        message: str,
        session: UserSession,
        conversation_id: str,
        tools: list[ToolDefinition] | None = None,
        file_ids: list[str] | None = None,
    ) -> AsyncGenerator[SSEEvent, None]:
        """Stream SSE events for a full agent turn.

        When a FireflyAgent is available, uses ``run_stream()`` with
        ``streaming_mode="incremental"`` for real token-by-token streaming.
        Falls back to chunked echo when no agent factory is configured.

        Yields:
            SSEEventType.TOOL_START before context enrichment.
            SSEEventType.TOOL_END after context enrichment completes.
            SSEEventType.TOKEN events for text tokens.
            SSEEventType.WIDGET events for each parsed widget.
            SSEEventType.TOOL_SUMMARY aggregate summary.
            SSEEventType.DONE when complete.
        """
        turn_id = str(uuid.uuid4())

        # Emit TOOL_START before context enrichment
        tool_call_id = str(uuid.uuid4())
        yield SSEEvent(
            event=SSEEventType.TOOL_START,
            data={
                "tool_call_id": tool_call_id,
                "tool_name": "knowledge_retrieval",
            },
        )

        start = time.monotonic()

        # Shared context enrichment + prompt building
        tools, system_prompt, multimodal_parts = await self._prepare_turn(
            message, session, conversation_id, tools, file_ids,
        )
        self._last_multimodal_parts = multimodal_parts

        elapsed_ms = round((time.monotonic() - start) * 1000)

        # Emit TOOL_END after context enrichment completes
        yield SSEEvent(
            event=SSEEventType.TOOL_END,
            data={
                "tool_call_id": tool_call_id,
                "tool_name": "knowledge_retrieval",
                "duration_ms": elapsed_ms,
            },
        )

        # Adapt catalog tools for genai tool-use
        adapted = await self._adapt_tools(tools, session, conversation_id)

        # Stream tokens from the LLM (real streaming or chunked fallback)
        full_text = ""
        usage_data: dict[str, Any] = {}
        t0 = time.monotonic()
        async for token in self._stream_llm(
            message, system_prompt, conversation_id, tools=adapted, usage_out=usage_data,
        ):
            full_text += token
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={"content": token},
            )
        latency_ms = round((time.monotonic() - t0) * 1000)

        # Post-processing: parse widget directives from full response
        parse_result = self._widget_parser.parse(full_text)

        # Replace streamed content with clean text (widget directives stripped)
        clean_text = "\n\n".join(parse_result.text_segments)
        if clean_text != full_text:
            yield SSEEvent(
                event=SSEEventType.CONTENT_REPLACE,
                data={"content": clean_text},
            )

        # Emit widget events
        for widget in parse_result.widgets:
            yield SSEEvent(
                event=SSEEventType.WIDGET,
                data={
                    "widget_id": widget.widget_id,
                    "type": widget.type,
                    "props": widget.props,
                    "display": widget.display,
                    "blocking": widget.blocking,
                    "action": widget.action,
                },
            )

        # Audit logging (after usage extraction so we can include model/tokens/cost)
        audit_event = AuditEvent(
            event_type=AuditEventType.AGENT_RESPONSE,
            user_id=session.user_id,
            conversation_id=conversation_id,
            action="agent_turn",
            detail={
                "turn_id": turn_id,
                "message_length": len(message),
                "response_length": len(full_text),
                "widget_count": len(parse_result.widgets),
                "model": usage_data.get("model", "unknown"),
                "input_tokens": usage_data.get("input_tokens", 0),
                "output_tokens": usage_data.get("output_tokens", 0),
                "latency_ms": latency_ms,
                "cost_usd": usage_data.get("cost_usd", 0.0),
            },
        )
        await self._audit_logger.log(audit_event)

        # Emit TOOL_SUMMARY with actual tool call data from the LLM run.
        agent_tool_calls = usage_data.pop("tool_calls", [])
        success_count = sum(1 for tc in agent_tool_calls if tc.get("success"))
        yield SSEEvent(
            event=SSEEventType.TOOL_SUMMARY,
            data={
                "tool_calls": agent_tool_calls,
                "total_duration_ms": 0,
                "success_count": success_count,
                "failure_count": len(agent_tool_calls) - success_count,
            },
        )

        # Emit USAGE event before DONE (if usage data was captured)
        if usage_data:
            yield SSEEvent(
                event=SSEEventType.USAGE,
                data=usage_data,
            )

        # Final done event
        yield SSEEvent(
            event=SSEEventType.DONE,
            data={
                "conversation_id": conversation_id,
                "turn_id": turn_id,
                "tool_count": len(adapted or []),
            },
        )

    async def run_with_reasoning(
        self,
        message: str,
        session: UserSession,
        conversation_id: str,
        *,
        pattern: str = "auto",
        tools: list[ToolDefinition] | None = None,
        file_ids: list[str] | None = None,
    ) -> AsyncGenerator[SSEEvent, None]:
        """Run the agent with a reasoning pattern, yielding SSE events for progress."""
        turn_id = str(uuid.uuid4())

        # Shared context enrichment + prompt building
        tools, system_prompt, multimodal_parts = await self._prepare_turn(
            message, session, conversation_id, tools, file_ids,
        )
        self._last_multimodal_parts = multimodal_parts
        adapted = await self._adapt_tools(tools, session, conversation_id)

        # Create agent
        if self._agent_factory is None:
            yield SSEEvent(event=SSEEventType.TOKEN, data={"content": self._echo_fallback(message)})
            yield SSEEvent(event=SSEEventType.DONE, data={"conversation_id": conversation_id, "turn_id": turn_id})
            return

        agent = await self._agent_factory.create_agent(system_prompt, tools=adapted)
        if agent is None:
            yield SSEEvent(event=SSEEventType.TOKEN, data={"content": self._echo_fallback(message)})
            yield SSEEvent(event=SSEEventType.DONE, data={"conversation_id": conversation_id, "turn_id": turn_id})
            return

        # Select reasoning pattern
        pattern_instance = self._select_reasoning_pattern(pattern, tools)

        # Execute reasoning with retry for transient errors
        usage_data: dict[str, Any] = {}
        t0 = time.monotonic()
        try:
            last_reasoning_exc: Exception | None = None
            result = None
            for attempt in range(_LLM_MAX_RETRIES):
                try:
                    result = await agent.run_with_reasoning(pattern_instance, message, conversation_id=conversation_id)
                    break  # Success
                except (_BudgetExceededError, _CircuitBreakerOpenError):
                    raise  # Let outer handlers deal with these
                except Exception as retry_exc:
                    last_reasoning_exc = retry_exc
                    if _is_transient_error(retry_exc) and attempt < _LLM_MAX_RETRIES - 1:
                        delay = min(
                            _LLM_RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1),
                            _LLM_RETRY_MAX_DELAY,
                        )
                        _logger.warning(
                            "Transient LLM error in reasoning (attempt %d/%d), retrying in %.1fs: %s",
                            attempt + 1, _LLM_MAX_RETRIES, delay, retry_exc,
                        )
                        await asyncio.sleep(delay)
                        continue
                    raise  # Non-transient or final attempt
            if result is None:
                raise last_reasoning_exc or RuntimeError("Reasoning failed after retries")

            # Emit reasoning steps as SSE events
            for i, step in enumerate(result.trace.steps):
                yield SSEEvent(
                    event=SSEEventType.REASONING_STEP,
                    data={
                        "step_number": i + 1,
                        "step_type": step.kind if hasattr(step, "kind") else type(step).__name__,
                        "description": step.content if hasattr(step, "content") else str(step),
                        "status": "completed",
                    },
                )

            # If PlanAndExecute, emit plan event
            if hasattr(result, "trace") and result.trace.pattern_name == "plan_and_execute":
                plan_steps = [
                    s for s in result.trace.steps
                    if hasattr(s, "kind") and s.kind == "plan"
                ]
                if plan_steps:
                    yield SSEEvent(
                        event=SSEEventType.PLAN,
                        data={"steps": [{"description": str(s), "status": "completed"} for s in plan_steps]},
                    )

            # Emit final text as tokens
            output_text = str(result.output) if result.output else ""
            for i in range(0, len(output_text), _STREAM_CHUNK_SIZE):
                yield SSEEvent(
                    event=SSEEventType.TOKEN,
                    data={"content": output_text[i : i + _STREAM_CHUNK_SIZE]},
                )

            # Parse widgets from output
            parse_result = self._widget_parser.parse(output_text)

            # Replace streamed content with clean text (widget directives stripped)
            reasoning_clean_text = "\n\n".join(parse_result.text_segments)
            if reasoning_clean_text != output_text:
                yield SSEEvent(
                    event=SSEEventType.CONTENT_REPLACE,
                    data={"content": reasoning_clean_text},
                )

            for widget in parse_result.widgets:
                yield SSEEvent(
                    event=SSEEventType.WIDGET,
                    data={
                        "widget_id": widget.widget_id,
                        "type": widget.type,
                        "props": widget.props,
                        "display": widget.display,
                    },
                )

            # Extract usage from reasoning result
            usage_data = self._extract_result_usage(result, agent)
            latency_ms = round((time.monotonic() - t0) * 1000)

            # Audit
            audit_event = AuditEvent(
                event_type=AuditEventType.AGENT_RESPONSE,
                user_id=session.user_id,
                conversation_id=conversation_id,
                action="agent_reasoning_turn",
                detail={
                    "turn_id": turn_id,
                    "pattern": result.trace.pattern_name,
                    "steps_taken": result.steps_taken,
                    "model": usage_data.get("model", "unknown"),
                    "input_tokens": usage_data.get("input_tokens", 0),
                    "output_tokens": usage_data.get("output_tokens", 0),
                    "latency_ms": latency_ms,
                    "cost_usd": usage_data.get("cost_usd", 0.0),
                },
            )
            await self._audit_logger.log(audit_event)

        except _BUDGET_EXCEEDED_ERROR as exc:
            _logger.warning("Budget exceeded during reasoning: %s", exc)
            yield SSEEvent(
                event=SSEEventType.ERROR,
                data={
                    "code": "budget_exceeded",
                    "message": (
                        "Your message could not be processed because the cost budget has been "
                        "reached. Please contact your administrator to increase the spending limit."
                    ),
                },
            )
        except _CIRCUIT_BREAKER_OPEN_ERROR as exc:
            _logger.warning("Circuit breaker open during reasoning: %s", exc)
            yield SSEEvent(
                event=SSEEventType.ERROR,
                data={
                    "code": "provider_unavailable",
                    "message": (
                        "The language model provider is temporarily unavailable. "
                        "Please try again in a few moments."
                    ),
                },
            )
        except Exception as exc:
            _logger.error("Reasoning failed: %s", exc, exc_info=True)
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={"content": _friendly_error_message(exc)},
            )

        # Emit USAGE event before DONE (if usage data was captured)
        if usage_data:
            yield SSEEvent(
                event=SSEEventType.USAGE,
                data=usage_data,
            )

        # Done
        yield SSEEvent(
            event=SSEEventType.DONE,
            data={"conversation_id": conversation_id, "turn_id": turn_id},
        )

    def _select_reasoning_pattern(self, pattern_name: str, tools: list | None) -> Any:
        """Select the reasoning pattern to use."""
        from fireflyframework_genai.reasoning import (
            PlanAndExecutePattern,
            ReActPattern,
        )

        if pattern_name == "auto":
            # Auto-detect: if tools available and more than 2, use PlanAndExecute; otherwise ReAct
            if tools and len(tools) > 2:
                return PlanAndExecutePattern(max_steps=8)
            return ReActPattern(max_steps=5)

        match pattern_name:
            case "react":
                return ReActPattern(max_steps=5)
            case "plan_and_execute":
                return PlanAndExecutePattern(max_steps=8)
            case "chain_of_thought":
                from fireflyframework_genai.reasoning import ChainOfThoughtPattern
                return ChainOfThoughtPattern(max_steps=5)
            case "reflexion":
                from fireflyframework_genai.reasoning import ReflexionPattern
                return ReflexionPattern(max_steps=5)
            case _:
                return ReActPattern(max_steps=5)

    # ------------------------------------------------------------------
    # Tool execution infrastructure
    # ------------------------------------------------------------------

    async def _execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
        session: UserSession,
        conversation_id: str,
        tool_defs: list[ToolDefinition] | None = None,
    ) -> AsyncGenerator[SSEEvent, None]:
        """Execute tool calls and yield SSE events for each.

        For every tool call:
        1. Check if the tool requires user confirmation (safety gate).
        2. If confirmation is required, emit a ``CONFIRMATION`` SSE event
           and skip execution for that call.
        3. Otherwise, emit ``TOOL_START`` with the call metadata.
        4. Execute via :class:`ToolExecutor` (parallel when possible).
        5. Emit ``TOOL_END`` per completed call with result summary.
        6. Emit ``TOOL_SUMMARY`` with aggregated results for the batch.

        Requires ``self._tool_executor`` to be set; raises
        :class:`RuntimeError` otherwise.
        """
        if self._tool_executor is None:
            msg = "ToolExecutor is not configured"
            raise RuntimeError(msg)

        # Build a lookup from endpoint_id -> ToolDefinition for confirmation checks.
        defs_by_endpoint: dict[str, ToolDefinition] = {}
        if tool_defs:
            for td in tool_defs:
                defs_by_endpoint[td.endpoint_id] = td

        # Partition tool calls: those that require confirmation vs. safe to execute.
        safe_calls: list[ToolCall] = []
        for call in tool_calls:
            tool_def = defs_by_endpoint.get(call.endpoint_id)

            if (
                tool_def is not None
                and self._confirmation_service is not None
                and self._confirmation_service.requires_confirmation(
                    tool_def, list(session.permissions),
                )
            ):
                # Create a pending confirmation and emit a CONFIRMATION event.
                pending = self._confirmation_service.create_confirmation(
                    tool_call=call,
                    tool_def=tool_def,
                    user_id=session.user_id,
                    conversation_id=conversation_id,
                )
                yield SSEEvent(
                    event=SSEEventType.CONFIRMATION,
                    data={
                        "confirmation_id": pending.confirmation_id,
                        "tool_call_id": call.call_id,
                        "tool_name": call.tool_name,
                        "risk_level": pending.risk_level.value,
                        "message": (
                            f"Tool '{call.tool_name}' requires confirmation "
                            f"(risk: {pending.risk_level.value}). "
                            "Reply with __confirm__:<id> or __reject__:<id>."
                        ),
                    },
                )
            else:
                safe_calls.append(call)

        if not safe_calls:
            # All calls need confirmation; emit an empty summary.
            yield SSEEvent(
                event=SSEEventType.TOOL_SUMMARY,
                data={
                    "tool_calls": [],
                    "total_duration_ms": 0,
                    "success_count": 0,
                    "failure_count": 0,
                },
            )
            return

        # Emit TOOL_START for each safe call.
        for call in safe_calls:
            yield SSEEvent(
                event=SSEEventType.TOOL_START,
                data={
                    "tool_call_id": call.call_id,
                    "tool_name": call.tool_name,
                },
            )

        # Execute with automatic parallelism classification.
        results: list[ToolResult] = await self._tool_executor.execute_parallel(
            safe_calls, session, conversation_id,
        )

        # Emit TOOL_END for each result.
        for result in results:
            yield SSEEvent(
                event=SSEEventType.TOOL_END,
                data={
                    "tool_call_id": result.call_id,
                    "tool_name": result.tool_name,
                    "success": result.success,
                    "duration_ms": result.duration_ms,
                    "error": result.error,
                },
            )

        # Emit TOOL_SUMMARY with aggregated statistics.
        success_count = sum(1 for r in results if r.success)
        failure_count = sum(1 for r in results if not r.success)
        total_duration = sum(r.duration_ms for r in results)

        yield SSEEvent(
            event=SSEEventType.TOOL_SUMMARY,
            data={
                "tool_calls": [
                    {
                        "call_id": r.call_id,
                        "tool_name": r.tool_name,
                        "success": r.success,
                        "duration_ms": r.duration_ms,
                        "error": r.error,
                    }
                    for r in results
                ],
                "total_duration_ms": round(total_duration, 1),
                "success_count": success_count,
                "failure_count": failure_count,
            },
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _load_conversation_history(
        self, conversation_id: str, user_id: str, limit: int = 20,
    ) -> list[dict[str, str]]:
        """Load recent messages from the conversation store, scoped to user."""
        if self._conversation_repo is None:
            return []
        messages = await self._conversation_repo.get_messages(
            conversation_id, user_id, limit=limit,
        )
        return [
            {"role": msg.role.value, "content": msg.content}
            for msg in messages
        ]

    @staticmethod
    def _format_conversation_history(history: list[dict[str, str]]) -> str:
        """Format conversation history into a summary for the system prompt."""
        if not history:
            return ""
        lines: list[str] = []
        for msg in history[-10:]:  # Last 10 messages for context
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")[:200]  # Truncate long messages
            lines.append(f"{role}: {content}")
        return "Recent conversation:\n" + "\n".join(lines)

    async def _build_file_context(
        self, file_ids: list[str] | None,
    ) -> tuple[str, list]:
        """Fetch uploaded files by ID and build text context + multimodal parts.

        Returns a tuple of ``(text_context, multimodal_parts)``.  The text
        context is the same concatenated extracted-text string used historically.
        The multimodal parts list contains :class:`BinaryContent` objects for
        images and string descriptions for text/document files, suitable for
        passing to multimodal LLMs.

        Returns ``("", [])`` when no file IDs are provided or the file
        repository is not configured.
        """
        if not file_ids or self._file_repo is None:
            return "", []

        uploads: list[FileUpload] = []
        parts: list[str] = []
        for file_id in file_ids:
            upload = await self._file_repo.get(file_id)
            if upload is None:
                continue
            uploads.append(upload)
            text = upload.extracted_text or ""
            if text:
                parts.append(f"- [{upload.filename}]: {text}")

        text_context = "\n".join(parts)

        # Build multimodal parts when file storage is available.
        multimodal_parts: list = []
        if self._file_storage is not None and uploads:
            multimodal_parts = await _build_multimodal_parts(
                uploads, self._file_storage,
            )

        return text_context, multimodal_parts

    async def _prepare_turn(
        self,
        message: str,
        session: UserSession,
        conversation_id: str,
        tools: list[ToolDefinition] | None,
        file_ids: list[str] | None,
    ) -> tuple[list[ToolDefinition], str, list]:
        """Shared context enrichment + prompt building for run() and stream().

        Returns:
            A tuple of (resolved_tools, system_prompt, multimodal_parts).
            ``multimodal_parts`` contains :class:`BinaryContent` objects for
            images and string descriptions for documents when file storage
            is configured, otherwise an empty list.
        """
        # 0. Auto-load tools from catalog + built-ins if not provided
        scopes = session.access_scopes
        admin_user = is_admin(list(session.permissions))

        if tools is None:
            tools = []
            # Catalog-derived tools (external system endpoints)
            if self._catalog_repo is not None:
                try:
                    endpoints = await self._catalog_repo.list_active_endpoints()

                    # Build agent_enabled map for whitelist filtering
                    agent_enabled_map: dict[str, bool] | None = None
                    tool_access_mode = "whitelist"
                    if self._settings_repo is not None:
                        mode = await self._settings_repo.get_app_setting("tool_access_mode")
                        if mode is not None:
                            tool_access_mode = mode
                        systems, _ = await self._catalog_repo.list_systems()
                        agent_enabled_map = {s.id: s.agent_enabled for s in systems}

                    tools = self._tool_factory.build_tool_definitions(
                        endpoints,
                        list(session.permissions),
                        access_scopes=None if admin_user else scopes,
                        tool_access_mode=tool_access_mode,
                        agent_enabled_map=agent_enabled_map,
                    )
                    _logger.debug("Loaded %d catalog tools for user %s", len(tools), session.user_id)
                except Exception:
                    _logger.debug("Failed to load tools from catalog.", exc_info=True)

            # Built-in platform tools
            builtin_tools = BuiltinToolRegistry.get_tool_definitions(
                list(session.permissions),
            )
            tools.extend(builtin_tools)
            _logger.debug("Added %d built-in tools for user %s", len(builtin_tools), session.user_id)

            catalog_tool_count = len(tools) - len(builtin_tools)
            _logger.info(
                "Prepared turn: %d catalog tools, %d builtin tools, total=%d",
                catalog_tool_count, len(builtin_tools), len(tools),
            )

        # Resolve knowledge tag filter from access scopes (admin bypasses)
        knowledge_tag_filter: list[str] | None = None
        if not admin_user and scopes.knowledge_tags:
            knowledge_tag_filter = scopes.knowledge_tags

        # 1. Context enrichment (with user-scoped conversation history)
        history = await self._load_conversation_history(
            conversation_id, session.user_id,
        )
        enriched = await self._context_enricher.enrich(
            message,
            conversation_history=history,
            knowledge_tag_filter=knowledge_tag_filter,
        )

        # 2. Prompt assembly
        tool_summaries = self._build_tool_summaries(tools or [])
        knowledge_context = self._format_knowledge_context(enriched)
        file_context, multimodal_parts = await self._build_file_context(file_ids)
        conversation_summary = self._format_conversation_history(
            enriched.conversation_history,
        )

        # Load agent profile from customization service (if available)
        agent_name = self._agent_name
        personality = ""
        tone = ""
        behavior_rules: list[str] = []
        custom_instructions = ""
        language = "en"
        if self._customization_service is not None:
            try:
                profile = await self._customization_service.get_profile_for_user(session.user_id)
                agent_name = profile.name
                personality = profile.personality
                tone = profile.tone
                behavior_rules = profile.behavior_rules
                custom_instructions = profile.custom_instructions
                language = profile.language
            except Exception:
                _logger.debug("Failed to load agent profile; using defaults.", exc_info=True)

        # Load user feedback summary for adaptive behavior
        feedback_context = ""
        if self._feedback_repo is not None:
            try:
                feedback_context = await self._feedback_repo.get_feedback_context(
                    session.user_id,
                )
            except Exception:
                _logger.debug("Failed to load feedback summary.", exc_info=True)

        prompt_context = PromptContext(
            agent_name=agent_name,
            company_name=self._company_name,
            user_name=session.display_name,
            user_roles=list(session.roles),
            user_permissions=list(session.permissions),
            user_department=session.department or "",
            user_title=session.title or "",
            tool_summaries=tool_summaries,
            knowledge_context=knowledge_context,
            file_context=file_context,
            conversation_summary=conversation_summary,
            process_context=enriched.relevant_processes,
            personality=personality,
            tone=tone,
            behavior_rules=behavior_rules,
            custom_instructions=custom_instructions,
            language=language,
            feedback_context=feedback_context,
        )
        system_prompt = self._prompt_builder.build(prompt_context)

        return tools, system_prompt, multimodal_parts

    async def _adapt_tools(
        self,
        tools: list[ToolDefinition] | None,
        session: UserSession,
        conversation_id: str,
    ) -> list[object] | None:
        """Wrap ToolDefinitions as genai BaseTools if a ToolExecutor is available.

        Returns ``None`` when there is no executor or no tools, so
        :meth:`_call_llm` / :meth:`_stream_llm` can pass the value
        directly to :meth:`DeskAgentFactory.create_agent`.

        When a :class:`CustomToolRepository` and :class:`SandboxExecutor` are
        configured, active custom tools are loaded and included alongside the
        catalog and built-in tools.
        """
        if not tools or self._tool_executor is None:
            return None

        # Load active custom tools from the repository (if configured).
        custom_tools: list[tuple[Any, Any]] | None = None
        if self._custom_tool_repo is not None and self._sandbox_executor is not None:
            try:
                active = await self._custom_tool_repo.list(active_only=True)
                if active:
                    custom_tools = [(t, self._sandbox_executor) for t in active]
                    _logger.debug("Loaded %d active custom tools.", len(active))
            except Exception:
                _logger.debug("Failed to load custom tools.", exc_info=True)

        return adapt_tools(
            tools, self._tool_executor, session, conversation_id,
            builtin_executor=self._builtin_executor,
            custom_tools=custom_tools,
        )

    async def _stream_llm(
        self,
        message: str,
        system_prompt: str,
        conversation_id: str | None = None,
        tools: list[object] | None = None,
        usage_out: dict[str, Any] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from the LLM via FireflyAgent.run_stream().

        When no agent factory is configured or the agent cannot be created,
        falls back to yielding the echo response in fixed-size chunks.

        Args:
            message: The user message.
            system_prompt: The assembled system prompt.
            conversation_id: Conversation ID for MemoryManager auto-injection.
            tools: Adapted genai tools for the FireflyAgent.
            usage_out: Optional mutable dict that will be populated with token
                usage data after the stream completes.  Keys:
                ``input_tokens``, ``output_tokens``, ``total_tokens``,
                ``cost_usd``, ``model``.

        Yields:
            Individual token strings as they arrive from the model.
        """
        if self._agent_factory is None:
            for chunk in self._echo_fallback_chunks(message):
                yield chunk
            return

        agent = await self._agent_factory.create_agent(system_prompt, tools=tools)
        if agent is None:
            for chunk in self._echo_fallback_chunks(message):
                yield chunk
            return

        _logger.info(
            "LLM agent streaming with %d tools (model=%s)",
            len(tools or []),
            str(getattr(agent, "_model_identifier", "unknown")),
        )

        # Log tool registration state for diagnostics
        try:
            inner_agent = agent.agent  # pydantic_ai.Agent
            toolset = getattr(inner_agent, "_function_toolset", None)
            if toolset is not None:
                tools_attr = getattr(toolset, "tools", {})
                if isinstance(tools_attr, dict):
                    tool_names = list(tools_attr.keys())
                    _logger.info(
                        "LLM agent created with %d tools: %s (model=%s)",
                        len(tool_names), tool_names[:5],
                        getattr(inner_agent, "model", "?"),
                    )
        except Exception:
            _logger.debug("Could not inspect agent tools.", exc_info=True)

        last_exc: Exception | None = None
        for attempt in range(_LLM_MAX_RETRIES):
            try:
                async with asyncio.timeout(_LLM_STREAM_TIMEOUT):
                    async with await agent.run_stream(
                        message,
                        streaming_mode="incremental",
                        conversation_id=conversation_id,
                    ) as stream:
                        async for token in stream.stream_tokens():
                            yield token
                        # After streaming completes, extract usage from the underlying stream
                        if usage_out is not None:
                            self._extract_stream_usage(stream, agent, usage_out)
                            # Also extract tool call info from the message history
                            self._extract_tool_calls(stream, usage_out)

                    # pydantic-ai's run_stream only handles the first model turn.
                    # If the model called tools, the follow-up response (with tool
                    # results) was never generated.  Detect this and do a follow-up
                    # run() with the accumulated message history so the model can
                    # produce the actual answer.
                    async for token in self._follow_up_after_tool_calls(
                        stream, agent, conversation_id, usage_out,
                    ):
                        yield token

                return  # Success — exit retry loop
            except _BUDGET_EXCEEDED_ERROR as exc:
                _logger.warning("Budget exceeded during streaming: %s", exc)
                yield (
                    "Your message could not be processed because the cost budget has been "
                    "reached. Please contact your administrator to increase the spending limit."
                )
                return
            except _CIRCUIT_BREAKER_OPEN_ERROR as exc:
                _logger.warning("Circuit breaker open during streaming: %s", exc)
                yield (
                    "The language model provider is temporarily unavailable. "
                    "Please try again in a few moments."
                )
                return
            except TimeoutError:
                _logger.warning("LLM streaming timed out after %ds", _LLM_STREAM_TIMEOUT)
                yield (
                    "The language model took too long to respond. "
                    "Please try again or check your LLM provider configuration."
                )
                return
            except Exception as exc:
                last_exc = exc
                if _is_transient_error(exc):
                    if attempt < _LLM_MAX_RETRIES - 1:
                        delay = min(
                            _LLM_RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1),
                            _LLM_RETRY_MAX_DELAY,
                        )
                        _logger.warning(
                            "Transient LLM error (attempt %d/%d), retrying in %.1fs: %s",
                            attempt + 1, _LLM_MAX_RETRIES, delay, exc,
                        )
                        await asyncio.sleep(delay)
                        continue
                    # Final attempt — fall through to fallback models below
                    _logger.warning(
                        "Primary model exhausted %d retries: %s", _LLM_MAX_RETRIES, exc,
                    )
                else:
                    # Non-transient error — report to user immediately
                    _logger.error("LLM streaming failed: %s", exc, exc_info=True)
                    yield _friendly_error_message(exc)
                    return

        # All retries on primary model exhausted — try fallback models.
        if last_exc is not None and _is_transient_error(last_exc) and self._agent_factory:
            fallback_models = await self._agent_factory.get_fallback_model_strings()
            for fb_model in fallback_models:
                _logger.warning("Primary model overloaded, trying fallback: %s", fb_model)
                fb_agent = await self._agent_factory.create_agent(
                    system_prompt, tools=tools, model_override=fb_model,
                )
                if fb_agent is None:
                    continue
                for fb_attempt in range(_LLM_FALLBACK_RETRIES):
                    try:
                        async with asyncio.timeout(_LLM_STREAM_TIMEOUT):
                            async with await fb_agent.run_stream(
                                message,
                                streaming_mode="incremental",
                                conversation_id=conversation_id,
                            ) as fb_stream:
                                async for token in fb_stream.stream_tokens():
                                    yield token
                                if usage_out is not None:
                                    self._extract_stream_usage(fb_stream, fb_agent, usage_out)
                                    self._extract_tool_calls(fb_stream, usage_out)

                            # Follow-up for tool calls (same as primary model)
                            async for token in self._follow_up_after_tool_calls(
                                fb_stream, fb_agent, conversation_id, usage_out,
                            ):
                                yield token

                        return  # Fallback succeeded
                    except Exception as fb_exc:
                        if _is_transient_error(fb_exc) and fb_attempt < _LLM_FALLBACK_RETRIES - 1:
                            delay = _LLM_RETRY_BASE_DELAY + random.uniform(0, 1)
                            _logger.warning(
                                "Fallback model %s also busy (attempt %d/%d), retrying in %.1fs",
                                fb_model, fb_attempt + 1, _LLM_FALLBACK_RETRIES, delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                        _logger.warning("Fallback model %s failed: %s", fb_model, fb_exc)
                        break  # Try next fallback model

        # All retries and fallbacks exhausted
        if last_exc is not None:
            _logger.error("LLM streaming failed after %d retries + fallbacks: %s", _LLM_MAX_RETRIES, last_exc)
            yield _friendly_error_message(last_exc)

    async def _follow_up_after_tool_calls(
        self,
        stream: object,
        agent: object,
        conversation_id: str | None,
        usage_out: dict[str, Any] | None,
    ) -> AsyncGenerator[str, None]:
        """If the stream's model turn included tool calls, run a follow-up.

        pydantic-ai's ``run_stream()`` only handles a single model turn.
        When the model emits text + tool_call, the ``on_complete()`` callback
        executes the tools and appends results to the message history, but
        there is no second LLM call to produce the actual answer.

        This method detects that situation, extracts the accumulated message
        history, and calls ``agent.run()`` with it so the LLM sees the tool
        results and can produce a meaningful response.  The follow-up text
        is yielded in fixed-size chunks to maintain the streaming feel.
        """
        # Check if any tool calls happened during the stream.
        tool_calls = (usage_out or {}).get("tool_calls", [])
        if not tool_calls:
            return

        _logger.info(
            "Stream had %d tool call(s); running follow-up to get tool-result response",
            len(tool_calls),
        )

        # Get the complete message history from the stream (includes the
        # user prompt, model response with tool calls, and tool return values).
        try:
            inner_stream = getattr(stream, "_stream", stream)
            all_messages_fn = getattr(inner_stream, "all_messages", None)
            if callable(all_messages_fn):
                message_history = all_messages_fn()
            elif isinstance(all_messages_fn, (list, tuple)):
                message_history = list(all_messages_fn)
            else:
                _logger.warning("Cannot extract message history from stream; skipping follow-up.")
                return
        except Exception:
            _logger.debug("Failed to extract message history for follow-up.", exc_info=True)
            return

        # Make a follow-up run() call with the accumulated history so the LLM
        # sees the tool results and produces the final answer.
        try:
            # Use the underlying pydantic-ai agent directly so we can pass
            # message_history without re-injecting memory.
            inner_agent = getattr(agent, "agent", agent)  # pydantic_ai.Agent
            async with asyncio.timeout(_LLM_FOLLOWUP_TIMEOUT):
                result = await inner_agent.run(
                    "Based on the tool results above, provide a complete answer.",
                    message_history=message_history,
                )
            follow_up_text = str(result.output) if hasattr(result, "output") else str(result.data)

            if follow_up_text:
                # Yield a separator so the user can distinguish the follow-up
                yield "\n\n"
                for i in range(0, len(follow_up_text), _STREAM_CHUNK_SIZE):
                    yield follow_up_text[i : i + _STREAM_CHUNK_SIZE]

                # Update usage with the follow-up call's tokens
                if usage_out is not None:
                    try:
                        fu_usage = result.usage() if callable(getattr(result, "usage", None)) else None
                        if fu_usage:
                            usage_out["input_tokens"] = usage_out.get("input_tokens", 0) + (getattr(fu_usage, "input_tokens", 0) or 0)
                            usage_out["output_tokens"] = usage_out.get("output_tokens", 0) + (getattr(fu_usage, "output_tokens", 0) or 0)
                            usage_out["total_tokens"] = usage_out["input_tokens"] + usage_out["output_tokens"]
                    except Exception:
                        _logger.debug("Failed to extract follow-up usage.", exc_info=True)
        except TimeoutError:
            _logger.warning("Follow-up LLM call timed out after %ds", _LLM_FOLLOWUP_TIMEOUT)
            yield "\n\n*The follow-up response timed out. The tool calls completed but the summary could not be generated.*"
        except Exception as exc:
            _logger.error("Follow-up LLM call after tool execution failed: %s", exc, exc_info=True)
            yield f"\n\n*Tool results could not be summarized: {exc}*"

    async def _call_llm(
        self,
        message: str,
        system_prompt: str,
        conversation_id: str | None = None,
        tools: list[object] | None = None,
        usage_out: dict[str, Any] | None = None,
    ) -> str:
        """Call the LLM via FireflyAgent.

        Args:
            message: The user message.
            system_prompt: The assembled system prompt.
            conversation_id: Conversation ID for MemoryManager auto-injection.
            tools: Adapted genai tools for the FireflyAgent.
            usage_out: Optional mutable dict that will be populated with token
                usage data after the call completes.
        """
        if self._agent_factory is None:
            return self._echo_fallback(message)

        agent = await self._agent_factory.create_agent(system_prompt, tools=tools)
        if agent is None:
            return self._echo_fallback(message)

        last_exc: Exception | None = None
        for attempt in range(_LLM_MAX_RETRIES):
            try:
                result = await agent.run(message, conversation_id=conversation_id)
                if usage_out is not None:
                    usage_out.update(self._extract_result_usage(result, agent))
                return str(result.output)
            except _BUDGET_EXCEEDED_ERROR as exc:
                _logger.warning("Budget exceeded during LLM call: %s", exc)
                return (
                    "Your message could not be processed because the cost budget has been "
                    "reached. Please contact your administrator to increase the spending limit."
                )
            except _CIRCUIT_BREAKER_OPEN_ERROR as exc:
                _logger.warning("Circuit breaker open during LLM call: %s", exc)
                return (
                    "The language model provider is temporarily unavailable. "
                    "Please try again in a few moments."
                )
            except Exception as exc:
                last_exc = exc
                if _is_transient_error(exc):
                    if attempt < _LLM_MAX_RETRIES - 1:
                        delay = min(
                            _LLM_RETRY_BASE_DELAY * (2 ** attempt) + random.uniform(0, 1),
                            _LLM_RETRY_MAX_DELAY,
                        )
                        _logger.warning(
                            "Transient LLM error (attempt %d/%d), retrying in %.1fs: %s",
                            attempt + 1, _LLM_MAX_RETRIES, delay, exc,
                        )
                        await asyncio.sleep(delay)
                        continue
                    _logger.warning(
                        "Primary model exhausted %d retries: %s", _LLM_MAX_RETRIES, exc,
                    )
                else:
                    _logger.error("LLM call failed: %s", exc, exc_info=True)
                    return _friendly_error_message(exc)

        # All retries on primary model exhausted — try fallback models.
        if last_exc is not None and _is_transient_error(last_exc) and self._agent_factory:
            fallback_models = await self._agent_factory.get_fallback_model_strings()
            for fb_model in fallback_models:
                _logger.warning("Primary model overloaded, trying fallback: %s", fb_model)
                fb_agent = await self._agent_factory.create_agent(
                    system_prompt, tools=tools, model_override=fb_model,
                )
                if fb_agent is None:
                    continue
                for fb_attempt in range(_LLM_FALLBACK_RETRIES):
                    try:
                        result = await fb_agent.run(message, conversation_id=conversation_id)
                        return str(result.output)
                    except Exception as fb_exc:
                        if _is_transient_error(fb_exc) and fb_attempt < _LLM_FALLBACK_RETRIES - 1:
                            delay = _LLM_RETRY_BASE_DELAY + random.uniform(0, 1)
                            _logger.warning(
                                "Fallback model %s also busy (attempt %d/%d), retrying in %.1fs",
                                fb_model, fb_attempt + 1, _LLM_FALLBACK_RETRIES, delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                        _logger.warning("Fallback model %s failed: %s", fb_model, fb_exc)
                        break  # Try next fallback model

        # All retries and fallbacks exhausted
        _logger.error("LLM call failed after %d retries + fallbacks: %s", _LLM_MAX_RETRIES, last_exc)
        return _friendly_error_message(last_exc or RuntimeError("Unknown error"))

    @staticmethod
    def _echo_fallback(message: str) -> str:
        """Fallback response when no LLM provider is configured."""
        return (
            "No language model provider is configured yet. "
            "Please set up an LLM provider in Admin > LLM Providers or "
            "run the setup wizard at /setup.\n\n"
            f"Your message: {message}"
        )

    @staticmethod
    def _echo_fallback_chunks(message: str) -> list[str]:
        """Return the echo fallback text as fixed-size chunks for streaming."""
        text = DeskAgent._echo_fallback(message)
        return [
            text[i : i + _STREAM_CHUNK_SIZE]
            for i in range(0, len(text), _STREAM_CHUNK_SIZE)
        ]

    @staticmethod
    def _extract_stream_usage(
        stream: object,
        agent: object,
        usage_out: dict[str, Any],
    ) -> None:
        """Extract token usage from a completed stream and populate *usage_out*.

        Reads ``usage()`` from the underlying pydantic-ai stream handle and
        combines it with the agent's model identifier to estimate cost.
        """
        try:
            usage_fn = getattr(stream, "usage", None)
            usage = usage_fn() if callable(usage_fn) else None
            if usage is None:
                return

            input_tokens = getattr(usage, "input_tokens", 0) or 0
            output_tokens = getattr(usage, "output_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or (input_tokens + output_tokens)

            model_name = getattr(agent, "_model_identifier", "unknown")

            cost_usd = 0.0
            try:
                from fireflyframework_genai.config import get_config
                from fireflyframework_genai.observability.cost import get_cost_calculator

                cfg = get_config()
                calculator = get_cost_calculator(cfg.cost_calculator)
                cost_usd = calculator.estimate(model_name, input_tokens, output_tokens)
            except Exception:
                _logger.debug("Cost estimation not available.", exc_info=True)

            usage_out.update({
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost_usd": round(cost_usd, 6),
                "model": model_name,
            })
        except Exception:
            _logger.debug("Failed to extract stream usage.", exc_info=True)

    @staticmethod
    def _extract_tool_calls(stream: object, usage_out: dict[str, Any]) -> None:
        """Extract tool call info from the completed pydantic-ai stream.

        Inspects the message history on the underlying stream to find any
        tool calls and tool returns that occurred during the agent run.
        """
        try:
            inner_stream = getattr(stream, "_stream", stream)
            all_messages = getattr(inner_stream, "all_messages", None)
            if callable(all_messages):
                messages = all_messages()
            elif isinstance(all_messages, (list, tuple)):
                messages = all_messages
            else:
                return

            tool_calls_info: list[dict[str, Any]] = []
            for msg in messages:
                parts = getattr(msg, "parts", [])
                for part in parts:
                    part_type = type(part).__name__
                    if "ToolCall" in part_type:
                        tool_calls_info.append({
                            "tool_name": getattr(part, "tool_name", "unknown"),
                            "tool_call_id": getattr(part, "tool_call_id", ""),
                        })
                    elif "ToolReturn" in part_type:
                        # Match return to call by ID
                        call_id = getattr(part, "tool_call_id", "")
                        for tc in tool_calls_info:
                            if tc.get("tool_call_id") == call_id:
                                tc["success"] = True

            if tool_calls_info:
                _logger.info("Agent made %d tool call(s): %s",
                             len(tool_calls_info),
                             [tc["tool_name"] for tc in tool_calls_info])
            usage_out["tool_calls"] = tool_calls_info
        except Exception:
            _logger.debug("Failed to extract tool calls.", exc_info=True)

    @staticmethod
    def _extract_result_usage(
        result: object,
        agent: object,
    ) -> dict[str, Any]:
        """Extract token usage from a FireflyAgent result (run or reasoning).

        Returns a dict suitable for the USAGE SSE event payload, or an empty
        dict when usage data is not available.
        """
        try:
            # For reasoning results, usage is tracked on the underlying agent runs
            # and accumulated in the global UsageTracker.  However, we can also
            # check if the result itself has a usage() method (standard agent.run
            # results do).
            usage_fn = getattr(result, "usage", None)
            usage = usage_fn() if callable(usage_fn) else None
            if usage is None:
                return {}

            input_tokens = getattr(usage, "input_tokens", 0) or 0
            output_tokens = getattr(usage, "output_tokens", 0) or 0
            total_tokens = getattr(usage, "total_tokens", 0) or (input_tokens + output_tokens)

            model_name = getattr(agent, "_model_identifier", "unknown")

            cost_usd = 0.0
            try:
                from fireflyframework_genai.config import get_config
                from fireflyframework_genai.observability.cost import get_cost_calculator

                cfg = get_config()
                calculator = get_cost_calculator(cfg.cost_calculator)
                cost_usd = calculator.estimate(model_name, input_tokens, output_tokens)
            except Exception:
                _logger.debug("Cost estimation not available.", exc_info=True)

            return {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
                "cost_usd": round(cost_usd, 6),
                "model": model_name,
            }
        except Exception:
            _logger.debug("Failed to extract result usage.", exc_info=True)
            return {}

    @staticmethod
    def _build_tool_summaries(tools: list[ToolDefinition]) -> list[dict[str, str]]:
        """Convert tool definitions into summary dicts for the prompt."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "risk_level": tool.risk_level.value,
            }
            for tool in tools
        ]

    @staticmethod
    def _format_knowledge_context(enriched: object) -> str:
        """Format enriched context into a string for the system prompt.

        Accepts the ``EnrichedContext`` dataclass but typed as ``object``
        to avoid a circular-feeling tight coupling in the signature.
        """
        from flydesk.agent.context import EnrichedContext

        if not isinstance(enriched, EnrichedContext):
            return ""

        parts: list[str] = []

        if enriched.relevant_entities:
            entity_lines = [
                f"- {e.name} ({e.entity_type})" for e in enriched.relevant_entities
            ]
            parts.append("Entities:\n" + "\n".join(entity_lines))

        if enriched.knowledge_snippets:
            snippet_lines = [
                f"- [{s.document_title}]: {s.chunk.content}"
                for s in enriched.knowledge_snippets
            ]
            parts.append("Knowledge:\n" + "\n".join(snippet_lines))

        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Module-level multimodal helpers
# ---------------------------------------------------------------------------

_IMAGE_CONTENT_TYPES = frozenset({
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
})


async def _build_multimodal_parts(
    uploads: list[FileUpload],
    storage: FileStorageProvider,
) -> list:
    """Build multimodal content parts from file uploads.

    - Images -> :class:`BinaryContent` (for multimodal LLMs)
    - Text/docs with ``extracted_text`` -> string context
    """
    from fireflyframework_genai.types import BinaryContent

    parts: list = []
    for upload in uploads:
        if upload.content_type in _IMAGE_CONTENT_TYPES:
            raw = await storage.retrieve(upload.storage_path)
            parts.append(BinaryContent(data=raw, media_type=upload.content_type))
        elif upload.extracted_text:
            parts.append(f"[{upload.filename}]: {upload.extracted_text}")
    return parts
