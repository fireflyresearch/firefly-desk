# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""DeskAgent -- the conversational super-agent that orchestrates the full agent lifecycle."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

from flydesk.agent.confirmation import ConfirmationService
from flydesk.agent.context import ContextEnricher
from flydesk.agent.prompt import PromptContext, SystemPromptBuilder
from flydesk.agent.response import AgentResponse
from flydesk.api.events import SSEEvent, SSEEventType
from flydesk.audit.logger import AuditLogger
from flydesk.audit.models import AuditEvent, AuditEventType
from flydesk.auth.models import UserSession
from flydesk.tools.builtin import BuiltinToolExecutor, BuiltinToolRegistry
from flydesk.tools.factory import ToolDefinition, ToolFactory
from flydesk.widgets.parser import WidgetParser

if TYPE_CHECKING:
    from flydesk.agent.genai_bridge import DeskAgentFactory
    from flydesk.catalog.repository import CatalogRepository
    from flydesk.conversation.repository import ConversationRepository
    from flydesk.files.repository import FileUploadRepository
    from flydesk.tools.executor import ToolCall, ToolExecutor, ToolResult

_logger = logging.getLogger(__name__)

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
        builtin_executor: BuiltinToolExecutor | None = None,
        file_repo: FileUploadRepository | None = None,
        confirmation_service: ConfirmationService | None = None,
        conversation_repo: ConversationRepository | None = None,
        agent_factory: DeskAgentFactory | None = None,
        catalog_repo: CatalogRepository | None = None,
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
        self._confirmation_service = confirmation_service
        self._conversation_repo = conversation_repo
        self._agent_factory = agent_factory
        self._catalog_repo = catalog_repo

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
        tools, system_prompt = await self._prepare_turn(
            message, session, conversation_id, tools, file_ids,
        )

        # 3. LLM execution
        raw_text = await self._call_llm(message, system_prompt, conversation_id)

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
        tools, system_prompt = await self._prepare_turn(
            message, session, conversation_id, tools, file_ids,
        )

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

        # Stream tokens from the LLM (real streaming or chunked fallback)
        full_text = ""
        async for token in self._stream_llm(message, system_prompt, conversation_id):
            full_text += token
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={"content": token},
            )

        # Post-processing: parse widget directives from full response
        parse_result = self._widget_parser.parse(full_text)

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

        # Audit logging
        clean_text = "\n\n".join(parse_result.text_segments)
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
            },
        )
        await self._audit_logger.log(audit_event)

        # Emit TOOL_SUMMARY (no tool calls executed in this flow, but
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
                "conversation_id": conversation_id,
                "turn_id": turn_id,
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

    async def _build_file_context(self, file_ids: list[str] | None) -> str:
        """Fetch uploaded files by ID and concatenate their extracted text.

        Returns an empty string when no file IDs are provided or the file
        repository is not configured.
        """
        if not file_ids or self._file_repo is None:
            return ""

        parts: list[str] = []
        for file_id in file_ids:
            upload = await self._file_repo.get(file_id)
            if upload is None:
                continue
            text = upload.extracted_text or ""
            if text:
                parts.append(f"- [{upload.filename}]: {text}")
        return "\n".join(parts)

    async def _prepare_turn(
        self,
        message: str,
        session: UserSession,
        conversation_id: str,
        tools: list[ToolDefinition] | None,
        file_ids: list[str] | None,
    ) -> tuple[list[ToolDefinition], str]:
        """Shared context enrichment + prompt building for run() and stream().

        Returns:
            A tuple of (resolved_tools, system_prompt).
        """
        # 0. Auto-load tools from catalog + built-ins if not provided
        if tools is None:
            tools = []
            # Catalog-derived tools (external system endpoints)
            if self._catalog_repo is not None:
                try:
                    endpoints = await self._catalog_repo.list_endpoints()
                    tools = self._tool_factory.build_tool_definitions(
                        endpoints, list(session.permissions),
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

        # 1. Context enrichment (with user-scoped conversation history)
        history = await self._load_conversation_history(
            conversation_id, session.user_id,
        )
        enriched = await self._context_enricher.enrich(
            message, conversation_history=history,
        )

        # 2. Prompt assembly
        tool_summaries = self._build_tool_summaries(tools or [])
        knowledge_context = self._format_knowledge_context(enriched)
        file_context = await self._build_file_context(file_ids)
        conversation_summary = self._format_conversation_history(
            enriched.conversation_history,
        )

        prompt_context = PromptContext(
            agent_name=self._agent_name,
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
        )
        system_prompt = self._prompt_builder.build(prompt_context)

        return tools, system_prompt

    async def _stream_llm(
        self,
        message: str,
        system_prompt: str,
        conversation_id: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Stream tokens from the LLM via FireflyAgent.run_stream().

        When no agent factory is configured or the agent cannot be created,
        falls back to yielding the echo response in fixed-size chunks.

        Args:
            message: The user message.
            system_prompt: The assembled system prompt.
            conversation_id: Conversation ID for MemoryManager auto-injection.

        Yields:
            Individual token strings as they arrive from the model.
        """
        if self._agent_factory is None:
            for chunk in self._echo_fallback_chunks(message):
                yield chunk
            return

        agent = await self._agent_factory.create_agent(system_prompt)
        if agent is None:
            for chunk in self._echo_fallback_chunks(message):
                yield chunk
            return

        try:
            async with await agent.run_stream(
                message,
                streaming_mode="incremental",
                conversation_id=conversation_id,
            ) as stream:
                async for token in stream.stream_tokens():
                    yield token
        except Exception as exc:
            _logger.error("LLM streaming failed: %s", exc, exc_info=True)
            error_text = (
                "I'm sorry, I encountered an error connecting to the language model. "
                "Please check your LLM provider configuration in Admin > LLM Providers.\n\n"
                f"Error: {exc}"
            )
            yield error_text

    async def _call_llm(
        self,
        message: str,
        system_prompt: str,
        conversation_id: str | None = None,
    ) -> str:
        """Call the LLM via FireflyAgent.

        Args:
            message: The user message.
            system_prompt: The assembled system prompt.
            conversation_id: Conversation ID for MemoryManager auto-injection.
        """
        if self._agent_factory is None:
            return self._echo_fallback(message)

        agent = await self._agent_factory.create_agent(system_prompt)
        if agent is None:
            return self._echo_fallback(message)

        try:
            result = await agent.run(message, conversation_id=conversation_id)
            return str(result.output)
        except Exception as exc:
            _logger.error("LLM call failed: %s", exc, exc_info=True)
            return (
                "I'm sorry, I encountered an error connecting to the language model. "
                "Please check your LLM provider configuration in Admin > LLM Providers.\n\n"
                f"Error: {exc}"
            )

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
