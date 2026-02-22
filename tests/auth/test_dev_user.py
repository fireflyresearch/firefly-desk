# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for _build_dev_user in the dev auth module."""

from __future__ import annotations

import os
from unittest.mock import patch

from flydesk.auth.dev import _build_dev_user


class TestBuildDevUserDefaults:
    """Tests for _build_dev_user with default environment (no env vars set)."""

    def test_default_display_name(self):
        """Display name defaults to 'Dev Admin' when FLYDESK_DEV_USER_NAME is unset."""
        with patch.dict(os.environ, {}, clear=True):
            user = _build_dev_user()
        assert user.display_name == "Dev Admin"

    def test_default_email(self):
        """Email defaults to 'admin@localhost' when FLYDESK_DEV_USER_EMAIL is unset."""
        with patch.dict(os.environ, {}, clear=True):
            user = _build_dev_user()
        assert user.email == "admin@localhost"

    def test_default_roles(self):
        """Roles default to ['admin', 'operator'] when FLYDESK_DEV_USER_ROLES is unset."""
        with patch.dict(os.environ, {}, clear=True):
            user = _build_dev_user()
        assert user.roles == ["admin", "operator"]

    def test_default_personalization_fields_are_none(self):
        """picture_url, department, and title default to None."""
        with patch.dict(os.environ, {}, clear=True):
            user = _build_dev_user()
        assert user.picture_url is None
        assert user.department is None
        assert user.title is None

    def test_default_fixed_fields(self):
        """user_id, tenant_id, and permissions have fixed default values."""
        with patch.dict(os.environ, {}, clear=True):
            user = _build_dev_user()
        assert user.user_id == "dev-user-001"
        assert user.tenant_id == "dev-tenant"
        assert user.permissions == ["*"]


class TestBuildDevUserCustomEnv:
    """Tests for _build_dev_user with custom env vars."""

    def test_custom_display_name(self):
        """FLYDESK_DEV_USER_NAME overrides display_name."""
        env = {"FLYDESK_DEV_USER_NAME": "Jane Doe"}
        with patch.dict(os.environ, env, clear=True):
            user = _build_dev_user()
        assert user.display_name == "Jane Doe"

    def test_custom_email(self):
        """FLYDESK_DEV_USER_EMAIL overrides email."""
        env = {"FLYDESK_DEV_USER_EMAIL": "jane@example.com"}
        with patch.dict(os.environ, env, clear=True):
            user = _build_dev_user()
        assert user.email == "jane@example.com"

    def test_custom_roles(self):
        """FLYDESK_DEV_USER_ROLES overrides roles with a comma-separated list."""
        env = {"FLYDESK_DEV_USER_ROLES": "viewer,billing"}
        with patch.dict(os.environ, env, clear=True):
            user = _build_dev_user()
        assert user.roles == ["viewer", "billing"]

    def test_custom_picture_url(self):
        """FLYDESK_DEV_USER_PICTURE sets picture_url."""
        env = {"FLYDESK_DEV_USER_PICTURE": "https://example.com/avatar.png"}
        with patch.dict(os.environ, env, clear=True):
            user = _build_dev_user()
        assert user.picture_url == "https://example.com/avatar.png"

    def test_custom_department(self):
        """FLYDESK_DEV_USER_DEPARTMENT sets department."""
        env = {"FLYDESK_DEV_USER_DEPARTMENT": "Engineering"}
        with patch.dict(os.environ, env, clear=True):
            user = _build_dev_user()
        assert user.department == "Engineering"

    def test_custom_title(self):
        """FLYDESK_DEV_USER_TITLE sets title."""
        env = {"FLYDESK_DEV_USER_TITLE": "Staff Engineer"}
        with patch.dict(os.environ, env, clear=True):
            user = _build_dev_user()
        assert user.title == "Staff Engineer"

    def test_all_custom_fields_together(self):
        """All env vars can be set simultaneously."""
        env = {
            "FLYDESK_DEV_USER_NAME": "Alice Smith",
            "FLYDESK_DEV_USER_EMAIL": "alice@corp.com",
            "FLYDESK_DEV_USER_ROLES": "admin,support,billing",
            "FLYDESK_DEV_USER_PICTURE": "https://cdn.example.com/alice.jpg",
            "FLYDESK_DEV_USER_DEPARTMENT": "Customer Success",
            "FLYDESK_DEV_USER_TITLE": "VP of Support",
        }
        with patch.dict(os.environ, env, clear=True):
            user = _build_dev_user()
        assert user.display_name == "Alice Smith"
        assert user.email == "alice@corp.com"
        assert user.roles == ["admin", "support", "billing"]
        assert user.picture_url == "https://cdn.example.com/alice.jpg"
        assert user.department == "Customer Success"
        assert user.title == "VP of Support"

    def test_empty_string_picture_becomes_none(self):
        """An empty FLYDESK_DEV_USER_PICTURE is treated as None."""
        env = {"FLYDESK_DEV_USER_PICTURE": ""}
        with patch.dict(os.environ, env, clear=True):
            user = _build_dev_user()
        assert user.picture_url is None

    def test_empty_string_department_becomes_none(self):
        """An empty FLYDESK_DEV_USER_DEPARTMENT is treated as None."""
        env = {"FLYDESK_DEV_USER_DEPARTMENT": ""}
        with patch.dict(os.environ, env, clear=True):
            user = _build_dev_user()
        assert user.department is None

    def test_empty_string_title_becomes_none(self):
        """An empty FLYDESK_DEV_USER_TITLE is treated as None."""
        env = {"FLYDESK_DEV_USER_TITLE": ""}
        with patch.dict(os.environ, env, clear=True):
            user = _build_dev_user()
        assert user.title is None

    def test_raw_claims_reflect_custom_name_and_email(self):
        """raw_claims sub, name, and email match the configured env vars."""
        env = {
            "FLYDESK_DEV_USER_NAME": "Custom Name",
            "FLYDESK_DEV_USER_EMAIL": "custom@test.io",
        }
        with patch.dict(os.environ, env, clear=True):
            user = _build_dev_user()
        assert user.raw_claims["name"] == "Custom Name"
        assert user.raw_claims["email"] == "custom@test.io"
        assert user.raw_claims["sub"] == "dev-user-001"
