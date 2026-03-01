---
type: tutorial
---

# Audit Log

The Audit Log provides a searchable, append-only record of all platform activity. Every conversation turn, tool invocation, administrative action, and discovery run is recorded with full context.

## Viewing Events

The audit viewer displays events with timestamps, user identities, event types, and detail payloads. Each record includes the enriched context that was available at the time, making it possible to understand not just what happened but why.

## Filtering

Filter audit events by:

- **User** -- See all actions by a specific user or the system account.
- **Event type** -- Filter by `agent_response`, `discovery_response`, `tool_invocation`, or administrative actions.
- **Date range** -- Narrow results to a specific time window.

## Event Types

- **agent_response** -- An interactive chat response from the AI agent, including token usage and cost.
- **discovery_response** -- An LLM call from the auto-discovery engine (process or system discovery), including token usage and cost.
- **tool_invocation** -- The agent called a registered tool or endpoint.
- **Administrative actions** -- Changes to configuration, users, roles, or credentials.

## Retention

Audit records are retained according to the `FLYDESK_AUDIT_RETENTION_DAYS` setting, which defaults to 365 days. Records are append-only and cannot be modified or deleted through the UI.

## Tips

- Use the audit log to investigate why the agent took a specific action -- each record includes the full context window.
- Discovery response events help track the cost of auto-discovery runs separately from interactive chat.
- Export audit data for compliance reporting or external analysis.
