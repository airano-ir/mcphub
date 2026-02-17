# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**MCP Hub** — a Python MCP (Model Context Protocol) server that manages multiple self-hosted projects through a unified plugin architecture. Supports 9 plugin types (WordPress, WooCommerce, WordPress Advanced, Gitea, n8n, Supabase, OpenPanel, Appwrite, Directus) with ~589 tools total. The tool count stays constant regardless of how many sites are configured.

## Quick Setup

```bash
cp env.example .env        # Copy and fill in credentials
pip install -e ".[dev]"    # Install with dev deps
python server.py           # Run (stdio) or:
python server.py --transport sse --port 8000  # Run (HTTP)
```

## Build & Development Commands

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run server (stdio transport for Claude Desktop)
python server.py

# Run server (SSE/HTTP transport for testing)
python server.py --transport sse --port 8000

# Run all tests
pytest

# Run single test file
pytest tests/test_api_keys.py

# Run by marker (unit, integration, security, slow)
pytest -m unit
pytest -m "not slow"

# Tests with coverage
pytest --cov --cov-report=html

# Format code
black .

# Lint
ruff check .
ruff check --fix .

# Type check
mypy .

# Docker build and run
docker build -t mcphub .
docker-compose up -d
```

## Code Quality Configuration

All configured in `pyproject.toml`:
- **Black**: line-length=100, target py311
- **Ruff**: strict rules (E, W, F, I, N, D, UP, B, C4, SIM, TCH, PTH), Google-style docstrings
- **mypy**: Python 3.11, strict equality, check_untyped_defs=true
- **pytest**: asyncio_mode="auto", testpaths=["tests"], markers: slow, integration, unit, security

## Architecture

### Root Directory Overview

```
├── server.py              # Primary entry point
├── server_multi.py        # Alternative multi-endpoint server
├── core/                  # Layer 1: Core system modules
├── plugins/               # Layer 2: Plugin system (9 plugins)
├── templates/             # Jinja2 templates (dashboard + OAuth)
├── tests/                 # Organized test suite
├── scripts/               # Setup & deployment scripts
├── wordpress-plugin/      # Companion WP plugins (PHP)
├── docs/                  # Extensive documentation
├── pyproject.toml         # All tool configs (black, ruff, mypy, pytest)
├── docker-compose.yaml    # Docker composition
└── env.example            # Environment variable template
```

### Three-Layer Clean Architecture ("Option B")

```
Layer 1: Core System    (core/)      — Auth, site discovery, tool registry, health, rate limiting
Layer 2: Plugin System  (plugins/)   — 9 plugin types, each with handlers + schemas
Layer 3: API & Web UI   (server.py + core/dashboard/) — FastMCP server, Starlette routes, dashboard
```

### Entry Points

- **`server.py`** (~3500 lines) — Primary entry point. Handles FastMCP server, Starlette routes, middleware, plugins.
- **`server_multi.py`** — Alternative multi-endpoint server (legacy, predates unified `server.py` endpoints).

### Multi-Endpoint Architecture

```
/mcp                        → Admin (all tools, Master API Key required)
/system/mcp                 → System tools only
/{plugin_type}/mcp          → Plugin-specific tools (wordpress, gitea, n8n, etc.)
/project/{alias_or_id}/mcp  → Per-project endpoint (auto-injects site parameter)
```

Implemented in `core/endpoints/` — EndpointConfig, MCPEndpointFactory, EndpointRegistry.

### Plugin System

All plugins extend `BasePlugin` (in `plugins/base.py`). Registration happens in `plugins/__init__.py` via `PluginRegistry`.

Each plugin follows this structure:
```
plugins/{name}/
├── plugin.py       # Main class extending BasePlugin
├── client.py       # REST API client for the service
├── handlers/       # Feature-specific handlers (posts.py, orders.py, etc.)
└── schemas/        # Pydantic models for validation
```

**Registered plugins**: wordpress, woocommerce, wordpress_advanced, gitea, n8n, supabase, openpanel, appwrite, directus

### Tool Generation

Tools are dynamically generated at startup:
1. `SiteManager` discovers sites from env vars (`{PLUGIN_TYPE}_{SITE_ID}_{CONFIG_KEY}`)
2. `ToolGenerator` creates unified tools with a `site` parameter injected
3. Tools are registered in `ToolRegistry` and exposed via FastMCP

Unified tool pattern: `wordpress_create_post(site="myblog", title="Hello")` — the `site` parameter accepts either a site_id or alias.

### Site Configuration via Environment Variables

Pattern: `{PLUGIN_TYPE}_{SITE_ID}_{CONFIG_KEY}`

```bash
WORDPRESS_SITE1_URL=https://example.com
WORDPRESS_SITE1_USERNAME=admin
WORDPRESS_SITE1_APP_PASSWORD=xxxx xxxx xxxx xxxx
WORDPRESS_SITE1_ALIAS=myblog          # optional friendly name
WORDPRESS_SITE1_CONTAINER=wp-docker   # optional, for WP-CLI
```

Parsed by `core/site_manager.py` into `SiteConfig` (Pydantic model). Sites are auto-discovered on startup.

### Key Core Modules

| Module | Purpose |
|--------|---------|
| `core/auth.py` | Master API key validation, request authentication |
| `core/api_keys.py` | Per-project API keys with scopes (read/write/admin) |
| `core/site_manager.py` | Type-safe site config discovery from env vars |
| `core/tool_registry.py` | Central tool definitions and lookup |
| `core/tool_generator.py` | Dynamic unified tool creation with site injection |
| `core/health.py` | Health monitoring, metrics, alerts |
| `core/rate_limiter.py` | Token bucket rate limiting (60/min, 1000/hr, 10k/day) |
| `core/audit_log.py` | GDPR-compliant JSON audit logging |
| `core/oauth/` | OAuth 2.1 with PKCE (RFC 8414, 7591, 7636) |
| `core/dashboard/routes.py` | Web UI dashboard (login, projects, API keys, health, audit) |
| `core/endpoints/` | Multi-endpoint architecture (factory, registry, config) |

### Dashboard

Web UI at the server root, built with Starlette + Jinja2 + HTMX + Tailwind CSS. Supports EN/FA i18n (`core/i18n.py`). 8 pages: Login, Home, Projects, API Keys, OAuth Clients, Audit Logs, Health, Settings.

### Legacy Modules (Deprecated)

`core/project_manager.py`, `core/site_registry.py`, `core/unified_tools.py` — kept for backward compatibility. New code should use `SiteManager`, `ToolRegistry`, and `ToolGenerator` instead.

## Commit Style

```
<type>(<scope>): <description>
```
Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Gotchas

- Test files exist in both `tests/` (proper) and root directory (legacy `test_*.py`). Run `pytest tests/` for organized tests only.
- `server_multi.py` is the alternative multi-endpoint entry point; `server.py` is the primary
- `wordpress-plugin/` contains companion WP plugins (openpanel, seo-api-bridge) — these are PHP, not Python
- `env.example` has "FUTURE" labels for Supabase/Gitea but both are fully implemented
- Dashboard templates live in `templates/` (not inside `core/dashboard/`)
- `ruff` config uses top-level `select` key in pyproject.toml (not `[tool.ruff.lint]` nested format)
- The `scripts/` directory has platform-specific setup scripts: `setup.sh` (Linux/Mac), `setup.ps1` (Windows)

## Deployment Notes

- **Coolify**: Docker Compose build pack, port 8000, health check `GET /health`
- Must listen on `0.0.0.0` (not localhost)
- Docker socket mount required for WP-CLI tools: `/var/run/docker.sock:/var/run/docker.sock:ro`
- Persistent volumes: `mcp-data` (API keys, OAuth), `mcp-logs` (audit, health)
- Required env vars: `MASTER_API_KEY`, `OAUTH_JWT_SECRET_KEY`, `OAUTH_BASE_URL`
