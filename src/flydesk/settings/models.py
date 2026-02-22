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


class AppSettings(BaseModel):
    """Application-wide settings (admin-managed)."""

    app_title: str = "Firefly Desk"
    agent_name: str = "Ember"
    accent_color: str = "#2563EB"
    max_turns_per_conversation: int = 200
    default_llm_provider_id: str | None = None
