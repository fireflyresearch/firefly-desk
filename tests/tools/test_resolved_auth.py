"""Tests for ResolvedAuth dataclass."""

from __future__ import annotations

from flydesk.tools.auth_resolver import ResolvedAuth


class TestResolvedAuth:
    def test_create_with_defaults(self):
        ra = ResolvedAuth(headers={"Authorization": "Bearer tok"})
        assert ra.headers == {"Authorization": "Bearer tok"}
        assert ra.query_params == {}
        assert ra.path_params == {}
        assert ra.body_params == {}

    def test_create_with_all_fields(self):
        ra = ResolvedAuth(
            headers={"Authorization": "Bearer tok"},
            query_params={"api_key": "abc"},
            path_params={"tenant_id": "t1"},
            body_params={"secret": "xyz"},
        )
        assert ra.query_params["api_key"] == "abc"
        assert ra.path_params["tenant_id"] == "t1"
        assert ra.body_params["secret"] == "xyz"

    def test_empty_resolved_auth(self):
        ra = ResolvedAuth()
        assert ra.headers == {}
        assert ra.query_params == {}
        assert ra.path_params == {}
        assert ra.body_params == {}
