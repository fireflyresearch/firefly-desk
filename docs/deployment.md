---
type: reference
---

# Deployment

## Overview

This guide covers deploying Firefly Desk to a production environment. Production deployment differs from development in four key ways: it requires PostgreSQL with pgvector instead of SQLite, it uses Redis for distributed state management, it enforces OIDC authentication instead of the development bypass, and it encrypts all stored credentials with a key you must manage securely.

If you are running Firefly Desk locally for development, see [Getting Started](getting-started.md) instead.

## Prerequisites

| Component | Version | Purpose |
|-----------|---------|---------|
| Python | 3.13+ | Backend runtime. Required for modern type annotations and async features. |
| Node.js | 22+ | Frontend build toolchain (SvelteKit). |
| PostgreSQL | 16+ with pgvector | Primary database with vector similarity search. |
| Redis | 7+ | Rate limiting, session caching, pub/sub for multi-instance deployments. |
| OIDC Provider | Any compliant provider | Authentication: Keycloak, Auth0, Entra ID, Google, Okta, or Cognito. |
| uv | Latest | Python package management. Install with `curl -LsSf https://astral.sh/uv/install.sh \| sh`. |

## Database Setup

Firefly Desk uses PostgreSQL as its production database. The pgvector extension is required because knowledge document embeddings are stored as vector columns in the same database, providing transactional consistency and eliminating the operational overhead of a separate vector database.

### Create the Database

```sql
-- Connect as a superuser or a user with CREATEDB privilege
CREATE DATABASE flydesk;

-- Connect to the new database
\c flydesk

-- Enable the pgvector extension (requires superuser or extension creation privilege)
CREATE EXTENSION IF NOT EXISTS vector;
```

If your PostgreSQL installation does not have pgvector available, install it following the [pgvector installation guide](https://github.com/pgvector/pgvector#installation). Most managed PostgreSQL services (AWS RDS, Google Cloud SQL, Azure Database for PostgreSQL) offer pgvector as a supported extension.

### Create an Application User

```sql
CREATE USER flydesk_user WITH PASSWORD 'strong_generated_password';
GRANT ALL PRIVILEGES ON DATABASE flydesk TO flydesk_user;

-- After connecting as flydesk_user, grant schema permissions
\c flydesk flydesk_user
GRANT ALL ON SCHEMA public TO flydesk_user;
```

### Run Migrations

Firefly Desk uses Alembic for schema migrations. Run the migration command to create all tables:

```bash
flydesk db upgrade head
```

This command applies all pending migrations in order, creating the required tables, indexes, and constraints. The migration history is tracked in the `alembic_version` table, so running the command again is safe -- it only applies new migrations.

### Configure the Connection

Set the database URL in your environment:

```bash
FLYDESK_DATABASE_URL=postgresql+asyncpg://flydesk_user:strong_generated_password@db-host:5432/flydesk
```

The URL follows SQLAlchemy async conventions. The `asyncpg` driver is required for async database access. Replace `db-host` with your PostgreSQL server's hostname or IP.

## Redis Setup

Redis is used for three purposes in production:

1. **Rate limiting.** Per-user request throttling to prevent abuse. Without Redis, rate limiting is in-memory and does not work across multiple application instances.
2. **Session caching.** Caches OIDC session data for faster authentication checks.
3. **Pub/sub.** Cross-instance communication for the indexing task queue in multi-node deployments.

### Configure the Connection

```bash
FLYDESK_REDIS_URL=redis://redis-host:6379/0
```

For Redis instances that require authentication:

```bash
FLYDESK_REDIS_URL=redis://:your_redis_password@redis-host:6379/0
```

Redis is optional in development mode. If `FLYDESK_REDIS_URL` is not set, rate limiting and session caching fall back to in-memory implementations, which are suitable for single-instance deployments only.

## OIDC Configuration

Production mode requires an OIDC provider for authentication. Firefly Desk supports six provider types with built-in claim mapping:

| Provider | `FLYDESK_OIDC_PROVIDER_TYPE` | Notes |
|----------|------------------------------|-------|
| Keycloak | `keycloak` | Self-hosted, full-featured. Default provider type. |
| Auth0 | `auth0` | Cloud-hosted, custom namespace for claims. |
| Microsoft Entra ID | `microsoft` | Requires `FLYDESK_OIDC_TENANT_ID`. |
| Google | `google` | Cloud Identity / Workspace. |
| Okta | `okta` | Enterprise SSO. |
| AWS Cognito | `cognito` | AWS-native identity. |

### Minimum Configuration

```bash
FLYDESK_DEV_MODE=false
FLYDESK_OIDC_ISSUER_URL=https://keycloak.example.com/realms/operations
FLYDESK_OIDC_CLIENT_ID=firefly-desk
FLYDESK_OIDC_CLIENT_SECRET=your-client-secret
FLYDESK_OIDC_REDIRECT_URI=https://desk.example.com/auth/callback
FLYDESK_OIDC_PROVIDER_TYPE=keycloak
```

See [SSO and OIDC](sso-oidc.md) for detailed configuration guides for each provider, including claim mapping, role extraction, and permission assignment.

## Reverse Proxy

In production, Firefly Desk should run behind a reverse proxy that handles TLS termination, static file serving, and WebSocket/SSE proxying.

### Nginx Example

```nginx
upstream flydesk_backend {
    server 127.0.0.1:8000;
}

server {
    listen 443 ssl http2;
    server_name desk.example.com;

    ssl_certificate     /etc/ssl/certs/desk.example.com.pem;
    ssl_certificate_key /etc/ssl/private/desk.example.com.key;

    # Frontend static files (SvelteKit build output)
    location / {
        root /var/www/flydesk/frontend/build;
        try_files $uri $uri/ @backend;
    }

    # API and SSE proxy
    location /api/ {
        proxy_pass http://flydesk_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # SSE support: disable buffering so tokens stream in real time
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;

        # Required for SSE connections to stay open
        proxy_http_version 1.1;
        proxy_set_header Connection '';
    }

    # Auth callbacks
    location /auth/ {
        proxy_pass http://flydesk_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    @backend {
        proxy_pass http://flydesk_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Key points for the reverse proxy configuration:

- **Disable proxy buffering** for `/api/` routes. SSE responses must stream through without buffering, or the client will not receive tokens in real time.
- **Increase read timeout** to at least 300 seconds. Agent responses that involve multiple tool calls can take longer than the default 60-second timeout.
- **Use HTTP/1.1** for the upstream connection with an empty `Connection` header. This prevents nginx from closing SSE connections prematurely.

## Docker Deployment

For containerized deployments, use Docker Compose to run Firefly Desk with all required services.

### Docker Compose Overview

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file: .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - uploads:/data/uploads

  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: flydesk
      POSTGRES_USER: flydesk_user
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U flydesk_user -d flydesk"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pgdata:
  redisdata:
  uploads:
```

### Environment Variables

Create a `.env` file alongside `docker-compose.yml` with your production configuration. See [Configuration](configuration.md) for the complete reference. At minimum, set:

```bash
# Core
FLYDESK_DEV_MODE=false
FLYDESK_DATABASE_URL=postgresql+asyncpg://flydesk_user:${DB_PASSWORD}@db:5432/flydesk
FLYDESK_REDIS_URL=redis://redis:6379/0

# Security
FLYDESK_CREDENTIAL_ENCRYPTION_KEY=your-generated-256-bit-key
FLYDESK_CORS_ORIGINS=https://desk.example.com

# OIDC
FLYDESK_OIDC_ISSUER_URL=https://keycloak.example.com/realms/operations
FLYDESK_OIDC_CLIENT_ID=firefly-desk
FLYDESK_OIDC_CLIENT_SECRET=your-client-secret
FLYDESK_OIDC_REDIRECT_URI=https://desk.example.com/auth/callback
FLYDESK_OIDC_PROVIDER_TYPE=keycloak

# File storage
FLYDESK_FILE_STORAGE_PATH=/data/uploads
```

### Persistent Volumes

Three volumes require persistence across container restarts:

| Volume | Mount Point | Purpose |
|--------|------------|---------|
| `pgdata` | `/var/lib/postgresql/data` | PostgreSQL data directory. All application data, embeddings, and audit records. |
| `redisdata` | `/data` | Redis persistence. Optional but recommended for session durability. |
| `uploads` | `/data/uploads` | Uploaded files. Must match `FLYDESK_FILE_STORAGE_PATH`. |

## Security Checklist

Before exposing Firefly Desk to users, verify the following:

| Item | How to Verify | Why It Matters |
|------|--------------|----------------|
| `FLYDESK_DEV_MODE=false` | Check `.env` or container env | Dev mode disables authentication and relaxes security constraints. |
| Encryption key set | `FLYDESK_CREDENTIAL_ENCRYPTION_KEY` is a 256-bit key | All credentials, API keys, and OIDC secrets are encrypted with this key. |
| CORS restricted | `FLYDESK_CORS_ORIGINS` lists only your frontend domain | Prevents cross-origin attacks from unauthorized domains. |
| OIDC configured | All `FLYDESK_OIDC_*` variables set and tested | Authentication enforcement depends on a properly configured provider. |
| Rate limiting enabled | `FLYDESK_RATE_LIMIT_PER_USER` is set (default: 60/min) | Prevents abuse and runaway scripts from overwhelming the system. |
| TLS enabled | Reverse proxy terminates TLS | All traffic should be encrypted in transit. |
| File storage path is absolute | `FLYDESK_FILE_STORAGE_PATH` starts with `/` | Avoids ambiguity about where files are stored. |
| Database credentials rotated | Not using default passwords | Standard security hygiene for production databases. |

### Generating an Encryption Key

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Store this key in your organization's secrets management system (HashiCorp Vault, AWS Secrets Manager, etc.). If the key is lost, all stored credentials become unrecoverable and must be re-entered.

## Scaling

### Multiple Workers

Run multiple uvicorn workers to handle concurrent requests:

```bash
uvicorn flydesk.server:create_app --factory --host 0.0.0.0 --port 8000 --workers 4
```

The number of workers should typically match the number of available CPU cores. Each worker runs an independent event loop, so async I/O scales well within each worker.

### Redis for Shared State

With multiple workers or instances, Redis is essential for:

- **Distributed rate limiting** -- All workers share the same rate limit counters.
- **Session caching** -- Authenticated sessions are accessible from any worker.
- **Indexing task queue** -- Document indexing tasks are distributed across workers through Redis pub/sub.

Without Redis, each worker maintains independent in-memory state, which means rate limits and sessions are not shared. This is acceptable for single-worker deployments only.

### Database Connection Pooling

SQLAlchemy's async engine manages a connection pool automatically. For high-concurrency deployments, consider tuning the pool parameters through the database URL or engine configuration:

- **pool_size** -- Maximum number of persistent connections (default: 5).
- **max_overflow** -- Additional temporary connections allowed above pool_size (default: 10).
- **pool_timeout** -- Seconds to wait for a connection from the pool before raising an error (default: 30).

For most deployments, the defaults are sufficient. If you observe connection timeouts under load, increase `pool_size` proportionally to the number of workers.

### Horizontal Scaling

For multi-node deployments behind a load balancer:

1. All instances must connect to the same PostgreSQL database.
2. All instances must connect to the same Redis instance.
3. The file storage path must point to a shared filesystem or object storage (NFS, EFS, GCS, S3).
4. Use sticky sessions or token-based authentication (not cookie-based sessions) if your load balancer does not support session affinity.

## Monitoring

### Health Endpoint

```bash
curl https://desk.example.com/api/health
```

Returns `{"status": "healthy", "version": "0.1.0"}` when the application is running and can reach the database. Use this as a readiness probe in container orchestration systems (Kubernetes, ECS, etc.).

### Audit Log

The audit system records every significant action:

- Chat turns with enriched context and agent responses
- Tool invocations with parameters and results
- Confirmation approvals and rejections
- Administrative changes (systems, credentials, roles, users, settings)
- Authentication events

Query the audit trail through `GET /api/audit/events` with filters for user, event type, and time range. Retention is controlled by `FLYDESK_AUDIT_RETENTION_DAYS` (default: 365 days).

### Background Jobs

Monitor background job status through `GET /api/jobs`:

- **Indexing jobs** -- Knowledge document chunking and embedding.
- **Process discovery jobs** -- LLM-driven business process analysis.
- **KG recompute jobs** -- Knowledge graph entity and relationship extraction.

Failed jobs include error details in their status records. The `JobRunner` retries transient failures automatically.

### Logging

The application uses Python's standard `logging` module. In production, configure structured logging through your deployment platform's log collection system. Key log sources:

- `flydesk.server` -- Startup/shutdown lifecycle events.
- `flydesk.agent` -- Agent pipeline execution, tool calls, errors.
- `flydesk.tools.executor` -- External system call details, timeouts, failures.
- `flydesk.knowledge` -- Indexing, embedding, retrieval operations.
- `flydesk.auth` -- Authentication events, token validation, permission checks.

## Backup and Recovery

### Database Backup

Use standard PostgreSQL backup tools:

```bash
pg_dump -U flydesk_user -d flydesk -F custom -f flydesk_backup.dump
```

This captures all application data including knowledge documents, embeddings, audit records, catalog configurations, and credentials (encrypted). Restore with:

```bash
pg_restore -U flydesk_user -d flydesk flydesk_backup.dump
```

### Encryption Key Backup

The `FLYDESK_CREDENTIAL_ENCRYPTION_KEY` must be backed up separately from the database. Without this key, encrypted credentials in the database backup are unrecoverable. Store the key in a secrets manager with its own backup and rotation policy.

### File Storage Backup

Back up the directory specified by `FLYDESK_FILE_STORAGE_PATH`. This contains uploaded files that may not be reproducible from other sources.
