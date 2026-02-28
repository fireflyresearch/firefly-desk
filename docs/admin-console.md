---
type: reference
---

# Admin Console

## Overview

The Admin Console is the graphical management interface for Firefly Desk. It provides administrators with the tools to configure external systems, manage credentials, curate the knowledge base, explore the knowledge graph, manage roles and users, configure SSO providers, manage exports, and review audit logs, all without writing API calls or editing configuration files. The console is part of the SvelteKit frontend and is accessible through the sidebar navigation within the AppShell layout.

Access to the Admin Console requires the admin role. Non-admin users do not see the admin navigation items and cannot access the admin routes directly. This restriction exists because the operations performed in the admin console, such as registering new systems, modifying credentials, and deleting knowledge documents, affect the behavior and capabilities of the entire platform for all users.

### Sidebar Navigation

The sidebar organizes features into collapsible groups with a left-bar accent indicator for the active page:

- **Dashboard** — Always visible at the top
- **Content & Data** — Workspaces, System Catalog, Knowledge Base, Processes
- **AI Configuration** — Agent, LLM Providers, Prompts, Tools, Email
- **Security & Access** — Users & Roles, Credentials, Single Sign-On
- **Operations** — Audit Log, Exports, Git Providers, Document Sources, Search Engine, Background Jobs
- **Help & Guides** — Pinned at the bottom

Each group is collapsible with a chevron toggle and item count badge.

## Admin Dashboard

**Route:** `/admin`

The Admin Dashboard provides an at-a-glance overview of platform health and activity. It displays aggregated statistics including total conversations, tool invocations, active users, system health status, and recent activity metrics. This view helps administrators quickly assess whether the platform is operating normally and identify trends in usage.

## System Catalog Manager

**Route:** `/admin/catalog`

The System Catalog Manager is where administrators register and configure the external systems and endpoints that Ember can interact with. The interface displays all registered systems with their status, endpoint count, and health information. From this view, administrators can add new systems, edit existing system configurations, and manage the endpoints within each system.

When adding or editing a system, the form captures the system name, description, base URL, authentication method, health check path, and tags. When managing endpoints, administrators define the HTTP method, path, parameter schema, risk level, required permissions, and the critical `when_to_use` guidance text that shapes how the agent selects tools.

The System Catalog Manager is the primary way that Firefly Desk's capabilities grow. Every new system registered here immediately becomes available to Ember in subsequent conversations, without any code deployment or agent retraining. This is why the catalog metadata, particularly the descriptions and `when_to_use` fields, deserves careful attention: the quality of these descriptions directly determines the quality of the agent's tool selection.

## Credential Vault

**Route:** `/admin/credentials`

The Credential Vault manages the authentication credentials used to connect to external systems. Credentials are encrypted at rest using the `FLYDESK_CREDENTIAL_ENCRYPTION_KEY` and are never exposed in plaintext through the API or the UI after initial entry.

Administrators can create new credentials, update existing ones, and delete credentials that are no longer needed. Each credential is associated with an authentication type (OAuth2, API key, basic, bearer, or mutual TLS) and is referenced by the systems that use it. The vault interface shows which systems depend on each credential, making it clear which integrations would be affected by a credential change.

The reason credentials are managed separately from system configurations is rotation safety. When an API key is rotated, the administrator updates a single credential entry rather than editing every system and endpoint that uses it. This separation also means that the person who registers a system in the catalog does not necessarily need access to the credentials, supporting the principle of least privilege.

## Knowledge Base Manager

**Route:** `/admin/knowledge`

The Knowledge Base Manager provides a comprehensive interface for managing all knowledge content. The interface is organized into three tabs: Documents, Add Document, and Graph Explorer.

### Documents Tab

Displays all knowledge documents with their titles, document types, source information, tags, and chunk counts. Administrators can:

- View document details including full content, metadata, and indexing status
- Edit document metadata (title, document type, tags)
- Delete outdated or irrelevant documents, which removes the document record and all associated chunks and embeddings

The document detail panel is resizable: drag the left edge to adjust its width between 300px and 800px. The panel also supports fullscreen mode via the Maximize/Minimize button in the detail header, which expands the panel to fill the viewport for easier reading of long documents.

OpenAPI specification documents (`api_spec` type or content containing OpenAPI/Swagger markers) are rendered with an interactive Swagger UI viewer instead of raw markdown. This provides a familiar, navigable interface for exploring API endpoints, parameters, and schemas directly within the knowledge base.

### Add Document Tab

Provides three methods for adding new documents:

- **Manual entry:** Type or paste content directly with a title, document type, source, and tags. The document is immediately chunked, embedded, and indexed.
- **URL import:** Enter a URL to fetch and import. HTML content is automatically converted to markdown. OpenAPI specifications are detected and parsed into structured API reference documents.
- **File upload:** Upload a file to extract its content and index it as a knowledge document.

### Knowledge Graph Explorer

**Also accessible from:** `/admin/knowledge` (Graph Explorer tab)

The Knowledge Graph Explorer provides a visual, interactive exploration of the knowledge graph using Cytoscape.js with an fcose force-directed layout. This view helps administrators understand the relationships between concepts, systems, and processes in their knowledge base.

Features of the graph explorer:

- **Interactive graph visualization:** Entities are rendered as typed, color-coded nodes with distinct shapes per entity type, and relationships as directed edges. The canvas supports pan, zoom, and hover-to-highlight neighbors.
- **Entity details:** Clicking on a node reveals its properties, type, and connected relationships in a detail panel.
- **Relationship navigation:** Edges show the relationship type and direction between entities, with labels displayed along the edge.
- **Automatic layout:** Nodes are automatically positioned using the fcose force-directed layout algorithm, optimized for readability with configurable node separation and edge lengths.
- **Discovery:** The visual layout often reveals unexpected connections or structural patterns in your operational knowledge that are not apparent when browsing documents individually.

The graph explorer is particularly valuable for understanding system dependencies, process flows, and concept hierarchies within your organization's operational domain.

## Agent Customization

**Route:** `/admin/agent`

The Agent Customization panel allows administrators to personalize the conversational agent's identity, communication style, and behavioral rules without modifying code or restarting the application. Changes take effect immediately for subsequent conversation turns.

The panel is organized into the following sections:

- **Identity:** Configure the agent's name, display name, and avatar image. The avatar preview updates in real-time. The display name appears in the chat header, message bubbles, and greeting messages throughout the UI.
- **Personality & Tone:** Define how the agent communicates using comma-separated personality traits and a tone description. Several presets are available (Warm & Professional, Technical & Concise, Friendly & Patient, Formal & Thorough) as starting points.
- **Greeting:** Set the initial message displayed when a user starts a new conversation. The `{name}` placeholder is automatically replaced with the agent's display name.
- **Behavior Rules:** Add specific prescriptive rules that the agent must follow in every conversation, such as "Always cite sources" or "Ask for confirmation before destructive operations."
- **Custom Instructions:** Free-form text area for additional instructions appended to the agent's system prompt. Use this for domain-specific guidance that does not fit into structured fields.
- **Language:** Set the preferred response language.

For complete documentation including API reference and personality presets, see [Agent Customization](agent-customization.md).

## Process Explorer

**Route:** `/admin/processes`

The Process Explorer provides a visual interface for viewing, editing, and verifying business processes discovered by the LLM-based process discovery engine. The interface combines a list view with an interactive SvelteFlow canvas that renders processes as flow diagrams.

Key features:

- **Process list:** All discovered, verified, modified, and archived processes are listed with their name, category, confidence score, status, and step count. Filter by category, status, or tags.
- **Flow canvas:** Selecting a process renders its steps and dependencies as an interactive flow diagram. Steps are displayed as typed nodes (action, decision, wait) with color coding, and dependencies are shown as directed edges with optional condition labels.
- **Step editing:** Click any step node to view and edit its name, description, type, system/endpoint mappings, inputs, and outputs.
- **Dependency editing:** Modify the edges between steps to correct the discovered workflow structure.
- **Verification:** Mark a discovered process as verified once a human has reviewed it, changing its status from "discovered" to "verified."
- **Discovery trigger:** Manually trigger a new discovery run from the interface, which submits a background job that analyzes all available context.

The process explorer uses SvelteFlow base components (`FlowCanvas`, `FlowNode`, `FlowEdge`) for flow diagram rendering, while the Knowledge Graph Explorer uses Cytoscape.js for force-directed graph visualization.

For complete documentation including the domain model and API reference, see [Process Discovery](processes.md).

## Role Manager

**Route:** `/admin/roles`

The Role Manager provides an interface for viewing and managing the RBAC roles that control access across the platform. Administrators can:

- View all roles, including the three built-in roles (Administrator, Operator, Viewer) and any custom roles
- See the full permission list for each role
- Create new custom roles with specific permission combinations
- Edit custom roles to add or remove permissions
- Delete custom roles that are no longer needed

Built-in roles are protected and cannot be modified or deleted. This ensures that the default access model always remains available as a baseline.

The permission system covers 20 discrete permissions across seven domains: knowledge (read, write, delete), catalog (read, write, delete), chat (send), exports (create, download, delete, templates), audit (read), credentials (read, write), and administration (users, settings, roles, SSO, LLM, dashboard). See the [Security](security.md) documentation for the complete permission reference.

## User Manager

**Route:** `/admin/users`

The User Manager displays all user accounts and their role assignments. Administrators can:

- View all users with their display names, email addresses, and assigned roles
- Assign roles to users to grant or restrict access
- View user activity history

## Export Manager

**Route:** `/admin/exports`

The Export Manager provides oversight of all export activity across the platform. Administrators can:

- View all exports with their status (pending, generating, completed, failed), format, title, and file size
- Download completed export files
- Delete export records and their associated files
- Manage export templates that define column mappings, headers, and footers for consistent output formatting

The export system supports CSV, JSON, and PDF formats. Templates allow organizations to standardize export output with custom column names, header text, and footer text. See the [Exports](exports.md) documentation for details on the export system.

## SSO Manager

**Route:** `/admin/sso`

The SSO Manager allows administrators to configure OIDC identity providers for production authentication. The interface provides:

- A list of configured OIDC providers with their type, issuer URL, and status
- Forms for adding new providers with pre-configured templates for common providers (Keycloak, Google, Microsoft Entra ID, Auth0, Amazon Cognito, Okta)
- Provider editing with fields for issuer URL, client ID, client secret, scopes, redirect URI, and claim mapping
- Provider deletion for removing unused configurations

Each provider configuration includes claim mapping fields that specify where in the JWT token the user's roles and permissions are located. Different providers use different claim structures, and the SSO Manager makes it straightforward to configure the correct mapping for each provider.

See the [SSO and OIDC](sso-oidc.md) documentation for detailed setup guides per provider.

## LLM Provider Manager

**Route:** `/admin/llm-providers`

The LLM Provider Manager configures the language model providers that power the agent. Administrators can:

- Register API keys for different LLM providers (OpenAI, Anthropic, Google, Azure OpenAI, Ollama)
- Configure model selection and parameters
- Set a default provider for the agent
- Configure fallback models per provider type for resilience when the primary model is unavailable
- Configure the embedding provider and model for knowledge base vectorization
- Test provider connectivity and view health status
- View provider usage metrics

API keys are encrypted at rest using the same encryption key as the credential vault.

## Document Sources

**Route:** `/admin/document-sources`

The Document Sources page manages connections to cloud storage and drive services for document import and sync. Supported source types include Amazon S3, Azure Blob Storage, Google Cloud Storage, OneDrive, SharePoint, and Google Drive.

When no sources are configured, the page displays a guided getting-started view with clickable source type cards. Selecting a source type opens the configuration form with an inline setup tutorial containing step-by-step instructions specific to that provider, including how to create credentials, which permissions to grant, and security best practices.

Each source supports automatic sync on a configurable schedule (every 6 hours, 12 hours, or daily), manual sync triggers, connectivity testing, and active/inactive toggling.

## Git Providers

**Route:** `/admin/git-providers`

The Git Providers page configures connections to GitHub, GitLab, and Bitbucket for repository browsing and knowledge import. Each provider supports two authentication methods: Personal Access Token (PAT) and OAuth App.

The interface includes inline setup tutorials that adapt based on the selected provider type and authentication method. For example, selecting GitHub with PAT authentication shows step-by-step instructions for generating a fine-grained token with the correct repository scopes. Selecting GitLab with OAuth shows how to create an application in the GitLab admin area and configure the redirect URI.

When no providers are configured, the empty state displays provider cards that launch the guided setup flow directly.

## Audit Viewer

**Route:** `/admin/audit`

The Audit Viewer provides a searchable interface for the platform's audit trail. Every conversation turn, tool invocation, and administrative action is recorded with timestamps, user identities, and full request and response details.

Administrators can filter audit events by user, event type, and date range. This capability is essential for compliance, incident investigation, and understanding how the platform is being used. The audit trail is append-only and retained according to the `FLYDESK_AUDIT_RETENTION_DAYS` configuration, which defaults to 365 days.

The Audit Viewer is particularly valuable when investigating why the agent took a specific action. Each audit record includes the enriched context that was available to the agent at the time of the interaction, making it possible to understand not just what happened but why the agent made the decisions it did.

## Search Engine

**Route:** `/admin/search-engine`

The Search Engine page configures the web search provider that gives the agent internet search capabilities. Currently supported providers include Tavily.

When no search provider is configured, the page displays a getting-started view explaining what web search enables and offering a one-click setup for Tavily. The configuration form includes an inline setup tutorial with step-by-step instructions for creating a Tavily account and obtaining an API key, a max results slider, a connection test button, and a save action. Changes take effect immediately for subsequent conversation turns.

Administrators can also disable search entirely, which removes the agent's ability to look up real-time information from the web.

## Email Channel

**Route:** `/admin/email`

The Email Channel page configures the email communication channel that allows the AI agent to send and receive emails through external providers. The Email entry appears in the **AI Configuration** sidebar group alongside Agent, LLM Providers, Prompts, and Tools.

When the email channel has not been configured, the page displays a setup wizard that walks administrators through provider selection, API key entry, validation, and identity configuration. Once configured, the page organises settings into five tabs:

### Connection Tab

Configures the email provider and credentials. Administrators select between Resend and AWS SES, enter the provider API key (or configure an AWS region for SES), and validate the credentials with a lightweight API call that does not send any email. The tab also displays the current connection status (enabled/disabled, provider name, configured state) and provides a disconnect action to clear credentials and disable the channel.

### Identity Tab

Controls how outbound emails appear to recipients. Fields include the from address (which must be verified with the provider), the display name shown alongside the address, and an optional reply-to address. A test email section lets administrators send a sample message to verify end-to-end delivery through the configured provider.

### Signature Tab

Provides an HTML signature editor with a live preview rendered in an iframe. Administrators can edit the raw HTML directly with syntax highlighting, upload a custom logo image (PNG, JPEG, GIF, or WebP, max 2 MB) that is embedded as a base64 data URI, or reset the signature to the auto-generated Flydesk-branded default. The default signature is built from the current display name and from address using email-safe `<table>` layout with inline styles.

### Behaviour Tab

Controls the agent's email behaviour: auto-reply toggle and delay (default 30 seconds), greeting and sign-off toggles, maximum email length (default 2000 characters), and CC handling mode. The CC mode determines whether replies go to the sender only (`respond_sender`), the sender and all CC recipients (`respond_all`), or are suppressed entirely (`silent`). The tab also includes email-specific persona overrides for tone, personality, and custom instructions that apply only when the agent is composing email responses.

### Inbound Tab

Configures how the platform receives inbound emails. The tab displays the webhook URL that must be registered with the email provider, along with provider-specific setup instructions for Resend and SES. In dev mode, a built-in ngrok tunnel section allows administrators to start and stop a tunnel that exposes the local server on a public HTTPS URL for testing inbound webhooks without deploying. The tab also provides identity resolution tools (check whether an email address maps to a known user, list all users with email addresses) and an inbound simulation form that runs the full pipeline -- identity resolution, thread creation, and optional auto-reply -- without requiring a real email.

For comprehensive documentation including provider setup guides, the agent email tool, and troubleshooting, see [Email Channel](help/email.md).

## Background Jobs

**Route:** `/admin/jobs`

The Background Jobs page provides visibility into the asynchronous tasks running on the platform. Jobs include operations such as process discovery runs, knowledge base indexing, document source sync, export generation, and other long-running tasks that execute outside the request-response cycle.

Administrators can:

- View all jobs with their status (queued, running, completed, failed, cancelled), type, creation time, and duration
- Monitor running jobs and track progress
- Cancel queued or running jobs that are no longer needed
- View error details for failed jobs to diagnose issues
- Filter jobs by status or type

The Background Jobs entry appears in the **Operations** sidebar group alongside Audit Log, Exports, Git Providers, Document Sources, and Search Engine.
