# MCP Hub

**The AI-native management hub for WordPress, WooCommerce, and self-hosted services.**

8 plugins, hundreds of tools. Connect your sites, stores, repos, and databases — manage them all through Claude, ChatGPT, Cursor, or any MCP client.

> **Don't want to self-host?** Try the hosted instance at **[mcp.palebluedot.live](https://mcp.palebluedot.live)** — log in with GitHub or Google, add your sites, and connect your AI client in minutes.

## Quick Start

### 1. Create a `.env` file

```bash
# Recommended (auto-generates temp key if omitted — check container logs)
MASTER_API_KEY=your-secure-key-here
```

After starting, open the **web dashboard** to add your sites — no env vars needed for site configuration.

### 2. Run the container

```bash
docker run -d \
  --name mcphub \
  -p 8000:8000 \
  --env-file .env \
  airano/mcphub:latest
```

### 3. Verify it works

```bash
# Health check (wait ~30 seconds for startup)
curl http://localhost:8000/health

# Open the web dashboard
# http://localhost:8000/dashboard
```

Log in with your `MASTER_API_KEY`, then add sites via **My Sites → Add Service**.

### 4. Connect your AI client

**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "mcphub": {
      "type": "streamableHttp",
      "url": "http://localhost:8000/wordpress/mcp",
      "headers": {
        "Authorization": "Bearer your-secure-key-here"
      }
    }
  }
}
```

**VS Code / Claude Code** (`.vscode/mcp.json` or `.mcp.json`):

```json
{
  "servers": {
    "mcphub": {
      "type": "http",
      "url": "http://localhost:8000/wordpress/mcp",
      "headers": {
        "Authorization": "Bearer your-secure-key-here"
      }
    }
  }
}
```

> Use a plugin-specific endpoint (e.g., `/wordpress/mcp`) instead of `/mcp` to keep the tool list focused and save tokens. See [Endpoints](#endpoints) below.

## Authentication

MCP Hub uses **Bearer token** authentication:

```
Authorization: Bearer YOUR_API_KEY
```

## Endpoints

Use the most specific endpoint for your use case:

| Endpoint | Use case |
|----------|----------|
| `/u/{user_id}/{alias}/mcp` | Hosted/OAuth users — single pre-scoped service |
| `/project/{alias}/mcp` | Single-site workflow (recommended) |
| `/{plugin}/mcp` | Multi-site management for one service type |
| `/mcp` | Admin & discovery — all enabled tools |

Available plugin endpoints: `/wordpress/mcp`, `/woocommerce/mcp`, `/wordpress-specialist/mcp`, `/gitea/mcp`, `/n8n/mcp`, `/supabase/mcp`, `/openpanel/mcp`, `/coolify/mcp`, `/system/mcp`

## Using Docker Compose

```yaml
services:
  mcphub:
    image: airano/mcphub:latest
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - mcphub-data:/app/data
      - mcphub-logs:/app/logs
      # Optional: mount Docker socket for WP-CLI tools
      # - /var/run/docker.sock:/var/run/docker.sock:ro
    restart: unless-stopped

volumes:
  mcphub-data:
  mcphub-logs:
```

```bash
docker compose up -d
```

> **WP-CLI tools** (cache flush, database export, plugin management via CLI) require Docker socket access. Uncomment the socket volume and set the `container` field when adding the WordPress site in the dashboard.

## After Starting

| URL | Description |
|-----|-------------|
| `http://localhost:8000/health` | Health check & status |
| `http://localhost:8000/dashboard` | Web dashboard — manage sites, API keys, OAuth clients, health |
| `http://localhost:8000/mcp` | MCP endpoint (connect your AI client here) |

## Environment Variables

### Required

| Variable | Description |
|----------|-------------|
| `MASTER_API_KEY` | API key for admin access. If omitted, a temporary key is auto-generated and printed to logs. |

### Optional — OAuth & Social Login

| Variable | Description |
|----------|-------------|
| `OAUTH_JWT_SECRET_KEY` | JWT secret for ChatGPT Remote MCP auto-registration. Not needed for Claude/Cursor/VS Code. |
| `OAUTH_BASE_URL` | Public URL of your server. Required for OAuth flows. |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` | Enable GitHub social login for multi-user mode. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | Enable Google social login for multi-user mode. |
| `PUBLIC_URL` | Public URL for OAuth callbacks (e.g., `https://mcp.example.com`). |

### Optional — Multi-user & Encryption

| Variable | Default | Description |
|----------|---------|-------------|
| `ENCRYPTION_KEY` | — | AES-256-GCM key for encrypting user site credentials. Generate: `python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"` |
| `MAX_SITES_PER_USER` | `10` | Maximum sites per user account (also configurable via the dashboard Settings page). |
| `USER_RATE_LIMIT_PER_MIN` | `30` | Per-user rate limit (requests/minute). Configurable via dashboard. |
| `USER_RATE_LIMIT_PER_HR` | `500` | Per-user rate limit (requests/hour). Configurable via dashboard. |
| `ENABLED_PLUGINS` | `wordpress,woocommerce,supabase,openpanel,gitea` | Comma-separated list of plugins visible to public/OAuth users. Admin always sees all plugins. |

### Optional — Logging

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` |

> **Site configuration** (URLs, credentials) is managed via the web dashboard — not environment variables. Log in and go to **My Sites → Add Service**.

## 8 Plugins, Hundreds of Tools

| Plugin | Approx. Tools | What you can do |
|--------|------:|-----------------|
| WordPress | ~70 | Posts, pages, media (incl. AI image gen), users, menus, taxonomies, SEO |
| WooCommerce | ~30 | Products, orders, customers, coupons, reports, shipping |
| WordPress Specialist | ~50 | Plugins, themes, options, cron, page editing, DB inspection, bulk fan-out |
| Gitea | ~65 | Repos, issues, PRs, releases, webhooks, orgs, batch file ops |
| n8n | ~55 | Workflows, executions, credentials, variables, audit |
| Supabase | ~70 | Database, auth, storage, edge functions, realtime |
| OpenPanel | ~40 | Events, export, insights, profiles, projects |
| Coolify | ~65 | Apps, deployments, servers, projects, databases, services |
| System | ~25 | Health monitoring, API keys, OAuth management, audit logs |

> **WordPress Specialist** requires [Airano MCP Bridge](https://wordpress.org/plugins/airano-mcp-bridge/) (v2.18.0+) installed on your WordPress site.

## Links

- **GitHub**: [github.com/airano-ir/mcphub](https://github.com/airano-ir/mcphub)
- **PyPI**: [pypi.org/project/mcphub-server](https://pypi.org/project/mcphub-server/)
- **Documentation**: [Getting Started Guide](https://github.com/airano-ir/mcphub/blob/main/docs/getting-started.md)
- **License**: MIT
