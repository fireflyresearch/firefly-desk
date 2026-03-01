---
type: tutorial
---

# Search Engine

The Search Engine page configures a web search provider that gives the AI agent the ability to look up real-time information from the internet during conversations.

## Supported Providers

- **Tavily** -- AI-optimized web search API with configurable result limits.

## Setting Up Search

1. Click the getting-started card or **Configure** button.
2. Follow the inline tutorial to create a Tavily account and obtain an API key.
3. Enter the API key and configure the maximum number of results per query.
4. Test the connection to verify the key works.
5. Save the configuration. Changes take effect immediately for subsequent conversations.

## Disabling Search

Toggle the search provider to inactive to remove the agent's ability to search the web. This is useful for environments where internet access should be restricted.

## Tips

- Web search is particularly useful for questions about current events, recent documentation, or topics not covered by the knowledge base.
- Keep the max results setting moderate (5-10) to balance relevance with token usage.
- The agent automatically decides when to use web search based on the conversation context -- you don't need to explicitly request it.
