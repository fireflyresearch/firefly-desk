# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0

"""Tests for Service Catalog domain models."""

from __future__ import annotations

from flydek.catalog.enums import AuthType, HttpMethod, RiskLevel, SystemStatus
from flydek.catalog.models import AuthConfig, ExternalSystem, ParamSchema, ServiceEndpoint


class TestExternalSystem:
    def test_create_system(self):
        system = ExternalSystem(
            id="crm-salesforce",
            name="Salesforce CRM",
            description="Customer relationship management",
            base_url="https://api.salesforce.com/v55",
            auth_config=AuthConfig(
                auth_type=AuthType.OAUTH2,
                credential_id="cred-sf-001",
                token_url="https://login.salesforce.com/services/oauth2/token",
            ),
            tags=["crm", "customers"],
        )
        assert system.id == "crm-salesforce"
        assert system.status == SystemStatus.ACTIVE
        assert system.auth_config.auth_type == AuthType.OAUTH2

    def test_system_defaults(self):
        system = ExternalSystem(
            id="test",
            name="Test",
            description="Test system",
            base_url="https://test.example.com",
            auth_config=AuthConfig(auth_type=AuthType.API_KEY, credential_id="c1"),
        )
        assert system.status == SystemStatus.ACTIVE
        assert system.tags == []
        assert system.health_check_path is None
        assert system.metadata == {}


class TestServiceEndpoint:
    def test_create_endpoint(self):
        endpoint = ServiceEndpoint(
            id="get-customer",
            system_id="crm-salesforce",
            name="Get Customer Profile",
            description="Retrieve a customer's full profile by ID",
            method=HttpMethod.GET,
            path="/customers/{customer_id}",
            path_params={
                "customer_id": ParamSchema(type="string", description="The customer ID"),
            },
            when_to_use="When the user asks about a customer's details",
            examples=["Show me customer 12345", "Get John's profile"],
            risk_level=RiskLevel.READ,
            required_permissions=["customers:read"],
        )
        assert endpoint.risk_level == RiskLevel.READ
        assert endpoint.timeout_seconds == 30.0
        assert len(endpoint.examples) == 2

    def test_endpoint_defaults(self):
        endpoint = ServiceEndpoint(
            id="test-ep",
            system_id="sys1",
            name="Test",
            description="Test endpoint",
            method=HttpMethod.GET,
            path="/test",
            when_to_use="Testing",
            risk_level=RiskLevel.READ,
            required_permissions=["test:read"],
        )
        assert endpoint.path_params is None
        assert endpoint.query_params is None
        assert endpoint.request_body is None
        assert endpoint.examples == []
        assert endpoint.timeout_seconds == 30.0
        assert endpoint.tags == []
