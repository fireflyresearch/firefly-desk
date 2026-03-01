# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for OpenAPIParser."""

from __future__ import annotations

import json

import pytest

from flydesk.knowledge.models import DocumentType
from flydesk.knowledge.openapi_parser import OpenAPIParser

MINIMAL_SPEC: dict = {
    "openapi": "3.0.3",
    "info": {"title": "Pet Store API", "version": "1.0.0", "description": "A sample pet store."},
    "paths": {
        "/pets": {
            "get": {
                "tags": ["Pets"],
                "summary": "List all pets",
                "operationId": "listPets",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {"type": "integer"},
                        "description": "Max items to return",
                    }
                ],
                "responses": {
                    "200": {"description": "A list of pets"},
                    "400": {"description": "Bad request"},
                },
            },
            "post": {
                "tags": ["Pets"],
                "summary": "Create a pet",
                "operationId": "createPet",
                "requestBody": {
                    "description": "Pet to add",
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["name"],
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Name of the pet",
                                    },
                                    "tag": {
                                        "type": "string",
                                        "description": "Optional tag",
                                    },
                                },
                            }
                        }
                    },
                },
                "responses": {"201": {"description": "Pet created"}},
            },
        },
        "/pets/{petId}": {
            "get": {
                "tags": ["Pets"],
                "summary": "Get a pet by ID",
                "parameters": [
                    {
                        "name": "petId",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                        "description": "The pet ID",
                    }
                ],
                "responses": {
                    "200": {"description": "A pet"},
                    "404": {"description": "Pet not found"},
                },
            }
        },
        "/health": {
            "get": {
                "tags": ["System"],
                "summary": "Health check",
                "responses": {"200": {"description": "OK"}},
            }
        },
    },
}

UNTAGGED_SPEC: dict = {
    "openapi": "3.0.0",
    "info": {"title": "Simple API", "version": "0.1.0"},
    "paths": {
        "/status": {
            "get": {
                "summary": "Get status",
                "responses": {"200": {"description": "Status OK"}},
            }
        },
        "/data": {
            "post": {
                "summary": "Post data",
                "responses": {"201": {"description": "Created"}},
            }
        },
    },
}


@pytest.fixture
def parser() -> OpenAPIParser:
    return OpenAPIParser()


class TestOpenAPIParser:
    def test_parse_valid_spec_returns_documents(self, parser: OpenAPIParser):
        """Parsing a valid spec returns overview + per-tag documents."""
        docs = parser.parse(json.dumps(MINIMAL_SPEC))

        # Overview + Pets + System = 3 documents
        assert len(docs) == 3
        assert all(d.document_type == DocumentType.API_SPEC for d in docs)

    def test_overview_document_content(self, parser: OpenAPIParser):
        """Overview document contains API title, version, and description."""
        docs = parser.parse(json.dumps(MINIMAL_SPEC))
        overview = docs[0]

        assert overview.title == "Pet Store API -- Overview"
        assert "Pet Store API" in overview.content
        assert "1.0.0" in overview.content
        assert "A sample pet store." in overview.content
        assert overview.metadata["role"] == "overview"

    def test_endpoints_grouped_by_tag(self, parser: OpenAPIParser):
        """Endpoints are grouped into tag-based documents."""
        docs = parser.parse(json.dumps(MINIMAL_SPEC))

        # Find the Pets tag document
        pets_doc = next(d for d in docs if d.title == "Pet Store API -- Pets")
        assert "GET /pets" in pets_doc.content
        assert "POST /pets" in pets_doc.content
        assert "GET /pets/{petId}" in pets_doc.content

        # Find the System tag document
        system_doc = next(d for d in docs if d.title == "Pet Store API -- System")
        assert "GET /health" in system_doc.content

    def test_untagged_endpoints_grouped_as_untagged(self, parser: OpenAPIParser):
        """Endpoints without tags are grouped under 'Untagged'."""
        docs = parser.parse(json.dumps(UNTAGGED_SPEC))

        # Overview + Untagged = 2 documents
        assert len(docs) == 2
        untagged = docs[1]
        assert untagged.title == "Simple API -- Untagged"
        assert "GET /status" in untagged.content
        assert "POST /data" in untagged.content

    def test_parameters_rendered(self, parser: OpenAPIParser):
        """Endpoint parameters are included in the output."""
        docs = parser.parse(json.dumps(MINIMAL_SPEC))
        pets_doc = next(d for d in docs if d.title == "Pet Store API -- Pets")

        assert "`limit`" in pets_doc.content
        assert "query" in pets_doc.content
        assert "Max items to return" in pets_doc.content
        assert "`petId`" in pets_doc.content
        assert "(required)" in pets_doc.content

    def test_request_body_rendered(self, parser: OpenAPIParser):
        """Request body schema is included in the output."""
        docs = parser.parse(json.dumps(MINIMAL_SPEC))
        pets_doc = next(d for d in docs if d.title == "Pet Store API -- Pets")

        assert "Request Body" in pets_doc.content
        assert "Pet to add" in pets_doc.content
        assert "`name`" in pets_doc.content
        assert "`application/json`" in pets_doc.content

    def test_responses_rendered(self, parser: OpenAPIParser):
        """Response status codes and descriptions are included."""
        docs = parser.parse(json.dumps(MINIMAL_SPEC))
        pets_doc = next(d for d in docs if d.title == "Pet Store API -- Pets")

        assert "200:" in pets_doc.content
        assert "A list of pets" in pets_doc.content
        assert "400:" in pets_doc.content
        assert "Bad request" in pets_doc.content

    def test_yaml_format(self, parser: OpenAPIParser):
        """Parser handles YAML format specs."""
        import yaml

        yaml_content = yaml.dump(MINIMAL_SPEC)
        docs = parser.parse(yaml_content, spec_format="yaml")

        assert len(docs) == 3
        assert docs[0].title == "Pet Store API -- Overview"

    def test_invalid_json_raises_value_error(self, parser: OpenAPIParser):
        """Malformed JSON raises ValueError."""
        with pytest.raises(ValueError):
            parser.parse("not valid json at all {{{")


    def test_empty_paths(self, parser: OpenAPIParser):
        """Spec with no paths returns only the overview document."""
        spec = {"openapi": "3.0.0", "info": {"title": "Empty API", "version": "0.0.1"}}
        docs = parser.parse(json.dumps(spec))

        assert len(docs) == 1
        assert docs[0].title == "Empty API -- Overview"

    def test_all_documents_have_api_tags(self, parser: OpenAPIParser):
        """All documents are tagged with 'api' and 'openapi'."""
        docs = parser.parse(json.dumps(MINIMAL_SPEC))
        for doc in docs:
            assert "api" in doc.tags
            assert "openapi" in doc.tags
