# Copyright 2026 Firefly Software Solutions Inc
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

# ---------------------------------------------------------------------------
# Firefly Desk Frontend -- multi-stage Docker build
# ---------------------------------------------------------------------------
# Base image: Node 22 Alpine
#
# NOTE: The SvelteKit project currently uses @sveltejs/adapter-auto. For
# production Docker deployment, switch to @sveltejs/adapter-node so that
# `npm run build` produces a standalone Node server in the `build/` directory.
#
#   npm install --save-dev @sveltejs/adapter-node
#
# Then update svelte.config.js:
#
#   import adapter from '@sveltejs/adapter-node';
# ---------------------------------------------------------------------------

# ---- Stage 1: builder ----
FROM node:22-alpine AS builder

WORKDIR /build

# Copy package manifests first to maximise layer cache hits.
COPY package.json package-lock.json ./

# Install all dependencies (including devDependencies needed for the build).
RUN npm ci

# Copy the rest of the source code.
COPY . .

# Build the SvelteKit application.
# With adapter-node this produces output in build/.
RUN npm run build

# ---- Stage 2: runtime ----
FROM node:22-alpine AS runtime

# Create a non-root user for security.
RUN addgroup -S flydesk && adduser -S flydesk -G flydesk

WORKDIR /app

# Copy the build output and the production package manifests.
COPY --from=builder /build/build ./build
COPY --from=builder /build/package.json ./

# Install only production dependencies (none at the moment, but future-proof).
RUN npm ci --omit=dev 2>/dev/null || true

# Switch to non-root user.
USER flydesk

EXPOSE 3000

# Health check -- verify the frontend responds on port 3000.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:3000/", "||", "exit", "1"]

# Start the Node server produced by adapter-node.
CMD ["node", "build"]
