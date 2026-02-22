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

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from flydek.api.events import SSEEvent, SSEEventType

router = APIRouter(prefix="/api/chat", tags=["chat"])

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    """Incoming chat message."""

    message: str
    conversation_id: str | None = None
    file_ids: list[str] = Field(default_factory=list)


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
        from flydek.conversation.models import Conversation, Message, MessageRole
        from flydek.conversation.repository import ConversationRepository

        repo: ConversationRepository | None = getattr(
            request.app.state, "conversation_repo", None
        )
        if repo is None:
            return

        user_session = getattr(request.state, "user_session", None)
        user_id = user_session.user_id if user_session else "anonymous"

        # Auto-create conversation if it doesn't exist
        existing = await repo.get_conversation(conversation_id)
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
            )
        )

        # Persist assistant message
        if assistant_content:
            await repo.add_message(
                Message(
                    id=str(uuid.uuid4()),
                    conversation_id=conversation_id,
                    role=MessageRole.ASSISTANT,
                    content=assistant_content,
                )
            )
    except Exception:
        logger.debug("Message persistence failed (non-fatal).", exc_info=True)


@router.post("/conversations/{conversation_id}/send")
async def send_message(
    conversation_id: str,
    body: ChatMessage,
    request: Request,
) -> StreamingResponse:
    """Send a message and receive an SSE stream of responses."""

    desk_agent = getattr(request.app.state, "desk_agent", None)
    user_session = getattr(request.state, "user_session", None)

    # Check for setup conversation handler
    setup_handlers = getattr(request.app.state, "setup_handlers", {})
    is_setup_init = body.message == "__setup_init__"
    has_active_setup = conversation_id in setup_handlers

    if is_setup_init or has_active_setup:
        from flydek.agent.setup_handler import SetupConversationHandler

        if is_setup_init and conversation_id not in setup_handlers:
            handler = SetupConversationHandler(request.app)
            setup_handlers[conversation_id] = handler
            if not hasattr(request.app.state, "setup_handlers"):
                request.app.state.setup_handlers = {}
            request.app.state.setup_handlers[conversation_id] = handler
        else:
            handler = setup_handlers[conversation_id]

        async def setup_stream():
            async for event in handler.handle(body.message):
                yield event.to_sse()

        return StreamingResponse(
            setup_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
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
