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

from flydek.config import DeskConfig


class TestDeskConfig:
    def test_defaults(self):
        """Config loads with sensible defaults for non-required fields."""
        with patch.dict(os.environ, {
            "FLYDEK_DATABASE_URL": "postgresql+asyncpg://localhost/flydek",
            "FLYDEK_OIDC_ISSUER_URL": "https://idp.example.com",
            "FLYDEK_OIDC_CLIENT_ID": "test-client",
            "FLYDEK_OIDC_CLIENT_SECRET": "test-secret",
            "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
        }):
            cfg = DeskConfig()
            assert cfg.database_url == "postgresql+asyncpg://localhost/flydek"
            assert cfg.oidc_issuer_url == "https://idp.example.com"
            assert cfg.agent_name == "Firefly Desk Assistant"
            assert cfg.audit_retention_days == 365
            assert cfg.rate_limit_per_user == 60
            assert cfg.accent_color == "#2563EB"
            assert cfg.app_title == "Firefly Desk"

    def test_env_prefix(self):
        """All settings read from FLYDEK_ prefixed env vars."""
        with patch.dict(os.environ, {
            "FLYDEK_DATABASE_URL": "postgresql+asyncpg://custom/db",
            "FLYDEK_OIDC_ISSUER_URL": "https://custom.idp.com",
            "FLYDEK_OIDC_CLIENT_ID": "custom-id",
            "FLYDEK_OIDC_CLIENT_SECRET": "custom-secret",
            "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": "b" * 32,
            "FLYDEK_APP_TITLE": "Acme Desk",
            "FLYDEK_ACCENT_COLOR": "#FF0000",
            "FLYDEK_AGENT_NAME": "Acme Assistant",
        }):
            cfg = DeskConfig()
            assert cfg.app_title == "Acme Desk"
            assert cfg.accent_color == "#FF0000"
            assert cfg.agent_name == "Acme Assistant"

    def test_redis_url_optional(self):
        """Redis URL is optional (None by default)."""
        with patch.dict(os.environ, {
            "FLYDEK_DATABASE_URL": "postgresql+asyncpg://localhost/flydek",
            "FLYDEK_OIDC_ISSUER_URL": "https://idp.example.com",
            "FLYDEK_OIDC_CLIENT_ID": "test-client",
            "FLYDEK_OIDC_CLIENT_SECRET": "test-secret",
            "FLYDEK_CREDENTIAL_ENCRYPTION_KEY": "a" * 32,
        }):
            cfg = DeskConfig()
            assert cfg.redis_url is None
