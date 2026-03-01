# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""Parse OpenAPI 3.x specifications into knowledge documents."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import yaml

from flydesk.knowledge.models import DocumentType, KnowledgeDocument

_logger = logging.getLogger(__name__)


class OpenAPIParser:
    """Parse OpenAPI 3.x specs into structured knowledge documents.

    Creates one parent document with the API overview and one document
    per tag group (or per path if untagged) with endpoint details.
    """

    def parse(self, spec_content: str, spec_format: str = "json") -> list[KnowledgeDocument]:
        """Parse OpenAPI 3.x spec into structured documents.

        Args:
            spec_content: The raw spec content as a string.
            spec_format: Either ``"json"`` or ``"yaml"``.

        Returns:
            A list of :class:`KnowledgeDocument` instances -- one overview
            document followed by one document per tag group.
        """
        spec = self._load_spec(spec_content, spec_format)

        info = spec.get("info", {})
        api_title = info.get("title", "Untitled API")
        api_version = info.get("version", "")
        api_description = info.get("description", "")

        # Group endpoints by tag
        tag_groups: dict[str, list[str]] = {}
        paths = spec.get("paths", {})

        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method in ("get", "post", "put", "patch", "delete", "options", "head"):
                operation = path_item.get(method)
                if operation is None or not isinstance(operation, dict):
                    continue
                tags = operation.get("tags", ["Untagged"])
                endpoint_doc = self._parse_endpoint(path, method, operation)
                for tag in tags:
                    tag_groups.setdefault(tag, []).append(endpoint_doc)

        documents: list[KnowledgeDocument] = []

        # Overview document
        overview_lines = [f"# {api_title}"]
        if api_version:
            overview_lines.append(f"\n**Version:** {api_version}")
        if api_description:
            overview_lines.append(f"\n{api_description}")
        if tag_groups:
            overview_lines.append("\n## Endpoint Groups")
            for tag in sorted(tag_groups.keys()):
                count = len(tag_groups[tag])
                overview_lines.append(f"- **{tag}**: {count} endpoint(s)")

        overview_doc = KnowledgeDocument(
            id=str(uuid.uuid4()),
            title=f"{api_title} -- Overview",
            content="\n".join(overview_lines),
            document_type=DocumentType.API_SPEC,
            tags=["api", "openapi"],
            metadata={
                "api_title": api_title,
                "api_version": api_version,
                "parser": "openapi",
                "role": "overview",
            },
        )
        documents.append(overview_doc)

        # Per-tag documents
        for tag in sorted(tag_groups.keys()):
            endpoints = tag_groups[tag]
            tag_content = f"# {api_title} -- {tag}\n\n" + "\n\n".join(endpoints)

            tag_doc = KnowledgeDocument(
                id=str(uuid.uuid4()),
                title=f"{api_title} -- {tag}",
                content=tag_content,
                document_type=DocumentType.API_SPEC,
                tags=["api", "openapi", tag.lower()],
                metadata={
                    "api_title": api_title,
                    "api_version": api_version,
                    "parser": "openapi",
                    "tag": tag,
                },
            )
            documents.append(tag_doc)

        return documents

    def _parse_endpoint(self, path: str, method: str, operation: dict[str, Any]) -> str:
        """Format a single endpoint into readable documentation."""
        lines: list[str] = []

        summary = operation.get("summary", "")
        description = operation.get("description", "")

        lines.append(f"## {method.upper()} {path}")
        if summary:
            lines.append(summary)
        if description and description != summary:
            lines.append(f"\n{description}")

        # Parameters
        parameters = operation.get("parameters", [])
        if parameters:
            lines.append("\n### Parameters")
            for param in parameters:
                if not isinstance(param, dict):
                    continue
                name = param.get("name", "?")
                location = param.get("in", "?")
                schema = param.get("schema", {})
                ptype = schema.get("type", "string") if isinstance(schema, dict) else "string"
                desc = param.get("description", "")
                required = param.get("required", False)
                req_marker = " (required)" if required else ""
                lines.append(f"- `{name}` ({location}, {ptype}){req_marker}: {desc}")

        # Request body
        request_body = operation.get("requestBody", {})
        if isinstance(request_body, dict) and request_body:
            lines.append("\n### Request Body")
            rb_desc = request_body.get("description", "")
            if rb_desc:
                lines.append(rb_desc)
            content = request_body.get("content", {})
            for media_type, media_obj in content.items():
                if not isinstance(media_obj, dict):
                    continue
                schema = media_obj.get("schema", {})
                lines.append(f"\n**Content-Type:** `{media_type}`")
                lines.append(self._format_schema(schema))

        # Responses
        responses = operation.get("responses", {})
        if responses:
            lines.append("\n### Response")
            for status_code, resp_obj in sorted(responses.items()):
                if not isinstance(resp_obj, dict):
                    continue
                resp_desc = resp_obj.get("description", "")
                lines.append(f"- {status_code}: {resp_desc}")

        return "\n".join(lines)

    def _format_schema(self, schema: dict[str, Any]) -> str:
        """Format a JSON Schema object into a readable description."""
        if not isinstance(schema, dict):
            return ""
        schema_type = schema.get("type", "object")
        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])

        if not properties:
            return f"Type: `{schema_type}`"

        lines = [f"Type: `{schema_type}`\n"]
        lines.append("| Field | Type | Required | Description |")
        lines.append("|-------|------|----------|-------------|")

        for field_name, field_schema in properties.items():
            if not isinstance(field_schema, dict):
                continue
            ftype = field_schema.get("type", "any")
            fdesc = field_schema.get("description", "")
            freq = "Yes" if field_name in required_fields else "No"
            lines.append(f"| `{field_name}` | {ftype} | {freq} | {fdesc} |")

        return "\n".join(lines)

    @staticmethod
    def _load_spec(content: str, spec_format: str) -> dict[str, Any]:
        """Load a spec string into a dict, handling both JSON and YAML.

        Raises:
            ValueError: If the content cannot be parsed as JSON or YAML.
        """
        if spec_format == "json":
            try:
                return json.loads(content)  # type: ignore[no-any-return]
            except json.JSONDecodeError:
                # Fallback: try YAML in case the caller mislabelled the format
                _logger.debug("JSON parse failed for spec labelled as JSON; trying YAML")
        try:
            result = yaml.safe_load(content)
            if isinstance(result, dict):
                return result
        except yaml.YAMLError:
            _logger.debug("YAML parse also failed for spec content")
        raise ValueError("Failed to parse spec as JSON or YAML")
