---
type: tutorial
---

# Getting Started

Firefly Desk is an AI-powered backoffice platform that connects your organization's knowledge, external systems, and business processes through a conversational AI agent. The admin console is where you configure everything the agent needs to operate.

## First-Time Setup Checklist

When you first access the admin console, follow these steps in order:

1. **Configure an LLM provider** -- The agent needs at least one language model to function. Go to **LLM Providers** and add your OpenAI, Anthropic, or other provider credentials.
2. **Add knowledge** -- Upload documents, import from URLs, or connect a Git repository in the **Knowledge Base** section. This gives the agent content to search and reference.
3. **Register external systems** -- If the agent should call APIs on behalf of users, add them in the **Catalog** section with their endpoints and authentication.
4. **Set up users and roles** -- Invite team members and assign roles (admin, operator, viewer) under **Users & Roles**.
5. **Configure SSO** (optional) -- Connect your identity provider (Azure AD, Okta, Google, etc.) for single sign-on under **SSO**.

## Admin Console Overview

The left sidebar organizes all platform sections:

- **Dashboard** -- System stats, health status, and usage analytics at a glance.
- **Knowledge Base** -- Document storage with vector search and knowledge graph.
- **Catalog** -- External system integrations and API endpoint registry.
- **Processes** -- AI-discovered business processes and workflow explorer.
- **Tools** -- Built-in and custom tools available to the agent.
- **Prompts** -- Jinja2 templates that shape the agent's behavior.
- **Exports** -- Generate CSV, JSON, or PDF documents from agent data.
- **Credentials** -- Encrypted vault for API keys and secrets.
- **Audit Log** -- Complete trail of every action taken in the system.
- **Settings** -- LLM providers, users, roles, SSO, and Git providers.

## What Happens Next

Once configured, end users can interact with the AI agent through the chat interface. The agent searches your knowledge base, calls registered APIs (with appropriate permissions), follows discovered business processes, and generates structured responses -- all governed by the roles and permissions you define here.

## Tips

- Start small: add one LLM provider and a few knowledge documents, then expand.
- Use the Dashboard to monitor system health after initial setup.
- The audit log tracks every configuration change -- useful for troubleshooting.
