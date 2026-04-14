# MCP Hub

**The AI-native management hub for WordPress, WooCommerce, and self-hosted services.**

633 tools across 10 plugins (incl. Coolify). Connect your sites, stores, repos, and databases — manage them all through Claude, ChatGPT, Cursor, or any MCP client.

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

**VS Code** (`.vscode/mcp.json`):

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

> Use a plugin-specific endpoint (e.g., `/wordpress/mcp`) instead of `/mcp` to reduce tool count and save tokens. See [Endpoints](#endpoints) below.

## Authentication

MCP Hub uses **Bearer token** authentication:

```
Authorization: Bearer YOUR_API_KEY
```

> `X-API-Key` header and query parameter auth are **not** supported.

## Endpoints

Use the most specific endpoint for your use case:

| Endpoint | Tools | `site` param? | Best for |
|----------|------:|:-------------:|----------|
| `/u/{user_id}/{alias}/mcp` | 22-100 | No (pre-scoped) | Hosted/OAuth users |
| `/project/{alias}/mcp` | 22-100 | No (pre-scoped) | Single-site workflow |
| `/{plugin}/mcp` | 23-101 | Yes | Multi-site management |
| `/mcp` | 633 | Yes | Admin & discovery only |

Available plugin endpoints: `/wordpress/mcp`, `/woocommerce/mcp`, `/wordpress-advanced/mcp`, `/gitea/mcp`, `/n8n/mcp`, `/supabase/mcp`, `/openpanel/mcp`, `/appwrite/mcp`, `/directus/mcp`, `/system/mcp`

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

> **WP-CLI tools** (cache flush, database export, plugin updates via CLI) require Docker socket access.
> Add `WORDPRESS_SITE1_CONTAINER=your-wp-container-name` to your `.env` and uncomment the Docker socket volume above.

```bash
docker compose up -d
```

## After Starting

| URL | Description |
|-----|-------------|
| `http://localhost:8000/health` | Health check & status |
| `http://localhost:8000/dashboard` | Web dashboard (manage sites, API keys, OAuth clients, health monitoring). Login via MASTER_API_KEY or GitHub/Google OAuth |
| `http://localhost:8000/mcp` | MCP endpoint (connect AI clients here) |

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MASTER_API_KEY` | Recommended | API key for authentication. If omitted, a temporary key is auto-generated and printed to logs |
| `WORDPRESS_SITE1_URL` | For WP | WordPress site URL |
| `WORDPRESS_SITE1_USERNAME` | For WP | WordPress admin username |
| `WORDPRESS_SITE1_APP_PASSWORD` | For WP | WordPress Application Password |
| `WORDPRESS_SITE1_ALIAS` | Recommended | Friendly name (e.g., `myblog`) |
| `WORDPRESS_SITE1_CONTAINER` | For WP-CLI | Docker container name of your WordPress site (enables cache/db/system tools) |
| `OAUTH_JWT_SECRET_KEY` | For OAuth | JWT secret for ChatGPT auto-registration (not needed for Claude/Cursor) |
| `OAUTH_BASE_URL` | For OAuth | Public URL of your server (not needed for Claude/Cursor) |
| `GITHUB_CLIENT_ID` | For Social Login | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | For Social Login | GitHub OAuth App client secret |
| `GOOGLE_CLIENT_ID` | For Social Login | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | For Social Login | Google OAuth client secret |
| `PUBLIC_URL` | For Social Login | Public URL for OAuth callbacks (e.g., `https://mcp.example.com`) |
| `ENCRYPTION_KEY` | For Multi-user | AES-256 key for encrypting user site credentials. Generate: `python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"` |

> **CONTAINER**: Required for WP-CLI tools (cache flush, database export, system info) and **all** WordPress Advanced tools. Find your container name: `docker ps --filter name=wordpress`. Also requires Docker socket mount.

> **OAuth**: Only needed for ChatGPT Remote MCP auto-registration. For Claude Desktop, Claude Code, Cursor, and VS Code — just use `MASTER_API_KEY` with Bearer token auth.

> **Social Login**: Enable GitHub/Google login for multi-user mode. Users can add sites via the dashboard and get personal MCP endpoints (`/u/{user_id}/{alias}/mcp`).

Add more sites with `SITE2`, `SITE3`, etc. See [full configuration guide](https://github.com/airano-ir/mcphub/blob/main/docs/getting-started.md).

## Supported Plugins

| Plugin | Tools | Env Prefix |
|--------|-------|------------|
| WordPress | 67 | `WORDPRESS_` |
| WooCommerce | 28 | `WOOCOMMERCE_` |
| WordPress Advanced | 22 | `WORDPRESS_ADVANCED_` |
| Gitea | 56 | `GITEA_` |
| n8n | 56 | `N8N_` |
| Supabase | 70 | `SUPABASE_` |
| OpenPanel | 73 | `OPENPANEL_` |
| Appwrite | 100 | `APPWRITE_` |
| Directus | 100 | `DIRECTUS_` |

## Links

- **GitHub**: [github.com/airano-ir/mcphub](https://github.com/airano-ir/mcphub)
- **PyPI**: [pypi.org/project/mcphub-server](https://pypi.org/project/mcphub-server/)
- **Documentation**: [Getting Started Guide](https://github.com/airano-ir/mcphub/blob/main/docs/getting-started.md)
- **License**: MIT
