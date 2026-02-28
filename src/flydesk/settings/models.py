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
    from_address: str = "ember@flydesk.ai"
    from_display_name: str = "Ember"
    reply_to: str = ""

    # Provider
    provider: str = "resend"  # "resend" | "ses"
    provider_api_key: str = ""
    provider_region: str = ""

    # Signature
    signature_html: str = ""
    signature_text: str = ""

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
