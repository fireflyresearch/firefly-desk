# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for SSOAttributeMappingResolver -- claim extraction, transforms, filtering."""

from __future__ import annotations

import base64

import pytest

from flydesk.auth.sso_mapping import (
    SSOAttributeMapping,
    SSOAttributeMappingResolver,
    _apply_transform,
    _extract_claim,
)


# ---------------------------------------------------------------------------
# _extract_claim
# ---------------------------------------------------------------------------


class TestExtractClaim:
    def test_simple_key(self):
        claims = {"employee_id": "EMP-42"}
        assert _extract_claim(claims, "employee_id") == "EMP-42"

    def test_dot_notation_nested(self):
        claims = {"custom_claims": {"hr_id": "HR-99"}}
        assert _extract_claim(claims, "custom_claims.hr_id") == "HR-99"

    def test_deep_nesting(self):
        claims = {"a": {"b": {"c": "deep"}}}
        assert _extract_claim(claims, "a.b.c") == "deep"

    def test_missing_top_level(self):
        claims = {"other": "value"}
        assert _extract_claim(claims, "employee_id") is None

    def test_missing_nested_segment(self):
        claims = {"custom_claims": {"other": "value"}}
        assert _extract_claim(claims, "custom_claims.hr_id") is None

    def test_non_dict_intermediate(self):
        claims = {"custom_claims": "not_a_dict"}
        assert _extract_claim(claims, "custom_claims.hr_id") is None

    def test_converts_non_string_to_string(self):
        claims = {"num": 42}
        assert _extract_claim(claims, "num") == "42"

    def test_empty_claims(self):
        assert _extract_claim({}, "anything") is None


# ---------------------------------------------------------------------------
# _apply_transform
# ---------------------------------------------------------------------------


class TestApplyTransform:
    def test_no_transform(self):
        assert _apply_transform("hello", None) == "hello"

    def test_uppercase(self):
        assert _apply_transform("hello", "uppercase") == "HELLO"

    def test_lowercase(self):
        assert _apply_transform("HELLO", "lowercase") == "hello"

    def test_prefix(self):
        assert _apply_transform("42", "prefix:EMP-") == "EMP-42"

    def test_prefix_empty(self):
        assert _apply_transform("42", "prefix:") == "42"

    def test_base64(self):
        expected = base64.b64encode(b"hello").decode()
        assert _apply_transform("hello", "base64") == expected

    def test_unknown_transform_passthrough(self):
        assert _apply_transform("hello", "unknown") == "hello"


# ---------------------------------------------------------------------------
# SSOAttributeMappingResolver
# ---------------------------------------------------------------------------


class TestSSOAttributeMappingResolver:
    def _mapping(
        self,
        mapping_id: str = "m1",
        claim_path: str = "employee_id",
        target_header: str = "X-Employee-ID",
        target_type: str = "header",
        system_filter: str | None = None,
        transform: str | None = None,
    ) -> SSOAttributeMapping:
        return SSOAttributeMapping(
            id=mapping_id,
            claim_path=claim_path,
            target_header=target_header,
            target_type=target_type,
            system_filter=system_filter,
            transform=transform,
        )

    def test_simple_claim_extraction(self):
        resolver = SSOAttributeMappingResolver()
        mappings = [self._mapping()]
        claims = {"employee_id": "EMP-42"}

        headers = resolver.resolve_headers(mappings, claims)

        assert headers == {"X-Employee-ID": "EMP-42"}

    def test_dot_notation_nested_claim(self):
        resolver = SSOAttributeMappingResolver()
        mappings = [
            self._mapping(
                claim_path="custom_claims.hr_id",
                target_header="X-HR-ID",
            )
        ]
        claims = {"custom_claims": {"hr_id": "HR-99"}}

        headers = resolver.resolve_headers(mappings, claims)

        assert headers == {"X-HR-ID": "HR-99"}

    def test_transform_uppercase(self):
        resolver = SSOAttributeMappingResolver()
        mappings = [self._mapping(transform="uppercase")]
        claims = {"employee_id": "emp-42"}

        headers = resolver.resolve_headers(mappings, claims)

        assert headers == {"X-Employee-ID": "EMP-42"}

    def test_transform_lowercase(self):
        resolver = SSOAttributeMappingResolver()
        mappings = [self._mapping(transform="lowercase")]
        claims = {"employee_id": "EMP-42"}

        headers = resolver.resolve_headers(mappings, claims)

        assert headers == {"X-Employee-ID": "emp-42"}

    def test_transform_prefix(self):
        resolver = SSOAttributeMappingResolver()
        mappings = [self._mapping(transform="prefix:EMP-")]
        claims = {"employee_id": "42"}

        headers = resolver.resolve_headers(mappings, claims)

        assert headers == {"X-Employee-ID": "EMP-42"}

    def test_transform_base64(self):
        resolver = SSOAttributeMappingResolver()
        mappings = [self._mapping(transform="base64")]
        claims = {"employee_id": "hello"}

        headers = resolver.resolve_headers(mappings, claims)

        expected = base64.b64encode(b"hello").decode()
        assert headers == {"X-Employee-ID": expected}

    def test_system_filter_match(self):
        resolver = SSOAttributeMappingResolver()
        mappings = [self._mapping(system_filter="sys-hr")]
        claims = {"employee_id": "EMP-42"}

        headers = resolver.resolve_headers(mappings, claims, system_id="sys-hr")

        assert headers == {"X-Employee-ID": "EMP-42"}

    def test_system_filter_no_match(self):
        resolver = SSOAttributeMappingResolver()
        mappings = [self._mapping(system_filter="sys-hr")]
        claims = {"employee_id": "EMP-42"}

        headers = resolver.resolve_headers(mappings, claims, system_id="sys-crm")

        assert headers == {}

    def test_system_filter_none_applies_to_all(self):
        resolver = SSOAttributeMappingResolver()
        mappings = [self._mapping(system_filter=None)]
        claims = {"employee_id": "EMP-42"}

        headers = resolver.resolve_headers(mappings, claims, system_id="any-system")

        assert headers == {"X-Employee-ID": "EMP-42"}

    def test_missing_claim_returns_empty(self):
        resolver = SSOAttributeMappingResolver()
        mappings = [self._mapping(claim_path="nonexistent")]
        claims = {"employee_id": "EMP-42"}

        headers = resolver.resolve_headers(mappings, claims)

        assert headers == {}

    def test_multiple_mappings(self):
        resolver = SSOAttributeMappingResolver()
        mappings = [
            self._mapping(
                mapping_id="m1",
                claim_path="employee_id",
                target_header="X-Employee-ID",
            ),
            self._mapping(
                mapping_id="m2",
                claim_path="department",
                target_header="X-Department",
                transform="uppercase",
            ),
            self._mapping(
                mapping_id="m3",
                claim_path="custom.org_code",
                target_header="X-Org-Code",
            ),
        ]
        claims = {
            "employee_id": "EMP-42",
            "department": "engineering",
            "custom": {"org_code": "ORG-1"},
        }

        headers = resolver.resolve_headers(mappings, claims)

        assert headers == {
            "X-Employee-ID": "EMP-42",
            "X-Department": "ENGINEERING",
            "X-Org-Code": "ORG-1",
        }

    def test_query_param_type_excluded_from_headers(self):
        """Mappings with target_type=query_param are not returned as headers."""
        resolver = SSOAttributeMappingResolver()
        mappings = [
            self._mapping(target_type="query_param"),
        ]
        claims = {"employee_id": "EMP-42"}

        headers = resolver.resolve_headers(mappings, claims)

        assert headers == {}

    def test_empty_mappings(self):
        resolver = SSOAttributeMappingResolver()
        headers = resolver.resolve_headers([], {"employee_id": "EMP-42"})
        assert headers == {}

    def test_empty_claims(self):
        resolver = SSOAttributeMappingResolver()
        mappings = [self._mapping()]
        headers = resolver.resolve_headers(mappings, {})
        assert headers == {}
