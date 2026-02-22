# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for widget directive parser."""

from __future__ import annotations

from flydek.widgets.parser import WidgetParser
from flydek.widgets.schema import WidgetDisplay


class TestWidgetParser:
    def test_parse_inline_widget(self):
        text = (
            'Some text before.\n\n'
            ':::widget{type="status-badge" inline=true}\n'
            '{"status": "active", "label": "Active"}\n'
            ':::\n\n'
            'Some text after.'
        )
        result = WidgetParser.parse(text)
        assert len(result.widgets) == 1
        assert result.widgets[0].type == "status-badge"
        assert result.widgets[0].display == WidgetDisplay.INLINE
        assert result.widgets[0].props["status"] == "active"
        assert "Some text before." in result.text_segments[0]
        assert "Some text after." in result.text_segments[1]

    def test_parse_panel_widget(self):
        text = (
            ':::widget{type="data-table" panel=true}\n'
            '{"title": "Transactions", "columns": ["Date", "Amount"]}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert len(result.widgets) == 1
        assert result.widgets[0].display == WidgetDisplay.PANEL
        assert result.widgets[0].props["title"] == "Transactions"

    def test_parse_blocking_confirmation(self):
        text = (
            ':::widget{type="confirmation" action="update-email" blocking=true}\n'
            '{"system": "CRM", "changes": []}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert result.widgets[0].blocking is True
        assert result.widgets[0].action == "update-email"

    def test_parse_no_widgets(self):
        text = "Just plain markdown with no widgets."
        result = WidgetParser.parse(text)
        assert len(result.widgets) == 0
        assert result.text_segments == ["Just plain markdown with no widgets."]

    def test_parse_multiple_widgets(self):
        text = (
            'Text 1\n\n'
            ':::widget{type="alert" inline=true}\n'
            '{"level": "info", "message": "Hello"}\n'
            ':::\n\n'
            'Text 2\n\n'
            ':::widget{type="key-value" inline=true}\n'
            '{"pairs": [["Name", "John"]]}\n'
            ':::\n\n'
            'Text 3'
        )
        result = WidgetParser.parse(text)
        assert len(result.widgets) == 2
        assert len(result.text_segments) == 3
