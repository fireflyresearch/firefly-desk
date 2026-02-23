# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for DeskConfig."""

from __future__ import annotations

import os
from unittest.mock import patch

from flydesk.config import DeskConfig


class TestDeskConfig:
    def test_defaults(self):
        """Config loads with sensible defaults for non-required fields."""
        with patch.dict(os.environ, {
            "FLYDESK_DATABASE_URL": "postgresql+asyncpg://localhost/flydesk",
            "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
            "FLYDESK_OIDC_CLIENT_ID": "test-client",
            "FLYDESK_OIDC_CLIENT_SECRET": "test-secret",
            "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
        }):
            cfg = DeskConfig()
            assert cfg.database_url == "postgresql+asyncpg://localhost/flydesk"
            assert cfg.oidc_issuer_url == "https://idp.example.com"
            assert cfg.agent_name == "Ember"
            assert cfg.audit_retention_days == 365
            assert cfg.rate_limit_per_user == 60
            assert cfg.accent_color == "#2563EB"
            assert cfg.app_title == "Firefly Desk"

    def test_env_prefix(self):
        """All settings read from FLYDESK_ prefixed env vars."""
        with patch.dict(os.environ, {
            "FLYDESK_DATABASE_URL": "postgresql+asyncpg://custom/db",
            "FLYDESK_OIDC_ISSUER_URL": "https://custom.idp.com",
            "FLYDESK_OIDC_CLIENT_ID": "custom-id",
            "FLYDESK_OIDC_CLIENT_SECRET": "custom-secret",
            "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "b" * 32,
            "FLYDESK_APP_TITLE": "Acme Desk",
            "FLYDESK_ACCENT_COLOR": "#FF0000",
            "FLYDESK_AGENT_NAME": "Acme Assistant",
        }):
            cfg = DeskConfig()
            assert cfg.app_title == "Acme Desk"
            assert cfg.accent_color == "#FF0000"
            assert cfg.agent_name == "Acme Assistant"

    def test_redis_url_optional(self):
        """Redis URL is optional (None by default)."""
        with patch.dict(os.environ, {
            "FLYDESK_DATABASE_URL": "postgresql+asyncpg://localhost/flydesk",
            "FLYDESK_OIDC_ISSUER_URL": "https://idp.example.com",
            "FLYDESK_OIDC_CLIENT_ID": "test-client",
            "FLYDESK_OIDC_CLIENT_SECRET": "test-secret",
            "FLYDESK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
        }):
            cfg = DeskConfig()
            assert cfg.redis_url is None

    def test_memory_defaults(self):
        """Memory config fields have sensible defaults."""
        with patch.dict(os.environ, {
            "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///test.db",
        }):
            cfg = DeskConfig()
            assert cfg.memory_backend == "in_memory"
            assert cfg.memory_max_tokens == 128_000
            assert cfg.memory_summarize_threshold == 10

    def test_memory_backend_from_env(self):
        """Memory backend can be overridden via environment variable."""
        with patch.dict(os.environ, {
            "FLYDESK_DATABASE_URL": "postgresql+asyncpg://localhost/flydesk",
            "FLYDESK_MEMORY_BACKEND": "postgres",
            "FLYDESK_MEMORY_MAX_TOKENS": "64000",
            "FLYDESK_MEMORY_SUMMARIZE_THRESHOLD": "20",
        }):
            cfg = DeskConfig()
            assert cfg.memory_backend == "postgres"
            assert cfg.memory_max_tokens == 64_000
            assert cfg.memory_summarize_threshold == 20

    # -- Middleware config fields --

    def test_middleware_defaults(self):
        """Middleware config fields have sensible defaults (all disabled)."""
        with patch.dict(os.environ, {
            "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///test.db",
        }):
            cfg = DeskConfig()
            # CostGuard
            assert cfg.cost_guard_enabled is False
            assert cfg.cost_guard_max_per_message == 1.0
            assert cfg.cost_guard_max_per_day == 50.0
            # PromptCache
            assert cfg.prompt_cache_enabled is False
            assert cfg.prompt_cache_ttl == 300
            # CircuitBreaker
            assert cfg.circuit_breaker_enabled is False
            assert cfg.circuit_breaker_failure_threshold == 5
            assert cfg.circuit_breaker_recovery_timeout == 60

    def test_middleware_from_env(self):
        """Middleware config fields can be set via environment variables."""
        with patch.dict(os.environ, {
            "FLYDESK_DATABASE_URL": "sqlite+aiosqlite:///test.db",
            "FLYDESK_COST_GUARD_ENABLED": "true",
            "FLYDESK_COST_GUARD_MAX_PER_MESSAGE": "2.5",
            "FLYDESK_COST_GUARD_MAX_PER_DAY": "100.0",
            "FLYDESK_PROMPT_CACHE_ENABLED": "true",
            "FLYDESK_PROMPT_CACHE_TTL": "600",
            "FLYDESK_CIRCUIT_BREAKER_ENABLED": "true",
            "FLYDESK_CIRCUIT_BREAKER_FAILURE_THRESHOLD": "10",
            "FLYDESK_CIRCUIT_BREAKER_RECOVERY_TIMEOUT": "120",
        }):
            cfg = DeskConfig()
            assert cfg.cost_guard_enabled is True
            assert cfg.cost_guard_max_per_message == 2.5
            assert cfg.cost_guard_max_per_day == 100.0
            assert cfg.prompt_cache_enabled is True
            assert cfg.prompt_cache_ttl == 600
            assert cfg.circuit_breaker_enabled is True
            assert cfg.circuit_breaker_failure_threshold == 10
            assert cfg.circuit_breaker_recovery_timeout == 120
