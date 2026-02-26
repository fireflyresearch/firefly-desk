# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Conversations REST API -- CRUD for conversations and messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from flydesk.api.deps import get_conversation_repo
from flydesk.conversation.models import Conversation, ConversationWithMessages, Message
from flydesk.conversation.repository import ConversationRepository

router = APIRouter(prefix="/api/conversations", tags=["conversations"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

Repo = Annotated[ConversationRepository, Depends(get_conversation_repo)]


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class CreateConversationRequest(BaseModel):
    """Body for creating a new conversation."""

    title: str | None = None
    model_id: str | None = None
    metadata: dict = {}


class UpdateConversationRequest(BaseModel):
    """Body for updating a conversation."""

    title: str | None = None
    metadata: dict | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("")
async def list_conversations(request: Request, repo: Repo) -> list[Conversation]:
    """List the authenticated user's conversations."""
    user_session = getattr(request.state, "user_session", None)
    user_id = user_session.user_id if user_session else "anonymous"
    return await repo.list_conversations(user_id)


@router.post("", status_code=201)
async def create_conversation(
    request: Request, body: CreateConversationRequest, repo: Repo
) -> Conversation:
    """Create a new conversation."""
    user_session = getattr(request.state, "user_session", None)
    user_id = user_session.user_id if user_session else "anonymous"

    now = datetime.now(timezone.utc)
    conversation = Conversation(
        id=str(uuid.uuid4()),
        title=body.title,
        user_id=user_id,
        model_id=body.model_id,
        metadata=body.metadata,
        created_at=now,
        updated_at=now,
    )
    await repo.create_conversation(conversation)
    return conversation


@router.get("/{conversation_id}")
async def get_conversation(
    conversation_id: str, request: Request, repo: Repo
) -> ConversationWithMessages:
    """Get a conversation with its messages."""
    user_session = getattr(request.state, "user_session", None)
    user_id = user_session.user_id if user_session else "anonymous"

    conversation = await repo.get_conversation(conversation_id, user_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

    messages = await repo.get_messages(conversation_id, user_id)
    return ConversationWithMessages(
        **conversation.model_dump(),
        messages=messages,
    )


@router.patch("/{conversation_id}")
async def update_conversation(
    conversation_id: str, body: UpdateConversationRequest, request: Request, repo: Repo
) -> Conversation:
    """Update a conversation's title or metadata."""
    user_session = getattr(request.state, "user_session", None)
    user_id = user_session.user_id if user_session else "anonymous"

    conversation = await repo.get_conversation(conversation_id, user_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

    if body.title is not None:
        conversation.title = body.title
    if body.metadata is not None:
        conversation.metadata = body.metadata

    await repo.update_conversation(conversation, user_id)
    return conversation


@router.delete("/{conversation_id}", status_code=204)
async def delete_conversation(
    conversation_id: str, request: Request, repo: Repo
) -> Response:
    """Soft-delete a conversation."""
    user_session = getattr(request.state, "user_session", None)
    user_id = user_session.user_id if user_session else "anonymous"

    conversation = await repo.get_conversation(conversation_id, user_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

    await repo.delete_conversation(conversation_id, user_id)
    return Response(status_code=204)


@router.get("/{conversation_id}/messages")
async def list_messages(
    conversation_id: str, request: Request, repo: Repo, limit: int = 100
) -> list[Message]:
    """Get paginated messages for a conversation."""
    user_session = getattr(request.state, "user_session", None)
    user_id = user_session.user_id if user_session else "anonymous"

    conversation = await repo.get_conversation(conversation_id, user_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail=f"Conversation {conversation_id} not found")

    return await repo.get_messages(conversation_id, user_id, limit=limit)
