# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for AuthResolver credential mapping and ResolvedAuth integration."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from flydesk.catalog.enums import AuthType
from flydesk.catalog.models import (
    AuthConfig,
    Credential,
    CredentialMapping,
    ExternalSystem,
)
from flydesk.tools.auth_resolver import AuthResolver, ResolvedAuth


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TOKEN = "secret-token-123"


def _make_credential(
    credential_id: str = "cred-1",
    encrypted_value: str = TOKEN,
) -> Credential:
    return Credential(
        id=credential_id,
        system_id="sys-1",
        name="Test Credential",
        encrypted_value=encrypted_value,
        credential_type="token",
    )


def _make_system(
    auth_type: AuthType = AuthType.BEARER,
    credential_id: str = "cred-1",
    auth_headers: dict[str, str] | None = None,
    credential_mappings: list[CredentialMapping] | None = None,
    static_headers: dict[str, str] | None = None,
) -> ExternalSystem:
    return ExternalSystem(
        id="sys-1",
        name="Test System",
        description="A test system",
        base_url="https://api.example.com",
        auth_config=AuthConfig(
            auth_type=auth_type,
            credential_id=credential_id,
            auth_headers=auth_headers,
            credential_mappings=credential_mappings or [],
            static_headers=static_headers,
        ),
    )


@pytest.fixture
def credential_store() -> MagicMock:
    mock = MagicMock()
    mock.get_credential = AsyncMock(return_value=_make_credential())
    return mock


@pytest.fixture
def resolver(credential_store: MagicMock) -> AuthResolver:
    return AuthResolver(credential_store)


# ---------------------------------------------------------------------------
# Return type
# ---------------------------------------------------------------------------


class TestResolvedAuthReturnType:
    async def test_resolve_returns_resolved_auth(self, resolver: AuthResolver):
        system = _make_system(AuthType.BEARER)
        result = await resolver.resolve_headers(system)

        assert isinstance(result, ResolvedAuth)
        assert result.headers == {"Authorization": f"Bearer {TOKEN}"}
        assert result.query_params == {}
        assert result.path_params == {}
        assert result.body_params == {}

    async def test_no_auth_returns_resolved_auth(self, resolver: AuthResolver):
        system = ExternalSystem(
            id="sys-1",
            name="No Auth System",
            description="desc",
            base_url="https://api.example.com",
            auth_config=AuthConfig(auth_type=AuthType.NONE),
        )
        result = await resolver.resolve_headers(system)

        assert isinstance(result, ResolvedAuth)
        assert result.headers == {}

    async def test_none_auth_config_returns_resolved_auth(self, resolver: AuthResolver):
        system = ExternalSystem(
            id="sys-1",
            name="No Config System",
            description="desc",
            base_url="https://api.example.com",
            auth_config=None,
        )
        result = await resolver.resolve_headers(system)

        assert isinstance(result, ResolvedAuth)
        assert result.headers == {}


# ---------------------------------------------------------------------------
# Static headers
# ---------------------------------------------------------------------------


class TestStaticHeaders:
    async def test_static_headers_merged_with_auth(self, resolver: AuthResolver):
        system = _make_system(
            AuthType.BEARER,
            static_headers={"X-Tenant": "acme", "X-Trace-Id": "abc123"},
        )
        result = await resolver.resolve_headers(system)

        assert result.headers["Authorization"] == f"Bearer {TOKEN}"
        assert result.headers["X-Tenant"] == "acme"
        assert result.headers["X-Trace-Id"] == "abc123"

    async def test_static_headers_with_no_auth(self, resolver: AuthResolver):
        system = ExternalSystem(
            id="sys-1",
            name="Static Only",
            description="desc",
            base_url="https://api.example.com",
            auth_config=AuthConfig(
                auth_type=AuthType.NONE,
                static_headers={"X-App": "flydesk"},
            ),
        )
        result = await resolver.resolve_headers(system)

        assert result.headers == {"X-App": "flydesk"}


# ---------------------------------------------------------------------------
# Credential mapping - raw $value
# ---------------------------------------------------------------------------


class TestRawValueMapping:
    async def test_raw_value_to_header(self, resolver: AuthResolver):
        system = _make_system(
            AuthType.NONE,
            credential_mappings=[
                CredentialMapping(
                    source="$value",
                    target="header",
                    field_name="X-Custom-Token",
                ),
            ],
        )
        result = await resolver.resolve_headers(system)

        assert result.headers["X-Custom-Token"] == TOKEN

    async def test_raw_value_to_query(self, resolver: AuthResolver):
        system = _make_system(
            AuthType.NONE,
            credential_mappings=[
                CredentialMapping(
                    source="$value",
                    target="query",
                    field_name="api_key",
                ),
            ],
        )
        result = await resolver.resolve_headers(system)

        assert result.query_params["api_key"] == TOKEN

    async def test_raw_value_to_body(self, resolver: AuthResolver):
        system = _make_system(
            AuthType.NONE,
            credential_mappings=[
                CredentialMapping(
                    source="$value",
                    target="body",
                    field_name="secret",
                ),
            ],
        )
        result = await resolver.resolve_headers(system)

        assert result.body_params["secret"] == TOKEN

    async def test_raw_value_to_path(self, resolver: AuthResolver):
        system = _make_system(
            AuthType.NONE,
            credential_mappings=[
                CredentialMapping(
                    source="$value",
                    target="path",
                    field_name="tenant_id",
                ),
            ],
        )
        result = await resolver.resolve_headers(system)

        assert result.path_params["tenant_id"] == TOKEN


# ---------------------------------------------------------------------------
# Credential mapping - JSON field extraction
# ---------------------------------------------------------------------------


class TestJsonFieldExtraction:
    async def test_extract_json_field(
        self, resolver: AuthResolver, credential_store
    ):
        cred_json = json.dumps({"api_key": "key-abc", "tenant": "t1"})
        credential_store.get_credential.return_value = _make_credential(
            encrypted_value=cred_json,
        )
        system = _make_system(
            AuthType.NONE,
            credential_mappings=[
                CredentialMapping(
                    source="api_key",
                    target="header",
                    field_name="X-Api-Key",
                ),
                CredentialMapping(
                    source="tenant",
                    target="query",
                    field_name="tenant_id",
                ),
            ],
        )
        result = await resolver.resolve_headers(system)

        assert result.headers["X-Api-Key"] == "key-abc"
        assert result.query_params["tenant_id"] == "t1"

    async def test_missing_json_field_is_skipped(
        self, resolver: AuthResolver, credential_store
    ):
        cred_json = json.dumps({"api_key": "key-abc"})
        credential_store.get_credential.return_value = _make_credential(
            encrypted_value=cred_json,
        )
        system = _make_system(
            AuthType.NONE,
            credential_mappings=[
                CredentialMapping(
                    source="nonexistent_field",
                    target="header",
                    field_name="X-Missing",
                ),
            ],
        )
        result = await resolver.resolve_headers(system)

        assert "X-Missing" not in result.headers

    async def test_non_dict_json_uses_raw_value(
        self, resolver: AuthResolver, credential_store
    ):
        """If JSON parses to a list, treat credential as raw string."""
        credential_store.get_credential.return_value = _make_credential(
            encrypted_value=json.dumps(["a", "b"]),
        )
        system = _make_system(
            AuthType.NONE,
            credential_mappings=[
                CredentialMapping(
                    source="$value",
                    target="header",
                    field_name="X-Raw",
                ),
            ],
        )
        result = await resolver.resolve_headers(system)

        assert result.headers["X-Raw"] == json.dumps(["a", "b"])


# ---------------------------------------------------------------------------
# Transforms
# ---------------------------------------------------------------------------


class TestTransforms:
    async def test_base64_transform(self, resolver: AuthResolver):
        system = _make_system(
            AuthType.NONE,
            credential_mappings=[
                CredentialMapping(
                    source="$value",
                    target="header",
                    field_name="X-Encoded",
                    transform="base64",
                ),
            ],
        )
        result = await resolver.resolve_headers(system)

        expected = base64.b64encode(TOKEN.encode()).decode()
        assert result.headers["X-Encoded"] == expected

    async def test_prefix_transform(self, resolver: AuthResolver):
        system = _make_system(
            AuthType.NONE,
            credential_mappings=[
                CredentialMapping(
                    source="$value",
                    target="header",
                    field_name="Authorization",
                    transform="prefix:Bearer ",
                ),
            ],
        )
        result = await resolver.resolve_headers(system)

        assert result.headers["Authorization"] == f"Bearer {TOKEN}"

    async def test_apply_transform_static_base64(self):
        value = AuthResolver._apply_transform("hello", "base64")
        assert value == base64.b64encode(b"hello").decode()

    async def test_apply_transform_static_prefix(self):
        value = AuthResolver._apply_transform("tok", "prefix:Token ")
        assert value == "Token tok"

    async def test_apply_transform_unknown_returns_value(self):
        value = AuthResolver._apply_transform("tok", "unknown")
        assert value == "tok"


# ---------------------------------------------------------------------------
# Mappings combined with base auth
# ---------------------------------------------------------------------------


class TestMappingsCombinedWithAuth:
    async def test_bearer_plus_query_mapping(
        self, resolver: AuthResolver, credential_store
    ):
        """BEARER auth sets the Authorization header; a mapping adds a query param."""
        cred_json = json.dumps({"token": "bearer-tok", "project": "proj-1"})
        credential_store.get_credential.return_value = _make_credential(
            encrypted_value=cred_json,
        )
        system = _make_system(
            AuthType.BEARER,
            credential_mappings=[
                CredentialMapping(
                    source="project",
                    target="query",
                    field_name="project_id",
                ),
            ],
        )
        result = await resolver.resolve_headers(system)

        # Bearer auth uses the raw decrypted value
        assert result.headers["Authorization"] == f"Bearer {cred_json}"
        # Mapping extracts a JSON field to query
        assert result.query_params["project_id"] == "proj-1"

    async def test_api_key_plus_body_mapping(
        self, resolver: AuthResolver, credential_store
    ):
        cred_json = json.dumps({"key": "abc", "secret": "xyz"})
        credential_store.get_credential.return_value = _make_credential(
            encrypted_value=cred_json,
        )
        system = _make_system(
            AuthType.API_KEY,
            credential_mappings=[
                CredentialMapping(
                    source="secret",
                    target="body",
                    field_name="client_secret",
                ),
            ],
        )
        result = await resolver.resolve_headers(system)

        # API_KEY auth uses the raw decrypted value for the header
        assert result.headers["X-Api-Key"] == cred_json
        # Mapping extracts JSON field to body
        assert result.body_params["client_secret"] == "xyz"

    async def test_credential_not_found_skips_mappings(
        self, resolver: AuthResolver, credential_store
    ):
        """When credential store returns None for mappings, mappings are skipped."""
        # First call returns credential (for base auth), second returns None (for mappings)
        credential_store.get_credential = AsyncMock(
            side_effect=[_make_credential(), None],
        )
        system = _make_system(
            AuthType.BEARER,
            credential_mappings=[
                CredentialMapping(
                    source="$value",
                    target="query",
                    field_name="extra",
                ),
            ],
        )
        result = await resolver.resolve_headers(system)

        # Base auth still works
        assert "Authorization" in result.headers
        # But mapping was skipped (credential not found on second call)
        assert result.query_params == {}

    async def test_mappings_with_static_headers(self, resolver: AuthResolver):
        system = _make_system(
            AuthType.NONE,
            credential_mappings=[
                CredentialMapping(
                    source="$value",
                    target="header",
                    field_name="X-Token",
                ),
            ],
            static_headers={"X-Version": "2"},
        )
        result = await resolver.resolve_headers(system)

        assert result.headers["X-Token"] == TOKEN
        assert result.headers["X-Version"] == "2"
