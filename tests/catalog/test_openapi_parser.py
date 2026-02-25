# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for OpenAPI spec parser."""

from __future__ import annotations

import pytest

from flydesk.catalog.openapi_parser import ParsedAPI, ParsedEndpoint, parse_openapi_spec


SAMPLE_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "Pet Store API",
        "description": "A sample pet store API",
        "version": "1.0.0",
    },
    "servers": [{"url": "https://petstore.example.com/v1"}],
    "components": {
        "securitySchemes": {
            "oauth2": {
                "type": "oauth2",
                "flows": {
                    "clientCredentials": {
                        "tokenUrl": "https://auth.example.com/token",
                        "scopes": {"read": "Read access"},
                    }
                },
            }
        }
    },
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "tags": ["pets"],
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "description": "Max items to return",
                        "schema": {"type": "integer"},
                    }
                ],
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "tag": {"type": "string"},
                                },
                            }
                        }
                    }
                },
            },
        },
        "/pets/{petId}": {
            "parameters": [
                {
                    "name": "petId",
                    "in": "path",
                    "required": True,
                    "description": "The pet ID",
                    "schema": {"type": "string"},
                }
            ],
            "get": {
                "operationId": "showPetById",
                "summary": "Info for a specific pet",
            },
        },
    },
}


class TestParseOpenAPISpec:
    def test_parses_info(self):
        result = parse_openapi_spec(SAMPLE_SPEC)
        assert result.title == "Pet Store API"
        assert result.description == "A sample pet store API"
        assert result.version == "1.0.0"

    def test_parses_base_url(self):
        result = parse_openapi_spec(SAMPLE_SPEC)
        assert result.base_url == "https://petstore.example.com/v1"

    def test_parses_auth_schemes(self):
        result = parse_openapi_spec(SAMPLE_SPEC)
        assert len(result.auth_schemes) == 1
        assert result.auth_schemes[0]["name"] == "oauth2"
        assert result.auth_schemes[0]["type"] == "oauth2"

    def test_parses_all_endpoints(self):
        result = parse_openapi_spec(SAMPLE_SPEC)
        assert len(result.endpoints) == 3  # listPets, createPet, showPetById

    def test_get_with_query_params(self):
        result = parse_openapi_spec(SAMPLE_SPEC)
        list_pets = next(e for e in result.endpoints if e.operation_id == "listPets")
        assert list_pets.method == "GET"
        assert list_pets.path == "/pets"
        assert len(list_pets.parameters) == 1
        assert list_pets.parameters[0]["name"] == "limit"
        assert list_pets.parameters[0]["in"] == "query"
        assert list_pets.parameters[0]["type"] == "integer"

    def test_post_with_request_body(self):
        result = parse_openapi_spec(SAMPLE_SPEC)
        create_pet = next(e for e in result.endpoints if e.operation_id == "createPet")
        assert create_pet.method == "POST"
        assert create_pet.request_body_schema is not None
        assert "name" in create_pet.request_body_schema["properties"]

    def test_path_params_inherited(self):
        result = parse_openapi_spec(SAMPLE_SPEC)
        show_pet = next(e for e in result.endpoints if e.operation_id == "showPetById")
        assert show_pet.method == "GET"
        assert len(show_pet.parameters) == 1
        assert show_pet.parameters[0]["name"] == "petId"
        assert show_pet.parameters[0]["in"] == "path"
        assert show_pet.parameters[0]["required"] is True

    def test_missing_title_raises(self):
        with pytest.raises(ValueError, match="info.title"):
            parse_openapi_spec({"info": {}})

    def test_empty_spec_raises(self):
        with pytest.raises(ValueError):
            parse_openapi_spec({})

    def test_no_servers_gives_empty_base_url(self):
        spec = {"info": {"title": "Minimal"}}
        result = parse_openapi_spec(spec)
        assert result.base_url == ""
        assert result.endpoints == []
