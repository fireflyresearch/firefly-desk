# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

# ---------------------------------------------------------------------------
# Firefly Desk API -- multi-stage Docker build
# ---------------------------------------------------------------------------
# Base image: Python 3.13 slim (Debian Bookworm)
# Build tool: uv for fast dependency resolution
#
# NOTE: The project depends on fireflyframework-genai which is referenced as a
# local path in [tool.uv.sources]. For Docker builds, this package must be
# available from a package registry (e.g. private PyPI). The uv source override
# is ignored during the Docker build because we install with pip, which reads
# only the standard [project.dependencies] table.
# ---------------------------------------------------------------------------

# ---- Stage 1: builder ----
FROM python:3.13-slim AS builder

# Install uv for fast dependency resolution
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /build

# Copy dependency manifests first to maximise layer cache hits.
# uv.lock is optional -- the build still works without it.
COPY pyproject.toml ./
COPY uv.lock* ./

# Install only production dependencies into a virtual environment.
# --no-install-project: do not install the project itself yet (source not copied).
# --no-dev: exclude development dependencies.
# The virtual environment lives at /build/.venv so it can be copied to the
# runtime image without dragging in build tooling.
RUN uv sync --no-install-project --no-dev --no-editable

# Copy the application source and install the project itself.
COPY src/ ./src/
RUN uv sync --no-dev --no-editable

# ---- Stage 2: runtime ----
FROM python:3.13-slim AS runtime

# Prevent Python from writing .pyc files and enable unbuffered stdout/stderr
# so that log output appears immediately in Docker logs.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Create a non-root user for security.
RUN groupadd --system flydek && \
    useradd --system --gid flydek --create-home flydek

WORKDIR /app

# Copy the virtual environment with all installed packages from the builder.
COPY --from=builder /build/.venv /app/.venv

# Put the venv on the PATH so the installed packages and uvicorn are found.
ENV PATH="/app/.venv/bin:$PATH"

# Switch to non-root user.
USER flydek

EXPOSE 8000

# Health check -- hit the /health endpoint every 30 seconds.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

# Start the FastAPI app via uvicorn with the application factory.
CMD ["uvicorn", "flydek.server:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
