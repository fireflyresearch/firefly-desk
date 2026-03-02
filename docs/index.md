---
type: manual
---

# Firefly Desk

## What is Firefly Desk?

Firefly Desk is a **Backoffice as Agent** platform. It provides an AI agent named Ember that understands your organization's systems, documentation, and processes, and can act on that understanding by calling external APIs, retrieving knowledge, and guiding operators through complex workflows -- all through a conversational interface.

The premise is simple: operations teams spend most of their time looking things up, navigating between systems, and following procedures that are documented somewhere but hard to find in the moment. Firefly Desk consolidates that work into a single conversational surface where the agent already knows what systems exist, what they do, how they authenticate, and what operational knowledge is available. Instead of switching between dashboards, searching wikis, and copy-pasting between tools, an operator asks a question and gets an answer grounded in organizational truth.

## Key Features

### Service Catalog

The Service Catalog is the registry of external systems and API endpoints that Ember can interact with on behalf of users. It supports multiple communication protocols -- REST, GraphQL, SOAP, gRPC, and WebSocket -- so the agent can work with modern microservices and legacy integrations alike. Each endpoint is classified with a risk level, required permissions, and a natural-language "when to use" description that helps the agent decide when to call it. See [Service Catalog](service-catalog.md) for the full guide.

### Knowledge Base

The Knowledge Base gives Ember access to operational documentation, runbooks, policies, and domain-specific information through two complementary retrieval systems: **RAG** (Retrieval-Augmented Generation) for semantic similarity search over document chunks, and a **Knowledge Graph** for structured entity-to-entity relationships. Together, they ensure the agent can find relevant information whether the user phrases a question the same way the documentation was written or not. See [Knowledge Base](knowledge-base.md) for details.

### Process Discovery

Process Discovery automatically identifies and maps business processes by analyzing registered systems, endpoints, knowledge documents, and entity relationships. Rather than requiring administrators to manually define every workflow, the discovery engine uses an LLM to infer how systems connect and what sequences of operations form coherent processes. Discovered processes can be reviewed, verified, edited, or archived. See [Process Discovery](processes.md) for the complete reference.

### Agent Customization

Ember's name, personality, tone, greeting, behavioral rules, and custom instructions are all configurable through the admin UI or API. Organizations can match the agent to their brand and communication style without modifying code. Customization settings are stored in the database and take effect immediately. See [Agent Customization](agent-customization.md) for all available options.

### RBAC with 20 Permissions

A permission-based role-based access control model governs who can do what. Twenty discrete permissions across seven domains (knowledge, catalog, chat, exports, audit, credentials, admin) are enforced at both the API middleware layer and the agent's tool resolution layer. Three built-in roles (Administrator, Operator, Viewer) cover common access patterns, and custom roles can be created for specific organizational needs. See [Security](security.md) for the full permission reference.

### Audit System

Every significant action is recorded in an append-only audit trail: chat turns with enriched context, tool invocations with parameters and results, confirmation decisions, administrative changes, and authentication events. The audit trail provides the accountability that operational environments require for incident investigation and compliance reporting.

## Architecture at a Glance

Firefly Desk follows a **hexagonal architecture** (ports and adapters) pattern. Core business logic is expressed through Python Protocols that define what the system needs, and concrete adapters implement those contracts for specific technologies. This separation means the agent pipeline, knowledge retrieval, and tool execution are all independent of their underlying storage or transport mechanisms.

The backend is **async-first Python** built on FastAPI. All I/O operations -- database queries, HTTP calls to external systems, embedding generation, LLM invocations -- are asynchronous. SQLAlchemy async handles persistence, Alembic manages schema migrations, and Pydantic AI provides the agent framework.

The frontend is a **SvelteKit** application styled with Tailwind CSS. It communicates with the backend through REST endpoints and receives streaming agent responses via Server-Sent Events (SSE).

For the full architecture breakdown, see [Architecture](architecture.md).

## How It Works

When a user sends a message, the platform processes it through a multi-stage pipeline:

1. **Message received.** The user's message arrives at the chat endpoint as an HTTP request.

2. **Context enrichment.** The `ContextEnricher` runs three retrieval processes in parallel: Knowledge Graph traversal finds structurally related entities, RAG retrieves semantically similar document chunks, and the user's saved memories are searched for relevant personal context. Running these in parallel minimizes latency because this enrichment happens on every conversation turn.

3. **Prompt composition.** The `SystemPromptBuilder` assembles the system prompt from Jinja2 templates, incorporating the agent's personality profile, enriched context, available tools (filtered by the user's permissions), and conversation history.

4. **LLM invocation.** The composed prompt is sent to the configured LLM provider. The model generates a response that may include natural language, tool calls, or widget directives.

5. **Tool execution.** When the LLM requests a tool call, the `ToolExecutor` routes it to the appropriate handler: external system calls go through the HTTP client with credential injection, while internal tools (knowledge search, audit queries, memory operations) are handled by the `BuiltinToolExecutor`. High-risk operations are intercepted by the `ConfirmationService` and require explicit user approval before execution.

6. **Streaming response.** The agent's response is streamed to the frontend via SSE, delivering text tokens, widget directives, tool execution status, and confirmation requests as they occur.

## Who Is It For?

Firefly Desk is built for teams that operate backend systems and need a smarter way to interact with them:

- **Operations teams** that manage multiple backend services and need quick access to system data, status checks, and operational procedures.
- **Support teams** that resolve incidents by looking up information across several systems and following documented runbooks.
- **IT departments** that want to provide a unified, permission-controlled interface to organizational systems without building custom tooling for every integration.

## Next Steps

| Goal | Document |
|------|----------|
| Run Firefly Desk locally | [Getting Started](getting-started.md) |
| Install from scratch | [Installation](installation.md) |
| Deploy to production | [Deployment](deployment.md) |
| Understand the architecture | [Architecture](architecture.md) |
| Configure environment variables | [Configuration](configuration.md) |
| Register external systems | [Service Catalog](service-catalog.md) |
| Add knowledge documents | [Knowledge Base](knowledge-base.md) |
| Set up SSO | [SSO and OIDC](sso-oidc.md) |
| Optimize LLM costs | [Smart Model Routing](model-routing.md) |
| Explore the API | [API Reference](api-reference.md) |
