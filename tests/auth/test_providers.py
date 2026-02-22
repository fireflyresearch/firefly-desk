# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for OIDC provider claim extraction and registry."""

from __future__ import annotations

import pytest

from flydesk.auth.providers import (
    PROVIDER_REGISTRY,
    extract_user_claims,
    get_provider,
)


class TestProviderRegistry:
    def test_get_provider_keycloak(self):
        """get_provider() returns the Keycloak profile."""
        profile = get_provider("keycloak")
        assert profile.name == "keycloak"
        assert profile.display_name == "Keycloak"
        assert profile.roles_claim == "realm_access.roles"

    def test_get_provider_case_insensitive(self):
        """Provider lookups are case-insensitive."""
        profile = get_provider("KEYCLOAK")
        assert profile.name == "keycloak"

    def test_get_provider_unknown_raises_key_error(self):
        """An unknown provider type raises KeyError."""
        with pytest.raises(KeyError, match="Unknown OIDC provider type"):
            get_provider("nonexistent")

    def test_all_six_providers_registered(self):
        """The registry contains all six standard providers."""
        expected = {"keycloak", "google", "microsoft", "auth0", "cognito", "okta"}
        assert set(PROVIDER_REGISTRY.keys()) == expected


class TestExtractUserClaims:
    def test_keycloak_nested_roles(self):
        """Keycloak roles are extracted from realm_access.roles."""
        profile = get_provider("keycloak")
        claims = {
            "realm_access": {"roles": ["admin", "user"]},
            "resource_access": {"client-app": {"roles": ["editor"]}},
            "picture": "https://example.com/avatar.png",
            "department": "Engineering",
            "title": "Senior Dev",
        }
        result = extract_user_claims(claims, profile)
        assert result["roles"] == ["admin", "user"]
        assert result["picture_url"] == "https://example.com/avatar.png"
        assert result["department"] == "Engineering"
        assert result["title"] == "Senior Dev"

    def test_microsoft_flat_roles(self):
        """Microsoft Entra ID roles are extracted from top-level 'roles'."""
        profile = get_provider("microsoft")
        claims = {
            "roles": ["GlobalAdmin", "Reader"],
            "wids": ["dir-role-1"],
        }
        result = extract_user_claims(claims, profile)
        assert result["roles"] == ["GlobalAdmin", "Reader"]
        assert result["permissions"] == ["dir-role-1"]

    def test_cognito_groups(self):
        """Cognito roles are extracted from cognito:groups."""
        profile = get_provider("cognito")
        claims = {
            "cognito:groups": ["admins", "power-users"],
            "picture": "https://example.com/photo.jpg",
        }
        result = extract_user_claims(claims, profile)
        assert result["roles"] == ["admins", "power-users"]
        assert result["picture_url"] == "https://example.com/photo.jpg"

    def test_okta_groups_and_department(self):
        """Okta extracts groups, department, and title."""
        profile = get_provider("okta")
        claims = {
            "groups": ["Everyone", "Developers"],
            "picture": "https://okta.example.com/pic.png",
            "department": "Platform",
            "title": "Staff Engineer",
        }
        result = extract_user_claims(claims, profile)
        assert result["roles"] == ["Everyone", "Developers"]
        assert result["department"] == "Platform"
        assert result["title"] == "Staff Engineer"

    def test_google_no_roles_claim(self):
        """Google has no roles_claim, so roles should be empty."""
        profile = get_provider("google")
        claims = {
            "picture": "https://lh3.googleusercontent.com/photo.jpg",
            "email": "user@gmail.com",
        }
        result = extract_user_claims(claims, profile)
        assert result["roles"] == []
        assert result["permissions"] == []
        assert result["picture_url"] == "https://lh3.googleusercontent.com/photo.jpg"

    def test_missing_claims_return_defaults(self):
        """When expected claims are absent, defaults are returned."""
        profile = get_provider("keycloak")
        claims = {"sub": "user-1", "email": "user@example.com"}
        result = extract_user_claims(claims, profile)
        assert result["roles"] == []
        assert result["permissions"] == []
        assert result["picture_url"] is None
        assert result["department"] is None
        assert result["title"] is None

    def test_string_role_wrapped_in_list(self):
        """A single string role value is wrapped in a list."""
        profile = get_provider("microsoft")
        claims = {"roles": "single-role"}
        result = extract_user_claims(claims, profile)
        assert result["roles"] == ["single-role"]
