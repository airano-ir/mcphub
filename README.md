<!-- mcp-name: io.github.airano-ir/mcphub -->

# MCP Hub

<div align="center">

**The AI-native management hub for WordPress, WooCommerce, and self-hosted services.**

Connect your sites, stores, repos, and databases — manage them all through Claude, ChatGPT, Cursor, or any MCP client.

[![GitHub Release](https://img.shields.io/github/v/release/airano-ir/mcphub)](https://github.com/airano-ir/mcphub/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-3776ab.svg)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/mcphub-server.svg)](https://pypi.org/project/mcphub-server/)
[![Docker](https://img.shields.io/docker/v/airano/mcphub?label=docker)](https://hub.docker.com/r/airano/mcphub)
[![Plugins: 10](https://img.shields.io/badge/plugins-10-orange.svg)]()
[![CI](https://github.com/airano-ir/mcphub/actions/workflows/ci.yml/badge.svg)](https://github.com/airano-ir/mcphub/actions/workflows/ci.yml)

</div>

---

## Why MCP Hub?

WordPress powers 43% of the web. WooCommerce runs 36% of online stores. Yet **no MCP server existed** for managing them through AI — until now.

MCP Hub is the first MCP server that lets you manage WordPress, WooCommerce, and 8 other self-hosted services through any AI assistant. Instead of clicking through dashboards, just tell your AI what to do:

> *"Update the SEO meta description for all WooCommerce products that don't have one"*
>
> *"Create a new blog post about our Black Friday sale and schedule it for next Monday"*
>
> *"Check the health of all 12 WordPress sites and report any with slow response times"*

### What Makes MCP Hub Different

| Feature | ManageWP | MainWP | AI Content Plugins | **MCP Hub** |
|---------|----------|--------|---------------------|-------------|
| Multi-site management | Yes | Yes | No | **Yes** |
| AI agent integration | No | No | No | **Native (MCP)** |
| Full WordPress API | Dashboard | Dashboard | Content only | **67 tools** |
| WooCommerce management | No | Limited | No | **28 tools** |
| Git/CI management | No | No | No | **65 tools (Gitea)** |
| Automation workflows | No | No | No | **56 tools (n8n)** |
| Self-hosted | No | Yes | N/A | **Yes** |
| Open source | No | Core only | Varies | **Fully open** |
| Price | $0.70-8/site/mo | $29-79/yr | $19-79/mo | **Free** |

---

## 10 Plugins, Hundreds of Tools

The exact tool count grows as new plugins ship and existing ones gain endpoints.
What you actually expose is controlled by your `ENABLED_PLUGINS` setting and per-key
scope — pick a plugin-specific endpoint to keep the surface area small.

| Plugin | Approx. Tools | What You Can Do |
|--------|---------------:|-----------------|
| **WordPress** | ~70 | Posts, pages, media (incl. AI image generation), users, menus, taxonomies, SEO (Rank Math/Yoast) |
| **WooCommerce** | ~30 | Products, orders, customers, coupons, reports, shipping |
| **WordPress Advanced** | ~20 | Database ops, bulk operations, WP-CLI, system management |
| **Gitea** | ~65 | Repos, issues, pull requests, releases, webhooks, organizations, labels, batch files, tree, search, compare |
| **n8n** | ~55 | Workflows, executions, credentials, variables, audit |
| **Supabase** | ~70 | Database, auth, storage, edge functions, realtime |
| **OpenPanel** | ~40 | Events, export, insights, profiles, projects, system |
| **Appwrite** | ~100 | Databases, auth, storage, functions, teams, messaging |
| **Directus** | ~100 | Collections, items, users, files, flows, permissions |
| **Coolify** | ~65 | Applications, deployments, servers, projects, databases, services |
| **System** | ~25 | Health monitoring, API keys, OAuth management, audit |

> Per-site duplication does **not** inflate the tool count — adding a second
> WordPress site reuses the same WordPress tools with a different `site` argument.

---

## Quick Start

### Option 1: Docker (Recommended)

```bash
git clone https://github.com/airano-ir/mcphub.git
cd mcphub
cp env.example .env
# Edit .env — set MASTER_API_KEY, then add sites via the web dashboard
docker compose up -d
```

### Option 2: Docker Hub (No Clone)

```bash
# Create a .env file with MASTER_API_KEY (see "Configure Your Sites" below)
docker run -d --name mcphub -p 8000:8000 --env-file .env airano/mcphub:latest
```

### Option 3: From Source

```bash
git clone https://github.com/airano-ir/mcphub.git
cd mcphub
pip install -e .
cp env.example .env
# Edit .env — set MASTER_API_KEY
python server.py --transport streamable-http --port 8000
```

### Verify It Works

After starting the server, wait ~30 seconds then:

```bash
# Check server health
curl http://localhost:8000/health
```

Open the **web dashboard** in your browser: **http://localhost:8000/dashboard**

You should see the login page. Log in with your `MASTER_API_KEY` or via **GitHub/Google OAuth** (if configured).

### Try It Now (No Setup Required)

**Don't want to self-host?** Use the hosted instance at **[mcp.example.com](https://mcp.example.com)**:

1. Log in with **GitHub** or **Google**
2. Add your sites via the dashboard (My Sites → Add Service)
3. Go to **Connect** page — generate config for your AI client
4. Copy-paste the config into Claude Desktop, VS Code, or Claude Code

Your personal MCP endpoint: `https://mcp.example.com/u/{your-user-id}/{alias}/mcp`

---

### Configure Your Sites

Sites are managed via the **web dashboard** — no environment variables needed.

1. Set `MASTER_API_KEY` in your `.env` file
2. Start the server and open the dashboard
3. Add sites with their credentials (URL, username, password/token)

```bash
# .env — only system configuration needed
MASTER_API_KEY=your-secure-key-here
```

<details>
<summary><b>Full Environment Variable Reference</b></summary>

**System Configuration:**

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MASTER_API_KEY` | Recommended | Auto-generated | Master API key for admin access |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `ENCRYPTION_KEY` | For Live Platform | — | AES-256-GCM key for credential encryption |
| `OAUTH_JWT_SECRET_KEY` | For OAuth | — | JWT secret for ChatGPT auto-registration (not needed for Claude/Cursor) |
| `OAUTH_BASE_URL` | For OAuth | — | Public URL of your server (not needed for Claude/Cursor) |

> **OAuth** is only needed for ChatGPT Remote MCP auto-registration. For Claude Desktop, Claude Code, Cursor, and VS Code — just use `MASTER_API_KEY` with Bearer token auth.

**Plugin Credential Reference** — when adding sites via dashboard, you'll need:

| Plugin | Required Credentials | Notes |
|--------|---------------------|-------|
| WordPress | URL, Username, App Password | [How to create App Password](https://wordpress.org/documentation/article/application-passwords/) |
| WooCommerce | URL, Consumer Key, Consumer Secret | WooCommerce → Settings → Advanced → REST API |
| WordPress Advanced | URL, Username, App Password, Container | Container = Docker container name (for WP-CLI) |
| Gitea | URL, Token | Settings → Applications → Personal Access Token |
| n8n | URL, API Key | Settings → API → Create API Key |
| Supabase | URL, Service Role Key | Supabase Dashboard → Settings → API |
| OpenPanel | URL, Client ID, Client Secret | OpenPanel Dashboard → Project Settings |
| Appwrite | URL, API Key, Project ID | Appwrite Console → Settings → API Keys |
| Directus | URL, Static Token | Directus Admin → Settings |

</details>

### Connect Your AI Client

All MCP clients use **Bearer token** authentication: `Authorization: Bearer YOUR_API_KEY`

> Use a plugin-specific endpoint (e.g., `/wordpress/mcp`) instead of `/mcp` to reduce tool count and save tokens. See [Architecture](#architecture) below.

<details>
<summary><b>Claude Desktop</b></summary>

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcphub-wordpress": {
      "type": "streamableHttp",
      "url": "http://your-server:8000/wordpress/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

</details>

<details>
<summary><b>Claude Code</b></summary>

Add to `.mcp.json` in your project:

```json
{
  "mcpServers": {
    "mcphub-wordpress": {
      "type": "http",
      "url": "http://your-server:8000/wordpress/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

</details>

<details>
<summary><b>Cursor</b></summary>

Go to **Settings > MCP Servers > Add Server**:

- **Name**: MCP Hub WordPress
- **URL**: `http://your-server:8000/wordpress/mcp`
- **Headers**: `Authorization: Bearer YOUR_API_KEY`

</details>

<details>
<summary><b>VS Code + Copilot</b></summary>

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "mcphub-wordpress": {
      "type": "http",
      "url": "http://your-server:8000/wordpress/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_API_KEY"
      }
    }
  }
}
```

</details>

<details>
<summary><b>ChatGPT (Remote MCP)</b></summary>

MCP Hub supports **Open Dynamic Client Registration** (RFC 7591). ChatGPT can auto-register as an OAuth client:

1. Deploy MCP Hub with `OAUTH_BASE_URL` set
2. In ChatGPT, add MCP server: `https://your-server:8000/mcp`
3. ChatGPT auto-discovers OAuth metadata and registers

</details>

> **Transport types**: Use `"type": "streamableHttp"` for Claude Desktop and `"type": "http"` for VS Code/Claude Code. Using `"type": "sse"` will cause `400 Bad Request` errors.

---

## Architecture

```
/mcp                        → Admin endpoint (every enabled tool)
/system/mcp                 → System tools only
/wordpress/mcp              → WordPress tools
/woocommerce/mcp            → WooCommerce tools
/wordpress-advanced/mcp     → WordPress Advanced tools
/gitea/mcp                  → Gitea tools
/n8n/mcp                    → n8n tools
/supabase/mcp               → Supabase tools
/openpanel/mcp              → OpenPanel tools
/appwrite/mcp               → Appwrite tools
/directus/mcp               → Directus tools
/coolify/mcp                → Coolify tools
/project/{alias}/mcp        → Per-project endpoint (auto-injects site)
/u/{user_id}/{alias}/mcp    → Per-user endpoint (hosted/OAuth users)
```

**Recommendation**: Use plugin-specific endpoints instead of the all-tools `/mcp`
admin endpoint to keep your AI client's tool window small (and your token bill
lower).

| Endpoint | Use Case |
|----------|----------|
| `/u/{user_id}/{alias}/mcp` | Hosted users (OAuth login) — single service |
| `/project/{alias}/mcp` | Single-site workflow (recommended) |
| `/{plugin}/mcp` | Multi-site management for one service |
| `/mcp` | Admin & discovery only — every enabled tool |

### Security

- **OAuth 2.1 + PKCE** (RFC 8414, 7591, 7636) with auto-registration for Claude/ChatGPT
- **Per-project API keys** with scoped permissions (read/write/admin)
- **Rate limiting**: 60/min, 1,000/hr, 10,000/day per client
- **GDPR-compliant audit logging** with automatic sensitive data filtering
- **Web dashboard** with real-time health monitoring (8 pages, EN/FA i18n)

> **Compatibility Note**: MCP Hub requires FastMCP 3.x (`>=3.0.0,<4.0.0`). The legacy multi-endpoint server and ProjectManager have been removed in v3.5.0.

### WordPress Plugin Requirements

Some MCP Hub tools require companion WordPress plugins:

| Tools | Requirement |
|-------|-------------|
| SEO + capability/audit tools (`wordpress_get_post_seo`, capability probe, audit hook, etc.) | [Airano MCP Bridge](https://wordpress.org/plugins/airano-mcp-bridge/) ([GitHub](wordpress-plugin/airano-mcp-bridge/)) + Rank Math or Yoast SEO |
| WP-CLI tools (15 tools: `wp_cache_*`, `wp_db_*`, etc.) | Docker socket + `CONTAINER` config |
| WordPress Advanced database/system tools | Docker socket + `CONTAINER` config |
| OpenPanel analytics integration | [OpenPanel Self-Hosted](wordpress-plugin/openpanel-self-hosted/) ([Download ZIP](wordpress-plugin/openpanel-self-hosted.zip)) |
| WooCommerce tools | WooCommerce plugin installed on your WordPress site |

**Docker socket** is needed for WP-CLI and WordPress Advanced system tools. Add to your docker-compose:

```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock:ro
```

Set the `container` field when adding a WordPress site in the dashboard. Without Docker socket, WP-CLI tools return "not available" but all REST API tools work normally.

---

## Documentation

| Guide | Description |
|-------|-------------|
| [Getting Started](docs/getting-started.md) | Full setup walkthrough |
| [Architecture](docs/ARCHITECTURE.md) | System design and module reference |
| [API Keys Guide](docs/API_KEYS_GUIDE.md) | Per-project API key management |
| [OAuth Guide](docs/OAUTH_GUIDE.md) | OAuth 2.1 setup for Claude/ChatGPT |
| [Gitea Guide](docs/GITEA_GUIDE.md) | Gitea plugin configuration |
| [Deployment Guide](docs/DEPLOYMENT_GUIDE.md) | Docker and Coolify deployment |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |
| [Plugin Development](docs/PLUGIN_DEVELOPMENT.md) | Build your own plugin |

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format and lint
black . && ruff check --fix .

# Run server locally
python server.py --transport streamable-http --port 8000
```

---

## Support This Project

MCP Hub is free and open-source. Development is funded by community donations.

[**Donate with Crypto (NOWPayments)**](https://nowpayments.io/donation/airano) — Global, no geographic restrictions.

| Goal | Monthly | Enables |
|------|---------|---------|
| Infrastructure | $50/mo | Demo hosting, CI/CD, domain |
| Part-time maintenance | $500/mo | Updates, security patches, issue triage |
| Active development | $2,000/mo | New plugins, features, community support |

---

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Priority areas:**
- New plugin development
- Client setup guides
- Workflow templates and examples
- Test coverage expansion
- Translations (i18n)

---

## License

MIT License. See [LICENSE](LICENSE).

---
