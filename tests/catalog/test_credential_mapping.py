# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for CredentialMapping model and AuthConfig updates."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from flydesk.catalog.enums import AuthType
from flydesk.catalog.models import AuthConfig, CredentialMapping


class TestCredentialMapping:
    def test_create_mapping_with_defaults(self):
        mapping = CredentialMapping(
            source="$.api_key",
            target="header",
            field_name="X-API-Key",
        )
        assert mapping.source == "$.api_key"
        assert mapping.target == "header"
        assert mapping.field_name == "X-API-Key"
        assert mapping.transform is None

    def test_create_mapping_with_transform(self):
        mapping = CredentialMapping(
            source="$value",
            target="header",
            field_name="Authorization",
            transform="prefix:Bearer ",
        )
        assert mapping.source == "$value"
        assert mapping.target == "header"
        assert mapping.field_name == "Authorization"
        assert mapping.transform == "prefix:Bearer "


class TestAuthConfigCredentialMappings:
    def test_auth_config_has_credential_mappings(self):
        config = AuthConfig(
            auth_type=AuthType.API_KEY,
            credential_id="cred-001",
            credential_mappings=[
                CredentialMapping(
                    source="$.api_key",
                    target="header",
                    field_name="X-API-Key",
                ),
                CredentialMapping(
                    source="$.secret",
                    target="query",
                    field_name="secret",
                    transform="base64",
                ),
            ],
        )
        assert len(config.credential_mappings) == 2
        assert config.credential_mappings[0].field_name == "X-API-Key"
        assert config.credential_mappings[1].transform == "base64"

    def test_auth_config_has_static_headers(self):
        config = AuthConfig(
            auth_type=AuthType.API_KEY,
            credential_id="cred-001",
            static_headers={
                "X-Custom-Tenant": "acme-corp",
                "Accept": "application/json",
            },
        )
        assert config.static_headers == {
            "X-Custom-Tenant": "acme-corp",
            "Accept": "application/json",
        }

    def test_auth_config_defaults_empty(self):
        config = AuthConfig(auth_type=AuthType.NONE)
        assert config.credential_mappings == []
        assert config.static_headers is None


class TestCredentialMappingValidation:
    def test_invalid_target_raises_validation_error(self):
        with pytest.raises(ValidationError):
            CredentialMapping(
                source="$.api_key",
                target="cookie",
                field_name="X-API-Key",
            )

    def test_invalid_transform_raises_validation_error(self):
        with pytest.raises(ValidationError):
            CredentialMapping(
                source="$.api_key",
                target="header",
                field_name="X-API-Key",
                transform="rot13",
            )

    def test_round_trip_serialization(self):
        config = AuthConfig(
            auth_type=AuthType.API_KEY,
            credential_id="cred-001",
            credential_mappings=[
                CredentialMapping(
                    source="$.api_key",
                    target="header",
                    field_name="X-API-Key",
                    transform="prefix:Bearer ",
                ),
            ],
            static_headers={"Accept": "application/json"},
        )
        data = config.model_dump()
        restored = AuthConfig(**data)
        assert restored == config
