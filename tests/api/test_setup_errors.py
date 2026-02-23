# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for _friendly_error helper and user-friendly error messages in setup endpoints."""

from __future__ import annotations

import pytest

from flydesk.api.setup import _friendly_error


class TestFriendlyError:
    """Unit tests for the _friendly_error helper."""

    # -- Connection refused --------------------------------------------------

    def test_connection_refused(self):
        exc = Exception("Connection refused")
        result = _friendly_error(exc, "LLM provider")
        assert "Could not connect to the LLM provider server" in result
        assert "ensure the service is running" in result

    def test_connect_error(self):
        exc = Exception(
            "ConnectError: [Errno 111] Connection refused"
        )
        result = _friendly_error(exc, "embedding provider")
        assert "Could not connect to the embedding provider server" in result

    # -- Authentication / API key -------------------------------------------

    def test_401_unauthorized(self):
        exc = Exception("Status 401: Unauthorized")
        result = _friendly_error(exc, "LLM provider")
        assert "Authentication failed" in result
        assert "LLM provider API key" in result

    def test_invalid_api_key(self):
        exc = Exception("Error: invalid_api_key")
        result = _friendly_error(exc, "embedding provider")
        assert "Authentication failed" in result
        assert "embedding provider API key" in result

    def test_unauthorized_keyword(self):
        exc = Exception("Unauthorized access to resource")
        result = _friendly_error(exc, "database")
        assert "Authentication failed" in result

    # -- Forbidden -----------------------------------------------------------

    def test_403_forbidden(self):
        exc = Exception("HTTP 403: Forbidden")
        result = _friendly_error(exc, "LLM provider")
        assert "Access denied" in result
        assert "permissions for LLM provider" in result

    def test_forbidden_keyword(self):
        exc = Exception("Forbidden: insufficient scope")
        result = _friendly_error(exc, "embedding provider")
        assert "Access denied" in result

    # -- Not found -----------------------------------------------------------

    def test_404_not_found(self):
        exc = Exception("HTTP 404: Not Found")
        result = _friendly_error(exc, "LLM provider")
        assert "endpoint was not found" in result
        assert "check the URL" in result

    # -- Timeout -------------------------------------------------------------

    def test_timeout_lowercase(self):
        exc = Exception("Connection timeout after 30s")
        result = _friendly_error(exc, "database")
        assert "timed out" in result
        assert "try again" in result

    def test_timeout_uppercase(self):
        exc = Exception("ReadTimeout: pool timeout exceeded")
        result = _friendly_error(exc, "embedding provider")
        assert "timed out" in result

    def test_timeout_mixed_case(self):
        exc = Exception("ConnectTimeoutError")
        result = _friendly_error(exc, "LLM provider")
        assert "timed out" in result

    # -- SSL / certificate ---------------------------------------------------

    def test_ssl_error(self):
        exc = Exception("SSL: CERTIFICATE_VERIFY_FAILED")
        result = _friendly_error(exc, "LLM provider")
        assert "SSL/TLS error" in result
        assert "certificate configuration" in result

    def test_certificate_lowercase(self):
        exc = Exception("certificate verify failed: unable to get local issuer")
        result = _friendly_error(exc, "database")
        assert "SSL/TLS error" in result

    # -- DNS resolution ------------------------------------------------------

    def test_name_not_known(self):
        exc = Exception("Name or service not known")
        result = _friendly_error(exc, "LLM provider")
        assert "Could not resolve" in result
        assert "hostname" in result

    def test_getaddrinfo(self):
        exc = Exception("getaddrinfo failed: nodename nor servname provided")
        result = _friendly_error(exc, "embedding provider")
        assert "Could not resolve" in result
        assert "hostname" in result

    # -- Fallback ------------------------------------------------------------

    def test_fallback_includes_context(self):
        exc = Exception("Some obscure library error")
        result = _friendly_error(exc, "database")
        assert result.startswith("database error:")
        assert "Some obscure library error" in result

    def test_fallback_truncates_long_messages(self):
        long_msg = "x" * 500
        exc = Exception(long_msg)
        result = _friendly_error(exc, "LLM provider")
        # The fallback truncates to 200 chars of the first line
        assert len(result) <= len("LLM provider error: ") + 200

    def test_fallback_takes_first_line_only(self):
        exc = Exception("First line\nSecond line\nThird line")
        result = _friendly_error(exc, "database")
        assert "First line" in result
        assert "Second line" not in result

    # -- Priority / ordering -------------------------------------------------

    def test_connection_refused_takes_priority_over_fallback(self):
        """Ensure specific patterns are matched before fallback."""
        exc = Exception("Connection refused on port 5432")
        result = _friendly_error(exc, "database")
        assert "Could not connect" in result
        assert "database error:" not in result

    def test_401_in_longer_message(self):
        exc = Exception(
            "HTTPSConnectionPool(host='api.openai.com', port=443): "
            "Max retries exceeded - 401 Client Error"
        )
        result = _friendly_error(exc, "LLM provider")
        assert "Authentication failed" in result


class TestFriendlyErrorContextVariation:
    """Verify that the context parameter is properly interpolated."""

    @pytest.mark.parametrize(
        "context",
        ["LLM provider", "embedding provider", "database"],
    )
    def test_context_appears_in_connection_refused(self, context):
        exc = Exception("Connection refused")
        result = _friendly_error(exc, context)
        assert context in result

    @pytest.mark.parametrize(
        "context",
        ["LLM provider", "embedding provider", "database"],
    )
    def test_context_appears_in_auth_failure(self, context):
        exc = Exception("401 Unauthorized")
        result = _friendly_error(exc, context)
        assert context in result

    @pytest.mark.parametrize(
        "context",
        ["LLM provider", "embedding provider", "database"],
    )
    def test_context_appears_in_fallback(self, context):
        exc = Exception("some random error")
        result = _friendly_error(exc, context)
        assert context in result
