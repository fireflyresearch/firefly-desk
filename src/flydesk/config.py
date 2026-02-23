# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Firefly Desk configuration via Pydantic Settings."""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class DeskConfig(BaseSettings):
    """Central configuration for a Firefly Desk deployment.

    All fields are read from environment variables with the ``FLYDESK_`` prefix
    or from a ``.env`` file in the working directory.

    When ``dev_mode`` is True the app runs with SQLite, auth is bypassed, and
    no OIDC configuration is required.  This is the default when no ``.env``
    file or ``FLYDESK_DATABASE_URL`` env var is provided.
    """

    model_config = SettingsConfigDict(
        env_prefix="FLYDESK_",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    # -- Mode --
    dev_mode: bool = True

    # -- Database --
    database_url: str = "sqlite+aiosqlite:///flydesk_dev.db"
    redis_url: str | None = None

    # -- OIDC (required only when dev_mode=False) --
    oidc_issuer_url: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_scopes: list[str] = ["openid", "profile", "email", "roles"]
    oidc_redirect_uri: str = "http://localhost:3000/auth/callback"
    oidc_roles_claim: str = "roles"
    oidc_permissions_claim: str = "permissions"
    oidc_provider_type: str = "keycloak"
    oidc_tenant_id: str = ""

    # -- CORS (comma-separated origins, default: localhost for dev) --
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # -- Agent --
    agent_name: str = "Ember"
    agent_instructions: str | None = None
    max_turns_per_conversation: int = 200
    max_tools_per_turn: int = 10

    # -- Memory --
    memory_backend: Literal["in_memory", "postgres"] = "in_memory"
    memory_max_tokens: int = 128_000
    memory_summarize_threshold: int = 10

    # -- Queue --
    queue_backend: Literal["memory", "redis"] = "memory"

    # -- Knowledge --
    embedding_model: str = "openai:text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    rag_top_k: int = 3
    kg_max_entities_in_context: int = 5

    # -- Security --
    credential_encryption_key: str = ""
    audit_retention_days: int = 365
    rate_limit_per_user: int = 60

    # -- File Uploads --
    file_storage_path: str = "./uploads"
    file_max_size_mb: int = 50

    # -- Branding --
    app_title: str = "Firefly Desk"
    app_logo_url: str | None = None
    accent_color: str = "#2563EB"

    @property
    def effective_encryption_key(self) -> str:
        """Return the encryption key, generating a dev key if empty."""
        if self.credential_encryption_key:
            return self.credential_encryption_key
        return secrets.token_urlsafe(32)


@lru_cache(maxsize=1)
def get_config() -> DeskConfig:
    """Return the singleton DeskConfig instance."""
    return DeskConfig()
