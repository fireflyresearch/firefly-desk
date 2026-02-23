# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Chat API with SSE streaming."""

from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from flydesk.api.events import SSEEvent, SSEEventType

router = APIRouter(prefix="/api/chat", tags=["chat"])

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    """Incoming chat message."""

    message: str
    conversation_id: str | None = None
    file_ids: list[str] = Field(default_factory=list)


class SuggestionItem(BaseModel):
    """A single chat suggestion chip."""

    icon: str
    title: str
    description: str
    text: str


class SuggestionsResponse(BaseModel):
    """Response payload for the suggestions endpoint."""

    suggestions: list[SuggestionItem]


# ---------------------------------------------------------------------------
# Default suggestion sets by role
# ---------------------------------------------------------------------------

_ADMIN_SUGGESTIONS: list[dict[str, str]] = [
    {
        "icon": "heart-pulse",
        "title": "System Health",
        "description": "Review current status of all systems",
        "text": "Review system health",
    },
    {
        "icon": "shield",
        "title": "Audit Events",
        "description": "Check recent security and activity logs",
        "text": "Check recent audit events",
    },
    {
        "icon": "settings",
        "title": "LLM Configuration",
        "description": "Manage AI model providers",
        "text": "Manage LLM providers",
    },
    {
        "icon": "activity",
        "title": "Active Sessions",
        "description": "Monitor current agent activity",
        "text": "Show active agent sessions",
    },
    {
        "icon": "cpu",
        "title": "Resources",
        "description": "Check running resources and usage",
        "text": "What resources are running?",
    },
    {
        "icon": "help-circle",
        "title": "Capabilities",
        "description": "Learn what I can do for you",
        "text": "What can you help me with?",
    },
]

_DEFAULT_SUGGESTIONS: list[dict[str, str]] = [
    {
        "icon": "search",
        "title": "Explore Systems",
        "description": "View all registered systems and services",
        "text": "Show me all registered systems",
    },
    {
        "icon": "activity",
        "title": "Service Status",
        "description": "Check the health of your services",
        "text": "What is the status of all services?",
    },
    {
        "icon": "book-open",
        "title": "Knowledge Base",
        "description": "Search organizational knowledge",
        "text": "How does the knowledge base work?",
    },
    {
        "icon": "help-circle",
        "title": "Get Help",
        "description": "Learn what I can do for you",
        "text": "What can you help me with?",
    },
]


@router.get("/suggestions", response_model=SuggestionsResponse)
async def get_suggestions(request: Request) -> SuggestionsResponse:
    """Return role-based suggestions for the chat empty state."""
    user_session = getattr(request.state, "user_session", None)
    roles: list[str] = list(user_session.roles) if user_session and hasattr(user_session, "roles") else []

    if "admin" in roles:
        items = _ADMIN_SUGGESTIONS
    else:
        items = _DEFAULT_SUGGESTIONS

    return SuggestionsResponse(
        suggestions=[SuggestionItem(**s) for s in items],
    )


async def _persist_messages(
    request: Request,
    conversation_id: str,
    user_message: str,
    assistant_content: str,
    file_ids: list[str] | None = None,
) -> None:
    """Persist user and assistant messages to the conversation store.

    This is non-fatal -- any error is logged but does not interrupt the chat flow.
    """
    try:
        from flydesk.conversation.models import Conversation, Message, MessageRole
        from flydesk.conversation.repository import ConversationRepository

        repo: ConversationRepository | None = getattr(
            request.app.state, "conversation_repo", None
        )
        if repo is None:
            return

        user_session = getattr(request.state, "user_session", None)
        user_id = user_session.user_id if user_session else "anonymous"

        # Auto-create conversation if it doesn't exist
        existing = await repo.get_conversation(conversation_id, user_id)
        if existing is None:
            title = user_message[:60].strip()
            if len(user_message) > 60:
                title = title.rsplit(" ", 1)[0] + "..."
            conversation = Conversation(
                id=conversation_id,
                title=title,
                user_id=user_id,
            )
            await repo.create_conversation(conversation)

        # Persist user message (file_ids embedded into metadata by the repository)
        await repo.add_message(
            Message(
                id=str(uuid.uuid4()),
                conversation_id=conversation_id,
                role=MessageRole.USER,
                content=user_message,
                file_ids=file_ids or [],
            ),
            user_id,
        )

        # Persist assistant message
        if assistant_content:
            await repo.add_message(
                Message(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=assistant_content,
                ),
                user_id,
            )
    except Exception:
        logger.debug("Message persistence failed (non-fatal).", exc_info=True)


async def _handle_confirmation(
    request: Request,
    body: ChatMessage,
    conversation_id: str,
    confirmation_service: object,
    user_session: object,
) -> StreamingResponse:
    """Handle __confirm__:<id> and __reject__:<id> messages.

    On approve: execute the pending tool call via the ToolExecutor and stream
    the results back.  On reject: emit a token message explaining what was
    skipped.
    """
    from flydesk.agent.confirmation import ConfirmationService

    svc: ConfirmationService = confirmation_service  # type: ignore[assignment]
    msg = body.message

    is_approve = msg.startswith("__confirm__:")
    confirmation_id = msg.split(":", 1)[1] if ":" in msg else ""

    if is_approve:
        pending = svc.approve(confirmation_id)
    else:
        pending = svc.reject(confirmation_id)

    async def confirmation_stream():
        if pending is None:
            text = (
                "The confirmation has expired or was not found. "
                "Please retry the original request."
            )
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={"content": text},
            ).to_sse()
            yield SSEEvent(
                event=SSEEventType.DONE,
                data={"conversation_id": conversation_id},
            ).to_sse()

            await _persist_messages(request, conversation_id, msg, text)
            return

        if not is_approve:
            text = f"Tool '{pending.tool_call.tool_name}' was rejected and will not be executed."
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={"content": text},
            ).to_sse()
            yield SSEEvent(
                event=SSEEventType.DONE,
                data={"conversation_id": conversation_id},
            ).to_sse()

            await _persist_messages(request, conversation_id, msg, text)
            return

        # Approved -- execute the pending tool call.
        desk_agent = getattr(request.app.state, "desk_agent", None)
        if desk_agent is None or desk_agent._tool_executor is None:
            text = "Tool execution is not available."
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={"content": text},
            ).to_sse()
            yield SSEEvent(
                event=SSEEventType.DONE,
                data={"conversation_id": conversation_id},
            ).to_sse()

            await _persist_messages(request, conversation_id, msg, text)
            return

        # Stream tool execution events directly (bypasses confirmation check).
        collected: list[str] = []

        yield SSEEvent(
            event=SSEEventType.TOOL_START,
            data={
                "tool_call_id": pending.tool_call.call_id,
                "tool_name": pending.tool_call.tool_name,
            },
        ).to_sse()

        results = await desk_agent._tool_executor.execute_parallel(
            [pending.tool_call], user_session, conversation_id,
        )

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
            ).to_sse()

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
        ).to_sse()

        # Emit a summary token for the user.
        for result in results:
            if result.success:
                text = f"Tool '{result.tool_name}' executed successfully."
            else:
                text = f"Tool '{result.tool_name}' failed: {result.error}"
            collected.append(text)
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={"content": text},
            ).to_sse()

        yield SSEEvent(
            event=SSEEventType.DONE,
            data={"conversation_id": conversation_id},
        ).to_sse()

        await _persist_messages(
            request, conversation_id, msg, "".join(collected),
        )

    return StreamingResponse(
        confirmation_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/conversations/{conversation_id}/send")
async def send_message(
    conversation_id: str,
    body: ChatMessage,
    request: Request,
) -> StreamingResponse:
    """Send a message and receive an SSE stream of responses."""

    desk_agent = getattr(request.app.state, "desk_agent", None)
    user_session = getattr(request.state, "user_session", None)

    # Setup init messages are no longer handled via chat.
    if body.message == "__setup_init__":
        async def setup_redirect_stream():
            yield SSEEvent(
                event=SSEEventType.TOKEN,
                data={"content": "Setup is handled via the setup wizard. Please visit /setup to configure Firefly Desk."},
            ).to_sse()
            yield SSEEvent(
                event=SSEEventType.DONE,
                data={"conversation_id": conversation_id},
            ).to_sse()

        return StreamingResponse(
            setup_redirect_stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
        )

    # Ownership guard: reject if conversation belongs to another user.
    # Skipped for setup-init messages (handled above) so that new setup
    # conversations can be created freely.
    from flydesk.conversation.repository import ConversationRepository

    user_id = user_session.user_id if user_session else "anonymous"
    repo: ConversationRepository | None = getattr(
        request.app.state, "conversation_repo", None
    )
    if repo:
        owned = await repo.get_conversation(conversation_id, user_id)
        if owned is None:
            exists = await repo.conversation_exists(conversation_id)
            if exists:
                raise HTTPException(
                    status_code=404, detail="Conversation not found"
                )
        # If owned is not None → user owns it, proceed.
        # If owned is None and exists is False → new conversation, proceed.

    # Handle confirmation responses (__confirm__:<id> or __reject__:<id>)
    confirmation_service = getattr(request.app.state, "confirmation_service", None)
    if confirmation_service and body.message.startswith(("__confirm__:", "__reject__:")):
        return await _handle_confirmation(
            request, body, conversation_id, confirmation_service, user_session,
        )

    if desk_agent and user_session:
        async def agent_stream():
            collected: list[str] = []
            async for event in desk_agent.stream(
                body.message, user_session, conversation_id,
                file_ids=body.file_ids or None,
            ):
                # Collect token content for persistence
                if event.event == SSEEventType.TOKEN and isinstance(event.data, dict):
                    token = event.data.get("content", "")
                    if token:
                        collected.append(token)
                yield event.to_sse()

            # Persist after stream completes
            await _persist_messages(
                request, conversation_id, body.message, "".join(collected),
                file_ids=body.file_ids or None,
            )

        return StreamingResponse(
            agent_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Fallback echo for tests and environments without DeskAgent
    async def event_stream():
        collected: list[str] = []

        token1 = f"Processing your message in conversation {conversation_id}..."
        collected.append(token1)
        yield SSEEvent(
            event=SSEEventType.TOKEN,
            data={"content": token1},
        ).to_sse()

        collected.append(body.message)
        yield SSEEvent(
            event=SSEEventType.TOKEN,
            data={"content": body.message},
        ).to_sse()

        yield SSEEvent(
            event=SSEEventType.DONE,
            data={"conversation_id": conversation_id},
        ).to_sse()

        # Persist after stream completes
        await _persist_messages(
            request, conversation_id, body.message, "".join(collected),
            file_ids=body.file_ids or None,
        )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
