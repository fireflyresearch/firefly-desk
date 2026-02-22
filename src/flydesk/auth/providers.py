# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Provider-specific OIDC claim mappings and profile registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OIDCProviderProfile:
    """Metadata and claim-mapping rules for a specific OIDC provider."""

    name: str
    display_name: str
    roles_claim: str
    permissions_claim: str
    picture_claim: str
    department_claim: str
    title_claim: str
    default_scopes: list[str] = field(default_factory=list)
    discovery_url_template: str = "{issuer}/.well-known/openid-configuration"
    supports_pkce: bool = True
    notes: str = ""


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

PROVIDER_REGISTRY: dict[str, OIDCProviderProfile] = {
    "keycloak": OIDCProviderProfile(
        name="keycloak",
        display_name="Keycloak",
        roles_claim="realm_access.roles",
        permissions_claim="resource_access",
        picture_claim="picture",
        department_claim="department",
        title_claim="title",
        default_scopes=["openid", "profile", "email", "roles"],
        discovery_url_template="{issuer}/.well-known/openid-configuration",
        supports_pkce=True,
        notes="Roles extracted from realm_access.roles in the ID token.",
    ),
    "google": OIDCProviderProfile(
        name="google",
        display_name="Google",
        roles_claim="",  # No roles claim; use group membership
        permissions_claim="",
        picture_claim="picture",
        department_claim="",
        title_claim="",
        default_scopes=["openid", "profile", "email"],
        discovery_url_template="https://accounts.google.com/.well-known/openid-configuration",
        supports_pkce=True,
        notes="Google does not provide roles. Use Google Groups for RBAC.",
    ),
    "microsoft": OIDCProviderProfile(
        name="microsoft",
        display_name="Microsoft Entra ID",
        roles_claim="roles",
        permissions_claim="wids",
        picture_claim="",  # Microsoft Graph API required for photos
        department_claim="",
        title_claim="",
        default_scopes=["openid", "profile", "email", "User.Read"],
        discovery_url_template=(
            "https://login.microsoftonline.com/{tenant}/v2.0"
            "/.well-known/openid-configuration"
        ),
        supports_pkce=True,
        notes="Requires tenant_id. Roles from Azure AD app roles.",
    ),
    "auth0": OIDCProviderProfile(
        name="auth0",
        display_name="Auth0",
        roles_claim="https://{domain}/roles",
        permissions_claim="permissions",
        picture_claim="picture",
        department_claim="",
        title_claim="",
        default_scopes=["openid", "profile", "email"],
        discovery_url_template="{issuer}/.well-known/openid-configuration",
        supports_pkce=True,
        notes="Roles from custom namespace claim. Add RBAC rules in Auth0 dashboard.",
    ),
    "cognito": OIDCProviderProfile(
        name="cognito",
        display_name="AWS Cognito",
        roles_claim="cognito:groups",
        permissions_claim="",
        picture_claim="picture",
        department_claim="",
        title_claim="",
        default_scopes=["openid", "profile", "email"],
        discovery_url_template="{issuer}/.well-known/openid-configuration",
        supports_pkce=True,
        notes="Roles mapped from Cognito user pool groups.",
    ),
    "okta": OIDCProviderProfile(
        name="okta",
        display_name="Okta",
        roles_claim="groups",
        permissions_claim="",
        picture_claim="picture",
        department_claim="department",
        title_claim="title",
        default_scopes=["openid", "profile", "email", "groups"],
        discovery_url_template="{issuer}/.well-known/openid-configuration",
        supports_pkce=True,
        notes="Add 'groups' scope and configure groups claim in Okta.",
    ),
}


def get_provider(provider_type: str) -> OIDCProviderProfile:
    """Retrieve a provider profile by type name.

    Raises ``KeyError`` if the provider type is not registered.
    """
    provider_type = provider_type.lower()
    if provider_type not in PROVIDER_REGISTRY:
        registered = ", ".join(sorted(PROVIDER_REGISTRY))
        msg = f"Unknown OIDC provider type: {provider_type!r}. Registered: {registered}"
        raise KeyError(msg)
    return PROVIDER_REGISTRY[provider_type]


def extract_user_claims(claims: dict[str, Any], provider: OIDCProviderProfile) -> dict[str, Any]:
    """Map provider-specific claims to normalized user fields.

    Returns a dict with keys: ``roles``, ``permissions``, ``picture_url``,
    ``department``, ``title``.
    """
    return {
        "roles": _extract_claim(claims, provider.roles_claim),
        "permissions": _extract_claim(claims, provider.permissions_claim),
        "picture_url": _extract_scalar(claims, provider.picture_claim),
        "department": _extract_scalar(claims, provider.department_claim),
        "title": _extract_scalar(claims, provider.title_claim),
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _extract_claim(claims: dict[str, Any], claim_path: str) -> list[str]:
    """Extract a list-valued claim using dot-notation paths."""
    if not claim_path:
        return []
    parts = claim_path.split(".")
    value: Any = claims
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return []
    if isinstance(value, list):
        return [str(v) for v in value]
    if isinstance(value, str):
        return [value]
    return []


def _extract_scalar(claims: dict[str, Any], claim_path: str) -> str | None:
    """Extract a scalar claim value using dot-notation paths."""
    if not claim_path:
        return None
    parts = claim_path.split(".")
    value: Any = claims
    for part in parts:
        if isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    if isinstance(value, str):
        return value
    return None
