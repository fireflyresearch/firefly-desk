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
from typing import ClassVar, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from flydesk.domain.common import EmailProviderType, VectorStoreType


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
    company_name: str = ""
    agent_instructions: str | None = None
    max_turns_per_conversation: int = 200
    max_tools_per_turn: int = 10

    # -- LLM Fallback Models --
    llm_fallback_models: dict[str, list[str]] = {
        "anthropic": ["claude-haiku-4-5-20251001"],
        "openai": ["gpt-4o-mini"],
        "google": ["gemini-2.0-flash"],
    }

    # -- Memory --
    memory_backend: Literal["in_memory", "postgres"] = "in_memory"
    memory_max_tokens: int = 128_000
    memory_summarize_threshold: int = 10

    # -- Queue --
    queue_backend: Literal["memory", "redis"] = "memory"

    # -- Knowledge --
    max_knowledge_tokens: int = 4000
    embedding_model: str = "openai:text-embedding-3-small"
    embedding_dimensions: int = 1536
    embedding_api_key: str = ""
    embedding_base_url: str = ""
    rag_top_k: int = 3
    kg_max_entities_in_context: int = 5

    # -- Knowledge Quality --
    chunk_size: int = 500
    chunk_overlap: int = 50
    chunking_mode: Literal["fixed", "structural", "auto"] = "auto"
    auto_kg_extract: bool = True

    # -- Vector Store --
    vector_store: VectorStoreType = VectorStoreType.SQLITE
    chroma_path: str = ""
    chroma_url: str = ""
    pinecone_api_key: str = ""
    pinecone_index_name: str = ""
    pinecone_environment: str = ""

    # -- Security --
    credential_encryption_key: str = ""
    kms_provider: Literal["fernet", "aws", "gcp", "azure", "vault", "noop"] = "fernet"
    aws_kms_key_arn: str = ""
    aws_kms_region: str = ""
    gcp_kms_key_name: str = ""
    azure_vault_url: str = ""
    azure_key_name: str = ""
    vault_url: str = ""
    vault_token: str = ""
    vault_transit_key: str = "flydesk"
    vault_mount_point: str = "transit"
    jwt_secret_key: str = ""
    audit_retention_days: int = 365
    rate_limit_per_user: int = 60

    # -- GitHub Integration --
    github_client_id: str = ""
    github_client_secret: str = ""

    _cached_jwt_secret: ClassVar[str | None] = None

    # -- Analysis --
    auto_analyze: bool = False

    # -- Docs --
    docs_path: str = "docs"
    docs_auto_index: bool = True

    # -- File Uploads --
    file_storage_path: str = "./uploads"
    file_max_size_mb: int = 50

    # -- Middleware --
    cost_guard_enabled: bool = False
    cost_guard_max_per_message: float = 1.0  # USD per call
    cost_guard_max_per_day: float = 50.0  # USD cumulative daily budget
    prompt_cache_enabled: bool = True
    prompt_cache_ttl: int = 300  # seconds
    circuit_breaker_enabled: bool = False
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60  # seconds

    # -- Branding --
    app_title: str = "Firefly Desk"
    app_logo_url: str | None = None
    accent_color: str = "#2563EB"

    # -- Email Channel --
    email_enabled: bool = False
    email_provider: EmailProviderType = EmailProviderType.RESEND
    email_api_key: str = ""
    email_from_address: str = ""
    email_ses_region: str = "us-east-1"

    # -- External API Base URLs --
    sendgrid_api_base: str = "https://api.sendgrid.com"
    tavily_api_url: str = "https://api.tavily.com"

    @property
    def effective_jwt_secret(self) -> str:
        """Return the JWT signing secret, generating one if not configured.

        The generated value is cached so that all tokens issued during the
        process lifetime can be verified.
        """
        if self.jwt_secret_key:
            return self.jwt_secret_key
        if self._cached_jwt_secret is None:
            object.__setattr__(self, "_cached_jwt_secret", secrets.token_urlsafe(32))
        return self._cached_jwt_secret  # type: ignore[return-value]


@lru_cache(maxsize=1)
def get_config() -> DeskConfig:
    """Return the singleton DeskConfig instance."""
    return DeskConfig()
