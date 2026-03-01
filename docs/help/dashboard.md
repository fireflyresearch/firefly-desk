---
type: tutorial
---

# Dashboard

The Dashboard is the first screen you see when entering the Admin Console. It provides an at-a-glance overview of platform health, usage metrics, and recent activity.

## Key Metrics

The dashboard displays aggregated statistics including:

- **Total conversations** -- Number of conversations across all users.
- **Tool invocations** -- How many times the agent has called registered tools.
- **Active users** -- Users who have interacted with the platform in the current period.
- **Token usage** -- Input and output token consumption across all LLM calls, including interactive chat and auto-discovery runs.
- **Estimated cost** -- Aggregated LLM cost based on token usage and model pricing.

## System Health

Health indicators show the status of connected systems registered in the System Catalog. Systems with health check endpoints are pinged periodically, and the dashboard reflects their availability.

## Tips

- Check the dashboard regularly to spot usage trends and unexpected cost spikes.
- Token usage now includes both interactive agent responses and auto-discovery runs, giving a complete picture of LLM consumption.
- Use the dashboard to verify that newly registered systems are reporting healthy before enabling them for the agent.
