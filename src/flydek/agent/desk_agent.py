# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""DeskAgent -- the conversational super-agent that orchestrates the full agent lifecycle."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from flydek.agent.context import ContextEnricher
from flydek.agent.prompt import PromptContext, SystemPromptBuilder
from flydek.agent.response import AgentResponse
from flydek.api.events import SSEEvent, SSEEventType
from flydek.audit.logger import AuditLogger
from flydek.audit.models import AuditEvent, AuditEventType
from flydek.auth.models import UserSession
from flydek.tools.factory import ToolDefinition, ToolFactory
from flydek.widgets.parser import WidgetParser

if TYPE_CHECKING:
    from flydek.tools.executor import ToolCall, ToolExecutor, ToolResult

# Token chunk size for simulated streaming (number of characters per token event).
_STREAM_CHUNK_SIZE = 20


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
    ) -> None:
        self._context_enricher = context_enricher
        self._prompt_builder = prompt_builder
        self._tool_factory = tool_factory
        self._widget_parser = widget_parser
        self._audit_logger = audit_logger
        self._agent_name = agent_name
        self._company_name = company_name
        self._tool_executor = tool_executor

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def run(
        self,
        message: str,
        session: UserSession,
        conversation_id: str,
        tools: list[ToolDefinition] | None = None,
    ) -> AgentResponse:
        """Execute a full agent turn.

        1. Enrich context (knowledge graph + RAG in parallel)
        2. Build system prompt
        3. Execute LLM (placeholder: echo message for now)
        4. Parse widgets from response
        5. Log audit event
        6. Return AgentResponse
        """
        turn_id = str(uuid.uuid4())

        # 1. Context enrichment
        enriched = await self._context_enricher.enrich(message)

        # 2. Prompt assembly
        tool_summaries = self._build_tool_summaries(tools or [])
        knowledge_context = self._format_knowledge_context(enriched)

        prompt_context = PromptContext(
            agent_name=self._agent_name,
            company_name=self._company_name,
            user_name=session.display_name,
            user_roles=list(session.roles),
            user_permissions=list(session.permissions),
            tool_summaries=tool_summaries,
            knowledge_context=knowledge_context,
        )
        _system_prompt = self._prompt_builder.build(prompt_context)

        # 3. LLM execution (placeholder -- will integrate FireflyAgent later)
        raw_text = self._placeholder_llm(message, _system_prompt)

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
    ) -> AsyncGenerator[SSEEvent, None]:
        """Stream SSE events for a full agent turn.

        Yields:
            SSEEventType.TOOL_START before context enrichment.
            SSEEventType.TOOL_END after context enrichment completes.
            SSEEventType.TOKEN events for text chunks.
            SSEEventType.WIDGET events for each parsed widget.
            SSEEventType.DONE when complete.
        """
        # Emit TOOL_START before context enrichment / LLM execution
        tool_call_id = str(uuid.uuid4())
        yield SSEEvent(
            event=SSEEventType.TOOL_START,
            data={
                "tool_call_id": tool_call_id,
                "tool_name": "knowledge_retrieval",
            },
        )

        start = time.monotonic()
        response = await self.run(message, session, conversation_id, tools=tools)
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

        # Stream text as token events (chunked)
        text = response.text
        for i in range(0, len(text), _STREAM_CHUNK_SIZE):
            chunk = text[i : i + _STREAM_CHUNK_SIZE]
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={"content": chunk},
            )

        # Emit widget events
        for widget in response.widgets:
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

        # Emit TOOL_SUMMARY (no tool calls executed in placeholder flow, but
        # the event is always emitted so the frontend can rely on its presence).
        yield SSEEvent(
            event=SSEEventType.TOOL_SUMMARY,
            data={
                "tool_calls": [],
                "total_duration_ms": 0,
                "success_count": 0,
                "failure_count": 0,
            },
        )

        # Final done event
        yield SSEEvent(
            event=SSEEventType.DONE,
            data={
                "conversation_id": response.conversation_id,
                "turn_id": response.turn_id,
            },
        )

    # ------------------------------------------------------------------
    # Tool execution infrastructure
    # ------------------------------------------------------------------

    async def _execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
        session: UserSession,
        conversation_id: str,
    ) -> AsyncGenerator[SSEEvent, None]:
        """Execute tool calls and yield SSE events for each.

        For every tool call:
        1. Emit ``TOOL_START`` with the call metadata.
        2. Execute via :class:`ToolExecutor` (parallel when possible).
        3. Emit ``TOOL_END`` per completed call with result summary.
        4. Emit ``TOOL_SUMMARY`` with aggregated results for the batch.

        Requires ``self._tool_executor`` to be set; raises
        :class:`RuntimeError` otherwise.
        """
        if self._tool_executor is None:
            msg = "ToolExecutor is not configured"
            raise RuntimeError(msg)

        # Emit TOOL_START for each call.
        for call in tool_calls:
            yield SSEEvent(
                event=SSEEventType.TOOL_START,
                data={
                    "tool_call_id": call.call_id,
                    "tool_name": call.tool_name,
                },
            )

        # Execute with automatic parallelism classification.
        results: list[ToolResult] = await self._tool_executor.execute_parallel(
            tool_calls, session, conversation_id,
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

    @staticmethod
    def _placeholder_llm(message: str, system_prompt: str) -> str:
        """Placeholder LLM that echoes the user message.

        This will be replaced with a real ``FireflyAgent`` call once the
        GenAI framework integration is wired up.
        """
        return (
            f"I received your message: {message}\n\n"
            f"(System prompt length: {len(system_prompt)} chars)"
        )

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
        from flydek.agent.context import EnrichedContext

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
