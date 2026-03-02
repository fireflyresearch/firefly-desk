# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Deterministic curl command parser.

Parses a curl command string into structured components (method, URL,
headers, body, query params). No LLM involved — pure string parsing.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlparse, urlunparse


@dataclass
class ParsedCurl:
    """Parsed components of a curl command."""

    method: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    body: str | None = None
    query_params: dict[str, str] = field(default_factory=dict)


def parse_curl(command: str) -> ParsedCurl:
    """Parse a curl command string into a ParsedCurl."""
    if not command or not command.strip():
        raise ValueError("Empty curl command")

    normalized = command.replace("\\\n", " ").replace("\\\r\n", " ").strip()
    tokens = shlex.split(normalized)

    if tokens and tokens[0] == "curl":
        tokens = tokens[1:]

    method: str | None = None
    url: str | None = None
    headers: dict[str, str] = {}
    body: str | None = None

    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-X", "--request") and i + 1 < len(tokens):
            method = tokens[i + 1].upper()
            i += 2
        elif tok in ("-H", "--header") and i + 1 < len(tokens):
            header_val = tokens[i + 1]
            if ":" in header_val:
                key, val = header_val.split(":", 1)
                headers[key.strip()] = val.strip()
            i += 2
        elif tok in ("-d", "--data", "--data-raw", "--data-binary") and i + 1 < len(tokens):
            body = tokens[i + 1]
            i += 2
        elif not tok.startswith("-"):
            url = tok
            i += 1
        else:
            if i + 1 < len(tokens) and not tokens[i + 1].startswith("-") and not tokens[i + 1].startswith("http"):
                i += 2
            else:
                i += 1

    if url is None:
        raise ValueError("No URL found in curl command")

    if method is None:
        method = "POST" if body else "GET"

    parsed = urlparse(url)
    query_params: dict[str, str] = {}
    if parsed.query:
        for key, values in parse_qs(parsed.query).items():
            query_params[key] = values[0]
        url = urlunparse(parsed._replace(query=""))

    return ParsedCurl(method=method, url=url, headers=headers, body=body, query_params=query_params)
