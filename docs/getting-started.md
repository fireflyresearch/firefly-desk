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

## Start the Backend

Launch the FastAPI backend server:

```bash
uvicorn flydesk.server:create_app --factory --port 8000
```

The `--factory` flag tells uvicorn to call `create_app()` as a factory function, which initializes the application lifespan, wires dependency injection, and runs database migrations. The server will be available at `http://localhost:8000`.

## Start the Frontend

In a separate terminal, install and start the SvelteKit frontend:

```bash
cd frontend
npm install
npm run dev
```

The frontend development server starts at `http://localhost:5173` and proxies API requests to the backend on port 8000.

## Seed Demo Data

To explore Firefly Desk with realistic data, seed the banking demo scenario:

```bash
flydesk-seed banking
```

This populates the Service Catalog with a sample banking system, registers endpoints for common operations like account lookups and transaction queries, and loads knowledge documents with operational procedures. The seed data is designed to demonstrate the full range of platform capabilities without requiring you to connect a real backend system.

## Your First Conversation

Open your browser to `http://localhost:5173`. You will see the chat interface with Ember ready to assist. Try asking something like "What systems are available?" or "Show me the endpoints for the banking system." Ember will consult the Service Catalog and Knowledge Base to provide accurate, contextual responses. As you explore, notice how Ember renders structured data using widgets directly in the conversation, presents information appropriate to your permissions, and maintains context across the conversation.
