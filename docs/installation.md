# Installation

## System Requirements

Firefly Desk has two operational modes with different infrastructure requirements. Understanding these modes is important because it lets you start developing immediately with zero external dependencies while using the same codebase that deploys to production.

### Development Mode Requirements

- **Python 3.13+** -- Required for modern type annotations and performance features used throughout the codebase.
- **Node.js 22+** -- Required by the SvelteKit frontend build toolchain.
- **uv** -- The fast Python package manager. No other Python tooling is required.

In development mode, the platform uses SQLite for persistence and operates without Redis or an OIDC provider. Authentication is bypassed with a development user, and all data is stored in a local `flydesk_dev.db` file.

### Production Requirements

- **Python 3.13+**
- **Node.js 22+**
- **PostgreSQL 16+** with the **pgvector** extension -- Required for vector similarity search in the Knowledge Base.
- **Redis 7+** -- Used for session caching, rate limiting, and pub/sub for multi-instance deployments.
- **OIDC Provider** -- Any OpenID Connect compliant identity provider such as Keycloak, Auth0, or Entra ID.

## Installing uv

If you do not already have uv installed, the recommended installation method is:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

After installation, restart your shell or source your profile so that the `uv` command is available on your PATH. uv replaces pip, virtualenv, and pip-tools with a single, fast tool that ensures reproducible builds across environments.

## Development Mode Setup

Development mode is designed for local work with minimal friction. Follow these steps to get a fully functional instance running.

```bash
git clone https://github.com/fireflyresearch/firefly-desk.git
cd firefly-desk
cp .env.example .env
```

The default `.env` file sets `FLYDESK_DEV_MODE=true` and `FLYDESK_DATABASE_URL=sqlite+aiosqlite:///flydesk_dev.db`. These defaults mean you need no further configuration.

Install Python dependencies:

```bash
uv sync
```

Start the backend server:

```bash
uvicorn flydesk.server:create_app --factory --port 8000
```

In a second terminal, set up and start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Seed the development database with demo data:

```bash
flydesk-seed banking
```

Navigate to `http://localhost:5173` to begin using Firefly Desk.

## Production Setup

Production deployment requires PostgreSQL with the pgvector extension for embedding storage and similarity search. The reason pgvector is required rather than a standalone vector database is architectural simplicity: keeping embeddings in the same database as the rest of the application data means transactional consistency, simpler backups, and fewer moving parts.

### PostgreSQL with pgvector

Install PostgreSQL 16 or later and enable the pgvector extension:

```sql
CREATE DATABASE flydesk;
\c flydesk
CREATE EXTENSION IF NOT EXISTS vector;
```

Set the database URL in your environment:

```bash
FLYDESK_DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/flydesk
```

### Redis

Install Redis 7 or later. Redis is used for rate limiting, session caching, and cross-instance communication in multi-node deployments. Set the connection URL:

```bash
FLYDESK_REDIS_URL=redis://localhost:6379/0
```

### Disabling Development Mode

Set `FLYDESK_DEV_MODE=false` in your environment. This activates OIDC authentication enforcement, enables rate limiting, and switches to production-grade session management. See the [Configuration](configuration.md) guide for the full list of environment variables.

## Docker Deployment

For containerized deployments, use the provided Docker Compose configuration:

```bash
docker-compose up -d
```

The Compose file defines services for the Firefly Desk application, PostgreSQL with pgvector, and Redis. All environment variables can be set in a `.env` file alongside the `docker-compose.yml`. This approach is recommended for staging environments and production deployments where container orchestration simplifies scaling and lifecycle management.

Ensure that the `FLYDESK_CREDENTIAL_ENCRYPTION_KEY` environment variable is set to a securely generated key before starting the containers. This key encrypts stored credentials for external systems and must remain consistent across restarts to avoid losing access to registered system credentials.
