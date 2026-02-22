# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Chat API with SSE streaming."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from flydek.api.events import SSEEvent, SSEEventType

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatMessage(BaseModel):
    """Incoming chat message."""

    message: str
    conversation_id: str | None = None


@router.post("/conversations/{conversation_id}/send")
async def send_message(
    conversation_id: str,
    body: ChatMessage,
    request: Request,
) -> StreamingResponse:
    """Send a message and receive an SSE stream of responses."""

    async def event_stream():
        # Emit a token event to acknowledge receipt
        yield SSEEvent(
            event=SSEEventType.TOKEN,
            data={"content": f"Processing your message in conversation {conversation_id}..."},
        ).to_sse()

        # TODO: In production, this will wire into DeskAgent.run()
        # For now, emit a simple echo response as a placeholder
        yield SSEEvent(
            event=SSEEventType.TOKEN,
            data={"content": body.message},
        ).to_sse()

        # Signal completion
        yield SSEEvent(
            event=SSEEventType.DONE,
            data={"conversation_id": conversation_id},
        ).to_sse()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
