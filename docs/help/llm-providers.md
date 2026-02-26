---
type: tutorial
---

# LLM Providers

LLM Providers configure the language models and embedding models that power the AI agent, knowledge base indexing, and process discovery. At least one active provider is required for the platform to function.

## Adding a Provider

Navigate to **LLM Providers** in the admin console and click **Add Provider**. Each provider entry requires:

- **Name** -- A descriptive label (e.g., "OpenAI Production" or "Anthropic Claude").
- **Provider type** -- The vendor: openai, anthropic, azure_openai, google, bedrock, ollama, or other compatible providers.
- **API key** -- Your provider's API key. This is encrypted at rest using the configured KMS provider (see [Credentials](credentials.md)).
- **Base URL** (optional) -- Override the default API endpoint. Useful for Azure OpenAI deployments, self-hosted models, or proxy servers.
- **Models** -- List of model IDs available through this provider (e.g., `gpt-4o`, `claude-sonnet-4-20250514`).
- **Default model** -- Which model to use when no specific model is requested.
- **Capabilities** -- What the provider supports: chat completion, embeddings, function calling, vision, etc.
- **Additional config** -- Provider-specific settings like temperature defaults, max tokens, or organization ID.

## Default Provider

One provider can be marked as the **default**. This is the provider used for:

- Agent conversations when no specific model is requested.
- Process discovery analysis.
- Any background task that needs LLM access.

If no default is set, the platform uses the first active provider.

## Embedding Models

Embedding models are used by the knowledge base to generate vector representations of document chunks. Configure embedding capability in the provider's capabilities field. The default embedding dimension is 1536 (matching OpenAI's text-embedding-3-small), but this can be adjusted in the platform configuration.

## Provider Health

The platform periodically checks provider availability. Unhealthy providers are flagged in the admin console but not automatically disabled -- you control the active/inactive toggle.

## Managing Providers

- **Active/Inactive toggle** -- Disable a provider without deleting it. Inactive providers are not used for any operations.
- **Edit** -- Update API keys, models, or configuration at any time.
- **Delete** -- Permanently removes the provider. Ensure another provider is available before deleting.

## Tips

- Configure at least two providers for resilience -- if one goes down, you can quickly switch the default.
- Use separate providers for chat and embeddings if your embedding provider differs from your chat provider.
- API keys are encrypted on save and never displayed again. Keep a secure copy externally.
- Monitor provider health from the Dashboard to catch outages early.
