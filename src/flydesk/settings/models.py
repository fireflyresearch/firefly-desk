# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Pydantic domain models for user and application settings."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class UserSettings(BaseModel):
    """Per-user preferences stored as a JSON blob."""

    theme: str = "system"  # light, dark, system
    agent_verbose: bool = False
    sidebar_collapsed: bool = False
    notifications_enabled: bool = True
    default_model_id: str | None = None
    display_preferences: dict[str, Any] = Field(default_factory=dict)
    picture_url: str | None = None
    agent_personality: str | None = None
    agent_tone: str | None = None
    agent_greeting: str | None = None
    agent_language: str | None = None


class AppSettings(BaseModel):
    """Application-wide settings (admin-managed)."""

    app_title: str = "Firefly Desk"
    agent_name: str = "Ember"
    accent_color: str = "#2563EB"
    max_turns_per_conversation: int = 200
    default_llm_provider_id: str | None = None


class AgentSettings(BaseModel):
    """Agent customization settings stored in the DB."""

    name: str = "Ember"
    display_name: str = "Ember"
    avatar_url: str = ""  # Empty = default Ember avatar
    personality: str = "warm, professional, knowledgeable"
    tone: str = "friendly yet precise"
    greeting: str = "Hello! I'm {name}, your intelligent assistant."
    behavior_rules: list[str] = Field(default_factory=list)
    custom_instructions: str = ""  # Free-form additional instructions
    language: str = "en"
    allow_user_personality_overrides: bool = True


class EmailSettings(BaseModel):
    """Email channel configuration settings."""

    # Identity
    enabled: bool = False
    from_address: str = ""
    from_display_name: str = "Ember"
    reply_to: str = ""

    # Provider
    provider: str = "resend"  # "resend" | "ses" | "sendgrid"
    provider_api_key: str = ""
    provider_region: str = ""

    # Signature
    signature_html: str = ""
    signature_text: str = ""
    signature_image_url: str = ""  # URL to an uploaded signature/logo image

    # Persona overrides (empty = inherit from agent settings)
    email_tone: str = ""
    email_personality: str = ""
    email_instructions: str = ""

    # Behavior
    auto_reply: bool = True
    auto_reply_delay_seconds: int = 30
    max_email_length: int = 2000
    include_greeting: bool = True
    include_sign_off: bool = True

    # CC behavior
    cc_mode: str = "respond_all"  # "respond_all" | "respond_sender" | "silent"
    cc_instructions: str = ""

    # Access control
    allowed_tool_ids: list[str] = Field(default_factory=list)
    allowed_workspace_ids: list[str] = Field(default_factory=list)

    # Dev mode
    dev_authorized_emails: list[str] = Field(default_factory=list)
    ngrok_auth_token: str = ""
    tunnel_backend: str = "ngrok"  # "ngrok" | "cloudflared"


# Knowledge snippet truncation limit — used when formatting knowledge context
# for system prompts and search tool results.  Shared constant so the two
# code-paths stay in sync.
KNOWLEDGE_SNIPPET_MAX_CHARS = 2_000


class LLMRuntimeSettings(BaseModel):
    """LLM runtime tuning constants (admin-managed).

    Defaults match the original hardcoded values so existing deployments
    behave identically when no DB overrides are present.
    """

    # -- Retry / timeout --
    llm_max_retries: int = 3
    llm_retry_base_delay: float = 3.0  # seconds
    llm_retry_max_delay: float = 15.0  # seconds
    llm_fallback_retries: int = 2
    llm_stream_timeout: int = 300  # seconds (5 min)
    llm_followup_timeout: int = 240  # seconds (4 min)
    followup_max_retries: int = 3
    followup_retry_base_delay: float = 15.0  # seconds
    followup_retry_max_delay: float = 60.0  # seconds

    # -- Context truncation --
    followup_max_content_chars: int = 8_000  # per tool-return part
    followup_max_total_chars: int = 60_000  # total budget across all parts

    # -- File context budgets --
    file_context_max_per_file: int = 12_000
    file_context_max_total: int = 40_000

    # -- Multimodal context --
    multimodal_max_context_chars: int = 12_000

    # -- LLM output --
    default_max_tokens: int = 4096

    # -- Knowledge processing --
    knowledge_analyzer_max_chars: int = 8_000  # max content sent to LLM for document analysis
    document_read_max_chars: int = 30_000  # default max_chars for the document_read tool

    # -- Context enricher --
    context_entity_limit: int = 5
    context_retrieval_top_k: int = 5
