# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Firefly Desk configuration via Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class DeskConfig(BaseSettings):
    """Central configuration for a Firefly Desk deployment.

    All fields are read from environment variables with the ``FLYDEK_`` prefix
    or from a ``.env`` file in the working directory.
    """

    model_config = SettingsConfigDict(
        env_prefix="FLYDEK_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # -- Database --
    database_url: str
    redis_url: str | None = None

    # -- OIDC --
    oidc_issuer_url: str
    oidc_client_id: str
    oidc_client_secret: str
    oidc_scopes: list[str] = ["openid", "profile", "email", "roles"]
    oidc_redirect_uri: str = "http://localhost:3000/auth/callback"
    oidc_roles_claim: str = "roles"
    oidc_permissions_claim: str = "permissions"

    # -- Agent --
    agent_name: str = "Firefly Desk Assistant"
    agent_instructions: str | None = None
    max_turns_per_conversation: int = 200
    max_tools_per_turn: int = 10

    # -- Knowledge --
    embedding_model: str = "openai:text-embedding-3-small"
    embedding_dimensions: int = 1536
    rag_top_k: int = 3
    kg_max_entities_in_context: int = 5

    # -- Security --
    credential_encryption_key: str
    audit_retention_days: int = 365
    rate_limit_per_user: int = 60

    # -- Branding --
    app_title: str = "Firefly Desk"
    app_logo_url: str | None = None
    accent_color: str = "#2563EB"


@lru_cache(maxsize=1)
def get_config() -> DeskConfig:
    """Return the singleton DeskConfig instance."""
    return DeskConfig()
