# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for the deterministic curl command parser."""

from __future__ import annotations

import pytest

from flydesk.catalog.curl_parser import ParsedCurl, parse_curl


class TestParseCurl:
    """Unit tests for parse_curl()."""

    def test_simple_get(self):
        result = parse_curl("curl https://api.example.com/users")
        assert result.method == "GET"
        assert result.url == "https://api.example.com/users"
        assert result.headers == {}
        assert result.body is None
        assert result.query_params == {}

    def test_post_with_body(self):
        result = parse_curl(
            'curl -X POST https://api.example.com/users -d \'{"name": "Alice"}\''
        )
        assert result.method == "POST"
        assert result.url == "https://api.example.com/users"
        assert result.body == '{"name": "Alice"}'

    def test_multiple_headers(self):
        result = parse_curl(
            "curl https://api.example.com/users "
            "-H 'Content-Type: application/json' "
            "-H 'Authorization: Bearer tok123'"
        )
        assert result.headers == {
            "Content-Type": "application/json",
            "Authorization": "Bearer tok123",
        }

    def test_query_params_extracted(self):
        result = parse_curl(
            "curl 'https://api.example.com/search?q=hello&limit=10'"
        )
        assert result.method == "GET"
        assert result.url == "https://api.example.com/search"
        assert result.query_params == {"q": "hello", "limit": "10"}

    def test_put_method(self):
        result = parse_curl(
            "curl -X PUT https://api.example.com/users/1 "
            "-d '{\"name\": \"Bob\"}'"
        )
        assert result.method == "PUT"
        assert result.url == "https://api.example.com/users/1"
        assert result.body == '{"name": "Bob"}'

    def test_data_implies_post(self):
        result = parse_curl(
            "curl https://api.example.com/users -d '{\"name\": \"Eve\"}'"
        )
        assert result.method == "POST"
        assert result.body == '{"name": "Eve"}'

    def test_multiline_curl(self):
        cmd = (
            "curl \\\n"
            "  -X POST \\\n"
            "  https://api.example.com/data \\\n"
            "  -H 'Content-Type: application/json' \\\n"
            "  -d '{\"key\": \"value\"}'"
        )
        result = parse_curl(cmd)
        assert result.method == "POST"
        assert result.url == "https://api.example.com/data"
        assert result.headers == {"Content-Type": "application/json"}
        assert result.body == '{"key": "value"}'

    def test_double_quoted_headers(self):
        result = parse_curl(
            'curl https://api.example.com/users '
            '-H "Accept: text/html" '
            '-H "X-Custom: my-value"'
        )
        assert result.headers == {
            "Accept": "text/html",
            "X-Custom": "my-value",
        }

    def test_empty_string_raises(self):
        with pytest.raises(ValueError, match="Empty curl command"):
            parse_curl("")

    def test_no_url_raises(self):
        with pytest.raises(ValueError, match="No URL found"):
            parse_curl("curl -X GET")
