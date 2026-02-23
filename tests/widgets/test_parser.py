# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Tests for widget directive parser."""

from __future__ import annotations

from flydesk.widgets.parser import WidgetParser
from flydesk.widgets.schema import WidgetDisplay


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

    # -----------------------------------------------------------------
    # Mermaid diagram
    # -----------------------------------------------------------------

    def test_parse_mermaid_diagram(self):
        text = (
            'Here is a diagram:\n\n'
            ':::widget{type="mermaid-diagram" inline=true}\n'
            '{"code": "graph TD\\n  A[Start] --> B[End]", "title": "Process Flow"}\n'
            ':::\n\n'
            'Explanation follows.'
        )
        result = WidgetParser.parse(text)
        assert len(result.widgets) == 1
        assert result.widgets[0].type == "mermaid-diagram"
        assert result.widgets[0].display == WidgetDisplay.INLINE
        assert "graph TD" in result.widgets[0].props["code"]
        assert result.widgets[0].props["title"] == "Process Flow"
        assert "Here is a diagram:" in result.text_segments[0]
        assert "Explanation follows." in result.text_segments[1]

    def test_parse_mermaid_diagram_panel(self):
        text = (
            ':::widget{type="mermaid-diagram" panel=true}\n'
            '{"code": "sequenceDiagram\\n  Alice->>Bob: Hello"}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert result.widgets[0].type == "mermaid-diagram"
        assert result.widgets[0].display == WidgetDisplay.PANEL
        assert "sequenceDiagram" in result.widgets[0].props["code"]

    # -----------------------------------------------------------------
    # Citation card
    # -----------------------------------------------------------------

    def test_parse_citation_card(self):
        text = (
            ':::widget{type="citation-card" inline=true}\n'
            '{"source_title": "Employee Handbook", "snippet": "Annual leave policy...", "score": 0.92}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert len(result.widgets) == 1
        assert result.widgets[0].type == "citation-card"
        assert result.widgets[0].props["source_title"] == "Employee Handbook"
        assert result.widgets[0].props["snippet"] == "Annual leave policy..."
        assert result.widgets[0].props["score"] == 0.92

    def test_parse_citation_card_with_url(self):
        text = (
            ':::widget{type="citation-card" inline=true}\n'
            '{"source_title": "KB Article", "snippet": "Reset your password by...", '
            '"source_url": "https://kb.example.com/article/123", "document_id": "doc-abc"}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert result.widgets[0].props["source_url"] == "https://kb.example.com/article/123"
        assert result.widgets[0].props["document_id"] == "doc-abc"

    # -----------------------------------------------------------------
    # Progress bar
    # -----------------------------------------------------------------

    def test_parse_progress_bar(self):
        text = (
            ':::widget{type="progress-bar" inline=true}\n'
            '{"value": 75, "max": 100, "label": "Upload Progress", "variant": "success"}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert len(result.widgets) == 1
        assert result.widgets[0].type == "progress-bar"
        assert result.widgets[0].props["value"] == 75
        assert result.widgets[0].props["max"] == 100
        assert result.widgets[0].props["label"] == "Upload Progress"
        assert result.widgets[0].props["variant"] == "success"

    def test_parse_progress_bar_indeterminate(self):
        text = (
            ':::widget{type="progress-bar" inline=true}\n'
            '{"value": null, "label": "Processing..."}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert result.widgets[0].type == "progress-bar"
        assert result.widgets[0].props["value"] is None
        assert result.widgets[0].props["label"] == "Processing..."

    # -----------------------------------------------------------------
    # Accordion
    # -----------------------------------------------------------------

    def test_parse_accordion(self):
        text = (
            ':::widget{type="accordion" inline=true}\n'
            '{"sections": [{"title": "FAQ 1", "content": "Answer 1."}, '
            '{"title": "FAQ 2", "content": "Answer 2."}], "defaultOpen": 0}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert len(result.widgets) == 1
        assert result.widgets[0].type == "accordion"
        assert len(result.widgets[0].props["sections"]) == 2
        assert result.widgets[0].props["sections"][0]["title"] == "FAQ 1"
        assert result.widgets[0].props["sections"][1]["content"] == "Answer 2."
        assert result.widgets[0].props["defaultOpen"] == 0

    def test_parse_accordion_multiple_defaults(self):
        text = (
            ':::widget{type="accordion" inline=true}\n'
            '{"sections": [{"title": "A", "content": "Content A"}, '
            '{"title": "B", "content": "Content B"}, '
            '{"title": "C", "content": "Content C"}], "defaultOpen": [0, 2]}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert result.widgets[0].props["defaultOpen"] == [0, 2]
        assert len(result.widgets[0].props["sections"]) == 3

    # -----------------------------------------------------------------
    # Metric card
    # -----------------------------------------------------------------

    def test_parse_metric_card(self):
        text = (
            ':::widget{type="metric-card" inline=true}\n'
            '{"metrics": [{"label": "Users", "value": "1,234"}]}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert len(result.widgets) == 1
        assert result.widgets[0].type == "metric-card"
        assert result.widgets[0].display == WidgetDisplay.INLINE
        assert len(result.widgets[0].props["metrics"]) == 1
        assert result.widgets[0].props["metrics"][0]["label"] == "Users"
        assert result.widgets[0].props["metrics"][0]["value"] == "1,234"

    def test_parse_metric_card_with_trend(self):
        text = (
            ':::widget{type="metric-card" inline=true}\n'
            '{"metrics": [{"label": "Revenue", "value": "$12.5k", "delta": "+15%", "trend": "up"}, '
            '{"label": "Errors", "value": "3", "delta": "-2", "trend": "down"}]}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert result.widgets[0].type == "metric-card"
        metrics = result.widgets[0].props["metrics"]
        assert len(metrics) == 2
        assert metrics[0]["delta"] == "+15%"
        assert metrics[0]["trend"] == "up"
        assert metrics[1]["trend"] == "down"

    # -----------------------------------------------------------------
    # Code block
    # -----------------------------------------------------------------

    def test_parse_code_block(self):
        text = (
            ':::widget{type="code-block" inline=true}\n'
            '{"code": "print(42)", "language": "python", "title": "Example"}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert len(result.widgets) == 1
        assert result.widgets[0].type == "code-block"
        assert result.widgets[0].props["code"] == "print(42)"
        assert result.widgets[0].props["language"] == "python"
        assert result.widgets[0].props["title"] == "Example"

    def test_parse_code_block_minimal(self):
        text = (
            ':::widget{type="code-block" inline=true}\n'
            '{"code": "SELECT * FROM users;"}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert result.widgets[0].type == "code-block"
        assert result.widgets[0].props["code"] == "SELECT * FROM users;"
        assert "language" not in result.widgets[0].props

    # -----------------------------------------------------------------
    # Action buttons
    # -----------------------------------------------------------------

    def test_parse_action_buttons(self):
        text = (
            ':::widget{type="action-buttons" inline=true}\n'
            '{"actions": [{"label": "Show details", "message": "Show me details"}, '
            '{"label": "Export", "message": "Export as CSV", "variant": "primary"}]}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert len(result.widgets) == 1
        assert result.widgets[0].type == "action-buttons"
        actions = result.widgets[0].props["actions"]
        assert len(actions) == 2
        assert actions[0]["label"] == "Show details"
        assert actions[0]["message"] == "Show me details"
        assert actions[1]["variant"] == "primary"

    def test_parse_action_buttons_single(self):
        text = (
            ':::widget{type="action-buttons" inline=true}\n'
            '{"actions": [{"label": "Try again", "message": "Retry the last operation"}]}\n'
            ':::'
        )
        result = WidgetParser.parse(text)
        assert result.widgets[0].type == "action-buttons"
        assert len(result.widgets[0].props["actions"]) == 1
        assert result.widgets[0].props["actions"][0]["message"] == "Retry the last operation"
