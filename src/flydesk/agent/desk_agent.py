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
from flydesk.agent.prompt import PromptContext, SystemPromptBuilder, truncate_to_token_budget
from flydesk.agent.response import AgentResponse
from flydesk.api.events import SSEEvent, SSEEventType
from flydesk.audit.logger import AuditLogger
from flydesk.audit.models import AuditEvent, AuditEventType
from flydesk.auth.models import UserSession
from flydesk.rbac.permissions import is_admin
from flydesk.tools.builtin import BuiltinToolExecutor, BuiltinToolRegistry
from flydesk.tools.factory import ToolDefinition, ToolFactory
from flydesk.settings.models import KNOWLEDGE_SNIPPET_MAX_CHARS, LLMRuntimeSettings
from flydesk.tools.genai_adapter import ToolTimingTracker, adapt_tools
from flydesk.widgets.parser import WidgetParser

if TYPE_CHECKING:
    from flydesk.agent.customization import AgentCustomizationService
    from flydesk.agent.genai_bridge import DeskAgentFactory
    from flydesk.agent.router.router import ModelRouter
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

# Reasoning-pattern step limits.
_REACT_MAX_STEPS = 5
_PLAN_AND_EXECUTE_MAX_STEPS = 8

# Conversation-history formatting limits.
_HISTORY_WINDOW_SIZE = 10  # number of recent messages to include
_HISTORY_MSG_CHAR_CAP = 200  # per-message content truncation

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


def _truncate_message_history(
    messages: list,
    *,
    max_chars: int = LLMRuntimeSettings.model_fields["followup_max_content_chars"].default,
    max_total_chars: int = LLMRuntimeSettings.model_fields["followup_max_total_chars"].default,
) -> None:
    """Truncate large text content in message history in-place.

    This prevents the follow-up LLM call from sending enormous tool results
    that would exceed token limits or trigger rate-limit errors.  Applies
    both per-part limits and a total budget across all parts.
    """
    import json as _json

    total_chars = 0

    for msg in messages:
        parts = getattr(msg, "parts", None)
        if not parts:
            continue
        for part in parts:
            kind = getattr(part, "part_kind", "")
            if kind == "tool-return":
                content = part.content
                if isinstance(content, str):
                    text = content
                elif content is not None:
                    try:
                        text = _json.dumps(content, default=str, ensure_ascii=False)
                    except Exception:
                        continue
                else:
                    continue
                # Per-part limit
                remaining = max(max_total_chars - total_chars, 500)
                effective_limit = min(max_chars, remaining)
                if len(text) > effective_limit:
                    part.content = text[:effective_limit] + "\n\n[... truncated]"
                    total_chars += effective_limit
                else:
                    total_chars += len(text)
            elif kind == "user-prompt":
                content = getattr(part, "content", None)
                user_limit = max_chars * 2
                remaining = max(max_total_chars - total_chars, 500)
                effective_limit = min(user_limit, remaining)
                if isinstance(content, str) and len(content) > effective_limit:
                    part.content = content[:effective_limit] + "\n\n[... truncated]"
                    total_chars += effective_limit
                elif isinstance(content, str):
                    total_chars += len(content)


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
        model_router: ModelRouter | None = None,
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
        self._model_router = model_router
        self._cached_llm_runtime: LLMRuntimeSettings | None = None

    # ------------------------------------------------------------------
    # LLM Runtime Settings
    # ------------------------------------------------------------------

    async def _get_llm_runtime(self) -> LLMRuntimeSettings:
        """Return cached LLM runtime settings, loading from DB on first call."""
        if self._cached_llm_runtime is not None:
            return self._cached_llm_runtime
        if self._settings_repo is not None:
            try:
                self._cached_llm_runtime = await self._settings_repo.get_llm_runtime_settings()
            except Exception:
                _logger.debug("Failed to load LLM runtime settings; using defaults.", exc_info=True)
                self._cached_llm_runtime = LLMRuntimeSettings()
        else:
            self._cached_llm_runtime = LLMRuntimeSettings()
        return self._cached_llm_runtime

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
        model_override, routing_decision = await self._route_model(message, adapted)
        usage_data: dict[str, Any] = {}
        t0 = time.monotonic()
        raw_text = await self._call_llm(
            message, system_prompt, conversation_id, tools=adapted,
            usage_out=usage_data, model_override=model_override,
        )
        latency_ms = round((time.monotonic() - t0) * 1000)

        # Attach routing metadata to usage data
        if routing_decision is not None:
            usage_data["routing"] = {
                "tier": routing_decision.tier.value if hasattr(routing_decision, 'tier') else str(routing_decision.tier),
                "confidence": routing_decision.confidence,
                "reasoning": routing_decision.reasoning,
                "model_used": routing_decision.model_string,
                "classifier_model": routing_decision.classifier_model,
                "classifier_latency_ms": routing_decision.classifier_latency_ms,
            }

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

        # Adapt catalog tools for genai tool-use (with timing tracker)
        timing_tracker = ToolTimingTracker()
        adapted = await self._adapt_tools(tools, session, conversation_id, timing_tracker=timing_tracker)

        # Route to cost-appropriate model
        model_override, routing_decision = await self._route_model(message, adapted)
        if routing_decision is not None:
            yield SSEEvent(
                event=SSEEventType.ROUTING,
                data={
                    "tier": routing_decision.tier.value,
                    "model": routing_decision.model_string,
                },
            )

        # Stream tokens from the LLM (real streaming or chunked fallback)
        full_text = ""
        usage_data: dict[str, Any] = {}
        t0 = time.monotonic()
        async for item in self._stream_llm(
            message, system_prompt, conversation_id, tools=adapted,
            usage_out=usage_data, model_override=model_override,
        ):
            if isinstance(item, SSEEvent):
                yield item
            else:
                full_text += item
                yield SSEEvent(
                    event=SSEEventType.TOKEN,
                    data={"content": item},
                )
        latency_ms = round((time.monotonic() - t0) * 1000)

        # Attach routing metadata to usage data
        if routing_decision is not None:
            usage_data["routing"] = {
                "tier": routing_decision.tier.value if hasattr(routing_decision, 'tier') else str(routing_decision.tier),
                "confidence": routing_decision.confidence,
                "reasoning": routing_decision.reasoning,
                "model_used": routing_decision.model_string,
                "classifier_model": routing_decision.classifier_model,
                "classifier_latency_ms": routing_decision.classifier_latency_ms,
            }

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

        # Emit TOOL_SUMMARY with actual tool call data and real durations.
        agent_tool_calls = usage_data.pop("tool_calls", [])
        tool_timings = timing_tracker.get_timings()
        for tc in agent_tool_calls:
            tc["duration_ms"] = round(tool_timings.get(tc.get("tool_name", ""), 0), 1)
        total_dur = sum(tc.get("duration_ms", 0) for tc in agent_tool_calls)
        success_count = sum(1 for tc in agent_tool_calls if tc.get("success"))
        yield SSEEvent(
            event=SSEEventType.TOOL_SUMMARY,
            data={
                "tool_calls": agent_tool_calls,
                "total_duration_ms": round(total_dur, 1),
                "success_count": success_count,
                "failure_count": len(agent_tool_calls) - success_count,
            },
        )

        # Total wall-clock time for this message turn.
        total_time_ms = round((time.monotonic() - start) * 1000)

        # Emit USAGE event before DONE (if usage data was captured)
        if usage_data:
            usage_data["total_time_ms"] = total_time_ms
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
                "total_time_ms": total_time_ms,
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
        rt = await self._get_llm_runtime()
        usage_data: dict[str, Any] = {}
        t0 = time.monotonic()
        try:
            last_reasoning_exc: Exception | None = None
            result = None
            for attempt in range(rt.llm_max_retries):
                try:
                    result = await agent.run_with_reasoning(pattern_instance, message, conversation_id=conversation_id)
                    break  # Success
                except (_BudgetExceededError, _CircuitBreakerOpenError):
                    raise  # Let outer handlers deal with these
                except Exception as retry_exc:
                    last_reasoning_exc = retry_exc
                    if _is_transient_error(retry_exc) and attempt < rt.llm_max_retries - 1:
                        delay = min(
                            rt.llm_retry_base_delay * (2 ** attempt) + random.uniform(0, 1),
                            rt.llm_retry_max_delay,
                        )
                        _logger.warning(
                            "Transient LLM error in reasoning (attempt %d/%d), retrying in %.1fs: %s",
                            attempt + 1, rt.llm_max_retries, delay, retry_exc,
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
                return PlanAndExecutePattern(max_steps=_PLAN_AND_EXECUTE_MAX_STEPS)
            return ReActPattern(max_steps=_REACT_MAX_STEPS)

        match pattern_name:
            case "react":
                return ReActPattern(max_steps=_REACT_MAX_STEPS)
            case "plan_and_execute":
                return PlanAndExecutePattern(max_steps=_PLAN_AND_EXECUTE_MAX_STEPS)
            case "chain_of_thought":
                from fireflyframework_genai.reasoning import ChainOfThoughtPattern
                return ChainOfThoughtPattern(max_steps=_REACT_MAX_STEPS)
            case "reflexion":
                from fireflyframework_genai.reasoning import ReflexionPattern
                return ReflexionPattern(max_steps=_REACT_MAX_STEPS)
            case _:
                return ReActPattern(max_steps=_REACT_MAX_STEPS)

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
        for msg in history[-_HISTORY_WINDOW_SIZE:]:
            role = msg.get("role", "unknown").capitalize()
            content = msg.get("content", "")[:_HISTORY_MSG_CHAR_CAP]
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

        rt = await self._get_llm_runtime()
        uploads: list[FileUpload] = []
        parts: list[str] = []
        max_per_file = rt.file_context_max_per_file
        max_total = rt.file_context_max_total
        total_chars = 0
        for file_id in file_ids:
            upload = await self._file_repo.get(file_id)
            if upload is None:
                continue
            uploads.append(upload)
            text = upload.extracted_text or ""
            if text:
                remaining = max_total - total_chars
                if remaining <= 0:
                    parts.append(
                        f"- [{upload.filename}] (file_id={file_id}): [content omitted — total file "
                        "context budget reached; use document_read(file_id=\"" + file_id + "\") to access]"
                    )
                    continue
                limit = min(max_per_file, remaining)
                if len(text) > limit:
                    text = text[:limit]
                    text += (
                        "\n\n[... truncated — use document_read(file_id=\"" + file_id
                        + "\", page_start=N, page_end=M) to read specific sections]"
                    )
                total_chars += len(text)
                parts.append(f"- [{upload.filename}] (file_id={file_id}): {text}")

        text_context = "\n".join(parts)

        # Build multimodal parts when file storage is available.
        multimodal_parts: list = []
        if self._file_storage is not None and uploads:
            multimodal_parts = await _build_multimodal_parts(
                uploads, self._file_storage,
                max_context_chars=rt.multimodal_max_context_chars,
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

        # Build system context preambles for enriching the prompt
        system_contexts_text = ""
        if self._catalog_repo is not None and tools:
            try:
                system_contexts_text = await self._build_system_contexts(tools)
            except Exception:
                _logger.debug("Failed to build system contexts.", exc_info=True)

        # Resolve knowledge tag filter from access scopes (admin bypasses)
        knowledge_tag_filter: list[str] | None = None
        if not admin_user and scopes.knowledge_tags:
            knowledge_tag_filter = scopes.knowledge_tags

        # 1. Context enrichment (with user-scoped conversation history)
        rt = await self._get_llm_runtime()
        self._context_enricher._entity_limit = rt.context_entity_limit
        self._context_enricher._retrieval_top_k = rt.context_retrieval_top_k

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

        # Apply token budget to prevent oversized prompts.
        rt = await self._get_llm_runtime()
        knowledge_context = truncate_to_token_budget(
            knowledge_context, max_tokens=rt.max_knowledge_tokens,
        )

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

        # Check if email channel is enabled for email composing guidance.
        email_enabled = False
        if self._settings_repo is not None:
            try:
                _email_settings = await self._settings_repo.get_email_settings()
                email_enabled = _email_settings.enabled
            except Exception:
                _logger.debug("Failed to check email settings.", exc_info=True)

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
            email_enabled=email_enabled,
            system_contexts=system_contexts_text,
        )
        system_prompt = self._prompt_builder.build(prompt_context)

        return tools, system_prompt, multimodal_parts

    async def _adapt_tools(
        self,
        tools: list[ToolDefinition] | None,
        session: UserSession,
        conversation_id: str,
        timing_tracker: ToolTimingTracker | None = None,
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
            timing_tracker=timing_tracker,
        )

    async def _route_model(
        self,
        message: str,
        tools: list[object] | None,
    ) -> tuple[str | None, object | None]:
        """Determine which model to use via the router.

        Returns (model_override, routing_decision) or (None, None) if routing
        is disabled or fails.
        """
        if self._model_router is None:
            return None, None
        try:
            tool_names = []
            if tools:
                for t in tools:
                    name = getattr(t, "name", None) or getattr(t, "tool_name", "")
                    if name:
                        tool_names.append(name)
            decision = await self._model_router.route(
                message=message,
                tool_count=len(tools or []),
                tool_names=tool_names,
                turn_count=0,
            )
            if decision is not None:
                _logger.info(
                    "Router: tier=%s model=%s confidence=%.2f (%s)",
                    decision.tier, decision.model_string,
                    decision.confidence, decision.reasoning,
                )
                return decision.model_string, decision
        except Exception:
            _logger.debug("Model router failed; using default model.", exc_info=True)
        return None, None

    async def _stream_llm(
        self,
        message: str,
        system_prompt: str,
        conversation_id: str | None = None,
        tools: list[object] | None = None,
        usage_out: dict[str, Any] | None = None,
        model_override: str | None = None,
    ) -> AsyncGenerator[str | SSEEvent, None]:
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
            model_override: Optional model string from the router to use instead
                of the default model.

        Yields:
            Individual token strings as they arrive from the model.
        """
        if self._agent_factory is None:
            for chunk in self._echo_fallback_chunks(message):
                yield chunk
            return

        agent = await self._agent_factory.create_agent(
            system_prompt, tools=tools, model_override=model_override,
        )
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

        rt = await self._get_llm_runtime()

        # Propagate default_max_tokens to the agent factory.
        if self._agent_factory is not None:
            self._agent_factory._default_max_tokens = rt.default_max_tokens

        last_exc: Exception | None = None
        stream_ref: object | None = None
        for attempt in range(rt.llm_max_retries):
            try:
                async with asyncio.timeout(rt.llm_stream_timeout):
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
                        stream_ref = stream

                # pydantic-ai's run_stream only handles the first model turn.
                # If the model called tools, the follow-up response (with tool
                # results) was never generated.  Run the follow-up OUTSIDE the
                # stream timeout so its own retry/backoff logic has a full
                # time budget (important for rate-limit recovery).
                if stream_ref is not None:
                    async for token in self._follow_up_after_tool_calls(
                        stream_ref, agent, conversation_id, usage_out,
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
                _logger.warning("LLM streaming timed out after %ds", rt.llm_stream_timeout)
                yield (
                    "The language model took too long to respond. "
                    "Please try again or check your LLM provider configuration."
                )
                return
            except Exception as exc:
                last_exc = exc
                if _is_transient_error(exc):
                    if attempt < rt.llm_max_retries - 1:
                        delay = min(
                            rt.llm_retry_base_delay * (2 ** attempt) + random.uniform(0, 1),
                            rt.llm_retry_max_delay,
                        )
                        _logger.warning(
                            "Transient LLM error (attempt %d/%d), retrying in %.1fs: %s",
                            attempt + 1, rt.llm_max_retries, delay, exc,
                        )
                        await asyncio.sleep(delay)
                        continue
                    # Final attempt — fall through to fallback models below
                    _logger.warning(
                        "Primary model exhausted %d retries: %s", rt.llm_max_retries, exc,
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
                for fb_attempt in range(rt.llm_fallback_retries):
                    try:
                        fb_stream_ref: object | None = None
                        async with asyncio.timeout(rt.llm_stream_timeout):
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
                                fb_stream_ref = fb_stream

                        # Follow-up for tool calls OUTSIDE the stream
                        # context — fb_stream_ref was captured while
                        # the context was still open.
                        if fb_stream_ref is not None:
                            async for token in self._follow_up_after_tool_calls(
                                fb_stream_ref, fb_agent, conversation_id, usage_out,
                            ):
                                yield token

                        return  # Fallback succeeded
                    except Exception as fb_exc:
                        if _is_transient_error(fb_exc) and fb_attempt < rt.llm_fallback_retries - 1:
                            delay = rt.llm_retry_base_delay + random.uniform(0, 1)
                            _logger.warning(
                                "Fallback model %s also busy (attempt %d/%d), retrying in %.1fs",
                                fb_model, fb_attempt + 1, rt.llm_fallback_retries, delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                        _logger.warning("Fallback model %s failed: %s", fb_model, fb_exc)
                        break  # Try next fallback model

        # All retries and fallbacks exhausted
        if last_exc is not None:
            _logger.error("LLM streaming failed after %d retries + fallbacks: %s", rt.llm_max_retries, last_exc)
            yield _friendly_error_message(last_exc)

    async def _follow_up_after_tool_calls(
        self,
        stream: object,
        agent: object,
        conversation_id: str | None,
        usage_out: dict[str, Any] | None,
    ) -> AsyncGenerator[str | SSEEvent, None]:
        """Run follow-up LLM call(s) after tool execution with retry logic.

        pydantic-ai's ``run_stream()`` only handles a single model turn.
        When the model emits text + tool_call, the ``on_complete()`` callback
        executes the tools and appends results to the message history, but
        there is no second LLM call to produce the actual answer.

        This method:
        1. Detects tool calls in the stream
        2. Extracts message history and truncates large results
        3. Retries the follow-up with exponential backoff on transient errors
        4. ALWAYS emits the completion widget (100%) via try/finally
        """
        tool_calls = (usage_out or {}).get("tool_calls", [])
        if not tool_calls:
            return

        rt = await self._get_llm_runtime()

        _logger.info(
            "Stream had %d tool call(s); running follow-up with retry",
            len(tool_calls),
        )

        message_history = self._extract_message_history(stream)
        if message_history is None:
            return

        _truncate_message_history(
            message_history,
            max_chars=rt.followup_max_content_chars,
            max_total_chars=rt.followup_max_total_chars,
        )

        inner_agent = getattr(agent, "agent", agent)  # pydantic_ai.Agent
        widget_id = f"doc-progress-{conversation_id or 'none'}"

        # Emit initial progress widget.
        yield SSEEvent(
            event=SSEEventType.WIDGET,
            data={
                "widget_id": widget_id,
                "type": "progress-bar",
                "props": {
                    "label": "Processing...",
                    "value": 50,
                    "max": 100,
                    "variant": "default",
                },
                "display": "inline",
            },
        )

        prompt = (
            "Based on the tool results above, provide a complete answer to "
            "the user's request. If the user asked you to generate content "
            "and save it to the knowledge base, do both: generate the full "
            "content AND call add_knowledge to save it."
        )

        # ------------------------------------------------------------------
        # Retry loop with exponential backoff.
        #
        # NOTE: We must NOT yield inside the ``finally`` block.  In Python
        # 3.10+ a ``yield`` inside ``finally`` of an async generator raises
        # ``RuntimeError`` when the generator is closed externally (e.g. by
        # ``asyncio.timeout``).  Instead we compute the completion widget in
        # ``finally`` and yield it after the block exits.
        # ------------------------------------------------------------------
        output = ""
        succeeded = False
        last_exc: Exception | None = None
        completion_widget: SSEEvent | None = None

        try:
            for attempt in range(rt.followup_max_retries):
                try:
                    result = await asyncio.wait_for(
                        inner_agent.run(
                            prompt,
                            message_history=message_history,
                        ),
                        timeout=rt.llm_followup_timeout,
                    )

                    # Accumulate usage.
                    if usage_out is not None:
                        try:
                            ru = result.usage()
                            if ru:
                                usage_out["input_tokens"] = usage_out.get("input_tokens", 0) + (
                                    getattr(ru, "request_tokens", 0) or getattr(ru, "input_tokens", 0) or 0
                                )
                                usage_out["output_tokens"] = usage_out.get("output_tokens", 0) + (
                                    getattr(ru, "response_tokens", 0) or getattr(ru, "output_tokens", 0) or 0
                                )
                                usage_out["total_tokens"] = usage_out["input_tokens"] + usage_out["output_tokens"]
                        except Exception:
                            _logger.debug("Failed to extract follow-up usage.", exc_info=True)

                    # Extract text output.
                    if hasattr(result, "output"):
                        output = str(result.output) if result.output else ""
                    elif hasattr(result, "data"):
                        output = str(result.data) if result.data else ""

                    succeeded = True
                    _logger.info("Follow-up run() completed: %d chars of output", len(output))
                    break  # Success — exit retry loop

                except (TimeoutError, asyncio.TimeoutError) as exc:
                    last_exc = exc
                    _logger.warning(
                        "Follow-up timed out (attempt %d/%d) after %ds",
                        attempt + 1, rt.followup_max_retries, rt.llm_followup_timeout,
                    )
                    if attempt < rt.followup_max_retries - 1:
                        delay = min(
                            rt.followup_retry_base_delay * (2 ** attempt) + random.uniform(0, 2),
                            rt.followup_retry_max_delay,
                        )
                        _logger.info("Retrying follow-up in %.1fs", delay)
                        await asyncio.sleep(delay)
                        continue
                    break  # last attempt — exit loop explicitly

                except Exception as exc:
                    last_exc = exc
                    if _is_transient_error(exc) and attempt < rt.followup_max_retries - 1:
                        delay = min(
                            rt.followup_retry_base_delay * (2 ** attempt) + random.uniform(0, 2),
                            rt.followup_retry_max_delay,
                        )
                        _logger.warning(
                            "Transient follow-up error (attempt %d/%d), retrying in %.1fs: %s",
                            attempt + 1, rt.followup_max_retries, delay, exc,
                        )
                        await asyncio.sleep(delay)
                        continue

                    # Non-transient or final attempt — stop retrying
                    _logger.error("Follow-up run() failed: %s", exc, exc_info=True)
                    break

        finally:
            # Compute the completion widget inside ``finally`` so it is
            # always prepared — even on external cancellation.  We do NOT
            # yield here to avoid the RuntimeError described above.
            if succeeded:
                completion_widget = SSEEvent(
                    event=SSEEventType.WIDGET,
                    data={
                        "widget_id": widget_id,
                        "type": "progress-bar",
                        "props": {
                            "label": "Complete",
                            "value": 100,
                            "max": 100,
                            "variant": "default",
                        },
                        "display": "inline",
                    },
                )
            else:
                completion_widget = SSEEvent(
                    event=SSEEventType.WIDGET,
                    data={
                        "widget_id": widget_id,
                        "type": "progress-bar",
                        "props": {
                            "label": "Failed",
                            "value": 100,
                            "max": 100,
                            "variant": "error",
                        },
                        "display": "inline",
                    },
                )

        # Yield the completion widget AFTER the try/finally exits.
        if completion_widget is not None:
            yield completion_widget

        # Yield output or error message.
        if succeeded and output:
            yield "\n\n"
            yield output
        elif not succeeded:
            if isinstance(last_exc, (TimeoutError, asyncio.TimeoutError)):
                yield (
                    "\n\n*Processing timed out after multiple attempts. "
                    "The document may be too large for a single pass. "
                    "Try asking about a specific section.*"
                )
            else:
                yield (
                    "\n\nI encountered an error processing the document "
                    f"after {rt.followup_max_retries} attempts. "
                    "Try asking about a specific section or topic."
                )

    @staticmethod
    def _extract_message_history(stream: object) -> list | None:
        """Extract message history from a pydantic-ai stream or result."""
        try:
            inner = getattr(stream, "_stream", stream)
            all_messages = getattr(inner, "all_messages", None)
            if callable(all_messages):
                return all_messages()
            if isinstance(all_messages, (list, tuple)):
                return list(all_messages)
            _logger.warning("Cannot extract message history from stream; skipping follow-up.")
            return None
        except Exception:
            _logger.debug("Failed to extract message history for follow-up.", exc_info=True)
            return None

    async def _call_llm(
        self,
        message: str,
        system_prompt: str,
        conversation_id: str | None = None,
        tools: list[object] | None = None,
        usage_out: dict[str, Any] | None = None,
        model_override: str | None = None,
    ) -> str:
        """Call the LLM via FireflyAgent.

        Args:
            message: The user message.
            system_prompt: The assembled system prompt.
            conversation_id: Conversation ID for MemoryManager auto-injection.
            tools: Adapted genai tools for the FireflyAgent.
            usage_out: Optional mutable dict that will be populated with token
                usage data after the call completes.
            model_override: Optional model string from the router to use instead
                of the default model.
        """
        if self._agent_factory is None:
            return self._echo_fallback(message)

        rt = await self._get_llm_runtime()
        agent = await self._agent_factory.create_agent(
            system_prompt, tools=tools, model_override=model_override,
        )
        if agent is None:
            return self._echo_fallback(message)

        last_exc: Exception | None = None
        for attempt in range(rt.llm_max_retries):
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
                    if attempt < rt.llm_max_retries - 1:
                        delay = min(
                            rt.llm_retry_base_delay * (2 ** attempt) + random.uniform(0, 1),
                            rt.llm_retry_max_delay,
                        )
                        _logger.warning(
                            "Transient LLM error (attempt %d/%d), retrying in %.1fs: %s",
                            attempt + 1, rt.llm_max_retries, delay, exc,
                        )
                        await asyncio.sleep(delay)
                        continue
                    _logger.warning(
                        "Primary model exhausted %d retries: %s", rt.llm_max_retries, exc,
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
                for fb_attempt in range(rt.llm_fallback_retries):
                    try:
                        result = await fb_agent.run(message, conversation_id=conversation_id)
                        return str(result.output)
                    except Exception as fb_exc:
                        if _is_transient_error(fb_exc) and fb_attempt < rt.llm_fallback_retries - 1:
                            delay = rt.llm_retry_base_delay + random.uniform(0, 1)
                            _logger.warning(
                                "Fallback model %s also busy (attempt %d/%d), retrying in %.1fs",
                                fb_model, fb_attempt + 1, rt.llm_fallback_retries, delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                        _logger.warning("Fallback model %s failed: %s", fb_model, fb_exc)
                        break  # Try next fallback model

        # All retries and fallbacks exhausted
        _logger.error("LLM call failed after %d retries + fallbacks: %s", rt.llm_max_retries, last_exc)
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

    async def _build_system_contexts(self, tools: list[ToolDefinition]) -> str:
        """Build per-system context preambles for the agent prompt.

        Collects tags, linked documents, and system metadata for each
        system referenced by the active tools and formats them using
        :meth:`ToolFactory.build_system_context`.
        """
        # Determine which system IDs are in use
        system_ids = {t.system_id for t in tools if t.system_id}
        if not system_ids or self._catalog_repo is None:
            return ""

        # Fetch system objects, tags, and linked documents in bulk
        systems_list, _ = await self._catalog_repo.list_systems()
        systems_by_id = {s.id: s for s in systems_list if s.id in system_ids}
        if not systems_by_id:
            return ""

        all_tags = await self._catalog_repo.list_all_system_tags()
        all_docs_map = await self._catalog_repo.list_all_system_documents()

        # Resolve linked document IDs to KnowledgeDocument objects
        from flydesk.knowledge.models import KnowledgeDocument

        doc_ids_needed: set[str] = set()
        for sid in system_ids:
            for sd in all_docs_map.get(sid, []):
                doc_ids_needed.add(sd.document_id)

        kb_docs_by_id: dict[str, KnowledgeDocument] = {}
        if doc_ids_needed:
            docs = await self._catalog_repo.get_knowledge_documents_by_ids(list(doc_ids_needed))
            for doc in docs:
                kb_docs_by_id[doc.id] = doc

        # Build context for each system
        context_parts: list[str] = []
        for sid in sorted(systems_by_id):
            system = systems_by_id[sid]
            # Attach tags to system for context building
            system_with_tags = system.model_copy(update={"tags": all_tags.get(sid, [])})
            linked_docs = [
                kb_docs_by_id[sd.document_id]
                for sd in all_docs_map.get(sid, [])
                if sd.document_id in kb_docs_by_id
            ]
            ctx = ToolFactory.build_system_context(system_with_tags, linked_docs)
            context_parts.append(ctx)

        return "\n\n".join(context_parts)

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
            max_chunk = KNOWLEDGE_SNIPPET_MAX_CHARS
            snippet_lines = []
            for s in enriched.knowledge_snippets:
                content = s.chunk.content
                if len(content) > max_chunk:
                    content = content[:max_chunk] + " [... truncated]"
                snippet_lines.append(f"- [{s.document_title}]: {content}")
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
    *,
    max_context_chars: int = 12_000,
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
            text = upload.extracted_text
            if len(text) > max_context_chars:
                text = text[:max_context_chars]
                text += (
                    "\n\n[... truncated — use document_read(file_id=\"" + upload.id
                    + "\", page_start=N, page_end=M) to read specific sections]"
                )
            parts.append(f"[{upload.filename}] (file_id={upload.id}): {text}")
    return parts
