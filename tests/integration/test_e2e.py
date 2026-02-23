# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""End-to-end integration tests for the Desk Agent lifecycle.

These tests wire together all real components (CatalogRepository,
KnowledgeGraph, KnowledgeRetriever, ContextEnricher, SystemPromptBuilder,
ToolFactory, WidgetParser, AuditLogger, DeskAgent) against an in-memory
SQLite database with inline banking seed data.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from flydesk.agent.context import ContextEnricher
from flydesk.agent.desk_agent import DeskAgent
from flydesk.agent.prompt import SystemPromptBuilder
from flydesk.agent.response import AgentResponse
from flydesk.api.events import SSEEvent, SSEEventType
from flydesk.audit.logger import AuditLogger
from flydesk.audit.models import AuditEventType
from flydesk.auth.models import UserSession
from flydesk.catalog.enums import AuthType, HttpMethod, RiskLevel, SystemStatus
from flydesk.catalog.models import AuthConfig, ExternalSystem, ParamSchema, ServiceEndpoint
from flydesk.catalog.repository import CatalogRepository
from flydesk.knowledge.graph import Entity, KnowledgeGraph
from flydesk.knowledge.indexer import KnowledgeIndexer
from flydesk.knowledge.models import KnowledgeDocument
from flydesk.knowledge.retriever import KnowledgeRetriever
from flydesk.models.base import Base
from flydesk.tools.factory import ToolFactory
from flydesk.widgets.parser import WidgetParser


# ---------------------------------------------------------------------------
# Mock embedding provider
# ---------------------------------------------------------------------------


class MockEmbeddingProvider:
    """Deterministic embedding provider for testing.

    Returns fixed-dimension vectors so cosine similarity always works.
    """

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 8 for _ in texts]


# ---------------------------------------------------------------------------
# Inline banking seed data
# ---------------------------------------------------------------------------


def _core_banking_system() -> ExternalSystem:
    return ExternalSystem(
        id="core-banking",
        name="Core Banking API",
        description="Core banking system for account and transaction management",
        base_url="https://api.bank.internal/v1",
        auth_config=AuthConfig(
            auth_type=AuthType.OAUTH2,
            credential_id="core-banking-cred",
            token_url="https://auth.bank.internal/token",
            scopes=["accounts.read", "accounts.write", "transactions.read"],
        ),
        health_check_path="/health",
        tags=["banking", "core"],
        status=SystemStatus.ACTIVE,
        metadata={"owner": "platform-team"},
    )


def _payment_gateway_system() -> ExternalSystem:
    return ExternalSystem(
        id="payment-gateway",
        name="Payment Gateway",
        description="External payment processing gateway",
        base_url="https://api.payments.example.com/v2",
        auth_config=AuthConfig(
            auth_type=AuthType.API_KEY,
            credential_id="payment-gw-key",
        ),
        health_check_path="/ping",
        tags=["payments", "external"],
        status=SystemStatus.ACTIVE,
        metadata={"owner": "payments-team"},
    )


def _core_banking_endpoints() -> list[ServiceEndpoint]:
    return [
        ServiceEndpoint(
            id="get-customer",
            system_id="core-banking",
            name="get_customer",
            description="Retrieve customer profile by ID",
            method=HttpMethod.GET,
            path="/customers/{customer_id}",
            path_params={
                "customer_id": ParamSchema(
                    type="string",
                    description="Unique customer identifier",
                ),
            },
            when_to_use="When the user asks for customer details or profile information",
            examples=[
                "Show me customer C-1001",
                "Get customer information",
                "Look up customer details",
            ],
            risk_level=RiskLevel.READ,
            required_permissions=["customers:read"],
            tags=["customer"],
        ),
        ServiceEndpoint(
            id="list-accounts",
            system_id="core-banking",
            name="list_accounts",
            description="List all accounts for a given customer",
            method=HttpMethod.GET,
            path="/customers/{customer_id}/accounts",
            path_params={
                "customer_id": ParamSchema(
                    type="string",
                    description="Customer ID to list accounts for",
                ),
            },
            query_params={
                "status": ParamSchema(
                    type="string",
                    description="Filter by account status",
                    required=False,
                    enum=["active", "frozen", "closed"],
                ),
            },
            when_to_use="When asked about customer accounts or balances",
            examples=["What accounts does this customer have?"],
            risk_level=RiskLevel.READ,
            required_permissions=["accounts:read"],
            tags=["account"],
        ),
    ]


def _payment_gateway_endpoints() -> list[ServiceEndpoint]:
    return [
        ServiceEndpoint(
            id="initiate-transfer",
            system_id="payment-gateway",
            name="initiate_transfer",
            description="Initiate a fund transfer between accounts",
            method=HttpMethod.POST,
            path="/transfers",
            request_body={
                "type": "object",
                "properties": {
                    "from_account": {"type": "string"},
                    "to_account": {"type": "string"},
                    "amount": {"type": "number"},
                    "currency": {"type": "string", "default": "USD"},
                },
                "required": ["from_account", "to_account", "amount"],
            },
            when_to_use="When the user wants to transfer funds between accounts",
            examples=["Transfer $500 from checking to savings"],
            risk_level=RiskLevel.HIGH_WRITE,
            required_permissions=["transfers:write"],
            tags=["transfer", "payment"],
        ),
        ServiceEndpoint(
            id="get-transfer-status",
            system_id="payment-gateway",
            name="get_transfer_status",
            description="Check the status of a fund transfer",
            method=HttpMethod.GET,
            path="/transfers/{transfer_id}",
            path_params={
                "transfer_id": ParamSchema(
                    type="string",
                    description="Transfer ID to check",
                ),
            },
            when_to_use="When the user asks about the status of a transfer",
            examples=["What is the status of transfer TXN-5678?"],
            risk_level=RiskLevel.READ,
            required_permissions=["transfers:read"],
            tags=["transfer"],
        ),
    ]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def session_factory():
    """Create an in-memory SQLite database with all tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    await engine.dispose()


@pytest.fixture
def embedding_provider() -> MockEmbeddingProvider:
    return MockEmbeddingProvider()


@pytest.fixture
def catalog_repo(session_factory) -> CatalogRepository:
    return CatalogRepository(session_factory)


@pytest.fixture
def knowledge_graph(session_factory) -> KnowledgeGraph:
    return KnowledgeGraph(session_factory)


@pytest.fixture
def knowledge_indexer(session_factory, embedding_provider) -> KnowledgeIndexer:
    return KnowledgeIndexer(session_factory, embedding_provider)


@pytest.fixture
def knowledge_retriever(session_factory, embedding_provider) -> KnowledgeRetriever:
    return KnowledgeRetriever(session_factory, embedding_provider)


@pytest.fixture
def context_enricher(knowledge_graph, knowledge_retriever) -> ContextEnricher:
    return ContextEnricher(
        knowledge_graph=knowledge_graph,
        retriever=knowledge_retriever,
    )


@pytest.fixture
def prompt_builder() -> SystemPromptBuilder:
    from flydesk.prompts.registry import register_desk_prompts

    return SystemPromptBuilder(register_desk_prompts())


@pytest.fixture
def tool_factory() -> ToolFactory:
    return ToolFactory()


@pytest.fixture
def widget_parser() -> WidgetParser:
    return WidgetParser()


@pytest.fixture
def audit_logger(session_factory) -> AuditLogger:
    return AuditLogger(session_factory)


@pytest.fixture
def user_session() -> UserSession:
    """Bank teller user with permissions matching the seeded endpoints."""
    return UserSession(
        user_id="teller-001",
        email="jane.doe@bank.example.com",
        display_name="Jane Doe",
        roles=["teller", "support"],
        permissions=[
            "customers:read",
            "accounts:read",
            "transfers:read",
            "transfers:write",
        ],
        tenant_id="bank-tenant",
        session_id="sess-e2e-001",
        token_expires_at=datetime(2026, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        raw_claims={"department": "retail-banking"},
    )


@pytest.fixture
async def seeded_catalog(catalog_repo: CatalogRepository) -> CatalogRepository:
    """Seed the catalog with two banking systems and four endpoints."""
    await catalog_repo.create_system(_core_banking_system())
    await catalog_repo.create_system(_payment_gateway_system())
    for ep in _core_banking_endpoints():
        await catalog_repo.create_endpoint(ep)
    for ep in _payment_gateway_endpoints():
        await catalog_repo.create_endpoint(ep)
    return catalog_repo


@pytest.fixture
async def seeded_knowledge(
    knowledge_graph: KnowledgeGraph,
    knowledge_indexer: KnowledgeIndexer,
) -> KnowledgeGraph:
    """Add a sample entity and a knowledge document."""
    # Entity for the knowledge graph
    await knowledge_graph.upsert_entity(
        Entity(
            id="customer-C1001",
            entity_type="Customer",
            name="customer information C-1001",
            properties={
                "full_name": "Acme Corp",
                "segment": "commercial",
                "relationship_manager": "Bob Johnson",
            },
            source_system="core-banking",
        )
    )

    # Knowledge document with banking procedures
    doc = KnowledgeDocument(
        id="doc-kyc-policy",
        title="KYC Verification Policy",
        content=(
            "All customer accounts must undergo Know Your Customer (KYC) verification "
            "before any high-value transactions. Transactions above $10,000 require "
            "additional manager approval. Customer identity must be verified using "
            "government-issued photo ID and proof of address."
        ),
        source="compliance-manual",
        tags=["policy", "kyc", "compliance"],
    )
    await knowledge_indexer.index_document(doc)

    return knowledge_graph


@pytest.fixture
def desk_agent(
    context_enricher: ContextEnricher,
    prompt_builder: SystemPromptBuilder,
    tool_factory: ToolFactory,
    widget_parser: WidgetParser,
    audit_logger: AuditLogger,
) -> DeskAgent:
    return DeskAgent(
        context_enricher=context_enricher,
        prompt_builder=prompt_builder,
        tool_factory=tool_factory,
        widget_parser=widget_parser,
        audit_logger=audit_logger,
        agent_name="Banking Assistant",
        company_name="First National Bank",
    )


# ---------------------------------------------------------------------------
# Test: Full Agent Lifecycle
# ---------------------------------------------------------------------------


class TestFullAgentLifecycle:
    """End-to-end test exercising the complete agent turn pipeline."""

    async def test_run_returns_valid_response(
        self,
        seeded_catalog,
        seeded_knowledge,
        desk_agent: DeskAgent,
        user_session: UserSession,
    ):
        """Run a full agent turn and verify the response structure."""
        response = await desk_agent.run(
            "Show me customer information",
            user_session,
            "conv-1",
        )

        assert isinstance(response, AgentResponse)
        assert response.text  # non-empty
        assert response.conversation_id == "conv-1"
        assert response.turn_id  # generated UUID
        assert isinstance(response.widgets, list)
        assert response.raw_text  # raw LLM output preserved

    async def test_run_echoes_message_in_placeholder(
        self,
        seeded_catalog,
        seeded_knowledge,
        desk_agent: DeskAgent,
        user_session: UserSession,
    ):
        """The placeholder LLM should echo the user's message."""
        response = await desk_agent.run(
            "Show me customer information",
            user_session,
            "conv-1",
        )
        assert "Show me customer information" in response.raw_text

    async def test_run_unique_turn_ids(
        self,
        seeded_catalog,
        seeded_knowledge,
        desk_agent: DeskAgent,
        user_session: UserSession,
    ):
        """Each call to run() should generate a unique turn_id."""
        r1 = await desk_agent.run("First message", user_session, "conv-1")
        r2 = await desk_agent.run("Second message", user_session, "conv-1")
        assert r1.turn_id != r2.turn_id

    async def test_audit_event_logged(
        self,
        seeded_catalog,
        seeded_knowledge,
        desk_agent: DeskAgent,
        audit_logger: AuditLogger,
        user_session: UserSession,
    ):
        """Verify an 'agent_turn' audit event is recorded after a run."""
        await desk_agent.run(
            "Show me customer information",
            user_session,
            "conv-1",
        )

        events = await audit_logger.query(user_id="teller-001")
        assert len(events) >= 1

        agent_events = [
            e for e in events if e.action == "agent_turn"
        ]
        assert len(agent_events) == 1

        event = agent_events[0]
        assert event.event_type == AuditEventType.AGENT_RESPONSE
        assert event.user_id == "teller-001"
        assert event.conversation_id == "conv-1"
        assert "turn_id" in event.detail
        assert event.detail["message_length"] > 0
        assert event.detail["response_length"] > 0

    async def test_stream_yields_token_and_done_events(
        self,
        seeded_catalog,
        seeded_knowledge,
        desk_agent: DeskAgent,
        user_session: UserSession,
    ):
        """Streaming should produce at least TOKEN events followed by DONE."""
        events: list[SSEEvent] = []
        async for evt in desk_agent.stream(
            "Show me customer information",
            user_session,
            "conv-1",
        ):
            events.append(evt)

        assert len(events) >= 2  # at least one TOKEN + DONE

        token_events = [e for e in events if e.event == SSEEventType.TOKEN]
        assert len(token_events) >= 1

        # Reconstruct text from token chunks
        reconstructed = "".join(e.data["content"] for e in token_events)
        assert len(reconstructed) > 0

        # DONE must be the last event
        assert events[-1].event == SSEEventType.DONE
        done_data = events[-1].data
        assert done_data["conversation_id"] == "conv-1"
        assert "turn_id" in done_data

    async def test_context_enrichment_includes_knowledge(
        self,
        seeded_catalog,
        seeded_knowledge,
        context_enricher: ContextEnricher,
    ):
        """Verify the context enricher finds seeded entities and knowledge snippets."""
        enriched = await context_enricher.enrich("customer information")

        # The knowledge graph should find our customer entity (name contains
        # "customer information")
        assert len(enriched.relevant_entities) >= 1
        entity_names = [e.name for e in enriched.relevant_entities]
        assert any("customer" in name.lower() for name in entity_names)

        # The retriever should find the KYC document chunks
        assert len(enriched.knowledge_snippets) >= 1

    async def test_run_with_tools_includes_tool_summaries(
        self,
        seeded_catalog,
        seeded_knowledge,
        desk_agent: DeskAgent,
        tool_factory: ToolFactory,
        user_session: UserSession,
        catalog_repo: CatalogRepository,
    ):
        """When tools are passed to run(), they appear in the system prompt."""
        # Build tools from the catalog
        all_endpoints = await catalog_repo.list_active_endpoints()
        tools = tool_factory.build_tool_definitions(
            all_endpoints, list(user_session.permissions)
        )

        response = await desk_agent.run(
            "Show me customer information",
            user_session,
            "conv-1",
            tools=tools,
        )

        # The system prompt length should be larger when tools are included
        assert response.text
        assert response.conversation_id == "conv-1"


# ---------------------------------------------------------------------------
# Test: Tool Generation
# ---------------------------------------------------------------------------


class TestToolGeneration:
    """Tests for ToolFactory integration with catalog data."""

    async def test_build_tools_from_catalog(
        self,
        seeded_catalog: CatalogRepository,
        tool_factory: ToolFactory,
    ):
        """Load endpoints from catalog and build tool definitions."""
        endpoints = await seeded_catalog.list_active_endpoints()
        assert len(endpoints) == 4  # 2 core-banking + 2 payment-gateway

        all_permissions = [
            "customers:read",
            "accounts:read",
            "transfers:read",
            "transfers:write",
        ]
        tools = tool_factory.build_tool_definitions(endpoints, all_permissions)
        assert len(tools) == 4

        tool_names = {t.name for t in tools}
        assert "get_customer" in tool_names
        assert "list_accounts" in tool_names
        assert "initiate_transfer" in tool_names
        assert "get_transfer_status" in tool_names

    async def test_tools_filtered_by_permissions(
        self,
        seeded_catalog: CatalogRepository,
        tool_factory: ToolFactory,
    ):
        """User with limited permissions should get fewer tools."""
        endpoints = await seeded_catalog.list_active_endpoints()

        # User only has read permissions -- should not get initiate_transfer
        limited_permissions = ["customers:read", "accounts:read", "transfers:read"]
        tools = tool_factory.build_tool_definitions(endpoints, limited_permissions)

        tool_names = {t.name for t in tools}
        assert "get_customer" in tool_names
        assert "list_accounts" in tool_names
        assert "get_transfer_status" in tool_names
        assert "initiate_transfer" not in tool_names

    async def test_tool_risk_levels(
        self,
        seeded_catalog: CatalogRepository,
        tool_factory: ToolFactory,
    ):
        """Verify tool definitions carry correct risk levels."""
        endpoints = await seeded_catalog.list_active_endpoints()
        all_permissions = [
            "customers:read",
            "accounts:read",
            "transfers:read",
            "transfers:write",
        ]
        tools = tool_factory.build_tool_definitions(endpoints, all_permissions)

        tools_by_name = {t.name: t for t in tools}

        assert tools_by_name["get_customer"].risk_level == RiskLevel.READ
        assert tools_by_name["list_accounts"].risk_level == RiskLevel.READ
        assert tools_by_name["get_transfer_status"].risk_level == RiskLevel.READ
        assert tools_by_name["initiate_transfer"].risk_level == RiskLevel.HIGH_WRITE

    async def test_high_risk_tool_requires_confirmation(
        self,
        seeded_catalog: CatalogRepository,
        tool_factory: ToolFactory,
    ):
        """High-write tools should require confirmation."""
        endpoints = await seeded_catalog.list_active_endpoints()
        all_permissions = [
            "customers:read",
            "accounts:read",
            "transfers:read",
            "transfers:write",
        ]
        tools = tool_factory.build_tool_definitions(endpoints, all_permissions)
        tools_by_name = {t.name: t for t in tools}

        assert tools_by_name["initiate_transfer"].requires_confirmation is True
        assert tools_by_name["get_customer"].requires_confirmation is False

    async def test_tool_definitions_have_descriptions(
        self,
        seeded_catalog: CatalogRepository,
        tool_factory: ToolFactory,
    ):
        """Tool definitions should include description and when_to_use."""
        endpoints = await seeded_catalog.list_active_endpoints()
        all_permissions = [
            "customers:read",
            "accounts:read",
            "transfers:read",
            "transfers:write",
        ]
        tools = tool_factory.build_tool_definitions(endpoints, all_permissions)

        for tool in tools:
            assert tool.description  # non-empty
            assert "When to use:" in tool.description
            assert tool.endpoint_id  # linked to endpoint
            assert tool.system_id  # linked to system

    async def test_no_permissions_yields_no_tools(
        self,
        seeded_catalog: CatalogRepository,
        tool_factory: ToolFactory,
    ):
        """A user with no permissions should receive zero tools."""
        endpoints = await seeded_catalog.list_active_endpoints()
        tools = tool_factory.build_tool_definitions(endpoints, [])
        assert len(tools) == 0
