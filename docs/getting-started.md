# Getting Started

## Prerequisites

Before you begin, ensure you have the following tools installed on your machine:

- **Python 3.13 or later.** Firefly Desk uses modern Python features including advanced type hints and performance improvements introduced in 3.13. Earlier versions will not work.
- **Node.js 22 or later.** The SvelteKit frontend requires a current LTS release of Node.
- **uv.** The Python package manager used by Firefly Desk. If you do not have it installed, you can install it with `curl -LsSf https://astral.sh/uv/install.sh | sh`.

## Clone and Configure

Start by cloning the repository and setting up your environment configuration.

```bash
git clone https://github.com/fireflyresearch/firefly-desk.git
cd firefly-desk
cp .env.example .env
```

The default `.env` file is pre-configured for development mode, which uses SQLite and requires no external services. You can start working immediately without setting up PostgreSQL, Redis, or an OIDC provider.

## Install Dependencies

Install the Python backend dependencies using uv:

```bash
uv sync
```

This creates a virtual environment and installs all required packages. The `uv sync` command is deterministic, meaning every developer gets exactly the same dependency versions.

## Initialize the Database

Run the Alembic migrations to create the database schema:

```bash
uv run flydesk db upgrade head
```

This uses [Alembic](https://alembic.sqlalchemy.org/) to apply all schema migrations. For fresh installs this creates all tables; for upgrades it applies only the new migrations.

## Start Backend and Frontend

The simplest way to start both services is the `flydesk dev` command:

```bash
uv run flydesk dev
```

This starts the FastAPI backend on port 8000 and the SvelteKit frontend on port 5173 in a single terminal, with auto-reload enabled. Press Ctrl+C to stop both.

You can customize the ports:

```bash
uv run flydesk dev --port 8000 --frontend-port 5173
```

Or start them separately if you prefer:

```bash
# Terminal 1: Backend
uv run flydesk serve --port 8000 --reload

# Terminal 2: Frontend
cd frontend
npm install
npm run dev
```

The frontend development server proxies API requests to the backend on port 8000.

## Seed Demo Data

To explore Firefly Desk with realistic data, seed the banking demo scenario:

```bash
flydesk-seed banking
```

This populates the Service Catalog with a sample banking system, registers endpoints for common operations like account lookups and transaction queries, and loads knowledge documents with operational procedures. The seed data is designed to demonstrate the full range of platform capabilities without requiring you to connect a real backend system.

## Setup Wizard

When you first open Firefly Desk in your browser, the application detects that it has not been configured and launches an interactive setup wizard. The wizard guides you through eight steps:

1. **Welcome** -- Introduction to Firefly Desk and what the wizard will configure.
2. **Database** -- Verify or configure the database connection. In development mode, SQLite is pre-configured and this step confirms connectivity.
3. **LLM Provider** -- Configure the language model provider that powers the agent. Enter API keys and select a model.
4. **Embedding** -- Configure the embedding model used for knowledge base vectorization. Test the connection to verify it works.
5. **Agent** -- Customize the agent's name, avatar, personality, and greeting. Choose from personality presets or define your own.
6. **Profile** -- Review and confirm your user profile settings.
7. **Data** -- Optionally seed demo data (banking scenario) and configure auto-analysis settings.
8. **Ready** -- Summary of all configured components with a launch button.

Each step validates its configuration before allowing you to proceed. You can navigate back to previous steps to change settings. The wizard stores all settings in the database, so they persist across restarts.

If you prefer to skip the wizard and configure everything manually through environment variables and the admin console, you can dismiss it and proceed directly to the chat interface.

## Your First Conversation

Open your browser to `http://localhost:5173`. You will see the chat interface with Ember ready to assist. Try asking something like "What systems are available?" or "Show me the endpoints for the banking system." Ember will consult the Service Catalog and Knowledge Base to provide accurate, contextual responses. As you explore, notice how Ember renders structured data using widgets directly in the conversation, presents information appropriate to your permissions, and maintains context across the conversation.
