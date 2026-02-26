#!/usr/bin/env bash
# Copyright 2026 Firefly Software Solutions Inc
# Licensed under the Apache License, Version 2.0
#
# Firefly Desk Installer
# Usage:
#   Interactive:     bash <(curl -fsSL https://get.flydesk.dev/install.sh)
#   Non-interactive: curl -fsSL ... | FLYDESK_MODE=docker bash
#   With flags:      bash install.sh --mode local --port 8000

set -euo pipefail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
readonly VERSION="0.1.0"
readonly DEFAULT_API_PORT=8000
readonly DEFAULT_DOCKER_FRONT_PORT=3000
readonly DEFAULT_LOCAL_FRONT_PORT=5173
readonly HEALTH_RETRIES=30
readonly HEALTH_INTERVAL=2

# ---------------------------------------------------------------------------
# Color support -- disabled when stdout is not a TTY (piped mode)
# ---------------------------------------------------------------------------
if [ -t 1 ]; then
    C_GREEN="\033[0;32m"
    C_RED="\033[0;31m"
    C_YELLOW="\033[0;33m"
    C_BLUE="\033[0;34m"
    C_BOLD="\033[1m"
    C_RESET="\033[0m"
else
    C_GREEN=""
    C_RED=""
    C_YELLOW=""
    C_BLUE=""
    C_BOLD=""
    C_RESET=""
fi

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
ok()   { printf "${C_GREEN}[ok]${C_RESET} %s\n" "$*"; }
err()  { printf "${C_RED}[!!]${C_RESET} %s\n" "$*" >&2; }
warn() { printf "${C_YELLOW}[..]${C_RESET} %s\n" "$*"; }
info() { printf "${C_BLUE}[>>]${C_RESET} %s\n" "$*"; }

die() {
    err "$1"
    [ -n "${2:-}" ] && printf "    %s\n" "$2" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Spinner -- runs a command in the background with an animated indicator
# Usage: spin "message" command [args...]
# ---------------------------------------------------------------------------
spin() {
    local msg="$1"; shift
    local frames='|/-\'
    local i=0

    info "$msg"

    # Run the command in the background, capturing output to a temp file
    local tmplog
    tmplog=$(mktemp)
    "$@" > "$tmplog" 2>&1 &
    local pid=$!

    # Animate only when we have a TTY
    if [ -t 1 ]; then
        while kill -0 "$pid" 2>/dev/null; do
            printf "\r  %s %s" "${frames:i++%${#frames}:1}" "$msg"
            sleep 0.1
        done
        printf "\r"
    fi

    # Wait for the process and check exit code
    if wait "$pid"; then
        ok "$msg"
        rm -f "$tmplog"
        return 0
    else
        err "$msg -- failed"
        printf "    Output:\n"
        sed 's/^/    /' "$tmplog" >&2
        rm -f "$tmplog"
        return 1
    fi
}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
header() {
    printf "\n"
    printf "${C_BOLD}  Firefly Desk Installer v%s${C_RESET}\n" "$VERSION"
    printf "  ──────────────────────────────────\n\n"
}

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
usage() {
    header
    cat <<'HELP'
  FLAGS
    --mode docker|local   Installation mode (skip interactive prompt)
    --port N              Backend API port (default: 8000)
    --frontend-port N     Frontend port (default: 5173 local, 3000 docker)
    --help                Show this help message

  ENVIRONMENT VARIABLES
    FLYDESK_MODE          Same as --mode
    FLYDESK_PORT          Same as --port
    FLYDESK_FRONT_PORT    Same as --frontend-port

  EXAMPLES
    bash install.sh --mode local --port 8000
    bash install.sh --mode local --frontend-port 3000
    FLYDESK_MODE=docker bash install.sh
    curl -fsSL https://get.flydesk.dev/install.sh | FLYDESK_MODE=docker bash

HELP
    exit 0
}

# ---------------------------------------------------------------------------
# Environment detection helpers
# ---------------------------------------------------------------------------
detect_os() {
    local uname_s
    uname_s=$(uname -s)
    case "$uname_s" in
        Darwin) echo "macOS" ;;
        Linux)
            if grep -qi microsoft /proc/version 2>/dev/null; then
                echo "WSL"
            else
                echo "Linux"
            fi
            ;;
        *) echo "unknown" ;;
    esac
}

detect_arch() {
    local machine
    machine=$(uname -m)
    case "$machine" in
        arm64|aarch64) echo "arm64" ;;
        x86_64|amd64)  echo "x86_64" ;;
        *)             echo "$machine" ;;
    esac
}

detect_os_version() {
    local os="$1"
    case "$os" in
        macOS) sw_vers -productVersion 2>/dev/null || echo "unknown" ;;
        Linux|WSL)
            if [ -f /etc/os-release ]; then
                . /etc/os-release
                echo "${PRETTY_NAME:-$ID $VERSION_ID}"
            else
                echo "unknown"
            fi
            ;;
        *) echo "unknown" ;;
    esac
}

# Check whether a TCP port is available
port_available() {
    local port="$1"
    if command -v lsof >/dev/null 2>&1; then
        ! lsof -iTCP:"$port" -sTCP:LISTEN -P -n >/dev/null 2>&1
    elif command -v ss >/dev/null 2>&1; then
        ! ss -tlnp | grep -q ":${port} "
    else
        # Cannot check; assume available
        return 0
    fi
}

# Compare two dot-separated version strings: returns 0 when $1 >= $2
version_gte() {
    local IFS='.'
    local -a v1=($1) v2=($2)
    local i
    for i in 0 1 2; do
        local a=${v1[$i]:-0}
        local b=${v2[$i]:-0}
        if (( a > b )); then return 0; fi
        if (( a < b )); then return 1; fi
    done
    return 0
}

# ---------------------------------------------------------------------------
# Full environment probe
# ---------------------------------------------------------------------------
probe_environment() {
    local os arch os_ver

    os=$(detect_os)
    arch=$(detect_arch)
    os_ver=$(detect_os_version "$os")

    ok "$os $os_ver ($arch)"

    # Docker
    HAS_DOCKER=false
    if command -v docker >/dev/null 2>&1; then
        local dv
        dv=$(docker --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        ok "Docker $dv"
        HAS_DOCKER=true
    else
        warn "Docker not found"
    fi

    # Docker Compose
    HAS_COMPOSE=false
    if docker compose version >/dev/null 2>&1; then
        local cv
        cv=$(docker compose version --short 2>/dev/null)
        ok "Docker Compose $cv"
        HAS_COMPOSE=true
    elif command -v docker-compose >/dev/null 2>&1; then
        local cv
        cv=$(docker-compose --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        ok "Docker Compose (standalone) $cv"
        HAS_COMPOSE=true
    else
        warn "Docker Compose not found"
    fi

    # Python
    HAS_PYTHON=false
    PYTHON_CMD=""
    for cmd in python3.13 python3 python; do
        if command -v "$cmd" >/dev/null 2>&1; then
            local pv
            pv=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
            if version_gte "$pv" "3.13.0"; then
                ok "Python $pv ($cmd)"
                HAS_PYTHON=true
                PYTHON_CMD="$cmd"
                break
            fi
        fi
    done
    if [ "$HAS_PYTHON" = false ]; then
        warn "Python 3.13+ not found"
    fi

    # Node
    HAS_NODE=false
    if command -v node >/dev/null 2>&1; then
        local nv
        nv=$(node --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        if version_gte "$nv" "22.0.0"; then
            ok "Node $nv"
            HAS_NODE=true
        else
            warn "Node $nv found -- 22+ recommended"
        fi
    else
        warn "Node not found"
    fi

    # uv
    HAS_UV=false
    if command -v uv >/dev/null 2>&1; then
        local uv_ver
        uv_ver=$(uv --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1)
        ok "uv $uv_ver"
        HAS_UV=true
    else
        warn "uv not found"
    fi

    # Port availability
    if port_available "$API_PORT"; then
        ok "Port $API_PORT is available"
    else
        warn "Port $API_PORT is in use"
    fi

    printf "\n"
}

# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------
select_mode() {
    # Already set via flag or env var
    if [ -n "${MODE:-}" ]; then
        return
    fi

    # Interactive TTY prompt
    if [ -t 0 ]; then
        printf "  Select installation mode:\n"
        printf "    1) ${C_BOLD}docker${C_RESET}  -- Docker Compose deployment\n"
        printf "    2) ${C_BOLD}local${C_RESET}   -- Local development\n"
        printf "\n"
        read -rp "  Enter choice [1/2]: " choice
        case "$choice" in
            1|docker) MODE="docker" ;;
            2|local)  MODE="local" ;;
            *)        die "Invalid choice: $choice" ;;
        esac
    else
        die "No mode specified" \
            "Set FLYDESK_MODE=docker|local or pass --mode docker|local"
    fi

    printf "\n"
}

# ---------------------------------------------------------------------------
# .env file creation
# ---------------------------------------------------------------------------
ensure_env_file() {
    local env_file=".env"
    local env_example=".env.example"

    if [ -f "$env_file" ]; then
        ok ".env file already exists -- keeping it"
        return
    fi

    if [ ! -f "$env_example" ]; then
        die ".env.example not found" \
            "Are you running this from the Firefly Desk project root?"
    fi

    info "Creating .env from .env.example"
    cp "$env_example" "$env_file"

    # Generate a secure encryption key
    local enc_key
    enc_key=$(openssl rand -base64 32 2>/dev/null || python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || echo "CHANGE-ME-$(date +%s)")

    # Patch in the generated key
    if [[ "$(uname -s)" == "Darwin" ]]; then
        sed -i '' "s|FLYDESK_CREDENTIAL_ENCRYPTION_KEY=.*|FLYDESK_CREDENTIAL_ENCRYPTION_KEY=${enc_key}|" "$env_file"
    else
        sed -i "s|FLYDESK_CREDENTIAL_ENCRYPTION_KEY=.*|FLYDESK_CREDENTIAL_ENCRYPTION_KEY=${enc_key}|" "$env_file"
    fi

    ok "Generated FLYDESK_CREDENTIAL_ENCRYPTION_KEY"

    # For local dev, prompt for database choice
    if [ "${MODE:-}" = "local" ]; then
        local db_choice="sqlite"
        if [ -t 0 ]; then
            printf "\n  Select database:\n"
            printf "    1) ${C_BOLD}SQLite${C_RESET}      -- Zero setup, good for development (default)\n"
            printf "    2) ${C_BOLD}PostgreSQL${C_RESET}  -- Production-ready with pgvector\n"
            printf "\n"
            read -rp "  Enter choice [1/2] (default: 1): " db_choice_input
            case "${db_choice_input:-1}" in
                2|postgresql|postgres) db_choice="postgresql" ;;
                *) db_choice="sqlite" ;;
            esac
        fi

        if [ "$db_choice" = "postgresql" ]; then
            local pg_url=""
            if [ -t 0 ]; then
                read -rp "  PostgreSQL URL (e.g., postgresql+asyncpg://user:pass@localhost:5432/flydesk): " pg_url
            fi
            if [ -z "$pg_url" ]; then
                pg_url="postgresql+asyncpg://flydesk:flydesk@localhost:5432/flydesk"
                warn "Using default PostgreSQL URL: $pg_url"
            fi
            if [[ "$(uname -s)" == "Darwin" ]]; then
                sed -i '' "s|FLYDESK_DATABASE_URL=.*|FLYDESK_DATABASE_URL=${pg_url}|" "$env_file"
            else
                sed -i "s|FLYDESK_DATABASE_URL=.*|FLYDESK_DATABASE_URL=${pg_url}|" "$env_file"
            fi
            ok "Configured PostgreSQL"
        else
            local sqlite_url="sqlite+aiosqlite:///./flydesk_dev.db"
            if [[ "$(uname -s)" == "Darwin" ]]; then
                sed -i '' "s|FLYDESK_DATABASE_URL=.*|FLYDESK_DATABASE_URL=${sqlite_url}|" "$env_file"
                sed -i '' "s|FLYDESK_REDIS_URL=.*|# FLYDESK_REDIS_URL=redis://localhost:6379/0|" "$env_file"
            else
                sed -i "s|FLYDESK_DATABASE_URL=.*|FLYDESK_DATABASE_URL=${sqlite_url}|" "$env_file"
                sed -i "s|FLYDESK_REDIS_URL=.*|# FLYDESK_REDIS_URL=redis://localhost:6379/0|" "$env_file"
            fi
            ok "Configured SQLite for local development"
        fi
    fi
}

# ---------------------------------------------------------------------------
# Open browser helper
# ---------------------------------------------------------------------------
open_browser() {
    local url="$1"
    case "$(detect_os)" in
        macOS)       open "$url" 2>/dev/null || true ;;
        Linux|WSL)   xdg-open "$url" 2>/dev/null || true ;;
    esac
}

# ---------------------------------------------------------------------------
# Wait for an HTTP endpoint to respond with 2xx
# ---------------------------------------------------------------------------
wait_for_health() {
    local url="$1"
    local label="$2"
    local retries="${3:-$HEALTH_RETRIES}"
    local interval="${4:-$HEALTH_INTERVAL}"
    local attempt=0

    info "Waiting for $label to become healthy..."

    while (( attempt < retries )); do
        if curl -sf "$url" >/dev/null 2>&1; then
            ok "$label is healthy"
            return 0
        fi
        (( attempt++ ))
        sleep "$interval"
    done

    err "$label did not become healthy after $((retries * interval))s"
    return 1
}

# ---------------------------------------------------------------------------
# Docker mode
# ---------------------------------------------------------------------------
install_docker() {
    info "Starting Docker Compose deployment"
    printf "\n"

    # Prerequisites
    [ "$HAS_DOCKER" = true ]  || die "Docker is required for docker mode" \
        "Install Docker: https://docs.docker.com/get-docker/"
    [ "$HAS_COMPOSE" = true ] || die "Docker Compose is required" \
        "Install Docker Compose: https://docs.docker.com/compose/install/"

    # .env
    ensure_env_file

    printf "\n"

    # Pull images
    spin "Pulling Docker images" docker compose pull

    # Start services
    spin "Starting Docker Compose services" docker compose up -d

    printf "\n"

    # Health check
    wait_for_health "http://localhost:${API_PORT}/api/health" "API (port $API_PORT)" || true

    printf "\n"
    printf "  ${C_GREEN}${C_BOLD}Firefly Desk is running!${C_RESET}\n"
    printf "\n"
    printf "    Frontend:  ${C_BOLD}http://localhost:%s${C_RESET}\n" "$FRONT_PORT"
    printf "    API:       ${C_BOLD}http://localhost:%s${C_RESET}\n" "$API_PORT"
    printf "\n"
    printf "  Stop with:   ${C_BOLD}docker compose down${C_RESET}\n"
    printf "  Logs:        ${C_BOLD}docker compose logs -f${C_RESET}\n"
    printf "\n"

    open_browser "http://localhost:${FRONT_PORT}"
}

# ---------------------------------------------------------------------------
# Local development mode
# ---------------------------------------------------------------------------
install_local() {
    info "Starting local development setup"
    printf "\n"

    # Prerequisites
    [ "$HAS_PYTHON" = true ] || die "Python 3.13+ is required for local mode" \
        "Install Python: https://www.python.org/downloads/ or use pyenv"
    [ "$HAS_NODE" = true ]   || die "Node 22+ is required for local mode" \
        "Install Node: https://nodejs.org/ or use nvm"
    [ "$HAS_UV" = true ]     || die "uv is required for local mode" \
        "Install uv: https://docs.astral.sh/uv/getting-started/installation/"

    # .env
    ensure_env_file

    printf "\n"

    # Python dependencies
    spin "Installing Python dependencies (uv sync)" uv sync

    # Frontend dependencies
    if [ -d "frontend" ]; then
        spin "Installing frontend dependencies (npm install)" \
            npm --prefix frontend install
    else
        warn "frontend/ directory not found -- skipping npm install"
    fi

    # Initialize database schema via Alembic
    spin "Initializing database schema (flydesk db upgrade head)" \
        uv run flydesk db upgrade head

    printf "\n"

    # Start backend + frontend via flydesk dev
    info "Starting backend (port $API_PORT) + frontend (port $FRONT_PORT)"
    uv run flydesk dev --port "$API_PORT" --frontend-port "$FRONT_PORT" &
    local dev_pid=$!

    # Trap to clean up on exit
    trap 'kill $dev_pid 2>/dev/null; exit' INT TERM

    printf "\n"

    # Health checks
    wait_for_health "http://localhost:${API_PORT}/api/health" "API (port $API_PORT)" || true
    wait_for_health "http://localhost:${FRONT_PORT}" "Frontend (port $FRONT_PORT)" || true

    printf "\n"
    printf "  ${C_GREEN}${C_BOLD}Firefly Desk is running!${C_RESET}\n"
    printf "\n"
    printf "    Frontend:  ${C_BOLD}http://localhost:%s${C_RESET}\n" "$FRONT_PORT"
    printf "    API:       ${C_BOLD}http://localhost:%s${C_RESET}\n" "$API_PORT"
    printf "\n"
    printf "  Stop with:   ${C_BOLD}Ctrl+C${C_RESET}\n"
    printf "\n"

    open_browser "http://localhost:${FRONT_PORT}"

    # Keep the script alive so background processes stay running
    wait
}

# ---------------------------------------------------------------------------
# Parse CLI arguments
# ---------------------------------------------------------------------------
MODE="${FLYDESK_MODE:-}"
API_PORT="${FLYDESK_PORT:-$DEFAULT_API_PORT}"
FRONT_PORT="${FLYDESK_FRONT_PORT:-}"

while [ $# -gt 0 ]; do
    case "$1" in
        --mode)
            [ -n "${2:-}" ] || die "--mode requires a value (docker|local)"
            MODE="$2"
            shift 2
            ;;
        --port)
            [ -n "${2:-}" ] || die "--port requires a value"
            API_PORT="$2"
            shift 2
            ;;
        --frontend-port)
            [ -n "${2:-}" ] || die "--frontend-port requires a value"
            FRONT_PORT="$2"
            shift 2
            ;;
        --help|-h)
            usage
            ;;
        *)
            die "Unknown option: $1" "Run with --help for usage"
            ;;
    esac
done

# Validate mode if already set
if [ -n "$MODE" ]; then
    case "$MODE" in
        docker|local) ;;
        *) die "Invalid mode: $MODE" "Allowed values: docker, local" ;;
    esac
fi

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
header
probe_environment
select_mode

# Set frontend port default based on mode (5173 for local/Vite, 3000 for docker)
if [ -z "$FRONT_PORT" ]; then
    case "$MODE" in
        local)  FRONT_PORT="$DEFAULT_LOCAL_FRONT_PORT" ;;
        docker) FRONT_PORT="$DEFAULT_DOCKER_FRONT_PORT" ;;
    esac
fi

case "$MODE" in
    docker) install_docker ;;
    local)  install_local ;;
esac
