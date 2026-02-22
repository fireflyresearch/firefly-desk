# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Parse widget directives from agent markdown output."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from flydesk.widgets.schema import WidgetDirective, WidgetDisplay

# Matches :::widget{attrs}\n{json}\n:::
_WIDGET_PATTERN = re.compile(
    r':::widget\{([^}]+)\}\s*\n(.*?)\n:::', re.DOTALL
)

# Matches key=value or key="value" pairs
_ATTR_PATTERN = re.compile(r'(\w+)=(?:"([^"]+)"|(\S+))')


@dataclass
class ParseResult:
    """Result of parsing agent output for widget directives."""

    text_segments: list[str] = field(default_factory=list)
    widgets: list[WidgetDirective] = field(default_factory=list)


class WidgetParser:
    """Parse :::widget{...} directives from markdown text."""

    @staticmethod
    def parse(text: str) -> ParseResult:
        result = ParseResult()
        last_end = 0

        for match in _WIDGET_PATTERN.finditer(text):
            # Text before this widget
            before = text[last_end:match.start()].strip()
            if before:
                result.text_segments.append(before)

            attrs_str = match.group(1)
            json_str = match.group(2).strip()

            attrs = WidgetParser._parse_attrs(attrs_str)
            props = json.loads(json_str) if json_str else {}

            display = WidgetDisplay.INLINE
            if attrs.get("panel") in ("true", True):
                display = WidgetDisplay.PANEL
            elif attrs.get("inline") in ("true", True):
                display = WidgetDisplay.INLINE

            directive = WidgetDirective(
                type=attrs.get("type", "unknown"),
                props=props,
                display=display,
                blocking=attrs.get("blocking") in ("true", True),
                action=attrs.get("action"),
            )
            result.widgets.append(directive)
            last_end = match.end()

        # Text after the last widget
        after = text[last_end:].strip()
        if after:
            result.text_segments.append(after)

        return result

    @staticmethod
    def _parse_attrs(attrs_str: str) -> dict[str, str]:
        attrs: dict[str, str] = {}
        for m in _ATTR_PATTERN.finditer(attrs_str):
            key = m.group(1)
            value = m.group(2) if m.group(2) is not None else m.group(3)
            attrs[key] = value
        return attrs
